import pytest

from conftest import PRECIOS, ventas
from diferencias.dominio.estado import Clasificacion, Estado, clasificar
from diferencias.dominio.reglas import calcular_diferencias, calcular_fila, calcular_totales, validar_fila
from diferencias.dominio.valores import normalizar_texto, parsear_fecha_usuario, parsear_numero


def test_solo_se_suman_las_diferencias_negativas():
    df = calcular_diferencias(
        ventas(
            [
                ("POSTRES", "Pavlova", 2, 17500),  # regaló 1 -> -17500
                ("BAR", "Fernet", 1, 0),  # regaló 1 -> -10000
                ("VINOS", "Vino", 2, 82800),  # cobrado de más -> +2800, no se suma
            ]
        ),
        PRECIOS,
    )
    t = calcular_totales(df)
    assert t.perdida == -27500
    assert t.cobrado_de_mas == 2800
    assert t.cantidad_con_perdida == 2
    assert t.cantidad_cobrado_de_mas == 1


def test_un_dia_solo_con_positivas_tiene_perdida_cero():
    t = calcular_totales(calcular_diferencias(ventas([("VINOS", "Vino", 1, 50000)]), PRECIOS))
    assert t.perdida == 0


def test_precio_comodin_no_genera_perdida_falsa():
    df = calcular_diferencias(ventas([("BAR", "ZVODKA", 1, 50000)]), PRECIOS)
    assert df.loc[0, "estado"] == Estado.PRECIO_ABIERTO
    assert calcular_totales(df).perdida == 0


def test_producto_sin_precio():
    df = calcular_diferencias(ventas([("X", "Inventado", 1, 100)]), PRECIOS)
    assert df.loc[0, "estado"] == Estado.SIN_PRECIO
    assert calcular_totales(df).perdida == 0


def test_calcular_fila_sin_diferencia():
    r = calcular_fila(3, 1000, 3000)
    assert (r.monto_esperado, r.diferencia, r.estado) == (3000, 0, Estado.SIN_DIFERENCIA)


@pytest.mark.parametrize(
    "estado,diferencia,esperado",
    [
        (Estado.CON_DIFERENCIA, -100, Clasificacion.PERDIDA),
        (Estado.CON_DIFERENCIA, 100, Clasificacion.COBRADO_DE_MAS),
        (Estado.SIN_DIFERENCIA, 0, Clasificacion.OK),
        (Estado.SIN_PRECIO, None, Clasificacion.SIN_PRECIO),
        (Estado.PRECIO_ABIERTO, None, Clasificacion.PRECIO_ABIERTO),
    ],
)
def test_clasificar(estado, diferencia, esperado):
    assert clasificar(estado.value, diferencia) == esperado


@pytest.mark.parametrize(
    "producto,cantidad,precio,monto",
    [
        ("", 1, 100, 100),
        ("Vino", None, 100, 100),
        ("Vino", 1, 100, None),
        ("Vino", -1, 100, 100),
        ("Vino", 1, -100, 100),
    ],
)
def test_validar_fila_rechaza_datos_invalidos(producto, cantidad, precio, monto):
    with pytest.raises(ValueError):
        validar_fila(producto, cantidad, precio, monto)


def test_validar_fila_acepta_precio_vacio():
    validar_fila("Vino", 1, None, 0)


@pytest.mark.parametrize(
    "texto,valor",
    [
        ("1.500", 1500),
        ("1.500,50", 1500.5),
        ("$ 2.000", 2000),
        ("1500.5", 1500.5),
        ("17500", 17500),
        ("", None),
        ("1.000.000", 1_000_000),
        ("0,5", 0.5),
    ],
)
def test_parsear_numero(texto, valor):
    assert parsear_numero(texto) == valor


def test_parsear_numero_invalido():
    with pytest.raises(ValueError):
        parsear_numero("abc")


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("01/09/2026", "2026-09-01"),
        ("2026-09-01", "2026-09-01"),
        ("1-9-2026", "2026-09-01"),
        ("ayer", None),
    ],
)
def test_parsear_fecha_usuario(texto, esperado):
    assert parsear_fecha_usuario(texto) == esperado


def test_normalizar_texto_ignora_tildes_y_mayusculas():
    assert normalizar_texto("  CHIPÁ ") == "chipa"
