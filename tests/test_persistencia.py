import sqlite3

import pytest

from conftest import EMPRESA, FECHA, OTRA_EMPRESA, PRECIOS, ventas
from diferencias.dominio.estado import Estado
from diferencias.dominio.reglas import calcular_diferencias, perdida_total
from diferencias.persistencia.base_de_datos import VERSION_ESQUEMA
from diferencias.persistencia.errores import ConflictoError, NoEncontradoError
from diferencias.persistencia.repo_papelera import TipoLote
from diferencias.persistencia.repositorios import Repositorios


def _guardar_basico(repos):
    dif = calcular_diferencias(ventas([("P", "Pavlova", 2, 17500), ("B", "Fernet", 1, 10000)]), PRECIOS)
    repos.diferencias.guardar_dia(EMPRESA, FECHA, dif)
    return repos.diferencias.cargar_dia(EMPRESA, FECHA).set_index("producto")


# ---------------------------------------------------------------------------
# Empresas y precios
# ---------------------------------------------------------------------------


def test_agregar_empresa_normaliza_el_nombre(repos):
    assert repos.empresas.agregar("  nueva ") == "NUEVA"
    assert "NUEVA" in repos.empresas.listar()


def test_reemplazar_lista_de_precios(repos):
    repos.precios.reemplazar(EMPRESA, PRECIOS)
    repos.precios.reemplazar(EMPRESA, PRECIOS.head(1))
    assert repos.precios.cargar(EMPRESA)["producto"].tolist() == ["Pavlova"]
    assert repos.precios.cargar(OTRA_EMPRESA).empty


# ---------------------------------------------------------------------------
# Diferencias
# ---------------------------------------------------------------------------


def test_lo_guardado_coincide_con_lo_calculado(repos):
    dif = calcular_diferencias(ventas([("P", "Pavlova", 1, 0), ("V", "Vino", 1, 50000)]), PRECIOS)
    repos.diferencias.guardar_dia(EMPRESA, FECHA, dif)
    assert perdida_total(repos.diferencias.cargar_dia(EMPRESA, FECHA)) == perdida_total(dif) == -17500


def test_editar_fila_recalcula_y_marca_la_edicion(repos):
    dia = _guardar_basico(repos)
    repos.diferencias.actualizar_fila(int(dia.loc["Pavlova", "id"]), "POSTRES", 2, 17500, 35000, "Se cobró bien")
    fila = repos.diferencias.cargar_dia(EMPRESA, FECHA).set_index("producto").loc["Pavlova"]
    assert fila["estado"] == Estado.SIN_DIFERENCIA and fila["diferencia"] == 0
    assert fila["nota"] == "Se cobró bien" and fila["editado_en"]


def test_agregar_fila_duplicada_da_error_claro(repos):
    _guardar_basico(repos)
    with pytest.raises(ConflictoError):
        repos.diferencias.agregar_fila(EMPRESA, FECHA, "Fernet", "B", 1, 10000, 0, None)


def test_editar_fila_borrada_da_error_claro(repos):
    fila_id = int(_guardar_basico(repos).loc["Fernet", "id"])
    repos.papelera.enviar_filas(EMPRESA, [fila_id])
    with pytest.raises(NoEncontradoError):
        repos.diferencias.actualizar_fila(fila_id, "B", 1, 10000, 0, None)


# ---------------------------------------------------------------------------
# Papelera
# ---------------------------------------------------------------------------


def test_papelera_dia_completo_y_restaurar(repos):
    _guardar_basico(repos)
    repos.papelera.enviar_dia(EMPRESA, FECHA)
    assert repos.diferencias.cargar_dia(EMPRESA, FECHA).empty

    lotes = repos.papelera.listar(EMPRESA)
    assert len(lotes) == 1 and lotes.loc[0, "filas"] == 2 and lotes.loc[0, "perdida"] == -17500

    repos.papelera.restaurar(int(lotes.loc[0, "id"]))
    assert len(repos.diferencias.cargar_dia(EMPRESA, FECHA)) == 2
    assert repos.papelera.listar(EMPRESA).empty


def test_reemplazar_dia_manda_la_version_vieja_a_la_papelera(repos):
    _guardar_basico(repos)
    nuevo = calcular_diferencias(ventas([("P", "Pavlova", 1, 17500)]), PRECIOS)
    repos.diferencias.guardar_dia(EMPRESA, FECHA, nuevo, reemplazar=True)
    lotes = repos.papelera.listar(EMPRESA)
    assert lotes.loc[0, "tipo"] == TipoLote.REEMPLAZO and lotes.loc[0, "filas"] == 2
    assert len(repos.diferencias.cargar_dia(EMPRESA, FECHA)) == 1


