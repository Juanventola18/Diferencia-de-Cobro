from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from diferencias.persistencia.base_de_datos import BaseDeDatos
from diferencias.persistencia.repo_diferencias import RepoDiferencias
from diferencias.persistencia.repo_empresas import RepoEmpresas
from diferencias.persistencia.repo_papelera import RepoPapelera
from diferencias.persistencia.repo_precios import RepoPrecios


@dataclass(frozen=True)
class Repositorios:
    """Todos los repositorios apuntando a la misma base. Se arma una vez en
    main.py y se le pasa a la interfaz; los tests arman uno con una base temporal."""

    base: BaseDeDatos
    empresas: RepoEmpresas
    precios: RepoPrecios
    diferencias: RepoDiferencias
    papelera: RepoPapelera

    @classmethod
    def sobre(cls, ruta: Path) -> Repositorios:
        base = BaseDeDatos(ruta)
        return cls(base, RepoEmpresas(base), RepoPrecios(base), RepoDiferencias(base), RepoPapelera(base))
