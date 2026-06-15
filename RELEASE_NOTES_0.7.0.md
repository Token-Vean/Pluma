# PlumA v0.7.0 — notas de release

## Resumen

v0.7.0 consolida PlumA como herramienta local-first con flujo **text-first / OCR-first** y endurecimiento de seguridad. La aplicación procesa primero el texto ya existente de un PDF; si no hay texto suficiente, aplica OCR local con Tesseract; y solo recurre a visión multimodal cuando OCR/texto no bastan.

## Cambios funcionales principales

- PDF con capa textual suficiente: no se re-OCRiza.
- PDF escaneado o imagen: OCR local previo con Tesseract (`spa+eng`).
- Visión multimodal: fallback, no ruta principal.
- Documentos compuestos: lista ordenable y botón único de procesamiento.
- Selector de modelos descargados en Ollama.
- Preferencias separadas para modelos textuales y visuales.
- Menú de tipo de entrada para evitar rutas lentas: automático, PDF con OCR/texto, PDF escaneado/sin OCR, imagen o texto/DOCX.
- Detección de tipo documental con IA opcional desde la interfaz. Si se desactiva, PlumA evita la primera llamada de clasificación y pasa directamente a la extracción archivística.

## Cambios de seguridad

- Imagen Docker actualizada a `pluma-app:0.7.0`.
- Imagen base conservadora: `python:3.12-slim-bookworm`.
- Eliminación de `pip`, `setuptools` y `wheel` de la imagen final.
- Se añade `SECURITY_NOTES.md` con criterio de aceptación de vulnerabilidades.
- Se añaden scripts de auditoría local:
  - `scripts/auditar_seguridad.ps1`
  - `scripts/auditar_seguridad.sh`
- Criterio de release: 0 críticas, 0 altas corregibles y 0 medias corregibles.

## Instalación recomendada

```powershell
cd C:\Users\geren\Documents\SEC\OneDrive\Escritorio\Pluma
docker compose down
docker compose build --no-cache app
docker compose up -d
```

También puede usarse `instalar.bat`, que reconstruye y arranca la aplicación.

## Verificación recomendada

```powershell
python scripts/security_static_check.py
python -m pytest -q
docker scout cves --only-fixed pluma-app:0.7.0
```

## Nota

La creación de perfiles `pluma-texto` y `pluma-vision` en Ollama es opcional. PlumA funciona seleccionando directamente modelos base descargados en Ollama, por ejemplo `gemma4:e2b` para texto y `qwen3.5:latest` para visión.
