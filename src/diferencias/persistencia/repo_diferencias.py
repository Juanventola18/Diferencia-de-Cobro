"""Historial de diferencias diarias: una fila por empresa, fecha y producto."""

from __future__ import annotations

import sqlite3

import pandas as pd

from diferencias.dominio.reglas import COLUMNAS_DIFERENCIAS, calcular_fila
from diferencias.dominio.valores import ahora
from diferencias.persistencia.base_de_datos import COLUMNAS_FILA, BaseDeDatos, a_sql, marcas
from diferencias.persistencia.errores import ConflictoError, NoEncontradoError
from diferencias.persistencia.repo_papelera import TipoLote, mover_a_papelera

_COLUMNAS = ", ".join(COLUMNAS_FILA)
_VALORES = marcas(len(COLUMNAS_FILA))
_INSERTAR = f"INSERT INTO diferencias ({_COLUMNAS}) VALUES ({_VALORES})"
# Si el producto ya estaba ese día (UNIQUE empresa+fecha+producto), lo pisa.
_INSERTAR_O_REEMPLAZAR = f"INSERT OR REPLACE INTO diferencias ({_COLUMNAS}) VALUES ({_VALORES})"


class RepoDiferencias:
    def __init__(self, base: BaseDeDatos):
        self._base = base

    def existe_dia(self, empresa: str, fecha: str) -> bool:
        with self._base.conectar() as conn:
            return (
                conn.execute(
                    "SELECT 1 FROM diferencias WHERE empresa = ? AND fecha = ? LIMIT 1", (empresa, fecha)
                ).fetchone()
                is not None
            )

    def guardar_dia(self, empresa: str, fecha: str, diferencias: pd.DataFrame, reemplazar: bool = False) -> None:
        """Guarda las filas de un día. Con `reemplazar`, la versión anterior va a la papelera."""
        filas = diferencias.reindex(columns=COLUMNAS_DIFERENCIAS).assign(fecha=fecha)
        valores = [(empresa, *(a_sql(v) for v in fila)) for fila in filas.itertuples(index=False)]

        with self._base.conectar() as conn:
            if reemplazar:
                ids = [
                    f[0]
                    for f in conn.execute(
                        "SELECT id FROM diferencias WHERE empresa = ? AND fecha = ?", (empresa, fecha)
                    )
                ]
                mover_a_papelera(
                    conn,
                    empresa,
                    fecha,
                    ids,
                    TipoLote.REEMPLAZO,
                    f"Versión anterior del día (reemplazada el {ahora()[:10]})",
                )
            conn.executemany(_INSERTAR_O_REEMPLAZAR, valores)

    def cargar_dia(self, empresa: str, fecha: str) -> pd.DataFrame:
        return self._consultar(
            "SELECT * FROM diferencias WHERE empresa = ? AND fecha = ? ORDER BY producto", (empresa, fecha)
        )

    def cargar_historial(self, empresa: str) -> pd.DataFrame:
        return self._consultar("SELECT * FROM diferencias WHERE empresa = ? ORDER BY fecha, producto", (empresa,))

    def historial_producto(self, empresa: str, producto: str) -> pd.DataFrame:
        return self._consultar(
            "SELECT * FROM diferencias WHERE empresa = ? AND producto = ? ORDER BY fecha DESC", (empresa, producto)
        )

    def _consultar(self, sql: str, params: tuple) -> pd.DataFrame:
        with self._base.conectar() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def actualizar_fila(self, fila_id: int, categoria, cantidad, precio_lista, monto_informado, nota) -> None:
        """Corrige una fila guardada. Monto esperado, diferencia y estado se recalculan siempre."""
        r = calcular_fila(cantidad, precio_lista, monto_informado)
        with self._base.conectar() as conn:
            cursor = conn.execute(
                """UPDATE diferencias SET categoria = ?, cantidad_vendida = ?, precio_lista = ?,
                   monto_informado = ?, monto_esperado = ?, diferencia = ?, estado = ?, nota = ?, editado_en = ?
                   WHERE id = ?""",
                (
                    categoria,
                    cantidad,
                    precio_lista,
                    monto_informado,
                    r.monto_esperado,
                    r.diferencia,
                    r.estado.value,
                    nota or None,
                    ahora(),
                    fila_id,
                ),
            )
            if cursor.rowcount == 0:
                raise NoEncontradoError("La fila ya no existe (¿la mandaron a la papelera desde otra ventana?).")

    def agregar_fila(
        self, empresa: str, fecha: str, producto: str, categoria, cantidad, precio_lista, monto_informado, nota
    ) -> None:
        producto = (producto or "").strip()
        if not producto:
            raise ValueError("El producto no puede quedar vacío.")
        r = calcular_fila(cantidad, precio_lista, monto_informado)
        valores = dict(
            fecha=fecha,
            categoria=categoria,
            producto=producto,
            cantidad_vendida=cantidad,
            precio_lista=precio_lista,
            monto_esperado=r.monto_esperado,
            monto_informado=monto_informado,
            diferencia=r.diferencia,
            estado=r.estado.value,
            nota=nota or None,
            editado_en=ahora(),
        )
        try:
            with self._base.conectar() as conn:
                conn.execute(_INSERTAR, (empresa, *(valores[c] for c in COLUMNAS_DIFERENCIAS)))
        except sqlite3.IntegrityError as exc:
            raise ConflictoError(
                f"'{producto}' ya existe en el {fecha}. Editá esa fila en vez de agregar otra."
            ) from exc
