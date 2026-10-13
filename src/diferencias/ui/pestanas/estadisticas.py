"""Pestaña "Estadísticas": árbol Año > Mes > Día con la pérdida de cada período."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk
import pandas as pd

from diferencias.dominio.reglas import calcular_totales
from diferencias.dominio.valores import coincide_busqueda
from diferencias.servicios.estadisticas import con_periodos, ranking_mas_regalados
from diferencias.ui import estilos, formato
from diferencias.ui.widgets import CampoBusqueda, PanelTotal, Tarjeta, boton, crear_tabla, etiqueta_ayuda, vaciar

if TYPE_CHECKING:
    from diferencias.ui.app import App

# Los iid de las filas del árbol codifican el período: "anio:2026", "mes:2026-09", "dia:2026-09-01".
ANIO, MES, DIA = "anio", "mes", "dia"


def _iid(tipo: str, clave: str) -> str:
    return f"{tipo}:{clave}"


def _partir_iid(iid: str) -> tuple[str, str]:
    tipo, clave = iid.split(":", 1)
    return tipo, clave


class PestanaEstadisticas:
    def __init__(self, app: App, contenedor: ctk.CTkFrame):
        self.app = app
        self.historial = pd.DataFrame()

        contenedor.configure(fg_color=estilos.FONDO)
        self.panel_total = PanelTotal(contenedor, "PÉRDIDA TOTAL")
        self.panel_total.pack(fill="x", padx=4, pady=(14, 10))

        barra = ctk.CTkFrame(contenedor, fg_color="transparent")
        barra.pack(fill="x", padx=4, pady=(0, 8))
        self.busqueda = CampoBusqueda(
            barra, lambda _t: self.refrescar(), placeholder="Filtrar por producto o categoría…"
        )
        self.busqueda.pack(side="left")
        boton(barra, "🗑 Mandar día a la papelera", self._papelera_dia_seleccionado, "peligro").pack(side="right")
        boton(barra, "✎ Ver / editar día", self._abrir_dia_seleccionado).pack(side="right", padx=8)
        etiqueta_ayuda(contenedor, "Doble clic en un día para verlo y editarlo · clic derecho para más opciones").pack(
            anchor="w", padx=8, pady=(0, 6)
        )

        cuerpo = ctk.CTkFrame(contenedor, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        self._armar_ranking(cuerpo)

        columnas = ["Pérdida", "Con pérdida", "Cobrado de más (info)"]
        tarjeta, self.arbol = crear_tabla(cuerpo, columnas, {c: 150 for c in columnas}, height=12, show="tree headings")
        self.arbol.heading("#0", text="Período")
        self.arbol.column("#0", width=230, anchor="w")
        self.arbol.tag_configure("anio", font=estilos.FUENTE_NEGRITA)
        tarjeta.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)

        self.arbol.bind("<<TreeviewSelect>>", lambda _e: self._al_seleccionar())
        self.arbol.bind("<Double-1>", lambda _e: self._al_hacer_doble_click())
        self.arbol.bind("<Delete>", lambda _e: self._papelera_dia_seleccionado())
        for evento in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):  # clic derecho en Windows, Linux y Mac
            self.arbol.bind(evento, self._menu_contextual)

        self.menu = tk.Menu(
            app,
            tearoff=0,
            bg=estilos.FONDO_TARJETA,
            fg=estilos.TEXTO,
            activebackground=estilos.ACENTO,
            activeforeground="#ffffff",
            bd=0,
        )
        self.menu.add_command(label="✎ Ver / editar día", command=self._abrir_dia_seleccionado)
        self.menu.add_separator()
        self.menu.add_command(label="🗑 Mandar día a la papelera", command=self._papelera_dia_seleccionado)

    def _armar_ranking(self, cuerpo):
        tarjeta = Tarjeta(cuerpo, width=430)
        tarjeta.pack(side="right", fill="y", padx=(10, 4), pady=4)
        tarjeta.pack_propagate(False)
        ctk.CTkLabel(
            tarjeta, text="Lo más regalado en el período", text_color=estilos.TEXTO, font=estilos.FUENTE_NEGRITA
        ).pack(anchor="w", padx=18, pady=(14, 4))
        columnas = ["Producto", "Veces", "Pérdida"]
        self.ranking = ttk.Treeview(tarjeta, columns=columnas, show="headings")
        for columna, ancho in zip(columnas, (210, 60, 110), strict=True):
            self.ranking.heading(columna, text=columna)
            self.ranking.column(
                columna, width=ancho, anchor="w" if columna == "Producto" else "center", stretch=columna == "Producto"
            )
        self.ranking.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        estilos.configurar_tags(self.ranking)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def refrescar(self):
        empresa = self.app.empresa
        historial = self.app.repos.diferencias.cargar_historial(empresa) if empresa else pd.DataFrame()
        if not historial.empty and self.busqueda.texto:
            historial = historial[coincide_busqueda(historial, self.busqueda.texto, ["producto", "categoria", "nota"])]
        self.historial = con_periodos(historial)
        self._reconstruir_arbol()

    def _segmento(self, iid: str) -> pd.DataFrame:
        tipo, clave = _partir_iid(iid)
        h = self.historial
        if tipo == ANIO:
            return h[h["anio"] == int(clave)]
        if tipo == MES:
            anio, mes = clave.split("-")
            return h[(h["anio"] == int(anio)) & (h["mes"] == int(mes))]
        return h[h["fecha"] == clave]

    # ------------------------------------------------------------------
    # Árbol
    # ------------------------------------------------------------------
    def _insertar_periodo(self, padre: str, iid: str, texto: str, segmento: pd.DataFrame, abiertos: set, *tags):
        t = calcular_totales(segmento)
        valores = (
            formato.pesos_o_cero(t.perdida),
            t.cantidad_con_perdida,
            formato.pesos(t.cobrado_de_mas) if t.cobrado_de_mas else "-",
        )
        self.arbol.insert(
            padre,
            "end",
            iid=iid,
            text=texto,
            open=iid in abiertos,
            values=valores,
            tags=(estilos.tag_por_signo(t.perdida), *tags),
        )

    def _reconstruir_arbol(self):
        # Se recuerda qué estaba abierto y seleccionado para no perder el lugar al refrescar.
        abiertos = {iid for iid in self._todos_los_iids() if self.arbol.item(iid, "open")}
        seleccion = self.arbol.selection()
        vaciar(self.arbol)

        h = self.historial
        if h.empty:
            filtro = self.busqueda.texto
            titulo = f"Sin resultados para '{filtro}'" if filtro else "Todavía no hay días guardados para esta empresa."
            self.panel_total.mostrar("$0", titulo=titulo, subtitulo="")
            self._mostrar_ranking(h)
            return

        for anio in sorted(h["anio"].unique(), reverse=True):
            iid_anio = _iid(ANIO, str(anio))
            self._insertar_periodo("", iid_anio, f"📅 {anio}", self._segmento(iid_anio), abiertos, "anio")
            for mes in sorted(h.loc[h["anio"] == anio, "mes"].unique()):
                iid_mes = _iid(MES, f"{anio}-{mes:02d}")
                del_mes = self._segmento(iid_mes)
                self._insertar_periodo(iid_anio, iid_mes, f"📁 {formato.MESES[mes - 1]}", del_mes, abiertos)
                for fecha in sorted(del_mes["fecha"].unique()):
                    iid_dia = _iid(DIA, fecha)
                    del_dia = self._segmento(iid_dia)
                    editado = " ✎" if del_dia["editado_en"].notna().any() else ""
                    self._insertar_periodo(iid_mes, iid_dia, f"📄 {formato.fecha(fecha)}{editado}", del_dia, abiertos)

        vigentes = [s for s in seleccion if self.arbol.exists(s)]
        if vigentes:
            self.arbol.selection_set(vigentes)
            self.arbol.see(vigentes[0])
        else:
            self._mostrar_total(h, "PÉRDIDA TOTAL (todo el historial)")

    def _todos_los_iids(self, padre: str = ""):
        for iid in self.arbol.get_children(padre):
            yield iid
            yield from self._todos_los_iids(iid)

    def _mostrar_total(self, segmento: pd.DataFrame, titulo: str):
        if self.busqueda.texto:
            titulo += f" — filtrado por '{self.busqueda.texto}'"
        t = calcular_totales(segmento)
        self.panel_total.mostrar(
            formato.pesos(t.perdida),
            estilos.color_total(t.perdida),
            titulo=titulo,
            subtitulo=f"{t.cantidad_con_perdida} platos con pérdida   ·   "
            f"Cobrado de más (no se suma): {formato.pesos(t.cobrado_de_mas)}",
        )
        self._mostrar_ranking(segmento)

    def _mostrar_ranking(self, segmento: pd.DataFrame):
        vaciar(self.ranking)
        for _, fila in ranking_mas_regalados(segmento).iterrows():
            self.ranking.insert(
                "",
                "end",
                tags=(estilos.TAG_NEGATIVO,),
                values=(fila["producto"], int(fila["veces_con_perdida"]), formato.pesos(fila["perdida_acumulada"])),
            )

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _al_seleccionar(self):
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        tipo, clave = _partir_iid(seleccion[0])
        if tipo == DIA:
            titulo = f"PÉRDIDA DEL DÍA {formato.fecha(clave)}"
        elif tipo == MES:
            anio, mes = clave.split("-")
            titulo = f"PÉRDIDA DE {formato.MESES[int(mes) - 1].upper()} {anio}"
        else:
            titulo = f"PÉRDIDA DEL AÑO {clave}"
        self._mostrar_total(self._segmento(seleccion[0]), titulo)

    def _dia_seleccionado(self) -> str | None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return None
        tipo, clave = _partir_iid(seleccion[0])
        return clave if tipo == DIA else None

    def _al_hacer_doble_click(self):
        # En años y meses el doble clic ya abre/cierra la rama por defecto.
        fecha = self._dia_seleccionado()
        if fecha:
            self.app.abrir_dia(self.app.empresa, fecha)

    def _menu_contextual(self, evento):
        iid = self.arbol.identify_row(evento.y)
        if not iid:
            return None
        self.arbol.selection_set(iid)
        estado = "normal" if _partir_iid(iid)[0] == DIA else "disabled"
        for indice in (0, 2):  # las dos opciones (el 1 es el separador)
            self.menu.entryconfigure(indice, state=estado)
        try:
            self.menu.tk_popup(evento.x_root, evento.y_root)
        finally:
            self.menu.grab_release()
        return "break"

    def _abrir_dia_seleccionado(self):
        fecha = self._dia_seleccionado()
        if not fecha:
            messagebox.showinfo("Elegí un día", "Seleccioná un día (📄) en el árbol.")
            return
        self.app.abrir_dia(self.app.empresa, fecha)

    def _papelera_dia_seleccionado(self):
        fecha = self._dia_seleccionado()
        if not fecha:
            messagebox.showinfo("Elegí un día", "Seleccioná un día (📄) en el árbol.")
            return
        self.app.mandar_dia_a_papelera(self.app.empresa, fecha)
