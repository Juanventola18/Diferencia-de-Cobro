"""Ventanas modales que piden datos al usuario."""

from __future__ import annotations

from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from diferencias.dominio.estado import clasificar
from diferencias.dominio.reglas import calcular_fila, validar_fila
from diferencias.dominio.valores import es_vacio, parsear_fecha_usuario, parsear_numero
from diferencias.ui import estilos, formato
from diferencias.ui.widgets import Tarjeta, boton, preparar_ventana

CAMPOS_FILA = [
    ("producto", "Producto"),
    ("categoria", "Categoría"),
    ("cantidad", "Cantidad vendida"),
    ("precio", "Precio de lista (vacío = sin precio)"),
    ("monto", "Monto informado (cobrado)"),
    ("nota", "Nota (opcional)"),
]
CAMPOS_NUMERICOS = {"cantidad": "La cantidad", "precio": "El precio", "monto": "El monto"}


def _leer_campos(campos: dict[str, ctk.CTkEntry]) -> dict:
    datos = {
        "producto": campos["producto"].get().strip(),
        "categoria": campos["categoria"].get().strip() or None,
        "nota": campos["nota"].get().strip() or None,
    }
    for clave, nombre in CAMPOS_NUMERICOS.items():
        try:
            datos[clave] = parsear_numero(campos[clave].get())
        except ValueError:
            raise ValueError(f"{nombre} no es un número válido.") from None
    validar_fila(datos["producto"], datos["cantidad"], datos["precio"], datos["monto"])
    return datos


def pedir_fila(
    padre, titulo: str, inicial: dict, producto_editable: bool, precios_lista: dict[str, float] | None = None
) -> dict | None:
    """Formulario para corregir o agregar una fila, con vista previa del resultado.

    `inicial` y el resultado tienen las claves de CAMPOS_FILA. Devuelve None si se cancela.
    """
    ventana = ctk.CTkToplevel(padre)
    preparar_ventana(ventana, padre, titulo, modal=True)
    ventana.resizable(False, False)
    resultado: dict = {}

    cuerpo = Tarjeta(ventana)
    cuerpo.pack(fill="both", expand=True, padx=16, pady=16)
    grilla = ctk.CTkFrame(cuerpo, fg_color="transparent")
    grilla.pack(padx=20, pady=16)

    campos: dict[str, ctk.CTkEntry] = {}
    for fila, (clave, texto) in enumerate(CAMPOS_FILA):
        ctk.CTkLabel(grilla, text=texto, text_color=estilos.TEXTO_SECUNDARIO, font=estilos.FUENTE_CHICA).grid(
            row=fila, column=0, sticky="w", pady=5, padx=(0, 14)
        )
        campo = ctk.CTkEntry(
            grilla,
            width=320,
            corner_radius=estilos.RADIO_CAMPO,
            fg_color=estilos.FONDO_TABLA,
            border_width=1,
            border_color=estilos.BORDE_CAMPO,
            font=estilos.FUENTE,
        )
        valor = inicial.get(clave)
        if clave in CAMPOS_NUMERICOS:
            campo.insert(0, formato.numero_editable(valor))
        elif not es_vacio(valor):
            campo.insert(0, str(valor))
        campo.grid(row=fila, column=1, pady=5)
        campos[clave] = campo
    if not producto_editable:
        campos["producto"].configure(state="disabled", text_color=estilos.TEXTO_SECUNDARIO)

    vista_previa = ctk.CTkLabel(grilla, text="", font=estilos.FUENTE_NEGRITA, justify="left")
    vista_previa.grid(row=len(CAMPOS_FILA), column=0, columnspan=2, sticky="w", pady=(12, 0))
    error = ctk.CTkLabel(grilla, text="", text_color=estilos.TEXTO_PERDIDA, font=estilos.FUENTE_CHICA, justify="left")
    error.grid(row=len(CAMPOS_FILA) + 1, column=0, columnspan=2, sticky="w")

    def actualizar_vista_previa(_evento=None):
        try:
            datos = _leer_campos(campos)
        except ValueError as exc:
            vista_previa.configure(text="")
            error.configure(text=str(exc))
            return
        error.configure(text="")
        r = calcular_fila(datos["cantidad"], datos["precio"], datos["monto"])
        clasificacion = clasificar(r.estado, r.diferencia)
        vista_previa.configure(
            text=f"Esperado: {formato.pesos(r.monto_esperado)}   ·   Diferencia: {formato.pesos(r.diferencia)}"
            f"   →   {clasificacion.value}",
            text_color=estilos.color_clasificacion(clasificacion),
        )

    def autocompletar_precio(_evento=None):
        if precios_lista and not campos["precio"].get().strip():
            precio = precios_lista.get(campos["producto"].get().strip())
            if precio is not None:
                campos["precio"].insert(0, formato.numero_editable(precio))
        actualizar_vista_previa()

    for clave in ("producto", "cantidad", "precio", "monto"):
        campos[clave].bind("<KeyRelease>", actualizar_vista_previa)
    campos["producto"].bind("<FocusOut>", autocompletar_precio)

    def confirmar(_evento=None):
        try:
            resultado.update(_leer_campos(campos))
        except ValueError as exc:
            error.configure(text=str(exc))
            return
        ventana.destroy()

    botones = ctk.CTkFrame(cuerpo, fg_color="transparent")
    botones.pack(fill="x", padx=20, pady=(0, 16))
    boton(botones, "Guardar", confirmar, "primario").pack(side="right")
    boton(botones, "Cancelar", ventana.destroy).pack(side="right", padx=8)
    ventana.bind("<Return>", confirmar)
    ventana.bind("<Escape>", lambda _e: ventana.destroy())

    actualizar_vista_previa()
    (campos["producto"] if producto_editable else campos["monto"]).focus_set()
    padre.wait_window(ventana)
    return resultado or None


def pedir_fecha(padre, sin_fecha: int, total: int) -> str | None:
    """Pide la fecha para las filas del reporte que no la tienen. Devuelve ISO o None si se cancela."""
    ventana = ctk.CTkToplevel(padre)
    preparar_ventana(ventana, padre, "Elegí la fecha", modal=True)
    explicacion = (
        "No se pudo detectar la fecha del reporte."
        if sin_fecha == total
        else f"{sin_fecha} de {total} productos no tienen una fecha legible."
    )
    ctk.CTkLabel(ventana, text=f"{explicacion}\nIngresá la fecha (DD/MM/AAAA):", font=estilos.FUENTE).pack(
        padx=20, pady=20
    )
    campo = ctk.CTkEntry(
        ventana, corner_radius=estilos.RADIO_CAMPO, fg_color=estilos.FONDO_TARJETA, font=estilos.FUENTE
    )
    campo.insert(0, date.today().strftime("%d/%m/%Y"))
    campo.pack(padx=20, pady=4)
    resultado: dict = {}

    def confirmar(_evento=None):
        fecha = parsear_fecha_usuario(campo.get())
        if fecha is None:
            messagebox.showerror("Fecha inválida", "Usá el formato DD/MM/AAAA, por ejemplo 01/09/2026.", parent=ventana)
            return
        resultado["fecha"] = fecha
        ventana.destroy()

    boton(ventana, "Confirmar", confirmar, "primario").pack(pady=16)
    ventana.bind("<Return>", confirmar)
    campo.focus_set()
    padre.wait_window(ventana)
    return resultado.get("fecha")
