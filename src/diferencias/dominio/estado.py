from __future__ import annotations

from enum import Enum

from diferencias.dominio.valores import es_vacio


class Estado(str, Enum):
    """Resultado de comparar una venta contra la lista de precios.

    Hereda de str para que se guarde en SQLite y se compare con pandas
    como texto común.
    """

    CON_DIFERENCIA = "CON_DIFERENCIA"
    SIN_DIFERENCIA = "SIN_DIFERENCIA"
    SIN_PRECIO = "SIN_PRECIO"
    PRECIO_ABIERTO = "PRECIO_ABIERTO"


class Clasificacion(Enum):
    """Cómo se cuenta y se muestra una fila. Separa CON_DIFERENCIA en
    pérdida y cobrado de más, que tienen reglas distintas."""

    PERDIDA = "Pérdida"
    COBRADO_DE_MAS = "Cobrado de más"
    OK = "OK"
    SIN_PRECIO = "Sin precio"
    PRECIO_ABIERTO = "Precio abierto"


def clasificar(estado: str, diferencia) -> Clasificacion:
    if estado == Estado.CON_DIFERENCIA and not es_vacio(diferencia):
        return Clasificacion.PERDIDA if float(diferencia) < 0 else Clasificacion.COBRADO_DE_MAS
    if estado == Estado.SIN_PRECIO:
        return Clasificacion.SIN_PRECIO
    if estado == Estado.PRECIO_ABIERTO:
        return Clasificacion.PRECIO_ABIERTO
    return Clasificacion.OK
