"""Cómo se muestran números y fechas en pantalla (formato argentino)."""

from __future__ import annotations

from datetime import datetime

from diferencias.dominio.valores import FORMATO_MARCA_TIEMPO, es_vacio

MESES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


def pesos(valor) -> str:
    """-17500 -> '-$17.500'. Vacío -> '-'."""
    if es_vacio(valor):
        return "-"
    valor = float(valor)
    signo = "-" if valor < 0 else ""
    return f"{signo}${abs(valor):,.0f}".replace(",", ".")


def pesos_o_cero(valor) -> str:
    return pesos(valor) if valor else "$0"


def cantidad(valor) -> str:
    if es_vacio(valor):
        return "-"
    valor = float(valor)
    return str(int(valor)) if valor.is_integer() else f"{valor:g}".replace(".", ",")


def numero_editable(valor) -> str:
    """Número para un campo de texto editable: sin '$' ni separador de miles."""
    if es_vacio(valor):
        return ""
    valor = float(valor)
    return str(int(valor)) if valor.is_integer() else str(valor).replace(".", ",")


def fecha(fecha_iso) -> str:
    """'2026-09-01' -> '01/09/2026'."""
    if es_vacio(fecha_iso):
        return "(sin fecha)"
    try:
        return datetime.strptime(str(fecha_iso)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(fecha_iso)


def fecha_hora(marca: str) -> str:
    return datetime.strptime(marca, FORMATO_MARCA_TIEMPO).strftime("%d/%m/%Y %H:%M")


def lista_corta(nombres: list[str], maximo: int) -> str:
    resultado = ", ".join(nombres[:maximo])
    if len(nombres) > maximo:
        resultado += f" y {len(nombres) - maximo} más"
    return resultado


def texto(valor) -> str:
    """Texto para una celda: los vacíos de pandas se muestran en blanco, no como 'nan'."""
    return "" if es_vacio(valor) else str(valor)
