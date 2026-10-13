"""Ventana principal: selector de empresa y las cuatro pestañas."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

from diferencias.dominio.reglas import es_precio_comodin, perdida_total
from diferencias.persistencia.base_de_datos import BaseDeDatos
from diferencias.persistencia.repositorios import Repositorios
from diferencias.ui import estilos, formato
from diferencias.ui.pestanas.diario import PestanaDiario
from diferencias.ui.pestanas.estadisticas import PestanaEstadisticas
from diferencias.ui.pestanas.papelera import PestanaPapelera
from diferencias.ui.pestanas.por_producto import PestanaPorProducto
from diferencias.ui.ventanas import VentanaDia
from diferencias.ui.widgets import Tarjeta, boton, etiqueta_ayuda

PESTANA_DIARIO = "Diferencias del día"
PESTANA_ESTADISTICAS = "Estadísticas"
PESTANA_POR_PRODUCTO = "Por producto"
PESTANA_PAPELERA = "🗑 Papelera"


class App(ctk.CTk):
    def __init__(self, repos: Repositorios):
        super().__init__()
        estilos.aplicar_tema()
        self.repos = repos
        self.title("Diferencias de ventas — Precios vs Reporte")
        self.geometry("1320x840")
        self.minsize(1080, 680)
        self.configure(fg_color=estilos.FONDO)

        backup = repos.base.inicializar()
        base_vacia = not BaseDeDatos.tiene_datos(repos.base.ruta)
        self._ventanas_dia: dict[tuple[str, str], VentanaDia] = {}

        self._armar_selector_empresa()
        pestanas = ctk.CTkTabview(
            self,
            fg_color=estilos.FONDO,
            segmented_button_selected_color=estilos.ACENTO,
            segmented_button_selected_hover_color=estilos.ACENTO_HOVER,
            segmented_button_fg_color=estilos.FONDO_TARJETA,
            corner_radius=estilos.RADIO_TARJETA,
        )
        pestanas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.diario = PestanaDiario(self, pestanas.add(PESTANA_DIARIO))
        self.estadisticas = PestanaEstadisticas(self, pestanas.add(PESTANA_ESTADISTICAS))
        self.por_producto = PestanaPorProducto(self, pestanas.add(PESTANA_POR_PRODUCTO))
        self.papelera = PestanaPapelera(self, pestanas.add(PESTANA_PAPELERA))

        self._al_cambiar_empresa()

        if base_vacia:
            self.after(500, self._ofrecer_importar_base)
        if backup:
            self.after(
                400,
                lambda: messagebox.showinfo(
                    "Base de datos actualizada",
                    "Se actualizó la base de datos a la versión nueva.\n\n"
                    f"Antes de cambiar nada se hizo una copia de seguridad en:\n{backup}",
                ),
            )

    # ------------------------------------------------------------------
    # Empresa seleccionada
    # ------------------------------------------------------------------
    @property
    def empresa(self) -> str:
        return self.empresa_var.get()

    def empresa_o_aviso(self) -> str | None:
        if not self.empresa:
            messagebox.showwarning("Elegí una empresa", "Seleccioná o creá una empresa antes de continuar.")
            return None
        return self.empresa

    def _armar_selector_empresa(self):
        tarjeta = Tarjeta(self)
        tarjeta.pack(fill="x", padx=16, pady=16)
        interior = ctk.CTkFrame(tarjeta, fg_color="transparent")
        interior.pack(fill="x", padx=18, pady=14)

        etiqueta_ayuda(interior, "EMPRESA").pack(side="left")
        empresas = self.repos.empresas.listar()
        self.empresa_var = tk.StringVar(value=empresas[0] if empresas else "")
        # Solo lectura: si se pudiera escribir, un error de tipeo crearía datos de una empresa inexistente.
        self.combo_empresa = ctk.CTkComboBox(
            interior,
            values=empresas,
            variable=self.empresa_var,
            width=180,
            state="readonly",
            corner_radius=estilos.RADIO_CAMPO,
            fg_color=estilos.FONDO_TABLA,
            button_color=estilos.ACENTO,
            button_hover_color=estilos.ACENTO_HOVER,
            border_width=0,
            font=estilos.FUENTE_NEGRITA,
            command=lambda _valor: self._al_cambiar_empresa(),
        )
        self.combo_empresa.pack(side="left", padx=10)
        boton(interior, "+ Nueva empresa", self._nueva_empresa, width=140).pack(side="left")
        boton(interior, "Importar datos…", self.importar_base, width=130).pack(side="right")
        self.lbl_precios = etiqueta_ayuda(interior, "")
        self.lbl_precios.pack(side="left", padx=20)

    def _nueva_empresa(self):
        nombre = simpledialog.askstring("Nueva empresa", "Nombre de la nueva empresa:", parent=self)
        if not nombre or not nombre.strip():
            return
        nombre = self.repos.empresas.agregar(nombre)
        self._actualizar_lista_empresas(seleccionar=nombre)

    def _actualizar_lista_empresas(self, seleccionar: str | None = None):
        empresas = self.repos.empresas.listar()
        self.combo_empresa.configure(values=empresas)
        if seleccionar:
            self.empresa_var.set(seleccionar)
        elif self.empresa not in empresas:
            self.empresa_var.set(empresas[0] if empresas else "")
        self._al_cambiar_empresa()

    def _al_cambiar_empresa(self):
        self.diario.cambiar_empresa(self.empresa or None)
        self.mostrar_estado_precios()
        self.refrescar_todo()

    def mostrar_estado_precios(self):
        if not self.empresa:
            self.lbl_precios.configure(text="Elegí o creá una empresa.")
            return
        precios = self.diario.precios
        if precios.empty:
            self.lbl_precios.configure(text=f"{self.empresa}: sin lista de precios cargada todavía.")
            return
        comodines = int(precios["precio"].map(es_precio_comodin).sum())
        actualizada = formato.fecha(self.repos.precios.fecha_actualizacion(self.empresa))
        self.lbl_precios.configure(
            text=f"{self.empresa}: {len(precios)} productos en lista de precios (act. {actualizada})"
            + (f" · {comodines} con precio abierto" if comodines else "")
            + "."
        )

    # ------------------------------------------------------------------
    # Coordinación entre pestañas y ventanas
    # ------------------------------------------------------------------
    def refrescar_todo(self, excepto=None):
        """Después de cualquier cambio en la base, deja todas las vistas coherentes."""
        self.estadisticas.refrescar()
        self.por_producto.refrescar()
        self.papelera.refrescar()
        for ventana in list(self._ventanas_dia.values()):
            if ventana is not excepto and ventana.winfo_exists():
                ventana.recargar()

    def abrir_dia(self, empresa: str, fecha: str):
        """Abre la ventana del día, o la trae al frente si ya estaba abierta."""
        ventana = self._ventanas_dia.get((empresa, fecha))
        if ventana is not None and ventana.winfo_exists():
            ventana.lift()
            ventana.focus_force()
            return
        if not self.repos.diferencias.existe_dia(empresa, fecha):
            messagebox.showinfo("Día sin datos", f"No hay datos guardados de {empresa} para el {formato.fecha(fecha)}.")
            return
        self._ventanas_dia[(empresa, fecha)] = VentanaDia(self, empresa, fecha)

    def olvidar_ventana_dia(self, empresa: str, fecha: str):
        self._ventanas_dia.pop((empresa, fecha), None)

    def mandar_dia_a_papelera(self, empresa: str, fecha: str, padre=None) -> bool:
        dia = self.repos.diferencias.cargar_dia(empresa, fecha)
        if dia.empty:
            return False
        if not messagebox.askyesno(
            "Mandar día a la papelera",
            f"¿Mandar a la papelera el {formato.fecha(fecha)} de {empresa}?\n\n"
            f"{len(dia)} productos · pérdida {formato.pesos(perdida_total(dia))}\n\n"
            "Se puede restaurar desde la pestaña Papelera.",
            parent=padre or self,
        ):
            return False
        self.repos.papelera.enviar_dia(empresa, fecha)
        ventana = self._ventanas_dia.get((empresa, fecha))
        if ventana is not None and ventana is not padre and ventana.winfo_exists():
            ventana.destroy()
        self.refrescar_todo(excepto=padre)
        return True

    # ------------------------------------------------------------------
    # Importar una base de otra carpeta
    # ------------------------------------------------------------------
    def _ofrecer_importar_base(self):
        if messagebox.askyesno(
            "No hay datos guardados",
            f"La aplicación no encontró datos guardados en:\n{self.repos.base.ruta}\n\n"
            "Si ya usabas la aplicación en otra carpeta, tus datos están en el archivo "
            "'data/diferencias.db' de esa carpeta.\n\n¿Querés buscarlo e importarlo ahora?",
        ):
            self.importar_base()

    def importar_base(self):
        ruta = filedialog.askopenfilename(
            title="Elegí el archivo diferencias.db de tu carpeta anterior",
            filetypes=[("Base de datos", "*.db"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        if not BaseDeDatos.tiene_datos(ruta) and not messagebox.askyesno(
            "Base vacía", "Ese archivo no tiene días ni precios guardados. ¿Importarlo igual?"
        ):
            return
        try:
            backup = self.repos.base.importar_desde(ruta)
        except ValueError as exc:
            messagebox.showerror("No se pudo importar", str(exc))
            return
        self._actualizar_lista_empresas()
        dias = self.repos.diferencias.cargar_historial(self.empresa)["fecha"].nunique() if self.empresa else 0
        extra = f"\n\nSe actualizó a la versión nueva; copia de seguridad en:\n{backup}" if backup else ""
        messagebox.showinfo(
            "Datos importados", f"Listo: se importaron tus datos ({dias} días de {self.empresa}).{extra}"
        )
