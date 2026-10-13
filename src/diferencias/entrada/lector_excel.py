"""Lectura de los dos Excel que exporta el sistema de ventas.

- Lista de precios: hoja "Productos" con columnas Nombre y Precio.
- Reporte de ventas: hoja "Detalle" con Fecha, Categoría, Producto,
  Cantidades vendidas y Monto total.

Los dos pueden venir como .xlsx, .xls o dentro de un .zip. Las columnas se
renombran a los nombres internos apenas se leen, así el resto del programa
no depende de cómo se llaman en el Excel.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd


class FormatoExcelError(Exception):
    """El archivo no tiene el formato esperado. El mensaje se muestra tal cual al usuario."""


COLUMNAS_PRECIOS = {"Nombre": "producto", "Precio": "precio"}
COLUMNAS_VENTAS = {
    "Fecha": "fecha",
    "Categoría": "categoria",
    "Producto": "producto",
    "Cantidades vendidas": "cantidad_vendida",
    "Monto total": "monto_informado",
}
EXTENSIONES_EXCEL = (".xlsx", ".xlsm", ".xls")


# ---------------------------------------------------------------------------
# Apertura del archivo (xlsx, xls o zip)
# ---------------------------------------------------------------------------


def _motor_para(nombre: str) -> str:
    # openpyxl no lee el formato viejo .xls; para ese hace falta xlrd.
    return "xlrd" if nombre.lower().endswith(".xls") else "openpyxl"


def _abrir_excel(ruta: str) -> pd.ExcelFile:
    nombre = Path(ruta).name
    try:
        if nombre.lower().endswith(".zip"):
            contenido, nombre_interno = _leer_excel_de_zip(ruta)
            return pd.ExcelFile(io.BytesIO(contenido), engine=_motor_para(nombre_interno))
        return pd.ExcelFile(ruta, engine=_motor_para(nombre))
    except ImportError as exc:
        raise FormatoExcelError(
            "Falta la librería 'xlrd' para leer archivos .xls. Instalala con: pip install xlrd"
        ) from exc
    except FormatoExcelError:
        raise
    except Exception as exc:  # pandas levanta errores muy variados según el archivo
        raise FormatoExcelError(f"No pude abrir '{nombre}': {exc}") from exc


def _leer_excel_de_zip(ruta: str) -> tuple[bytes, str]:
    """Devuelve el contenido y el nombre del primer Excel que haya dentro del zip."""
    nombre = Path(ruta).name
    try:
        with zipfile.ZipFile(ruta) as zf:
            candidatos = [
                n for n in zf.namelist() if n.lower().endswith(EXTENSIONES_EXCEL) and not n.startswith("__MACOSX")
            ]
            if not candidatos:
                raise FormatoExcelError(f"El archivo '{nombre}' es un .zip pero no tiene ningún Excel adentro.")
            return zf.read(candidatos[0]), candidatos[0]
    except zipfile.BadZipFile as exc:
        raise FormatoExcelError(f"El archivo '{nombre}' está dañado o no es un .zip válido.") from exc


def _leer_hoja(ruta: str, hoja_preferida: str, columnas: dict[str, str]) -> pd.DataFrame:
    """Lee la hoja (o la primera si no existe), valida columnas y las renombra."""
    excel = _abrir_excel(ruta)
    hoja = hoja_preferida if hoja_preferida in excel.sheet_names else excel.sheet_names[0]
    df = pd.read_excel(excel, sheet_name=hoja)

    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        raise FormatoExcelError(
            f"Al archivo '{Path(ruta).name}' le faltan las columnas: {', '.join(faltantes)}.\n"
            f"Columnas encontradas: {', '.join(df.columns.astype(str))}"
        )
    return df[list(columnas)].rename(columns=columnas).copy()


# ---------------------------------------------------------------------------
# Lista de precios
# ---------------------------------------------------------------------------


def leer_lista_precios(ruta: str) -> tuple[pd.DataFrame, list[str]]:
    """Devuelve (precios, productos duplicados).

    Los productos sin precio numérico se descartan en vez de tomarse como 0:
    con precio 0 parecerían "cobrados de más" y al venderse no quedarían
    marcados como SIN_PRECIO.
    """
    df = _leer_hoja(ruta, "Productos", COLUMNAS_PRECIOS)
    df = df[df["producto"].notna()].copy()
    df["producto"] = df["producto"].astype(str).str.strip()
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df = df[(df["producto"] != "") & df["precio"].notna()]

    duplicados = df.loc[df["producto"].duplicated(), "producto"].unique().tolist()
    df = df.drop_duplicates(subset="producto", keep="last")
    return df.reset_index(drop=True), duplicados


# ---------------------------------------------------------------------------
# Reporte de ventas
# ---------------------------------------------------------------------------


def _parsear_fecha(valor) -> pd.Timestamp:
    """Las fechas en texto se leen como día/mes/año ('01/09/2026' = 1 de septiembre),
    salvo las ISO ('2026-09-01'), que empiezan por el año."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return pd.NaT
    if isinstance(valor, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(valor)
    texto = str(valor).strip()
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}", texto):
        return pd.to_datetime(texto, errors="coerce", yearfirst=True, dayfirst=False)
    return pd.to_datetime(texto, errors="coerce", dayfirst=True)


def _es_fila_de_relleno(df: pd.DataFrame) -> pd.Series:
    """Filas vacías o separadoras ('-------') que el reporte trae entre categorías."""
    sin_movimiento = (df["cantidad_vendida"] == 0) & (df["monto_informado"] == 0)
    sin_nombre = df["producto"].isin(["", "nan", "None"])
    separador = df["producto"].str.fullmatch(r"[-_=\s.]+")
    return sin_movimiento | sin_nombre | separador


def leer_reporte_ventas(ruta: str) -> tuple[pd.DataFrame, str | None]:
    """Devuelve (ventas, fecha).

    `fecha` es la fecha ISO del reporte si todas las filas tienen la misma,
    o None si hay varias fechas o alguna fila sin fecha legible.
    Un producto que aparece en varias filas del mismo día (por ejemplo en dos
    categorías) se suma en una sola, porque se guarda una fila por producto y día.
    """
    df = _leer_hoja(ruta, "Detalle", COLUMNAS_VENTAS)
    df["producto"] = df["producto"].astype(str).str.strip()
    df["cantidad_vendida"] = pd.to_numeric(df["cantidad_vendida"], errors="coerce").fillna(0)
    df["monto_informado"] = pd.to_numeric(df["monto_informado"], errors="coerce").fillna(0)
    df = df[~_es_fila_de_relleno(df)].copy()

    if pd.api.types.is_datetime64_any_dtype(df["fecha"]):
        fechas = df["fecha"]
    else:
        fechas = pd.to_datetime(df["fecha"].map(_parsear_fecha), errors="coerce")
    df["fecha"] = fechas.dt.strftime("%Y-%m-%d").where(fechas.notna(), None)

    ventas = (
        df.assign(_clave_fecha=df["fecha"].fillna(""))
        .groupby(["_clave_fecha", "producto"], sort=False)
        .agg(
            fecha=("fecha", "first"),
            categoria=("categoria", lambda s: " / ".join(dict.fromkeys(s.dropna().astype(str)))),
            cantidad_vendida=("cantidad_vendida", "sum"),
            monto_informado=("monto_informado", "sum"),
        )
        .reset_index()
        .drop(columns="_clave_fecha")
    )

    fechas_distintas = ventas["fecha"].dropna().unique()
    fecha = None
    if len(fechas_distintas) == 1 and ventas["fecha"].notna().all():
        fecha = str(fechas_distintas[0])
    return ventas, fecha
