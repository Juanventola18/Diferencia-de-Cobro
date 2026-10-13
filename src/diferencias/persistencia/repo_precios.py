from __future__ import annotations

from datetime import date

import pandas as pd

from diferencias.persistencia.base_de_datos import BaseDeDatos


class RepoPrecios:
    """Última lista de precios cargada por cada empresa."""

    def __init__(self, base: BaseDeDatos):
        self._base = base

    def reemplazar(self, empresa: str, precios: pd.DataFrame) -> None:
        hoy = date.today().isoformat()
        filas = [
            (empresa, p, float(precio), hoy) for p, precio in zip(precios["producto"], precios["precio"], strict=True)
        ]
        with self._base.conectar() as conn:
            conn.execute("DELETE FROM precios WHERE empresa = ?", (empresa,))
            conn.executemany(
                "INSERT INTO precios (empresa, producto, precio, actualizado_en) VALUES (?, ?, ?, ?)", filas
            )

    def cargar(self, empresa: str) -> pd.DataFrame:
        with self._base.conectar() as conn:
            return pd.read_sql_query(
                "SELECT producto, precio FROM precios WHERE empresa = ? ORDER BY producto", conn, params=(empresa,)
            )

    def fecha_actualizacion(self, empresa: str) -> str | None:
        with self._base.conectar() as conn:
            return conn.execute("SELECT MAX(actualizado_en) FROM precios WHERE empresa = ?", (empresa,)).fetchone()[0]
