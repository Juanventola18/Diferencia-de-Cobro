import zipfile

import pandas as pd
import pytest

from conftest import ventas_excel
from diferencias.entrada.lector_excel import FormatoExcelError, leer_lista_precios, leer_reporte_ventas


def _guardar_reporte(df, ruta):
    df.to_excel(ruta, sheet_name="Detalle", index=False)
    return str(ruta)


def test_producto_repetido_en_el_reporte_se_suma(tmp_path):
    ruta = _guardar_reporte(ventas_excel([("BAR", "Fernet", 3, 0), ("PROMO", "Fernet", 2, 20000)]), tmp_path / "v.xlsx")
    ventas, _ = leer_reporte_ventas(ruta)
    assert len(ventas) == 1
    assert ventas.loc[0, "cantidad_vendida"] == 5
    assert ventas.loc[0, "categoria"] == "BAR / PROMO"


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("01/09/2026", "2026-09-01"),
        ("13/09/2026", "2026-09-13"),
        ("2026-09-01", "2026-09-01"),
    ],
)
def test_fechas_en_formato_argentino(tmp_path, texto, esperado):
    ruta = _guardar_reporte(ventas_excel([("BAR", "Fernet", 1, 10000)], fecha=texto), tmp_path / "v.xlsx")
    assert leer_reporte_ventas(ruta)[1] == esperado


def test_reporte_con_varias_fechas_no_detecta_una_sola(tmp_path):
    df = pd.concat(
        [ventas_excel([("B", "Fernet", 1, 0)], "2026-09-01"), ventas_excel([("B", "Fernet", 1, 0)], "2026-09-02")]
    )
    ventas, fecha = leer_reporte_ventas(_guardar_reporte(df, tmp_path / "v.xlsx"))
    assert fecha is None
    assert sorted(ventas["fecha"].unique()) == ["2026-09-01", "2026-09-02"]


def test_filas_separadoras_se_descartan_aunque_tengan_cantidad(tmp_path):
    df = ventas_excel([("SALADOS", "--------------------", 81, 0), ("BAR", "Fernet", 1, 10000)])
    ventas, _ = leer_reporte_ventas(_guardar_reporte(df, tmp_path / "v.xlsx"))
    assert ventas["producto"].tolist() == ["Fernet"]


def test_precio_vacio_no_se_convierte_en_cero(tmp_path):
    ruta = tmp_path / "p.xlsx"
    pd.DataFrame({"Nombre": ["Vino X", None, "Agua"], "Precio": [None, 5, 2000]}).to_excel(
        ruta, sheet_name="Productos", index=False
    )
    precios, _ = leer_lista_precios(str(ruta))
    assert precios.to_dict("records") == [{"producto": "Agua", "precio": 2000}]


def test_precios_duplicados_se_queda_con_el_ultimo(tmp_path):
    ruta = tmp_path / "p.xlsx"
    pd.DataFrame({"Nombre": ["Agua", "Agua"], "Precio": [1000, 1500]}).to_excel(
        ruta, sheet_name="Productos", index=False
    )
    precios, duplicados = leer_lista_precios(str(ruta))
    assert duplicados == ["Agua"]
    assert precios.to_dict("records") == [{"producto": "Agua", "precio": 1500}]


def test_lee_el_excel_que_viene_dentro_de_un_zip(tmp_path):
    excel = _guardar_reporte(ventas_excel([("BAR", "Fernet", 1, 10000)]), tmp_path / "Reporte.xlsx")
    ruta_zip = tmp_path / "reporte.zip"
    with zipfile.ZipFile(ruta_zip, "w") as zf:
        zf.write(excel, "Reporte.xlsx")
    ventas, fecha = leer_reporte_ventas(str(ruta_zip))
    assert ventas["producto"].tolist() == ["Fernet"] and fecha == "2026-09-01"


def test_zip_sin_excel_da_error_claro(tmp_path):
    ruta_zip = tmp_path / "vacio.zip"
    with zipfile.ZipFile(ruta_zip, "w") as zf:
        zf.writestr("leeme.txt", "nada")
    with pytest.raises(FormatoExcelError, match="no tiene ningún Excel"):
        leer_reporte_ventas(str(ruta_zip))


def test_faltan_columnas_da_error_claro(tmp_path):
    ruta = tmp_path / "v.xlsx"
    pd.DataFrame({"Producto": ["Fernet"]}).to_excel(ruta, sheet_name="Detalle", index=False)
    with pytest.raises(FormatoExcelError, match="le faltan las columnas"):
        leer_reporte_ventas(str(ruta))
