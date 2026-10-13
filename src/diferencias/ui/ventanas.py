"""Ventanas secundarias: un día guardado (editable) y listas de solo lectura."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk
import pandas as pd

from diferencias.dominio.estado import Estado, clasificar
from diferencias.dominio.reglas import calcular_totales, perdida_total
from diferencias.dominio.valores import coincide_busqueda, es_vacio
from diferencias.persistencia.errores import ConflictoError, NoEncontradoError
from diferencias.ui import estilos, formato
from diferencias.ui.dialogos import pedir_fila
from diferencias.ui.widgets import (
    CampoBusqueda,
    PanelTotal,
    boton,
    casilla,
    crear_tabla,
    etiqueta_ayuda,
    preparar_ventana,
    vaciar,
)

if TYPE_CHECKING:
    from diferencias.ui.app import App


class VentanaDia(ctk.CTkToplevel):
    """Muestra un día guardado y permite corregir, agregar o quitar productos."""

    COLUMNAS = [
        "Producto",
        "Categoría",
        "Cantidad",
        "Precio lista",
        "Esperado",
        "Monto informado",
        "Diferencia",
        "Estado",
        "Nota",
    ]
    ANCHOS = {
        "Producto": 200,
        "Categoría": 110,
        "Cantidad": 70,
        "Precio lista": 95,
        "Esperado": 100,
        "Monto informado": 110,
        "Diferencia": 100,
        "Estado": 130,
        "Nota": 150,
    }

    def __init__(self, app: App, empresa: str, fecha: str):
        super().__init__(app)
        self.app, self.empresa, self.fecha = app, empresa, fecha
        preparar_ventana(self, app, f"{empresa} — {formato.fecha(fecha)} (ver / editar)", "1240x660")
        self.dia = pd.DataFrame()

        self.panel_total = PanelTotal(self, f"PÉRDIDA DEL {formato.fecha(fecha)} — solo diferencias negativas")
        self.panel_total.pack(fill="x", padx=16, pady=(16, 8))

        filtros = ctk.CTkFrame(self, fg_color="transparent")
        filtros.pack(fill="x", padx=16, pady=(0, 6))
        self.busqueda = CampoBusqueda(filtros, lambda _t: self.mostrar_filas())
        self.busqueda.pack(side="left")
        self.mostrar_todos = tk.BooleanVar(value=False)
        casilla(
            filtros,
            "Mostrar todos los productos (también sin diferencia / sin precio)",
            self.mostrar_todos,
            self.mostrar_filas,
        ).pack(side="left", padx=16)

        abajo = ctk.CTkFrame(self, fg_color="transparent")
        abajo.pack(side="bottom", fill="x", padx=16, pady=(6, 16))
        boton(abajo, "✎ Editar fila", self.editar).pack(side="left")
        boton(abajo, "+ Agregar producto", self.agregar).pack(side="left", padx=8)
        boton(abajo, "🗑 Quitar seleccionadas", self.quitar_filas, "peligro").pack(side="left")
        boton(abajo, "🗑 Mandar el día entero a la papelera", self.quitar_dia, "peligro").pack(side="left", padx=8)
        boton(abajo, "Cerrar", self.destroy, "primario").pack(side="right")
        etiqueta_ayuda(self, "Doble clic para editar · Ctrl/Shift + clic para elegir varias · Supr para quitar").pack(
            side="bottom", anchor="w", padx=20
        )

        tarjeta, self.tabla = crear_tabla(self, self.COLUMNAS, self.ANCHOS, selectmode="extended")
        tarjeta.pack(fill="both", expand=True, padx=16, pady=6)
        self.tabla.bind("<Double-1>", lambda _e: self.editar())
        self.tabla.bind("<Delete>", lambda _e: self.quitar_filas())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.recargar()

    def destroy(self):
        self.app.olvidar_ventana_dia(self.empresa, self.fecha)
        super().destroy()

    def recargar(self) -> bool:
        """Relee el día de la base. Si ya no tiene filas, avisa y se cierra."""
        self.dia = self.app.repos.diferencias.cargar_dia(self.empresa, self.fecha)
        if self.dia.empty:
            messagebox.showinfo(
                "Día sin datos",
                f"El {formato.fecha(self.fecha)} de {self.empresa} ya no tiene productos (está en la papelera).",
                parent=self,
            )
            self.destroy()
            return False
        t = calcular_totales(self.dia)
        self.panel_total.mostrar(
            formato.pesos(t.perdida),
            estilos.color_total(t.perdida),
            subtitulo=f"{t.cantidad_con_perdida} platos con pérdida   ·   Cobrado de más (no se suma): "
            f"{formato.pesos(t.cobrado_de_mas)}   ·   {len(self.dia)} productos en total",
        )
        self.mostrar_filas()
        return True

    def mostrar_filas(self):
        seleccion = set(self.tabla.selection())
        vaciar(self.tabla)
        filas = self.dia
        if not self.mostrar_todos.get():
            filas = filas[filas["estado"] == Estado.CON_DIFERENCIA.value]
        filas = filas[coincide_busqueda(filas, self.busqueda.texto, ["producto", "categoria", "nota"])]
        for _, r in filas.iterrows():
            clasificacion = clasificar(r["estado"], r["diferencia"])
            nota = ("✎ " if not es_vacio(r["editado_en"]) else "") + formato.texto(r["nota"])
            iid = str(int(r["id"]))
            self.tabla.insert(
                "",
                "end",
                iid=iid,
                tags=(clasificacion.name,),
                values=(
                    r["producto"],
                    formato.texto(r["categoria"]),
                    formato.cantidad(r["cantidad_vendida"]),
                    formato.pesos(r["precio_lista"]),
                    formato.pesos(r["monto_esperado"]),
                    formato.pesos(r["monto_informado"]),
                    formato.pesos(r["diferencia"]),
                    clasificacion.value,
                    nota,
                ),
            )
            if iid in seleccion:
                self.tabla.selection_add(iid)

    def _hubo_cambios(self):
        if self.recargar():
            self.app.refrescar_todo(excepto=self)

    def editar(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showinfo("Editar", "Elegí una fila para editar.", parent=self)
            return
        fila = self.dia[self.dia["id"] == int(seleccion[0])].iloc[0]
        datos = pedir_fila(
            self,
            f"Editar — {fila['producto']}",
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
        try:
            self.app.repos.diferencias.actualizar_fila(
                int(fila["id"]), datos["categoria"], datos["cantidad"], datos["precio"], datos["monto"], datos["nota"]
            )
        except NoEncontradoError as exc:
            messagebox.showerror("No se pudo editar", str(exc), parent=self)
        self._hubo_cambios()

    def agregar(self):
        precios = self.app.repos.precios.cargar(self.empresa)
        datos = pedir_fila(
            self,
            f"Agregar producto al {formato.fecha(self.fecha)}",
            {"cantidad": 1, "monto": 0},
            producto_editable=True,
            precios_lista=dict(zip(precios["producto"], precios["precio"], strict=True)),
        )
        if not datos:
            return
        try:
            self.app.repos.diferencias.agregar_fila(
                self.empresa,
                self.fecha,
                datos["producto"],
                datos["categoria"],
                datos["cantidad"],
                datos["precio"],
                datos["monto"],
                datos["nota"],
            )
        except (ConflictoError, ValueError) as exc:
            messagebox.showerror("No se pudo agregar", str(exc), parent=self)
            return
        self._hubo_cambios()

    def quitar_filas(self):
        ids = [int(i) for i in self.tabla.selection()]
        if not ids:
            messagebox.showinfo("Quitar", "Elegí una o más filas.", parent=self)
            return
        nombres = self.dia.loc[self.dia["id"].isin(ids), "producto"].tolist()
        if not messagebox.askyesno(
            "Mandar a la papelera",
            f"¿Mandar a la papelera {len(nombres)} producto(s)?\n\n{formato.lista_corta(nombres, 5)}\n\n"
            "Se pueden restaurar desde la pestaña Papelera.",
            parent=self,
        ):
            return
        self.app.repos.papelera.enviar_filas(self.empresa, ids)
        self._hubo_cambios()

    def quitar_dia(self):
        if self.app.mandar_dia_a_papelera(self.empresa, self.fecha, padre=self):
            self.destroy()


class VentanaLista(ctk.CTkToplevel):
    """Lista de filas de solo lectura: historial de un producto o contenido de un lote de la papelera."""

    COLUMNAS = ["Fecha", "Producto", "Cantidad", "Precio lista", "Monto informado", "Diferencia", "Estado", "Nota"]

    def __init__(
        self,
        padre,
        titulo: str,
        subtitulo: str,
        filas: pd.DataFrame,
        al_doble_click: Callable[[str], None] | None = None,
    ):
        super().__init__(padre)
        preparar_ventana(self, padre, titulo, "1050x560")
        perdida = perdida_total(filas)
        panel = PanelTotal(self, subtitulo)
        panel.mostrar(formato.pesos(perdida), estilos.color_total(perdida))
        panel.pack(fill="x", padx=16, pady=(16, 8))

        boton(self, "Cerrar", self.destroy, "primario").pack(side="bottom", anchor="e", padx=16, pady=(6, 16))
        if al_doble_click:
            etiqueta_ayuda(self, "Doble clic en una fila para abrir ese día.").pack(side="bottom", anchor="w", padx=20)
        tarjeta, tabla = crear_tabla(self, self.COLUMNAS, {"Producto": 240, "Nota": 180})
        tarjeta.pack(fill="both", expand=True, padx=16, pady=6)

        filas = filas.reset_index(drop=True)
        for i, r in filas.iterrows():
            clasificacion = clasificar(r["estado"], r["diferencia"])
            tabla.insert(
                "",
                "end",
                iid=str(i),
                tags=(clasificacion.name,),
                values=(
                    formato.fecha(r["fecha"]),
                    r["producto"],
                    formato.cantidad(r["cantidad_vendida"]),
                    formato.pesos(r["precio_lista"]),
                    formato.pesos(r["monto_informado"]),
                    formato.pesos(r["diferencia"]),
                    clasificacion.value,
                    formato.texto(r["nota"]),
                ),
            )
        if al_doble_click:

            def abrir(_evento):
                if tabla.selection():
                    al_doble_click(filas.loc[int(tabla.selection()[0]), "fecha"])

            tabla.bind("<Double-1>", abrir)
