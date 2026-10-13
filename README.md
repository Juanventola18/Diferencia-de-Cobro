# Diferencias de cobro

Aplicación de escritorio para restaurantes que compara lo que **se debería haber cobrado** según la lista de precios contra lo que **se cobró realmente** según el reporte de ventas diario, y lleva un historial de la plata que se pierde en productos regalados o cobrados de menos.

Trabaja con los Excel que exporta el sistema de ventas (Fudo) y soporta varias empresas, cada una con su propia lista de precios e historial.

## Qué hace

- Cruza el reporte de ventas del día con la lista de precios y marca cada producto como pérdida, cobrado de más, OK, sin precio o precio abierto.
- Suma **solo las pérdidas**. Lo cobrado de más se muestra aparte y no compensa la pérdida, porque son errores distintos.
- Guarda cada día en una base SQLite y muestra estadísticas por año, mes, día y producto.
- Permite corregir filas, agregar productos que no figuran en el reporte y deshacer borrados con una papelera.

## Instalación

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

En Linux puede hacer falta instalar tkinter aparte (`sudo apt install python3-tk`).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Los tests cubren las reglas de cálculo, la lectura de Excel, la base de datos (incluidas las migraciones) y los servicios. No necesitan interfaz gráfica.

## Estructura

```
src/diferencias/
├── dominio/        Reglas de negocio puras: cálculo de diferencias, estados, validaciones
├── entrada/        Lectura de los Excel (.xlsx, .xls o dentro de un .zip)
├── persistencia/   SQLite: esquema, migraciones y un repositorio por tabla
├── servicios/      Pasos que combinan reglas y datos: preparar un día para guardar, estadísticas
└── ui/             Interfaz con customtkinter, una clase por pestaña
```

Las dependencias apuntan siempre hacia el dominio: `persistencia` y `servicios` usan `dominio`, la `ui` usa todo lo anterior, y nada importa a la `ui`. El dominio no depende de ninguna otra capa, por eso se puede testear sin base de datos ni ventanas.

`main.py` arma los repositorios con la ruta de la base y se los pasa a la interfaz. Los tests hacen lo mismo con una base temporal.

## Archivos de entrada

**Lista de precios**: hoja `Productos` con las columnas `Nombre` y `Precio`. Los productos con precio vacío se ignoran (quedan como "sin precio" al venderse) y los que tienen un precio comodín de 9.999.999 o más se toman como precio abierto y no se comparan.

**Reporte de ventas**: hoja `Detalle` con `Fecha`, `Categoría`, `Producto`, `Cantidades vendidas` y `Monto total`. Las fechas en texto se leen como día/mes/año. Si un producto aparece en dos filas del mismo día, se suman.

El cruce se hace por nombre exacto del producto.

## Datos

La base se crea sola en `data/diferencias.db`. Antes de actualizar el esquema de una base existente se guarda una copia al lado. Ni la base ni los Excel se suben al repositorio (ver `.gitignore`).
