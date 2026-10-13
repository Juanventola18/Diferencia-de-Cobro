import pandas as pd
import pytest

from diferencias.persistencia.repositorios import Repositorios

EMPRESA = "EMPRESA_A"
OTRA_EMPRESA = "EMPRESA_B"
FECHA = "2026-09-01"

PRECIOS = pd.DataFrame(
    {
        "producto": ["Pavlova", "Fernet", "Vino", "ZVODKA"],
        "precio": [17500, 10000, 40000, 9_999_999],
    }
)


def ventas(filas, fecha=FECHA) -> pd.DataFrame:
    """Arma un reporte de ventas a partir de tuplas (categoria, producto, cantidad, monto)."""
    return pd.DataFrame(
        [
            {"fecha": fecha, "categoria": c, "producto": p, "cantidad_vendida": q, "monto_informado": m}
            for c, p, q, m in filas
        ]
    )


def ventas_excel(filas, fecha=FECHA) -> pd.DataFrame:
    """Lo mismo pero con los encabezados del Excel real."""
    return ventas(filas, fecha).rename(
        columns={
            "fecha": "Fecha",
            "categoria": "Categoría",
            "producto": "Producto",
            "cantidad_vendida": "Cantidades vendidas",
            "monto_informado": "Monto total",
        }
    )


@pytest.fixture
def repos(tmp_path) -> Repositorios:
    r = Repositorios.sobre(tmp_path / "test.db")
    r.base.inicializar([EMPRESA, OTRA_EMPRESA])
    return r
