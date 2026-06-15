# Changelog

Todos los cambios relevantes de PlumA se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado es SemVer con sufijos `-alpha` / `-beta`. Las notas íntegras
de cada versión publicada, junto con su manifiesto SHA-256, están adjuntas a
la entrada correspondiente de
[GitHub Releases](https://github.com/Token-Vean/Pluma/releases).

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
