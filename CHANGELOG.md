# Changelog

Los cambios de cada versión del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones usan [versionado semántico](https://semver.org/lang/es/).

## [1.0.0] - 2026-10-13

Primera versión publicada.

### Agregado
- Comparación del reporte de ventas diario contra la lista de precios, con estados: pérdida, cobrado de más, OK, sin precio y precio abierto.
- Lectura de Excel `.xlsx`, `.xls` o dentro de un `.zip`.
- Historial por empresa en SQLite, con estadísticas por año, mes, día y producto.
- Corrección manual de filas, alta de productos y papelera para deshacer borrados.
- Migraciones de esquema con copia de seguridad automática.
- Tests de dominio, lectura de archivos, persistencia y servicios.
