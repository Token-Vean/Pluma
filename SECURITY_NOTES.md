# Notas de seguridad de la release v0.7.2

Fecha: 2026-09-07

## Criterio de aceptación

Para publicar una build local de PlumA se aplica el siguiente umbral mínimo:

- 0 vulnerabilidades críticas.
- 0 vulnerabilidades altas corregibles.
- 0 vulnerabilidades medias corregibles.
- Las vulnerabilidades bajas o sin versión corregida deben quedar documentadas y mitigadas por diseño.

## Resultados de v0.7.0 a v0.7.2

En la imagen preliminar `pluma-app:0.6.2-beta`, Docker Scout detectó 87 vulnerabilidades en 28 paquetes: 0 críticas, 2 altas, 8 medias y 77 bajas. Al filtrar solo las vulnerabilidades con versión corregida disponible (`docker scout cves --only-fixed`), el resultado bajó a 5 vulnerabilidades en un único paquete: `pip 25.0.1`.

La versión v0.7.0 corrige ese punto eliminando `pip`, `setuptools` y `wheel` de la imagen final. PlumA no instala paquetes en runtime, por lo que conservar esas herramientas dentro del contenedor no aporta funcionalidad y sí aumenta superficie de ataque.

La versión v0.7.1 actualiza las dependencias Python y corrige los avisos
PYSEC-2026-2253 a PYSEC-2026-2257 mediante Pillow 12.3.0. El workflow de la
release finaliza con `pip-audit` sin vulnerabilidades conocidas y Trivy sin
vulnerabilidades críticas o altas corregibles en la imagen de aplicación.

La versión v0.7.2 sube `pypdf` de 6.13.3 a 6.16.1 (CVE-2026-71870,
CVE-2026-84310 y CVE-2026-84311, todos de agotamiento de recursos, publicados
después del corte de la v0.7.1) y endurece cinco puntos del propio código:
bloqueo de los controles de seguridad del procesamiento frente a `.env`,
neutralización de los delimitadores del prompt en el contenido del documento y
en los nombres de fichero, `trust_env=False` en el cliente HTTP hacia Ollama y
reordenación de la pila de middlewares para que las cabeceras de seguridad
alcancen también las respuestas de rechazo.

Limitación conocida del inventario: `backend/requirements.txt` está escrito a
mano y su transitiva no está cerrada, así que `pip-audit -r` sobre ese fichero
no cubre las dependencias indirectas no listadas. El paso `pip-audit` del
workflow se ejecuta después de instalar, lo que compensa parcialmente, pero la
solución correcta es regenerar el fichero con `pip-compile --generate-hashes`
según `backend/HASHES.md`.

## Riesgos residuales esperables

Es normal que una herramienta con OCR, PDF e imagen arrastre librerías nativas con avisos de seguridad, especialmente `tiff`, `openjpeg`, `libxml2`, `glibc`, `perl-base` o dependencias indirectas de Tesseract/PDFium. Algunos CVE pueden aparecer como `not fixed` en la distribución base.

Estos avisos deben revisarse en cada release, pero no todos implican explotabilidad práctica en PlumA. Las mitigaciones activas son:

- Interfaz publicada solo en `127.0.0.1:8082`.
- Modo estricto local (`PLUMA_STRICT_LOCAL=true`).
- Rechazo de endpoints LLM remotos en la release pública.
- Contenedor de aplicación sin privilegios (`appuser`, no root).
- `read_only: true` y `/tmp` en `tmpfs`.
- `cap_drop: ALL` y `no-new-privileges:true`.
- Límites de memoria, CPU y procesos en Docker Compose.
- Procesamiento documental en proceso hijo con timeout.
- Límites de tamaño, páginas, píxeles, longitud de texto y concurrencia.
- Validación por firma de ficheros y rechazo de formatos ambiguos.
- CSRF y comprobación estricta de `Host`/`Origin`.
- No registro de contenido documental completo en logs.

## Comandos de verificación recomendados

```powershell
# Build limpio
docker compose down
docker compose build --no-cache app

# Comprobación de vulnerabilidades corregibles
docker scout cves --only-fixed pluma-app:0.7.2

# Recomendaciones de imagen base
docker scout recommendations pluma-app:0.7.2
```

Alternativa con Trivy:

```powershell
trivy image --ignore-unfixed --severity CRITICAL,HIGH,MEDIUM pluma-app:0.7.2
```

## Decisión de diseño sobre OCR

v0.7.0 adopta flujo **text-first / OCR-first**. Un PDF con capa textual suficiente no se reprocesa con OCR. Solo se aplica Tesseract si la capa textual es inexistente o de baja calidad. La visión multimodal queda como último recurso para manuscritos o imágenes donde el OCR no alcanza un umbral mínimo.
