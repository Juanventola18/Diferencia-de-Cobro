"""Pestaña "Por producto": pérdida acumulada de cada producto en todo el historial."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk
import pandas as pd

from diferencias.dominio.valores import coincide_busqueda, normalizar_texto
from diferencias.servicios.estadisticas import resumen_por_producto
from diferencias.ui import estilos, formato
from diferencias.ui.ventanas import VentanaLista
from diferencias.ui.widgets import CampoBusqueda, PanelTotal, casilla, crear_tabla, etiqueta_ayuda, vaciar

if TYPE_CHECKING:
    from diferencias.ui.app import App

TITULO = "PÉRDIDA ACUMULADA (todo el historial, solo diferencias negativas)"

# (encabezado visible, columna del DataFrame)
COLUMNAS = [
    ("Producto", "producto"),
    ("Días vendido", "veces_vendido"),
    ("Días con pérdida", "veces_con_perdida"),
    ("Cantidad", "cantidad_total_vendida"),
    ("Monto informado", "monto_total_informado"),
    ("Pérdida", "perdida_acumulada"),
    ("Cobrado de más (info)", "cobrado_de_mas"),
]


class PestanaPorProducto:
    def __init__(self, app: App, contenedor: ctk.CTkFrame):
        self.app = app
        self.resumen = pd.DataFrame()
        self.columna_orden = "perdida_acumulada"
        self.ascendente = True  # la pérdida más grande (más negativa) primero

        contenedor.configure(fg_color=estilos.FONDO)
        self.panel_total = PanelTotal(contenedor, TITULO)
        self.panel_total.pack(fill="x", padx=4, pady=(14, 10))

        barra = ctk.CTkFrame(contenedor, fg_color="transparent")
        barra.pack(fill="x", padx=4, pady=(0, 8))
        self.busqueda = CampoBusqueda(barra, lambda _t: self.mostrar_filas(), placeholder="Buscar producto…")
        self.busqueda.pack(side="left")
        self.mostrar_todos = tk.BooleanVar(value=False)
        casilla(
            barra, "Mostrar todos los productos (también sin diferencia)", self.mostrar_todos, self.mostrar_filas
        ).pack(side="left", padx=16)
        etiqueta_ayuda(barra, "Clic en encabezado = ordenar · doble clic = historial").pack(side="right")

        tarjeta, self.tabla = crear_tabla(
            contenedor, [titulo for titulo, _ in COLUMNAS], {"Producto": 280, "Cobrado de más (info)": 170}, height=18
        )
        tarjeta.pack(fill="both", expand=True, padx=4, pady=4)
        for titulo, columna in COLUMNAS:
            self.tabla.heading(titulo, text=titulo, command=lambda c=columna: self.ordenar_por(c))
        self.tabla.bind("<Double-1>", lambda _e: self._abrir_historial())

    def refrescar(self):
        empresa = self.app.empresa
        historial = self.app.repos.diferencias.cargar_historial(empresa) if empresa else pd.DataFrame()
        self.resumen = resumen_por_producto(historial)
        self._ordenar()
        self.mostrar_filas()

    def ordenar_por(self, columna: str):
        """Un clic ordena por esa columna; otro clic en la misma invierte el orden."""
        if self.columna_orden == columna:
            self.ascendente = not self.ascendente
        else:
            self.columna_orden = columna
            self.ascendente = columna in ("producto", "perdida_acumulada")
        self._ordenar()
        self.mostrar_filas()

    def _ordenar(self):
        if self.resumen.empty:
            return
        self.resumen = self.resumen.sort_values(
            self.columna_orden,
            ascending=self.ascendente,
            key=lambda s: s.map(normalizar_texto) if s.name == "producto" else s,
        ).reset_index(drop=True)

    def mostrar_filas(self):
        vaciar(self.tabla)
        filas = self.resumen
        if not filas.empty and not self.mostrar_todos.get():
            filas = filas[(filas["perdida_acumulada"] != 0) | (filas["cobrado_de_mas"] != 0)]
        filtro = self.busqueda.texto
        if not filas.empty and filtro:
            filas = filas[coincide_busqueda(filas, filtro, ["producto"])]

        total = float(filas["perdida_acumulada"].sum()) if not filas.empty else 0.0
        titulo = TITULO + (f" — {len(filas)} productos que coinciden con '{filtro}'" if filtro else "")
        self.panel_total.mostrar(formato.pesos(total), estilos.color_total(total), titulo=titulo)

        for indice, r in filas.iterrows():
            self.tabla.insert(
                "",
                "end",
                iid=str(indice),
                tags=(estilos.tag_por_signo(r["perdida_acumulada"]),),
                values=(
                    r["producto"],
                    int(r["veces_vendido"]),
                    int(r["veces_con_perdida"]),
                    formato.cantidad(r["cantidad_total_vendida"]),
                    formato.pesos(r["monto_total_informado"]),
                    formato.pesos(r["perdida_acumulada"]),
                    formato.pesos(r["cobrado_de_mas"]) if r["cobrado_de_mas"] else "-",
                ),
            )

    def _abrir_historial(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        empresa = self.app.empresa
        producto = self.resumen.loc[int(seleccion[0]), "producto"]
        historial = self.app.repos.diferencias.historial_producto(empresa, producto)
        VentanaLista(
            self.app,
            f"{producto} — {empresa}",
            f"PÉRDIDA ACUMULADA DE '{producto}' ({len(historial)} días vendido)",
            historial,
            al_doble_click=lambda fecha: self.app.abrir_dia(empresa, fecha),
        )
