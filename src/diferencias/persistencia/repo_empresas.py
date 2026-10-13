from __future__ import annotations

from diferencias.persistencia.base_de_datos import BaseDeDatos


class RepoEmpresas:
    def __init__(self, base: BaseDeDatos):
        self._base = base

    def listar(self) -> list[str]:
        with self._base.conectar() as conn:
            return [fila[0] for fila in conn.execute("SELECT nombre FROM empresas ORDER BY nombre")]

    def agregar(self, nombre: str) -> str:
        """Guarda la empresa en mayúsculas y devuelve el nombre normalizado."""
        nombre = nombre.strip().upper()
        if not nombre:
            raise ValueError("El nombre de la empresa no puede quedar vacío.")
        with self._base.conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO empresas (nombre) VALUES (?)", (nombre,))
        return nombre