def test_restaurar_con_conflicto_no_toca_nada_sin_permiso(repos):
    _guardar_basico(repos)
    repos.papelera.enviar_dia(EMPRESA, FECHA)
    repos.diferencias.guardar_dia(EMPRESA, FECHA, calcular_diferencias(ventas([("P", "Pavlova", 1, 0)]), PRECIOS))
    lote = int(repos.papelera.listar(EMPRESA).loc[0, "id"])

    assert repos.papelera.conflictos(lote) == ["Pavlova"]
    with pytest.raises(ConflictoError):
        repos.papelera.restaurar(lote)
    assert len(repos.diferencias.cargar_dia(EMPRESA, FECHA)) == 1

    repos.papelera.restaurar(lote, reemplazar=True)
    dia = repos.diferencias.cargar_dia(EMPRESA, FECHA).set_index("producto")
    assert len(dia) == 2 and dia.loc["Pavlova", "cantidad_vendida"] == 2
    assert len(repos.papelera.listar(EMPRESA)) == 1  # la versión desplazada quedó en la papelera


def test_papelera_separada_por_empresa_y_vaciar(repos):
    _guardar_basico(repos)
    repos.papelera.enviar_dia(EMPRESA, FECHA)
    assert repos.papelera.listar(OTRA_EMPRESA).empty
    assert repos.papelera.vaciar(OTRA_EMPRESA) == 0
    assert repos.papelera.vaciar(EMPRESA) == 1
    with repos.base.conectar() as conn:
        assert conn.execute("SELECT COUNT(*) FROM papelera_filas").fetchone()[0] == 0


def test_un_error_a_mitad_de_camino_no_deja_cambios_a_medias(repos):
    _guardar_basico(repos)
    with pytest.raises(RuntimeError):
        with repos.base.conectar() as conn:
            conn.execute("DELETE FROM diferencias")
            raise RuntimeError("falla simulada")
    assert len(repos.diferencias.cargar_dia(EMPRESA, FECHA)) == 2


# ---------------------------------------------------------------------------
# Migraciones
# ---------------------------------------------------------------------------


def _crear_base_v0(ruta):
    conn = sqlite3.connect(ruta)
    conn.executescript("""
        CREATE TABLE diferencias (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT NOT NULL,
          fecha TEXT NOT NULL, producto TEXT NOT NULL, categoria TEXT, cantidad_vendida REAL,
          precio_lista REAL, ganancia_esperada REAL, monto_informado REAL, diferencia REAL,
          estado TEXT, UNIQUE(empresa, fecha, producto));
        INSERT INTO diferencias VALUES (NULL,'EMPRESA_B','2026-09-19','ZVODKA','BAR',1,9999999,9999999,50000,-9949999,'CON_DIFERENCIA');
        INSERT INTO diferencias VALUES (NULL,'EMPRESA_B','2026-09-19','Pavlova','P',1,17500,17500,0,-17500,'CON_DIFERENCIA');
    """)
    conn.commit()
    conn.close()


def test_migracion_base_vieja_hace_backup_y_corrige_comodines(tmp_path):
    ruta = tmp_path / "vieja.db"
    _crear_base_v0(ruta)
    repos = Repositorios.sobre(ruta)

    backup = repos.base.inicializar()
    assert backup is not None and backup.exists()
    historial = repos.diferencias.cargar_historial("EMPRESA_B")
    assert perdida_total(historial) == -17500
    assert "monto_esperado" in historial.columns and "ganancia_esperada" not in historial.columns

    assert repos.base.inicializar() is None  # la segunda vez no migra ni hace backup
    with repos.base.conectar() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == VERSION_ESQUEMA


def test_importar_base_de_otra_carpeta(tmp_path, repos):
    vieja = tmp_path / "vieja.db"
    _crear_base_v0(vieja)
    repos.diferencias.guardar_dia(EMPRESA, FECHA, calcular_diferencias(ventas([("P", "Pavlova", 1, 0)]), PRECIOS))

    repos.base.importar_desde(str(vieja))
    assert repos.diferencias.cargar_historial(EMPRESA).empty
    assert len(repos.diferencias.cargar_historial("EMPRESA_B")) == 2
    assert list(tmp_path.glob("test_backup_*.db"))  # la base que había antes quedó copiada


def test_importar_un_archivo_que_no_es_base(tmp_path, repos):
    falso = tmp_path / "falso.db"
    falso.write_text("esto no es sqlite")
    with pytest.raises(ValueError):
        repos.base.importar_desde(str(falso))
