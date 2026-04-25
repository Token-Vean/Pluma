# Tipografías autohospedadas

La release endurecida no incluye ficheros `.ttf` descargados parcialmente.
La interfaz funciona con tipografías del sistema y no hace peticiones a
Google Fonts ni a otros CDN.

Si quieres volver a usar tipografías autohospedadas, ejecuta desde esta
carpeta:

- `./descargar-fuentes.sh` en Linux/macOS.
- `descargar-fuentes.bat` en Windows.

Después verifica que los `.ttf` pesan cientos de KB o varios MB, no unos
pocos bytes, y reactiva las reglas `@font-face` en `frontend/static/styles.css`
si deseas forzar esas fuentes.

Los proyectos de fuente referenciados por los scripts son:

- Newsreader: https://github.com/productiontype/Newsreader
- IBM Plex: https://github.com/IBM/plex

Consulta `OFL.txt` para la licencia SIL Open Font License 1.1.
