"""Preparación de un reporte calculado antes de guardarlo.

Acá vive la lógica de "Guardar día" que no depende de la interfaz: completar
fechas faltantes, separar por fecha y aplicar correcciones manuales. Las
preguntas al usuario (confirmar, pedir una fecha) quedan en la UI.
"""

from __future__ import annotations

import pandas as pd

from diferencias.dominio.reglas import calcular_fila
from diferencias.dominio.valores import ahora


def cantidad_sin_fecha(diferencias: pd.DataFrame) -> int:
    return int(diferencias["fecha"].isna().sum())


def completar_fechas(diferencias: pd.DataFrame, fecha: str) -> pd.DataFrame:
    """Asigna `fecha` a las filas sin fecha. Levanta ValueError si eso deja
    un producto repetido en el mismo día."""
    resultado = diferencias.copy()
    resultado["fecha"] = resultado["fecha"].astype(object)
    resultado.loc[resultado["fecha"].isna(), "fecha"] = fecha
    if resultado.duplicated(subset=["fecha", "producto"]).any():
        raise ValueError(
            "Al asignar esa fecha a las filas sin fecha quedan productos repetidos en el mismo día. "
            "Elegí otra fecha o revisá el reporte."
        )
    return resultado


def separar_por_fecha(diferencias: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Un DataFrame por fecha, ordenado por fecha. Las filas deben tener fecha."""
    return {str(fecha): grupo for fecha, grupo in diferencias.groupby("fecha", sort=True)}


def corregir_fila(diferencias: pd.DataFrame, indice, categoria, cantidad, precio, monto, nota) -> None:
    """Corrige en memoria una fila todavía no guardada y la recalcula."""
    r = calcular_fila(cantidad, precio, monto)
    # Las columnas pueden haber quedado con tipo entero o todo-vacío; se pasan
    # a tipos que acepten lo que se va a escribir.
    for col in ("precio_lista", "monto_esperado", "diferencia", "cantidad_vendida", "monto_informado"):
        diferencias[col] = diferencias[col].astype(float)
    for col in ("categoria", "nota", "editado_en", "estado"):
        diferencias[col] = diferencias[col].astype(object)

    diferencias.loc[indice, ["categoria", "cantidad_vendida", "precio_lista", "monto_informado"]] = [
        categoria,
        cantidad,
        precio,
        monto,
    ]
    diferencias.loc[indice, ["monto_esperado", "diferencia", "estado", "nota", "editado_en"]] = [
        r.monto_esperado,
        r.diferencia,
        r.estado.value,
        nota,
        ahora(),
    ]
