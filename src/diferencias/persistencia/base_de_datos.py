"""Conexión a SQLite, creación del esquema y migraciones.

La versión del esquema se guarda en `PRAGMA user_version`. Antes de migrar
una base que ya tiene datos se hace una copia de seguridad al lado.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from diferencias.dominio.estado import Estado
from diferencias.dominio.reglas import COLUMNAS_DIFERENCIAS, PRECIO_COMODIN_MINIMO
from diferencias.dominio.valores import es_vacio

VERSION_ESQUEMA = 2

# Columnas de una fila de diferencias, iguales en `diferencias` y `papelera_filas`.
COLUMNAS_FILA = ["empresa", *COLUMNAS_DIFERENCIAS]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS empresas (
    nombre TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS precios (
    empresa TEXT NOT NULL,
    producto TEXT NOT NULL,
    precio REAL,
    actualizado_en TEXT,
    PRIMARY KEY (empresa, producto)
);

CREATE TABLE IF NOT EXISTS diferencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa TEXT NOT NULL,
    fecha TEXT NOT NULL,
    producto TEXT NOT NULL,
    categoria TEXT,
    cantidad_vendida REAL,
    precio_lista REAL,
    monto_esperado REAL,
    monto_informado REAL,
    diferencia REAL,
    estado TEXT,
    nota TEXT,
    editado_en TEXT,
    UNIQUE (empresa, fecha, producto)
);
CREATE INDEX IF NOT EXISTS idx_diferencias_empresa_fecha ON diferencias (empresa, fecha);

CREATE TABLE IF NOT EXISTS papelera_lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa TEXT NOT NULL,
    fecha TEXT NOT NULL,
    tipo TEXT NOT NULL,
    descripcion TEXT,
    eliminado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papelera_filas (
    lote_id INTEGER NOT NULL REFERENCES papelera_lotes (id) ON DELETE CASCADE,
    empresa TEXT NOT NULL,
    fecha TEXT NOT NULL,
    producto TEXT NOT NULL,
    categoria TEXT,
    cantidad_vendida REAL,
    precio_lista REAL,
    monto_esperado REAL,
    monto_informado REAL,
    diferencia REAL,
    estado TEXT,
    nota TEXT,
    editado_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_papelera_filas_lote ON papelera_filas (lote_id);
"""


def a_sql(valor):
    """pandas marca los vacíos con NaN y usa tipos de numpy; SQLite espera None y tipos de Python."""
    if es_vacio(valor):
        return None
    return valor.item() if hasattr(valor, "item") else valor


def marcas(cantidad: int) -> str:
    """'?, ?, ?' para armar consultas parametrizadas con IN (...)."""
    return ", ".join("?" * cantidad)


def _columnas(conn: sqlite3.Connection, tabla: str) -> set[str]:
    return {fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")}


def _tablas(conn: sqlite3.Connection) -> set[str]:
    return {fila[0] for fila in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _migrar(conn: sqlite3.Connection, version: int) -> None:
    # v1: notas y marca de edición por fila.
    columnas = _columnas(conn, "diferencias")
    for columna in ("nota", "editado_en"):
        if columna not in columnas:
            conn.execute(f"ALTER TABLE diferencias ADD COLUMN {columna} TEXT")

    # v2: "ganancia_esperada" no era una ganancia sino lo que se debería haber cobrado.
    for tabla in ("diferencias", "papelera_filas"):
        if "ganancia_esperada" in _columnas(conn, tabla):
            conn.execute(f"ALTER TABLE {tabla} RENAME COLUMN ganancia_esperada TO monto_esperado")

    if version < 1:
        # Filas guardadas antes de reconocer los precios comodín: inflaban la pérdida.
        conn.execute(
            "UPDATE diferencias SET estado = ?, monto_esperado = NULL, diferencia = NULL "
            "WHERE precio_lista >= ? AND estado <> ?",
            (Estado.PRECIO_ABIERTO.value, PRECIO_COMODIN_MINIMO, Estado.PRECIO_ABIERTO.value),
        )


class BaseDeDatos:
    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)

    @contextmanager
    def conectar(self) -> Iterator[sqlite3.Connection]:
        """Cada bloque `with` es una transacción: se confirma entero o no se aplica nada."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.ruta)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def inicializar(self, empresas_iniciales: Iterable[str] = ()) -> Path | None:
        """Crea o actualiza el esquema. Devuelve la ruta del backup si hubo que migrar datos."""
        with self.conectar() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            hay_datos = (
                "diferencias" in _tablas(conn)
                and conn.execute("SELECT 1 FROM diferencias LIMIT 1").fetchone() is not None
            )

        backup = self._hacer_backup() if version < VERSION_ESQUEMA and hay_datos else None

        with self.conectar() as conn:
            conn.executescript(ESQUEMA)
            _migrar(conn, version)
            conn.executemany("INSERT OR IGNORE INTO empresas (nombre) VALUES (?)", [(e,) for e in empresas_iniciales])
            conn.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")
        return backup

    def _hacer_backup(self) -> Path | None:
        if not self.ruta.exists() or self.ruta.stat().st_size == 0:
            return None
        destino = self.ruta.with_name(f"{self.ruta.stem}_backup_{datetime.now():%Y%m%d_%H%M%S}.db")
        shutil.copy2(self.ruta, destino)
        return destino

    @staticmethod
    def tiene_datos(ruta: Path) -> bool:
        """True si el archivo es una base con al menos un día o una lista de precios guardada."""
        ruta = Path(ruta)
        if not ruta.exists():
            return False
        try:
            conn = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
            try:
                tablas = _tablas(conn)
                return any(
                    tabla in tablas and conn.execute(f"SELECT 1 FROM {tabla} LIMIT 1").fetchone()
                    for tabla in ("diferencias", "precios")
                )
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            return False

    def importar_desde(self, ruta_origen: str) -> Path | None:
        """Reemplaza esta base por otra (por ejemplo la de una instalación anterior).

        Si la actual tenía datos, primero se copia. Devuelve el backup de la
        migración si la base importada era de una versión vieja.
        """
        origen = Path(ruta_origen).resolve()
        if origen == self.ruta.resolve():
            raise ValueError("Ese archivo ya es la base que está usando la aplicación.")
        try:
            conn = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
            try:
                tablas = _tablas(conn)
            finally:
                conn.close()
        except sqlite3.DatabaseError as exc:
            raise ValueError("El archivo elegido no es una base de datos válida.") from exc
        if "diferencias" not in tablas:
            raise ValueError("El archivo elegido no es una base de esta aplicación (no tiene la tabla 'diferencias').")

        if self.tiene_datos(self.ruta):
            self._hacer_backup()
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, self.ruta)
        return self.inicializar()
