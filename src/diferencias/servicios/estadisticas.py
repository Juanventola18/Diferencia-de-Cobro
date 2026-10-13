"""Resúmenes del historial. Igual que en el resto del programa, la pérdida
suma solo diferencias negativas y lo cobrado de más va aparte."""

from __future__ import annotations

import pandas as pd

from diferencias.dominio.reglas import mascara_cobrado_de_mas, mascara_perdida

COLUMNAS_POR_PRODUCTO = [
    "producto",
    "veces_vendido",
    "veces_con_perdida",
    "cantidad_total_vendida",
    "monto_total_informado",
    "perdida_acumulada",
    "cobrado_de_mas",
]


def con_periodos(historial: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas anio y mes para agrupar el árbol Año > Mes > Día."""
    if historial.empty:
        return historial
    fechas = pd.to_datetime(historial["fecha"])
    return historial.assign(anio=fechas.dt.year, mes=fechas.dt.month)


def ranking_mas_regalados(diferencias: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    """Productos con más pérdida acumulada, del peor al mejor."""
    columnas = ["producto", "veces_con_perdida", "perdida_acumulada"]
    if diferencias.empty:
        return pd.DataFrame(columns=columnas)
    negativas = diferencias[mascara_perdida(diferencias)]
    if negativas.empty:
        return pd.DataFrame(columns=columnas)
    resumen = (
        negativas.groupby("producto")
        .agg(
            veces_con_perdida=("producto", "count"),
            perdida_acumulada=("diferencia", "sum"),
        )
        .reset_index()
    )
    return resumen.sort_values("perdida_acumulada").head(top).reset_index(drop=True)


def resumen_por_producto(historial: pd.DataFrame) -> pd.DataFrame:
    if historial.empty:
        return pd.DataFrame(columns=COLUMNAS_POR_PRODUCTO)

    es_perdida = mascara_perdida(historial)
    es_de_mas = mascara_cobrado_de_mas(historial)
    df = historial.assign(
        _perdida=historial["diferencia"].where(es_perdida, 0.0),
        _de_mas=historial["diferencia"].where(es_de_mas, 0.0),
        _es_perdida=es_perdida.astype(int),
    )
    resumen = (
        df.groupby("producto")
        .agg(
            veces_vendido=("producto", "count"),
            veces_con_perdida=("_es_perdida", "sum"),
            cantidad_total_vendida=("cantidad_vendida", "sum"),
            monto_total_informado=("monto_informado", "sum"),
            perdida_acumulada=("_perdida", "sum"),
            cobrado_de_mas=("_de_mas", "sum"),
        )
        .reset_index()
    )
    return resumen.sort_values(["perdida_acumulada", "producto"])[COLUMNAS_POR_PRODUCTO].reset_index(drop=True)
