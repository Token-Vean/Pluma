# Frontend

Esta carpeta contiene la interfaz web estática del PlumA.

La versión distribuida usa HTML, CSS y JavaScript sin proceso de compilación,
sin dependencias de Node y sin llamadas a CDN. La interfaz real se sirve desde
`frontend/static/` mediante FastAPI `StaticFiles`.

## Estructura

```text
frontend/
└── static/
    ├── index.html
    ├── styles.css
    ├── app.js
    └── fonts/
        ├── README.md
        ├── descargar-fuentes.bat
        └── descargar-fuentes.sh
```

## Fuentes

Por defecto se usan tipografías del sistema. Los scripts de `static/fonts/`
son opcionales y solo deben usarse si se desea autohospedar fuentes con
licencias compatibles. La release no incluye ficheros de fuente descargados a
medias ni depende de Google Fonts.

## Endpoints consumidos

- `GET /api/estado` — estado del bootstrap inicial.
- `GET /api/csrf` — token CSRF para operaciones mutadoras.
- `GET /api/normas` y `GET /api/tipos` — datos de configuración.
- `POST /api/describir` — procesamiento documental.
- `POST /api/exportar/{formato}` — exportación de la propuesta revisada.
- `POST /api/apagar` — apagado local del servidor de aplicación desde la interfaz.


## Idiomas

La interfaz incorpora selector ES/EN. La traducción se aplica en cliente a textos estáticos, mensajes y etiquetas normativas visuales habituales. Además, el idioma activo se envía en `POST /api/describir` como `idioma_salida`, por lo que la propuesta archivística se redacta en el idioma seleccionado en la interfaz. Si se cambia el idioma tras analizar un documento, debe pulsarse **Reprocesar** para generar una nueva propuesta en ese idioma.


## Autoría y licencia en interfaz

El pie de página muestra la autoría del desarrollo, con enlace a https://www.victorvillapalos.es/, y una referencia a la licencia AGPL-3.0 mediante `frontend/static/LICENSE.txt`.
