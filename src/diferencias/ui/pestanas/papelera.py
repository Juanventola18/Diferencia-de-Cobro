"""Pestaña "Papelera": ver, restaurar o eliminar definitivamente lo borrado."""

from __future__ import annotations

from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk
import pandas as pd

from diferencias.persistencia.errores import ConflictoError, NoEncontradoError
from diferencias.persistencia.repo_papelera import TipoLote
from diferencias.ui import estilos, formato
from diferencias.ui.ventanas import VentanaLista
from diferencias.ui.widgets import PanelTotal, boton, crear_tabla, vaciar

if TYPE_CHECKING:
    from diferencias.ui.app import App

NOMBRE_TIPO = {
    TipoLote.DIA.value: "Día completo",
    TipoLote.FILAS.value: "Productos sueltos",
    TipoLote.REEMPLAZO.value: "Versión reemplazada",
}


class PestanaPapelera:
    def __init__(self, app: App, contenedor: ctk.CTkFrame):
        self.app = app
        self.lotes = pd.DataFrame()

        contenedor.configure(fg_color=estilos.FONDO)
        self.panel = PanelTotal(contenedor, "PAPELERA DE RECICLAJE")
        self.panel.mostrar(
            "Vacía",
            subtitulo="Todo lo que borres o reemplaces viene acá primero. Lo que está en la "
            "papelera no cuenta en las estadísticas hasta que lo restaures.",
        )
        self.panel.pack(fill="x", padx=4, pady=(14, 10))

        abajo = ctk.CTkFrame(contenedor, fg_color="transparent")
        abajo.pack(side="bottom", fill="x", padx=4, pady=(10, 4))
        boton(abajo, "Ver contenido", self.ver_lote).pack(side="left")
        boton(abajo, "↩ Restaurar", self.restaurar_lote, "primario").pack(side="left", padx=8)
        boton(abajo, "Eliminar para siempre", self.eliminar_lote, "peligro").pack(side="left")
        boton(abajo, "Vaciar papelera", self.vaciar_papelera, "peligro").pack(side="right")

        columnas = ["Eliminado el", "Fecha", "Tipo", "Detalle", "Productos", "Pérdida"]
        tarjeta, self.tabla = crear_tabla(
            contenedor, columnas, {"Detalle": 360, "Eliminado el": 160, "Tipo": 190}, height=16
        )
        tarjeta.pack(fill="both", expand=True, padx=4, pady=4)
        self.tabla.bind("<Double-1>", lambda _e: self.ver_lote())
        self.tabla.bind("<Delete>", lambda _e: self.eliminar_lote())

    def refrescar(self):
        empresa = self.app.empresa
        self.lotes = self.app.repos.papelera.listar(empresa) if empresa else pd.DataFrame()
        vaciar(self.tabla)
        for _, r in self.lotes.iterrows():
            self.tabla.insert(
                "",
                "end",
                iid=str(int(r["id"])),
                tags=(estilos.tag_por_signo(r["perdida"]),),
                values=(
                    formato.fecha_hora(r["eliminado_en"]),
                    formato.fecha(r["fecha"]),
                    NOMBRE_TIPO.get(r["tipo"], r["tipo"]),
                    r["descripcion"],
                    int(r["filas"]),
                    formato.pesos(r["perdida"]),
                ),
            )
        n = len(self.lotes)
        self.panel.mostrar("Vacía" if n == 0 else f"{n} elemento{'s' if n != 1 else ''}")

    def _lote_seleccionado(self) -> int | None:
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showinfo("Papelera", "Elegí un elemento de la papelera.")
            return None
        return int(seleccion[0])

    def ver_lote(self):
        lote = self._lote_seleccionado()
        if lote is None:
            return
        fila = self.lotes[self.lotes["id"] == lote].iloc[0]
        VentanaLista(
            self.app,
            f"Papelera — {formato.fecha(fila['fecha'])}",
            f"EN LA PAPELERA: {fila['descripcion']} — pérdida que suma al restaurar",
            self.app.repos.papelera.cargar_lote(lote),
        )

    def restaurar_lote(self):
        lote = self._lote_seleccionado()
        if lote is None:
            return
        conflictos = self.app.repos.papelera.conflictos(lote)
        if conflictos and not messagebox.askyesno(
            "Ya existen esos datos",
            f"{len(conflictos)} producto(s) de esa fecha ya están otra vez en el historial:\n"
            f"{formato.lista_corta(conflictos, 6)}\n\n"
            "¿Restaurar igual? Los datos actuales que chocan se van a mandar a la papelera (no se pierden).",
        ):
            return
        try:
            self.app.repos.papelera.restaurar(lote, reemplazar=bool(conflictos))
        except (NoEncontradoError, ConflictoError) as exc:
            messagebox.showerror("No se pudo restaurar", str(exc))
        self.app.refrescar_todo()

    def eliminar_lote(self):
        lote = self._lote_seleccionado()
        if lote is None:
            return
        if messagebox.askyesno(
            "Eliminar para siempre",
            "¿Eliminar este elemento para siempre?\n\nEsto NO se puede deshacer.",
            icon="warning",
        ):
            self.app.repos.papelera.eliminar(lote)
            self.refrescar()

    def vaciar_papelera(self):
        if self.lotes.empty:
            messagebox.showinfo("Papelera", "La papelera ya está vacía.")
            return
        if messagebox.askyesno(
            "Vaciar papelera",
            f"¿Eliminar para siempre los {len(self.lotes)} elementos de la papelera de "
            f"{self.app.empresa}?\n\nEsto NO se puede deshacer.",
            icon="warning",
        ):
            self.app.repos.papelera.vaciar(self.app.empresa)
            self.refrescar()
