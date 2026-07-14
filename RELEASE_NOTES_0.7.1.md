# PlumA v0.7.1 — notas de release

## Resumen

v0.7.1 es una versión de mantenimiento centrada en seguridad de dependencias,
coherencia operativa y correcciones detectadas tras la auditoría interna de
v0.7.0. No introduce cambios incompatibles en la API.

## Cambios principales

- `/api/describir` acepta `preferencia_entrada` y refleja la preferencia
  normalizada en la respuesta.
- El parseo documental, el OCR y el cálculo del hash se delegan a hilos para no
  bloquear el event loop durante el procesamiento.
- Las fichas técnicas incorporan timestamps con zona horaria.
- El instalador reutiliza Ollama nativo cuando contiene algún modelo. Si no hay
  una instalación utilizable, activa el perfil `bundled`, descarga el modelo
  base y arranca la aplicación contra el Ollama incluido en Docker.

## Seguridad

- Dependencias Python actualizadas, incluida Pillow 12.3.0.
- `pip-audit` sin vulnerabilidades conocidas en las dependencias fijadas.
- Trivy sin vulnerabilidades críticas o altas corregibles en la imagen de la
  aplicación.
- Cabeceras `x-forwarded-proto` y `x-forwarded-port` rechazadas en modo local
  estricto.
- Job de CI en Windows para detectar dependencias incompatibles.
- `uvloop` conserva el marcador `sys_platform != "win32"`.

## Instalación

Requisito: Docker Desktop o Docker Engine con Docker Compose.

- Windows: ejecutar `instalar.bat`.
- Linux/macOS: ejecutar `chmod +x instalar.sh && ./instalar.sh`.

Si se usa el perfil `bundled`, la primera instalación descarga el modelo base y
puede tardar varios minutos. La interfaz se publica únicamente en
<http://127.0.0.1:8082>.

## Verificación

```bash
python scripts/security_static_check.py
PYTHONPATH=backend python -m pytest -q
docker compose build --no-cache app
trivy image --ignore-unfixed --severity CRITICAL,HIGH pluma-app:0.7.1
```

Antes de publicar la release deben crearse la etiqueta `v0.7.1`, la entrada de
GitHub Releases y el manifiesto SHA-256 de los artefactos distribuidos.
