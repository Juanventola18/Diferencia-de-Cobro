"""Componentes visuales reutilizables."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

import customtkinter as ctk

from diferencias.ui import estilos

COLUMNAS_ALINEADAS_A_IZQUIERDA = {"Producto", "Categoría", "Detalle", "Nota"}


class Tarjeta(ctk.CTkFrame):
    """Panel con bordes redondeados, el contenedor básico de todas las pantallas."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", estilos.FONDO_TARJETA)
        kwargs.setdefault("corner_radius", estilos.RADIO_TARJETA)
        super().__init__(master, **kwargs)


class CampoBusqueda(ctk.CTkFrame):
    """Caja de búsqueda con botón para limpiar.

    Llama a `al_cambiar(texto)` 250 ms después de la última tecla, para no
    refiltrar la tabla en cada letra.
    """

    DEMORA_MS = 250

    def __init__(
        self,
        master,
        al_cambiar: Callable[[str], None],
        placeholder: str = "Buscar producto o categoría…",
        width: int = 300,
    ):
        super().__init__(master, fg_color="transparent")
        self._al_cambiar = al_cambiar
        self._pendiente = None
        self._ultimo = ""
        # Sin textvariable: con una textvariable customtkinter no muestra el placeholder.
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="🔍  " + placeholder,
            width=width,
            corner_radius=estilos.RADIO_CAMPO,
            fg_color=estilos.FONDO_TABLA,
            border_width=1,
            border_color=estilos.FONDO_ENCABEZADO,
            font=estilos.FUENTE,
        )
        self.entry.pack(side="left")
        ctk.CTkButton(
            self,
            text="✕",
            width=30,
            command=self.limpiar,
            corner_radius=estilos.RADIO_CAMPO,
            fg_color=estilos.FONDO_ENCABEZADO,
            hover_color=estilos.SECUNDARIO_HOVER,
        ).pack(side="left", padx=(4, 0))
        self.entry.bind("<KeyRelease>", lambda _e: self._programar())
        self.entry.bind("<<Paste>>", lambda _e: self.after(10, self._programar))
        self.entry.bind("<Escape>", lambda _e: self.limpiar())

    @property
    def texto(self) -> str:
        return self.entry.get().strip()

    def _programar(self):
        if self._pendiente:
            self.after_cancel(self._pendiente)
        self._pendiente = self.after(self.DEMORA_MS, self._disparar)

    def _disparar(self):
        self._pendiente = None
        if self.texto != self._ultimo:
            self._ultimo = self.texto
            self._al_cambiar(self.texto)

    def limpiar(self):
        self.entry.delete(0, "end")
        self._disparar()
        self.entry._activate_placeholder()
        self.focus_set()


def boton(master, texto: str, comando, tipo: str = "secundario", **kwargs) -> ctk.CTkButton:
    """tipo: 'primario', 'secundario' o 'peligro'."""
    fondo, hover, fuente = {
        "primario": (estilos.ACENTO, estilos.ACENTO_HOVER, estilos.FUENTE_NEGRITA),
        "secundario": (estilos.FONDO_ENCABEZADO, estilos.SECUNDARIO_HOVER, estilos.FUENTE),
        "peligro": (estilos.PELIGRO, estilos.PELIGRO_HOVER, estilos.FUENTE),
    }[tipo]
    kwargs.setdefault("fg_color", fondo)
    kwargs.setdefault("hover_color", hover)
    kwargs.setdefault("font", fuente)
    return ctk.CTkButton(master, text=texto, command=comando, corner_radius=estilos.RADIO_BOTON, **kwargs)


def casilla(master, texto: str, variable: tk.BooleanVar, comando) -> ctk.CTkCheckBox:
    return ctk.CTkCheckBox(
        master,
        text=texto,
        variable=variable,
        command=comando,
        corner_radius=6,
        fg_color=estilos.ACENTO,
        hover_color=estilos.ACENTO_HOVER,
        font=estilos.FUENTE,
    )


def etiqueta_ayuda(master, texto: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=texto, text_color=estilos.TEXTO_SECUNDARIO, font=estilos.FUENTE_CHICA)


class PanelTotal(Tarjeta):
    """Tarjeta con un título chico, un número grande y un subtítulo opcional."""

    def __init__(self, master, titulo: str = ""):
        super().__init__(master)
        interior = ctk.CTkFrame(self, fg_color="transparent")
        interior.pack(fill="x", padx=20, pady=16)
        self.titulo = etiqueta_ayuda(interior, titulo)
        self.titulo.pack(anchor="w")
        self.total = ctk.CTkLabel(interior, text="$0", text_color=estilos.TEXTO, font=estilos.FUENTE_TOTAL)
        self.total.pack(anchor="w")
        self.subtitulo = etiqueta_ayuda(interior, "")
        self.subtitulo.pack(anchor="w")

    def mostrar(
        self, texto_total: str, color: str = estilos.TEXTO, titulo: str | None = None, subtitulo: str | None = None
    ) -> None:
        self.total.configure(text=texto_total, text_color=color)
        if titulo is not None:
            self.titulo.configure(text=titulo)
        if subtitulo is not None:
            self.subtitulo.configure(text=subtitulo)


def crear_tabla(
    master,
    columnas: list[str],
    anchos: dict[str, int] | None = None,
    selectmode: str = "browse",
    height: int = 14,
    show: str = "headings",
) -> tuple[Tarjeta, ttk.Treeview]:
    """Treeview con scrollbar dentro de una Tarjeta. Devuelve (tarjeta, tabla)."""
    anchos = anchos or {}
    tarjeta = Tarjeta(master)
    tabla = ttk.Treeview(tarjeta, columns=columnas, show=show, height=height, selectmode=selectmode)
    for c in columnas:
        tabla.heading(c, text=c)
        tabla.column(c, width=anchos.get(c, 115), anchor="w" if c in COLUMNAS_ALINEADAS_A_IZQUIERDA else "center")
    barra = ttk.Scrollbar(tarjeta, orient="vertical", command=tabla.yview)
    tabla.configure(yscrollcommand=barra.set)
    tabla.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=14)
    barra.pack(side="right", fill="y", padx=(0, 10), pady=14)
    estilos.configurar_tags(tabla)
    return tarjeta, tabla


def vaciar(tabla: ttk.Treeview) -> None:
    tabla.delete(*tabla.get_children())


def preparar_ventana(
    ventana: ctk.CTkToplevel, padre, titulo: str, geometria: str | None = None, modal: bool = False
) -> None:
    """Configura una ventana secundaria: título, tamaño, y que aparezca adelante de la principal."""
    ventana.title(titulo)
    ventana.configure(fg_color=estilos.FONDO)
    if geometria:
        ventana.geometry(geometria)
    ventana.transient(padre)
    ventana.lift()
    # En Windows una Toplevel nueva a veces queda detrás de la principal.
    ventana.attributes("-topmost", True)
    ventana.after(200, lambda: ventana.attributes("-topmost", False))
    ventana.focus_force()
    if modal:
        ventana.after(50, lambda: _tomar_foco_exclusivo(ventana))


def _tomar_foco_exclusivo(ventana) -> None:
    try:
        ventana.grab_set()
    except tk.TclError:  # todavía no es visible; se reintenta
        ventana.after(100, lambda: _tomar_foco_exclusivo(ventana))
