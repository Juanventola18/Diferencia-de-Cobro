"""Pestaña "Diferencias del día": cargar archivos, calcular, corregir y guardar."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk
import pandas as pd

from diferencias.dominio.estado import Estado, clasificar
from diferencias.dominio.reglas import calcular_diferencias, calcular_totales, perdida_total
from diferencias.dominio.valores import coincide_busqueda, es_vacio
from diferencias.entrada.lector_excel import FormatoExcelError, leer_lista_precios, leer_reporte_ventas
from diferencias.servicios import registro_dia
from diferencias.ui import estilos, formato
from diferencias.ui.dialogos import pedir_fecha, pedir_fila
from diferencias.ui.widgets import CampoBusqueda, PanelTotal, boton, casilla, crear_tabla, etiqueta_ayuda, vaciar

if TYPE_CHECKING:
    from diferencias.ui.app import App

TIPOS_ARCHIVO = [("Excel o ZIP", "*.xlsx *.xls *.zip"), ("Todos los archivos", "*.*")]
TOTALES_VACIOS = "Platos con pérdida: —   ·   Cobrado de más (no se suma): —   ·   Sin precio: —"


class PestanaDiario:
    COLUMNAS = [
        "Fecha",
        "Producto",
        "Categoría",
        "Cantidad",
        "Precio lista",
        "Esperado",
        "Monto informado",
        "Diferencia",
        "Estado",
    ]

    def __init__(self, app: App, contenedor: ctk.CTkFrame):
        self.app = app
        self.precios = pd.DataFrame(columns=["producto", "precio"])
        self.ventas: pd.DataFrame | None = None
        self.diferencias: pd.DataFrame | None = None
        self.fecha_detectada: str | None = None

        contenedor.configure(fg_color=estilos.FONDO)
        arriba = ctk.CTkFrame(contenedor, fg_color="transparent")
        arriba.pack(fill="x", padx=4, pady=(14, 10))
        boton(arriba, "Cargar / actualizar precios", self.cargar_precios, fg_color=estilos.FONDO_TARJETA).pack(
            side="left", padx=(0, 8)
        )
        boton(arriba, "Cargar reporte de ventas", self.cargar_ventas, fg_color=estilos.FONDO_TARJETA).pack(
            side="left", padx=8
        )
        self.lbl_ventas = etiqueta_ayuda(arriba, "(sin cargar)")
        self.lbl_ventas.pack(side="left", padx=8)
        boton(arriba, "Calcular diferencias", self.calcular, "primario").pack(side="left", padx=(16, 0))

        self.panel_total = PanelTotal(
            contenedor, "PÉRDIDA DEL DÍA — solo diferencias negativas (platos / bebidas regalados)"
        )
        self.panel_total.pack(fill="x", padx=4, pady=(0, 10))

        filtros = ctk.CTkFrame(contenedor, fg_color="transparent")
        filtros.pack(fill="x", padx=4, pady=(0, 10))
        self.busqueda = CampoBusqueda(filtros, lambda _t: self.mostrar_filas())
        self.busqueda.pack(side="left")
        self.mostrar_todos = tk.BooleanVar(value=False)
        casilla(
            filtros,
            "Mostrar todos los productos (también sin diferencia / sin precio)",
            self.mostrar_todos,
            self.mostrar_filas,
        ).pack(side="left", padx=16)
        etiqueta_ayuda(filtros, "Doble clic en una fila para corregirla antes de guardar").pack(side="right")

        abajo = ctk.CTkFrame(contenedor, fg_color="transparent")
        abajo.pack(side="bottom", fill="x", padx=4, pady=(10, 4))
        self.lbl_totales = ctk.CTkLabel(
            abajo, text=TOTALES_VACIOS, font=estilos.FUENTE_NEGRITA, text_color=estilos.TEXTO
        )
        self.lbl_totales.pack(side="left")
        boton(abajo, "Guardar día", self.guardar, "primario").pack(side="right")

        tarjeta, self.tabla = crear_tabla(
            contenedor, self.COLUMNAS, {"Producto": 240, "Fecha": 100, "Estado": 150, "Cantidad": 85}
        )
        tarjeta.pack(fill="both", expand=True, padx=4, pady=4)
        self.tabla.bind("<Double-1>", lambda _e: self.corregir_fila())

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def cambiar_empresa(self, empresa: str | None) -> None:
        """Descarta lo cargado de la empresa anterior y trae la lista de precios de la nueva."""
        self.ventas = None
        self._descartar_calculo()
        self.lbl_ventas.configure(text="(sin cargar)")
        self.precios = (
            self.app.repos.precios.cargar(empresa) if empresa else pd.DataFrame(columns=["producto", "precio"])
        )

    def _descartar_calculo(self) -> None:
        self.diferencias = None
        vaciar(self.tabla)
        self.lbl_totales.configure(text=TOTALES_VACIOS)
        self.panel_total.mostrar("$0")

    # ------------------------------------------------------------------
    # Carga de archivos y cálculo
    # ------------------------------------------------------------------
    def cargar_precios(self):
        empresa = self.app.empresa_o_aviso()
        if not empresa:
            return
        ruta = filedialog.askopenfilename(
            title=f"Seleccioná el archivo de precios de {empresa}", filetypes=TIPOS_ARCHIVO
        )
        if not ruta:
            return
        try:
            precios, duplicados = leer_lista_precios(ruta)
        except FormatoExcelError as exc:
            messagebox.showerror("Error en archivo de precios", str(exc))
            return
        if precios.empty:
            messagebox.showerror("Lista vacía", "El archivo no tiene ningún producto con precio. No se cambió nada.")
            return

        self.app.repos.precios.reemplazar(empresa, precios)
        self.precios = precios
        self.app.mostrar_estado_precios()
        if duplicados:
            messagebox.showwarning(
                "Productos duplicados",
                "Estos productos aparecen más de una vez en la lista de precios; "
                "se usó el último precio informado:\n" + ", ".join(duplicados),
            )
        # Si ya había un cálculo, se rehace para no guardar diferencias contra la lista vieja.
        if self.ventas is not None and self.diferencias is not None:
            self.calcular()

    def cargar_ventas(self):
        empresa = self.app.empresa_o_aviso()
        if not empresa:
            return
        if self.precios.empty and not messagebox.askyesno(
            "Sin lista de precios",
            f"{empresa} todavía no tiene una lista de precios cargada. ¿Querés cargar igual el reporte de ventas?",
        ):
            return
        ruta = filedialog.askopenfilename(
            title=f"Seleccioná el reporte de ventas de {empresa}", filetypes=TIPOS_ARCHIVO
        )
        if not ruta:
            return
        try:
            self.ventas, self.fecha_detectada = leer_reporte_ventas(ruta)
        except FormatoExcelError as exc:
            messagebox.showerror("Error en reporte de ventas", str(exc))
            return
        self._descartar_calculo()

        fechas = sorted(self.ventas["fecha"].dropna().unique())
        if self.fecha_detectada:
            descripcion = formato.fecha(self.fecha_detectada)
        elif len(fechas) > 1:
            descripcion = f"{len(fechas)} fechas: {formato.fecha(fechas[0])} a {formato.fecha(fechas[-1])}"
        else:
            descripcion = "sin detectar"
        self.lbl_ventas.configure(text=f"{Path(ruta).name} ({len(self.ventas)} productos, fecha: {descripcion})")

    def calcular(self):
        empresa = self.app.empresa_o_aviso()
        if not empresa:
            return
        if self.precios.empty:
            messagebox.showwarning("Falta la lista de precios", f"Cargá primero la lista de precios de {empresa}.")
            return
        if self.ventas is None:
            messagebox.showwarning("Falta el reporte", "Cargá primero el reporte de ventas del día.")
            return
        self.diferencias = calcular_diferencias(self.ventas, self.precios)
        self.mostrar_filas()

    # ------------------------------------------------------------------
    # Tabla
    # ------------------------------------------------------------------
    def mostrar_filas(self):
        vaciar(self.tabla)
        if self.diferencias is None:
            return
        filas = self.diferencias
        if not self.mostrar_todos.get():
            filas = filas[filas["estado"] == Estado.CON_DIFERENCIA.value]
        filas = filas[coincide_busqueda(filas, self.busqueda.texto, ["producto", "categoria", "nota"])]

        for indice, r in filas.iterrows():
            clasificacion = clasificar(r["estado"], r["diferencia"])
            estado = clasificacion.value + (" ✎" if not es_vacio(r["editado_en"]) else "")
            self.tabla.insert(
                "",
                "end",
                iid=str(indice),
                tags=(clasificacion.name,),
                values=(
                    formato.fecha(r["fecha"]),
                    r["producto"],
                    formato.texto(r["categoria"]),
                    formato.cantidad(r["cantidad_vendida"]),
                    formato.pesos(r["precio_lista"]),
                    formato.pesos(r["monto_esperado"]),
                    formato.pesos(r["monto_informado"]),
                    formato.pesos(r["diferencia"]),
                    estado,
                ),
            )

        t = calcular_totales(self.diferencias)
        partes = [
            f"Platos con pérdida: {t.cantidad_con_perdida}",
            f"Cobrado de más (no se suma): {formato.pesos(t.cobrado_de_mas)} en {t.cantidad_cobrado_de_mas}",
            f"Sin precio: {t.cantidad_sin_precio}",
        ]
        if t.cantidad_precio_abierto:
            partes.append(f"Precio abierto: {t.cantidad_precio_abierto}")
        self.lbl_totales.configure(text="   ·   ".join(partes))
        self.panel_total.mostrar(formato.pesos(t.perdida), estilos.color_total(t.perdida))

    def corregir_fila(self):
        seleccion = self.tabla.selection()
        if not seleccion or self.diferencias is None:
            return
        indice = int(seleccion[0])
        fila = self.diferencias.loc[indice]
        datos = pedir_fila(
            self.app,
            f"Corregir — {fila['producto']}",
            {
                "producto": fila["producto"],
                "categoria": fila["categoria"],
                "cantidad": fila["cantidad_vendida"],
                "precio": fila["precio_lista"],
                "monto": fila["monto_informado"],
                "nota": fila["nota"],
            },
            producto_editable=False,
        )
        if not datos:
            return
        registro_dia.corregir_fila(
            self.diferencias,
            indice,
            datos["categoria"],
            datos["cantidad"],
            datos["precio"],
            datos["monto"],
            datos["nota"],
        )
        self.mostrar_filas()
        if self.tabla.exists(str(indice)):
            self.tabla.selection_set(str(indice))
            self.tabla.see(str(indice))

    # ------------------------------------------------------------------
    # Guardado
    # ------------------------------------------------------------------
    def guardar(self):
        empresa = self.app.empresa_o_aviso()
        if not empresa:
            return
        if self.diferencias is None:
            messagebox.showwarning("Nada para guardar", "Primero calculá las diferencias.")
            return

        diferencias = self.diferencias
        sin_fecha = registro_dia.cantidad_sin_fecha(diferencias)
        if sin_fecha:
            fecha = pedir_fecha(self.app, sin_fecha, len(diferencias))
            if not fecha:
                return
            try:
                diferencias = registro_dia.completar_fechas(diferencias, fecha)
            except ValueError as exc:
                messagebox.showerror("Productos repetidos", str(exc))
                return

        por_fecha = registro_dia.separar_por_fecha(diferencias)
        if len(por_fecha) > 1 and not messagebox.askyesno(
            "Varias fechas",
            f"El reporte trae {len(por_fecha)} fechas distintas:\n"
            + ", ".join(formato.fecha(f) for f in por_fecha)
            + "\n\nSe va a guardar cada fecha por separado. ¿Continuar?",
        ):
            return

        existentes = [f for f in por_fecha if self.app.repos.diferencias.existe_dia(empresa, f)]
        if existentes and not messagebox.askyesno(
            "La fecha ya existe",
            f"Ya hay datos guardados de {empresa} para: {', '.join(formato.fecha(f) for f in existentes)}.\n\n"
            "¿Querés reemplazarlos? La versión anterior queda en la Papelera por si te equivocaste.",
        ):
            return

        lineas = []
        for fecha, filas in por_fecha.items():
            self.app.repos.diferencias.guardar_dia(empresa, fecha, filas, reemplazar=fecha in existentes)
            lineas.append(f"{formato.fecha(fecha)}: pérdida {formato.pesos(perdida_total(filas))}")
        messagebox.showinfo("Guardado", f"Datos de {empresa} guardados correctamente.\n\n" + "\n".join(lineas))
        self.app.refrescar_todo()
