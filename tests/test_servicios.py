import pandas as pd
import pytest

from conftest import EMPRESA, FECHA, PRECIOS, ventas, ventas_excel
from diferencias.dominio.estado import Estado
from diferencias.dominio.reglas import calcular_diferencias
from diferencias.entrada.lector_excel import leer_reporte_ventas
from diferencias.servicios.estadisticas import ranking_mas_regalados, resumen_por_producto
from diferencias.servicios.registro_dia import (
    cantidad_sin_fecha,
    completar_fechas,
    corregir_fila,
    separar_por_fecha,
)


def test_estadisticas_suman_solo_negativas(repos):
    dif = calcular_diferencias(ventas([("P", "Pavlova", 1, 0), ("V", "Vino", 1, 1_000_000)]), PRECIOS)
    repos.diferencias.guardar_dia(EMPRESA, FECHA, dif)
    historial = repos.diferencias.cargar_historial(EMPRESA)

    por_producto = resumen_por_producto(historial).set_index("producto")
    assert por_producto["perdida_acumulada"].sum() == -17500
    assert por_producto.loc["Vino", "cobrado_de_mas"] == 1_000_000 - 40000
    assert ranking_mas_regalados(historial)["producto"].tolist() == ["Pavlova"]


def test_completar_fechas_solo_toca_las_vacias():
    df = pd.concat([ventas([("B", "Fernet", 1, 0)], fecha=None), ventas([("B", "Vino", 1, 0)], "2026-09-02")])
    dif = calcular_diferencias(df, PRECIOS)
    assert cantidad_sin_fecha(dif) == 1
    completado = completar_fechas(dif, FECHA)
    assert completado["fecha"].tolist() == [FECHA, "2026-09-02"]
    assert cantidad_sin_fecha(dif) == 1  # no modifica el original


def test_completar_fechas_que_genera_repetidos_da_error():
    df = pd.concat([ventas([("B", "Fernet", 1, 0)], fecha=None), ventas([("B", "Fernet", 1, 0)], FECHA)])
    with pytest.raises(ValueError):
        completar_fechas(calcular_diferencias(df, PRECIOS), FECHA)


def test_separar_por_fecha():
    df = pd.concat([ventas([("B", "Fernet", 1, 0)], "2026-09-02"), ventas([("B", "Vino", 1, 0)], FECHA)])
    grupos = separar_por_fecha(calcular_diferencias(df, PRECIOS))
    assert list(grupos) == [FECHA, "2026-09-02"]


def test_corregir_fila_en_memoria_recalcula():
    dif = calcular_diferencias(ventas([("P", "Pavlova", 2, 17500)]), PRECIOS)
    corregir_fila(dif, 0, "POSTRES", 2, 17500, 35000, "Estaba bien")
    fila = dif.loc[0]
    assert fila["estado"] == Estado.SIN_DIFERENCIA and fila["diferencia"] == 0
    assert fila["nota"] == "Estaba bien" and fila["editado_en"]


def test_guardar_dia_completo_de_punta_a_punta(repos, tmp_path):
    """Excel -> cálculo -> base, con un producto repetido en dos categorías."""
    ruta = tmp_path / "v.xlsx"
    ventas_excel([("BAR", "Fernet", 3, 0), ("PROMO", "Fernet", 2, 20000)]).to_excel(
        ruta, sheet_name="Detalle", index=False
    )
    leidas, fecha = leer_reporte_ventas(str(ruta))
    dif = calcular_diferencias(leidas, PRECIOS)
    for f, grupo in separar_por_fecha(dif).items():
        repos.diferencias.guardar_dia(EMPRESA, f, grupo)
    assert repos.diferencias.cargar_dia(EMPRESA, fecha)["diferencia"].sum() == -30000
