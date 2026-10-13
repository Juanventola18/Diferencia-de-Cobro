"""Colores, fuentes y estilo de las tablas. Todo lo visual se cambia desde acá."""

from tkinter import ttk

import customtkinter as ctk

from diferencias.dominio.estado import Clasificacion

FONDO = "#121212"
FONDO_TARJETA = "#1c1c1f"
FONDO_TABLA = "#1a1a1d"
FONDO_ENCABEZADO = "#242428"
TEXTO = "#e8e8ea"
TEXTO_SECUNDARIO = "#98989c"
ACENTO = "#4f8cff"
ACENTO_HOVER = "#3d78e0"
PELIGRO = "#c0392b"
PELIGRO_HOVER = "#a93226"
SECUNDARIO_HOVER = "#333338"
BORDE_CAMPO = "#3a3a40"

# (fondo, texto) de cada tipo de fila
COLORES_CLASIFICACION = {
    Clasificacion.PERDIDA: ("#3a1f22", "#ff9a9a"),
    Clasificacion.COBRADO_DE_MAS: ("#1d3326", "#8ef0b4"),
    Clasificacion.OK: (FONDO_TABLA, TEXTO_SECUNDARIO),
    Clasificacion.SIN_PRECIO: ("#3a3320", "#ffd58a"),
    Clasificacion.PRECIO_ABIERTO: ("#2b2440", "#c9b8ff"),
}
TEXTO_PERDIDA = COLORES_CLASIFICACION[Clasificacion.PERDIDA][1]

FUENTE = ("Segoe UI", 13)
FUENTE_NEGRITA = ("Segoe UI", 13, "bold")
FUENTE_CHICA = ("Segoe UI", 11)
FUENTE_TOTAL = ("Segoe UI", 26, "bold")

RADIO_TARJETA = 16
RADIO_BOTON = 10
RADIO_CAMPO = 8

# Tags extra para filas que no son de una diferencia (totales del árbol, ranking).
TAG_NEGATIVO = "negativo"
TAG_NEUTRO = "neutro"


def aplicar_tema() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    estilo = ttk.Style()
    estilo.theme_use("clam")
    estilo.configure(
        "Treeview",
        background=FONDO_TABLA,
        fieldbackground=FONDO_TABLA,
        foreground=TEXTO,
        rowheight=30,
        borderwidth=0,
        font=FUENTE,
    )
    estilo.configure(
        "Treeview.Heading",
        background=FONDO_ENCABEZADO,
        foreground=TEXTO,
        font=FUENTE_NEGRITA,
        borderwidth=0,
        relief="flat",
    )
    estilo.map("Treeview.Heading", background=[("active", FONDO_ENCABEZADO)])
    estilo.map("Treeview", background=[("selected", ACENTO)], foreground=[("selected", "#ffffff")])
    estilo.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    estilo.configure(
        "Vertical.TScrollbar", background=FONDO_ENCABEZADO, troughcolor=FONDO, bordercolor=FONDO, arrowcolor=TEXTO
    )


def configurar_tags(tabla: ttk.Treeview) -> None:
    for clasificacion, (fondo, texto) in COLORES_CLASIFICACION.items():
        tabla.tag_configure(clasificacion.name, background=fondo, foreground=texto)
    tabla.tag_configure(TAG_NEGATIVO, foreground=TEXTO_PERDIDA)
    tabla.tag_configure(TAG_NEUTRO, foreground=TEXTO_SECUNDARIO)


def tag_por_signo(valor: float) -> str:
    return TAG_NEGATIVO if valor < 0 else TAG_NEUTRO


def color_total(valor: float) -> str:
    return TEXTO_PERDIDA if valor < 0 else TEXTO


def color_clasificacion(clasificacion: Clasificacion) -> str:
    return TEXTO if clasificacion == Clasificacion.OK else COLORES_CLASIFICACION[clasificacion][1]
