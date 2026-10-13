class ConflictoError(Exception):
    """Ya existe una fila con la misma empresa, fecha y producto."""


class NoEncontradoError(LookupError):
    """La fila o el lote ya no existen (por ejemplo, se borraron desde otra ventana)."""
