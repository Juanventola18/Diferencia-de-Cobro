"""Papelera de reciclaje: lo que se borra o se reemplaza queda acá hasta vaciarla.

Cada operación de borrado genera un "lote" con las filas que se sacaron,
para poder restaurarlas juntas.
"""

from __future__ import annotations

import sqlite3
from enum import Enum

import pandas as pd

from diferencias.dominio.reglas import perdida_total
from diferencias.dominio.valores import ahora
from diferencias.persistencia.base_de_datos import COLUMNAS_FILA, BaseDeDatos, marcas
from diferencias.persistencia.errores import ConflictoError, NoEncontradoError


class TipoLote(str, Enum):
    DIA = "DIA"
    FILAS = "FILAS"
    REEMPLAZO = "REEMPLAZO"


def mover_a_papelera(
    conn: sqlite3.Connection, empresa: str, fecha: str, ids: list[int], tipo: TipoLote, descripcion: str
) -> int | None:
    """Pasa las filas `ids` de `diferencias` a un lote nuevo de la papelera.

    Trabaja sobre una conexión abierta para ser parte de la misma transacción
    que la operación que la llama. Devuelve el id del lote, o None si no había filas.
    """
    if not ids:
        return None
    lote_id = conn.execute(
        "INSERT INTO papelera_lotes (empresa, fecha, tipo, descripcion, eliminado_en) VALUES (?, ?, ?, ?, ?)",
        (empresa, fecha, tipo.value, descripcion, ahora()),
    ).lastrowid
    columnas = ", ".join(COLUMNAS_FILA)
    conn.execute(
        f"INSERT INTO papelera_filas (lote_id, {columnas}) "
        f"SELECT ?, {columnas} FROM diferencias WHERE id IN ({marcas(len(ids))})",
        (lote_id, *ids),
    )
    conn.execute(f"DELETE FROM diferencias WHERE id IN ({marcas(len(ids))})", ids)
    return lote_id


def _describir(productos: list[str], maximo: int = 3) -> str:
    texto = ", ".join(productos[:maximo])
    if len(productos) > maximo:
        texto += f" y {len(productos) - maximo} más"
    return texto


class RepoPapelera:
    def __init__(self, base: BaseDeDatos):
        self._base = base

    def enviar_dia(self, empresa: str, fecha: str) -> int | None:
        with self._base.conectar() as conn:
            ids = [
                f[0]
                for f in conn.execute("SELECT id FROM diferencias WHERE empresa = ? AND fecha = ?", (empresa, fecha))
            ]
            return mover_a_papelera(conn, empresa, fecha, ids, TipoLote.DIA, f"Día completo ({len(ids)} productos)")

    def enviar_filas(self, empresa: str, ids: list[int]) -> list[int]:
        """Manda filas sueltas a la papelera, un lote por cada fecha involucrada."""
        if not ids:
            return []
        with self._base.conectar() as conn:
            filas = conn.execute(
                f"SELECT id, fecha, producto FROM diferencias WHERE empresa = ? AND id IN ({marcas(len(ids))}) "
                "ORDER BY fecha, producto",
                (empresa, *ids),
            ).fetchall()
            por_fecha: dict[str, list[tuple[int, str]]] = {}
            for fila_id, fecha, producto in filas:
                por_fecha.setdefault(fecha, []).append((fila_id, producto))

            lotes = []
            for fecha, grupo in por_fecha.items():
                lote = mover_a_papelera(
                    conn, empresa, fecha, [i for i, _ in grupo], TipoLote.FILAS, _describir([p for _, p in grupo])
                )
                lotes.append(lote)
            return lotes

    def listar(self, empresa: str) -> pd.DataFrame:
        """Lotes de la empresa, del más reciente al más viejo, con su cantidad de filas y su pérdida."""
        with self._base.conectar() as conn:
            lotes = pd.read_sql_query(
                """SELECT l.id, l.fecha, l.tipo, l.descripcion, l.eliminado_en, COUNT(f.lote_id) AS filas
                   FROM papelera_lotes l LEFT JOIN papelera_filas f ON f.lote_id = l.id
                   WHERE l.empresa = ? GROUP BY l.id ORDER BY l.eliminado_en DESC, l.id DESC""",
                conn,
                params=(empresa,),
            )
            filas = pd.read_sql_query(
                "SELECT lote_id, diferencia, estado FROM papelera_filas WHERE empresa = ?", conn, params=(empresa,)
            )
        perdidas = {lote_id: perdida_total(grupo) for lote_id, grupo in filas.groupby("lote_id")}
        lotes["perdida"] = lotes["id"].map(perdidas).fillna(0.0) if not lotes.empty else pd.Series(dtype=float)
        return lotes

    def cargar_lote(self, lote_id: int) -> pd.DataFrame:
        with self._base.conectar() as conn:
            return pd.read_sql_query(
                "SELECT * FROM papelera_filas WHERE lote_id = ? ORDER BY producto", conn, params=(lote_id,)
            )

    def _ids_en_conflicto(self, conn: sqlite3.Connection, lote_id: int) -> list[tuple[int, str]]:
        """Filas activas con la misma empresa, fecha y producto que alguna del lote."""
        return conn.execute(
            """SELECT d.id, d.producto FROM papelera_filas f JOIN diferencias d
               ON d.empresa = f.empresa AND d.fecha = f.fecha AND d.producto = f.producto
               WHERE f.lote_id = ? ORDER BY d.producto""",
            (lote_id,),
        ).fetchall()

    def conflictos(self, lote_id: int) -> list[str]:
        with self._base.conectar() as conn:
            return [producto for _, producto in self._ids_en_conflicto(conn, lote_id)]

    def restaurar(self, lote_id: int, reemplazar: bool = False) -> None:
        """Devuelve el lote al historial.

        Si choca con filas activas: sin `reemplazar` levanta ConflictoError y no
        toca nada; con `reemplazar`, las filas activas que chocan van a la papelera.
        """
        with self._base.conectar() as conn:
            lote = conn.execute("SELECT empresa, fecha FROM papelera_lotes WHERE id = ?", (lote_id,)).fetchone()
            if lote is None:
                raise NoEncontradoError("Ese elemento ya no está en la papelera.")
            empresa, fecha = lote

            en_conflicto = [fila_id for fila_id, _ in self._ids_en_conflicto(conn, lote_id)]
            if en_conflicto and not reemplazar:
                raise ConflictoError(f"{len(en_conflicto)} productos del {fecha} ya existen en el historial.")
            mover_a_papelera(
                conn, empresa, fecha, en_conflicto, TipoLote.REEMPLAZO, "Reemplazado al restaurar desde la papelera"
            )

            columnas = ", ".join(COLUMNAS_FILA)
            conn.execute(
                f"INSERT INTO diferencias ({columnas}) SELECT {columnas} FROM papelera_filas WHERE lote_id = ?",
                (lote_id,),
            )
            conn.execute("DELETE FROM papelera_lotes WHERE id = ?", (lote_id,))

    def eliminar(self, lote_id: int) -> None:
        with self._base.conectar() as conn:
            conn.execute("DELETE FROM papelera_lotes WHERE id = ?", (lote_id,))

    def vaciar(self, empresa: str) -> int:
        """Borra definitivamente todos los lotes de la empresa. Devuelve cuántos había."""
        with self._base.conectar() as conn:
            return conn.execute("DELETE FROM papelera_lotes WHERE empresa = ?", (empresa,)).rowcount
