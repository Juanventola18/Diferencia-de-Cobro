"""Punto de entrada: python main.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from diferencias.config import RUTA_BASE_DE_DATOS  # noqa: E402
from diferencias.persistencia.repositorios import Repositorios  # noqa: E402
from diferencias.ui.app import App  # noqa: E402


def main():
    repos = Repositorios.sobre(RUTA_BASE_DE_DATOS)
    App(repos).mainloop()


if __name__ == "__main__":
    main()
