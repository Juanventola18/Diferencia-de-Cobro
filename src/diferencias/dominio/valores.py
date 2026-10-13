"""Conversión de valores que escribe el usuario o que vienen de pandas."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

import pandas as pd

FORMATO_MARCA_TIEMPO = "%Y-%m-%d %H:%M:%S"


def es_vacio(valor) -> bool:
    """True para None y para los distintos "vacíos" de pandas (NaN, NA, NaT)."""
    if valor is None:
        return True
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


def ahora() -> str:
    return datetime.now().strftime(FORMATO_MARCA_TIEMPO)


def parsear_numero(texto) -> float | None:
    """Acepta formato argentino ('1.500', '1.500,50', '$ 2.000') y con
    punto decimal ('1500.5'). Vacío -> None. Si no es un número, ValueError."""
    if texto is None:
        return None
    s = str(texto).strip().replace("$", "").replace(" ", "")
    if s == "":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    return float(s)


def parsear_fecha_usuario(texto: str) -> str | None:
    """Fecha escrita a mano (DD/MM/AAAA y variantes) a ISO. None si no se entiende."""
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto.strip(), formato).date().isoformat()
        except ValueError:
            continue
    return None


def normalizar_texto(texto) -> str:
    """Minúsculas y sin tildes, para que 'chipa' encuentre 'CHIPÁ'."""
    if es_vacio(texto):
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower().strip()


def coincide_busqueda(df: pd.DataFrame, texto: str, columnas: list[str]) -> pd.Series:
    """Filas donde todas las palabras buscadas aparecen en alguna de las columnas."""
    palabras = normalizar_texto(texto).split()
    if df.empty or not palabras:
        return pd.Series(True, index=df.index)
    columnas = [c for c in columnas if c in df.columns]
    texto_fila = df[columnas].fillna("").astype(str).agg(" ".join, axis=1).map(normalizar_texto)
    mascara = pd.Series(True, index=df.index)
    for palabra in palabras:
        mascara &= texto_fila.str.contains(palabra, regex=False)
    return mascara
