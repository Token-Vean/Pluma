# Changelog

Todos los cambios relevantes de PlumA se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado es SemVer con sufijos `-alpha` / `-beta`. Las notas íntegras
de cada versión publicada, junto con su manifiesto SHA-256, están adjuntas a
la entrada correspondiente de
[GitHub Releases](https://github.com/Token-Vean/Pluma/releases).

## [0.7.2] — 2026-09-07

Versión de mantenimiento derivada de una auditoría de seguridad completa sobre
la v0.7.1. Sin cambios funcionales: la API, los esquemas y los exportadores no
se tocan. Todo lo que sigue es endurecimiento o actualización de dependencias.

### Seguridad

- **Los controles de seguridad del procesamiento dejan de ser configurables
  desde `.env`.** `USAR_SANDBOX_PARSERS`, `SANDBOX_TIMEOUT_SEGUNDOS`,
  `SANDBOX_MEMORIA_MB`, `INCLUIR_HASH_DOCUMENTO_AUDITORIA` y
  `PERMITIR_APAGADO_UI` pasan a valor literal en `docker-compose.yml` y se
  añaden a la lista de claves bloqueadas del saneador (`instalar.sh` y
  `tools/windows/enforce-local-config.ps1`). El caso crítico era
  `USAR_SANDBOX_PARSERS`: un `.env` manipulado o heredado de una instalación
  anterior con el valor a `false` desactivaba el aislamiento en proceso hijo de
  los parsers de PDF/DOCX/imagen —la defensa central frente a entrada no
  confiable— sin que nada avisara. Es la misma clase de problema corregida con
  `OLLAMA_IMAGE` en la v0.7.0.
- **El contenido del documento ya no puede cerrar el bloque delimitado del
  prompt.** El texto que se entrega al modelo va entre `<<<DOCUMENTO_INICIO>>>`
  y `<<<DOCUMENTO_FIN>>>`, pero esos literales no se filtraban del contenido: un
  documento que los incluyera cerraba el bloque de forma prematura y todo lo que
  viniera después el modelo lo leía como instrucción y no como contenido. Se
  añade `extractor.neutralizar_delimitadores()`, que neutraliza la construcción
  sintáctica completa —ninguna secuencia de tres o más ángulos sobrevive dentro
  del bloque— y se aplica en `extractor.construir_prompt()` y en
  `identificador_tipo.detectar()`, que tiene su propio prompt con los mismos
  centinelas. Las secuencias `stop` de `schemas/pluma-runtime.yaml` no cambian.
- **Los nombres de fichero se sanean antes de incrustarse en el prompt.** El
  nombre del fichero subido aparecía sin filtrar en la cabecera de cada tramo de
  OCR local (`router._ocr_imagenes`) y en la etiqueta de cada pieza de un
  documento compuesto (`api._combinar_documentos`). Se añade
  `extractor.etiqueta_segura()`, que neutraliza delimitadores, colapsa saltos de
  línea —que permitirían simular una sección nueva del prompt— y trunca a 120
  caracteres.
- **El cliente HTTP hacia Ollama deja de honrar las variables de proxy del
  entorno.** `httpx.AsyncClient` usa `trust_env=True` por defecto, de modo que
  un `HTTP_PROXY`/`ALL_PROXY` heredado del sistema —habitual en equipos
  corporativos— habría sido el único camino por el que el texto íntegro de un
  documento podía salir del equipo pese a que `validate_ollama_url()` aprobara
  la URL. Se añade `llm.cliente_local()` con `trust_env=False` y
  `follow_redirects=False` explícito, y se usa en las tres llamadas de `llm.py`
  y en las dos de `bootstrap.py`.
- **Las cabeceras de seguridad se aplican ahora a todas las respuestas.** El
  middleware `CabecerasSeguridad` era el más interno de la pila, así que los 403
  de Host no local, los 403 de CSRF y los 411/413 de límite de cuerpo salían sin
  CSP, sin `X-Frame-Options`, sin `Referrer-Policy` ni `Permissions-Policy`. Se
  reordena el registro en `main.py` para que sea el más externo, y el comentario
  del bloque pasa a describir la pila efectiva real (el anterior afirmaba un
  orden que no era el que Starlette construía).
- `pypdf` 6.13.3 → 6.16.1: corrige CVE-2026-71870 (consumo de memoria al
  analizar entradas `/ToUnicode` con valores anómalos, corregido en 6.15.0),
  CVE-2026-84310 (tiempos y memoria al recuperar los outlines de un documento
  con anidamiento reutilizado) y CVE-2026-84311 (ídem al extraer el texto de
  páginas con muchos objetos XForm). Los tres son de agotamiento de recursos y
  dos de ellos caen sobre la ruta de `_extraer_texto_pdf()`. Todos publicados
  después del corte de la v0.7.1.

### Añadido

- `scripts/security_static_check.py` comprueba que los cinco controles de
  seguridad del procesamiento figuran en `docker-compose.yml` como valor
  literal y no como `${VAR:-...}`, de modo que una regresión que los devuelva a
  sustitución desde `.env` rompa CI en lugar de pasar inadvertida.
- `tests/test_release_configuration.py` sustituye la aserción sobre
  `PERMITIR_APAGADO_UI` —que esperaba la sustitución `${PERMITIR_APAGADO_UI:-false}`—
  por dos pruebas nuevas: `test_controles_seguridad_no_configurables_desde_env()`
  verifica los cinco literales en `docker-compose.yml`, y
  `test_env_example_no_declara_controles_seguridad()` impide que `.env.example`
  vuelva a declararlos como si surtieran efecto.
- `test_version_coherence()` cubre ahora también
  `.github/workflows/security-checks.yml`, `backend/Dockerfile` y
  `backend/pyproject.toml`. El workflow quedaba fuera y era el caso con
  consecuencia real: escanea con Trivy la imagen que construye el compose, así
  que un tag desincronizado hace que `docker compose build app` produzca
  `pluma-app:<nueva>` mientras Trivy busca `pluma-app:<vieja>`, el job no la
  encuentra en local y termina intentando descargarla de Docker Hub.

### Documentado

- `.env.example` deja de declarar las cinco variables de seguridad como
  configurables y pasa a documentarlas como valores en vigor fijados en
  `docker-compose.yml`, con la explicación de por qué. Antes inducía a pensar
  que definirlas en `.env` surtía efecto.
- `backend/requirements.txt`: se hace constar que la transitiva no está cerrada
  —faltan al menos `sniffio` y `colorama`— y que la reproducibilidad completa
  requiere regenerar el fichero con `pip-compile` según `HASHES.md`.

## [0.7.1] — 2026-07-14

Versión de mantenimiento centrada en seguridad de dependencias y correcciones
de la auditoría interna de v0.7.0. Sin cambios funcionales que rompan la API:
`/api/describir` añade un parámetro opcional retrocompatible.

### Seguridad

- Dependencias Python actualizadas (grupo Dependabot de 2026-06-22):
  `fastapi` 0.136.0→0.138.0, `starlette` 1.0.1→1.3.1, `uvicorn` 0.45.0→0.49.0,
  `python-multipart` 0.0.27→0.0.32, `pypdf` 6.12.0→6.13.3,
  `pypdfium2` 5.7.1→5.10.1, `httptools` 0.7.1→0.8.0. Se conserva el marcador
  `; sys_platform != "win32"` de `uvloop` (Dependabot lo eliminaba y rompería
  la instalación nativa en Windows).
- `Pillow` 12.2.0→12.3.0: corrige los avisos PYSEC-2026-2253 a PYSEC-2026-2257
  detectados por `pip-audit` en CI (posteriores al grupo de Dependabot).
- GitHub Actions actualizadas: `actions/checkout@v6`, `actions/setup-python@v6`,
  `aquasecurity/trivy-action@v0.36.0`.
- `x-forwarded-proto` y `x-forwarded-port` se añaden a las cabeceras de proxy
  rechazadas en modo local estricto (completa la lista existente).
- Se incorpora una comprobación de dependencias en Windows y se fija
  explícitamente el marcador de plataforma de `uvloop`, evitando que una
  actualización automática intente instalarlo en Windows.

### Corregido

- `/api/describir` ya no bloquea el event loop: el parseo documental
  (sandbox, OCR) y el cálculo del hash SHA-256 se ejecutan en un hilo
  aparte con `asyncio.to_thread`. El polling de `/api/estado` deja de
  congelarse mientras se procesa un documento.
- La ficha técnica de auditoría genera el timestamp con zona horaria
  (`datetime.now().astimezone()`) en lugar de hora local naïve.
- Scripts de arranque, desinstalación y auditoría alineados con la imagen
  `pluma-app:0.7.1`.
- Restaurada la selección automática de perfil: Ollama nativo cuando contiene
  algún modelo y perfil `bundled` con descarga del modelo base en caso contrario.
- Documentación de instalación, cumplimiento y seguridad realineada con el
  comportamiento efectivo de la versión.

### Añadido

- `/api/describir` acepta el parámetro de formulario opcional
  `preferencia_entrada` (`auto` | `pdf_texto` | `pdf_escaneado` | `imagen` |
  `texto`). El router ya lo implementaba pero la API no lo exponía; permite a
  la interfaz saltar rutas costosas cuando el usuario conoce el tipo de
  documento. La preferencia aplicada se refleja en la respuesta
  (`documento.preferencia_entrada`). Valor por defecto `auto`: comportamiento
  idéntico a 0.7.0 si no se envía.

## [0.7.0] — 2026-06-15

### Añadido

- Flujo **OCR-first**: los PDF con capa textual suficiente se procesan directamente como texto; los PDF escaneados e imágenes pasan por OCR local con Tesseract antes de recurrir a visión multimodal.
- Soporte operativo para documentos compuestos por varios ficheros, con lista ordenable y procesamiento manual mediante botón único.
- Selector de modelos de Ollama descargados por el usuario.
- Preferencia separada para modelos visuales y textuales.
- Scripts de auditoría local `scripts/auditar_seguridad.ps1` y `scripts/auditar_seguridad.sh`.
- Documento `SECURITY_NOTES.md` con criterio de aceptación de vulnerabilidades y mitigaciones.
- Selector explícito de **tipo de entrada** en la interfaz: automático, PDF con OCR/texto, PDF escaneado/sin OCR, imagen o texto/DOCX.
- Casilla opcional para activar/desactivar la detección de tipo documental con IA. Por defecto puede dejarse desactivada para evitar una llamada adicional al modelo.

### Cambiado

- La imagen Docker pasa a `pluma-app:0.7.0`.
- La ruta visual usa `/api/chat`, `think=false`, `keep_alive` y parámetros conservadores de contexto/salida.
- La visión multimodal queda como fallback, no como vía principal para documentos escaneados.
- El backend acepta la pista `preferencia_entrada` y evita OCR/renderizado/visión cuando el usuario declara que el PDF ya tiene capa textual.
- El frontend solo envía el modelo a `/api/describir` cuando el usuario lo ha elegido manualmente; si no, deja que el backend seleccione el modelo textual o visual según la ruta real de procesamiento.
- La imagen base pasa a `python:3.12-slim-bookworm` para la rama 0.7.x.

### Seguridad

- La imagen final elimina `pip`, `setuptools` y `wheel` del runtime, porque Pluma no instala dependencias en ejecución. Esto elimina la principal vulnerabilidad corregible detectada por Docker Scout en la imagen v0.6.2/v0.7 preliminar.
- Se alinean `requirements.in` y `requirements.txt`.
- Se actualiza el script de comprobación estática para exigir coherencia de versión `0.7.0`.
- Se documenta el umbral de release: 0 críticas, 0 altas corregibles y 0 medias corregibles; las vulnerabilidades sin fixed version deben quedar justificadas y mitigadas.

## [0.6.2-beta] — histórico de desarrollo

### Añadido

- OCR local previo a la IA mediante Tesseract dentro del contenedor de aplicación.
  Para PDF escaneados e imágenes, PlumA intenta extraer texto primero y solo usa
  visión multimodal si el OCR no ofrece texto suficiente.
- Variables de configuración OCR: `PLUMA_OCR_LOCAL`, `PLUMA_OCR_LANG`,
  `PLUMA_OCR_PSM`, `PLUMA_OCR_TIMEOUT_SEGUNDOS`, `PLUMA_OCR_MAX_IMAGENES`,
  `PLUMA_OCR_MIN_CARACTERES` y `PLUMA_OCR_MIN_ALFANUM_RATIO`.
- Dependencias de sistema para OCR: `tesseract-ocr`, `tesseract-ocr-spa` y
  `tesseract-ocr-eng`.

### Cambiado

- Los documentos visuales pasan por una arquitectura OCR-first: si el OCR local
  es suficiente, la detección de tipo y la extracción archivística se ejecutan
  sobre texto consolidado. Esto evita llamadas visuales lentas a Ollama en los
  casos en que no son necesarias.
- Timeout del parser aislado aumentado a 120 segundos para permitir OCR local
  en documentos escaneados razonables.

## [0.6.1-beta]

### Cambiado

- Modo visual rápido: la lectura de imágenes se realiza una vez por imagen,
  con prompt corto, contexto reducido, imagen normalizada y salida acotada.
  Después la extracción archivística se ejecuta sobre el texto consolidado,
  evitando reenviar imágenes a la detección de tipo y a la extracción principal.
- Se recupera de forma opcional la idea de perfiles Ollama derivados mediante
  `crear_modelos_pluma.bat` / `crear_modelos_pluma.sh`: `pluma-texto`
  y `pluma-vision`. No son obligatorios; PlumA sigue funcionando contra
  modelos base descargados en Ollama.

- Ruta visual segura para Ollama: los documentos con imágenes se envían por
  `/api/chat`, con `think=false`, sin `format=json` nativo y con timeout de
  visión ampliado. Esto evita fallos observados con algunos modelos
  multimodales cuando combinan imagen y gramática JSON estricta.
- Selección diferenciada de modelos: PlumA mantiene preferencias para texto
  (`MODELO_BASE` / `PLUMA_MODELOS_PREFERIDOS`) y para visión
  (`PLUMA_MODELOS_VISUALES_PREFERIDOS`), priorizando modelos Qwen visuales
  cuando existen localmente.
- La interfaz cambia automáticamente al modelo visual recomendado al añadir
  imágenes, salvo que el usuario seleccione manualmente otro modelo.
- El modelo derivado de Ollama deja de ser obligatorio: el comportamiento del
  asistente vive en `schemas/pluma-runtime.yaml` y se inyecta desde el backend.
  Para rendimiento local, se añaden perfiles derivados opcionales `pluma-texto`
  y `pluma-vision`.
- El instalador detecta Ollama nativo en el host con el modelo base ya
  descargado y, en ese caso, activa el modo `host`
  (`host.docker.internal:11434`) sin levantar el contenedor de Ollama. En
  caso contrario activa el profile `bundled` de Docker Compose.
- Lectura visual previa configurable (`MODELO_VISUAL_LECTURA`,
  `PLUMA_LECTURA_VISUAL_PREVIA`, `MAX_TRANSCRIPCION_VISUAL`).

### Seguridad

- La imagen del contenedor de Ollama queda fijada en `docker-compose.yml` y
  deja de ser configurable por variable de entorno (`OLLAMA_IMAGE`
  eliminada): el saneador del instalador no la cubría y permitía sustituir
  desde un `.env` manipulado el contenedor que recibe el texto íntegro de
  los documentos.
- `cap_drop: ALL` y `restart: "no"` también en el contenedor de Ollama,
  alineándolo con el de la aplicación. Ollama ya no rearranca con cada
  inicio de Docker Desktop.
- Instalador de Windows con detección de modo a fallo cerrado: un error del
  saneador de configuración aborta la instalación en lugar de interpretarse
  en silencio como "modo host".
- `127.0.0.1` explícito en instaladores y documentación (el puerto se
  publica solo en loopback IPv4; `localhost` puede resolver a `::1`).
- Puerto de la interfaz fijado por diseño en `127.0.0.1:8082`. `PUERTO`
  desaparece de `.env`, README e instaladores como variable de usuario;
  `security_static_check.py` verifica el invariante por comparación literal.

### Documentación

- README, `.env.example` y `KNOWN_ISSUES.md` realineados con la versión en
  desarrollo (defaults reales de `OLLAMA_NUM_CTX`/`OLLAMA_NUM_PREDICT`,
  arquitectura sin `Modelfile`, sección "Garantías de aislamiento local"
  con la limitación de `internal: false` reconocida).
- Notas de release por versión retiradas de la raíz del repositorio y
  consolidadas en este fichero; las íntegras quedan en GitHub Releases.

## [0.5.0-beta] — 2026-04-25

Primera beta pública. Notas íntegras y manifiesto del repositorio en la
[release v0.5.0-beta](https://github.com/Token-Vean/Pluma/releases/tag/v0.5.0-beta).

Resumen: cobertura funcional completa de las normas declaradas (ISAD(G),
DACS, ISAAR(CPF), ISDF, ISDIAH, RIC simplificado); modo local estricto por
defecto con rechazo de Ollama remoto y de exposición en red; sandbox de
parsers; CSRF con Origin/Referer y token; SBOM CycloneDX y workflow de CI
con Bandit, pip-audit, Trivy y pytest; texto íntegro de la AGPL-3 en
`LICENSE`; interfaz bilingüe ES/EN; instaladores para Windows, Linux y
macOS.

## [0.4.6-alpha] y anteriores

Las versiones alpha (0.4.1 a 0.4.6) se documentaron en ficheros
`RELEASE_NOTES_0.4.x-alpha.md` que han sido retirados de la raíz del
repositorio. Su contenido queda disponible en el historial git y, para las
versiones que tuvieron release publicada, en GitHub Releases.

<!--
Nota de mantenimiento: al preparar cada release, (1) cerrar aquí la sección
"en desarrollo" con la fecha, (2) copiar las notas íntegras a la entrada de
GitHub Releases, (3) adjuntar el manifiesto SHA-256 como asset de la
release, no como fichero del árbol.
-->
