"""Reglas de negocio: cruzar ventas con precios y calcular la pérdida.

Regla principal: la pérdida es la suma de las diferencias negativas
(productos regalados o cobrados por debajo de lista). Lo cobrado de más se
informa aparte y nunca se compensa con la pérdida.

Columnas esperadas:
  ventas:  fecha, categoria, producto, cantidad_vendida, monto_informado
  precios: producto, precio
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from diferencias.dominio.estado import Estado
from diferencias.dominio.valores import es_vacio

# El sistema de ventas (Fudo) usa precios como 9.999.999 para los productos
# de precio libre. Desde este valor el precio no se compara.
PRECIO_COMODIN_MINIMO = 9_999_999

COLUMNAS_DIFERENCIAS = [
    "fecha",
    "categoria",
    "producto",
    "cantidad_vendida",
    "precio_lista",
    "monto_esperado",
    "monto_informado",
    "diferencia",
    "estado",
    "nota",
    "editado_en",
]


@dataclass(frozen=True)
class ResultadoFila:
    monto_esperado: float | None
    diferencia: float | None
    estado: Estado


@dataclass(frozen=True)
class Totales:
    perdida: float
    cobrado_de_mas: float
    cantidad_con_perdida: int
    cantidad_cobrado_de_mas: int
    cantidad_sin_precio: int
    cantidad_precio_abierto: int


def es_precio_comodin(precio) -> bool:
    return not es_vacio(precio) and float(precio) >= PRECIO_COMODIN_MINIMO


def calcular_fila(cantidad, precio_lista, monto_informado) -> ResultadoFila:
    """Única fuente de verdad del cálculo: la usan el cálculo masivo y la edición manual."""
    if es_vacio(precio_lista):
        return ResultadoFila(None, None, Estado.SIN_PRECIO)
    if es_precio_comodin(precio_lista):
        return ResultadoFila(None, None, Estado.PRECIO_ABIERTO)

    cantidad = 0.0 if es_vacio(cantidad) else float(cantidad)
    monto = 0.0 if es_vacio(monto_informado) else float(monto_informado)
    esperado = round(cantidad * float(precio_lista), 2)
    diferencia = round(monto - esperado, 2)
    estado = Estado.CON_DIFERENCIA if diferencia != 0 else Estado.SIN_DIFERENCIA
    return ResultadoFila(esperado, diferencia, estado)


def validar_fila(producto: str, cantidad, precio, monto) -> None:
    """Valida una fila cargada o corregida a mano. Levanta ValueError con un mensaje para el usuario."""
    if not producto:
        raise ValueError("El producto no puede quedar vacío.")
    if cantidad is None:
        raise ValueError("Falta la cantidad vendida.")
    if monto is None:
        raise ValueError("Falta el monto informado (poné 0 si fue regalado).")
    if cantidad < 0 or monto < 0 or (precio is not None and precio < 0):
        raise ValueError("Cantidad, precio y monto no pueden ser negativos.")


def calcular_diferencias(ventas: pd.DataFrame, precios: pd.DataFrame) -> pd.DataFrame:
    cruce = ventas.merge(precios.rename(columns={"precio": "precio_lista"}), on="producto", how="left")

    resultados = [
        calcular_fila(c, p, m)
        for c, p, m in zip(cruce["cantidad_vendida"], cruce["precio_lista"], cruce["monto_informado"], strict=True)
    ]
    cruce["monto_esperado"] = pd.to_numeric(pd.Series([r.monto_esperado for r in resultados], dtype=object))
    cruce["diferencia"] = pd.to_numeric(pd.Series([r.diferencia for r in resultados], dtype=object))
    cruce["estado"] = [r.estado.value for r in resultados]
    cruce["nota"] = None
    cruce["editado_en"] = None
    return cruce.reindex(columns=COLUMNAS_DIFERENCIAS).reset_index(drop=True)


def mascara_perdida(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    return (df["estado"] == Estado.CON_DIFERENCIA.value) & (pd.to_numeric(df["diferencia"]) < 0)


def mascara_cobrado_de_mas(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    return (df["estado"] == Estado.CON_DIFERENCIA.value) & (pd.to_numeric(df["diferencia"]) > 0)


def perdida_total(df: pd.DataFrame) -> float:
    """Suma solo las diferencias negativas, así que nunca es positiva."""
    if df.empty:
        return 0.0
    return float(pd.to_numeric(df.loc[mascara_perdida(df), "diferencia"]).sum())


def cobrado_de_mas_total(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(pd.to_numeric(df.loc[mascara_cobrado_de_mas(df), "diferencia"]).sum())


def calcular_totales(df: pd.DataFrame) -> Totales:
    if df.empty:
        return Totales(0.0, 0.0, 0, 0, 0, 0)
    return Totales(
        perdida=perdida_total(df),
        cobrado_de_mas=cobrado_de_mas_total(df),
        cantidad_con_perdida=int(mascara_perdida(df).sum()),
        cantidad_cobrado_de_mas=int(mascara_cobrado_de_mas(df).sum()),
        cantidad_sin_precio=int((df["estado"] == Estado.SIN_PRECIO.value).sum()),
        cantidad_precio_abierto=int((df["estado"] == Estado.PRECIO_ABIERTO.value).sum()),
    )
