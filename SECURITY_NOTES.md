# Notas de seguridad de la release v0.7.0

Fecha: 2026-06-15

## Criterio de aceptación

Para publicar una build local de PlumA se aplica el siguiente umbral mínimo:

- 0 vulnerabilidades críticas.
- 0 vulnerabilidades altas corregibles.
- 0 vulnerabilidades medias corregibles.
- Las vulnerabilidades bajas o sin versión corregida deben quedar documentadas y mitigadas por diseño.

## Resultado que motivó v0.7.0

En la imagen preliminar `pluma-app:0.6.2-beta`, Docker Scout detectó 87 vulnerabilidades en 28 paquetes: 0 críticas, 2 altas, 8 medias y 77 bajas. Al filtrar solo las vulnerabilidades con versión corregida disponible (`docker scout cves --only-fixed`), el resultado bajó a 5 vulnerabilidades en un único paquete: `pip 25.0.1`.

La versión v0.7.0 corrige ese punto eliminando `pip`, `setuptools` y `wheel` de la imagen final. PlumA no instala paquetes en runtime, por lo que conservar esas herramientas dentro del contenedor no aporta funcionalidad y sí aumenta superficie de ataque.

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
docker scout cves --only-fixed pluma-app:0.7.0

# Recomendaciones de imagen base
docker scout recommendations pluma-app:0.7.0
```

Alternativa con Trivy:

```powershell
trivy image --ignore-unfixed --severity CRITICAL,HIGH,MEDIUM pluma-app:0.7.0
```

## Decisión de diseño sobre OCR

v0.7.0 adopta flujo **text-first / OCR-first**. Un PDF con capa textual suficiente no se reprocesa con OCR. Solo se aplica Tesseract si la capa textual es inexistente o de baja calidad. La visión multimodal queda como último recurso para manuscritos o imágenes donde el OCR no alcanza un umbral mínimo.
