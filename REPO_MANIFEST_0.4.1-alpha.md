# PlumA v0.4.1-alpha — repositorio completo

Este paquete contiene el árbol completo recomendado para sustituir el repositorio de PlumA en GitHub.

## Qué subir al repositorio

Sube el contenido de la carpeta `Pluma/` como raíz del repositorio. Es decir, en GitHub deben quedar en la raíz archivos como:

- `README.md`
- `docker-compose.yml`
- `instalar.bat`
- `instalar.sh`
- `detener.bat`
- `detener.sh`
- `desinstalar.bat`
- `desinstalar.sh`
- `.env.example`
- `.gitignore`
- `backend/`
- `frontend/`
- `schemas/`
- `tests/`
- `.github/workflows/security.yml`

No subas la carpeta `Pluma/` como subcarpeta adicional dentro del repositorio, salvo que ese sea deliberadamente el nombre de la raíz local.

## Cambios principales de esta versión

- Versión unificada en `backend/app/version.py`.
- Protección por defecto contra exposición no local mediante `backend/app/local_access.py`.
- Corrección de variable interna del sandbox: `_PLUMA_SANDBOX_CHILD`.
- Ficha técnica de auditoría del procesamiento en `backend/app/auditoria.py`.
- Estado de evidencia por campo: `localizada`, `no_localizada`, `no_verificable`, `sin_evidencia`, `sin_valor`.
- Exportadores reforzados frente a CSV formula injection, caracteres de control y propiedades RDF/Turtle no válidas.
- Modo personalizado mejorado con envío real de campos seleccionados al backend.
- Imagen de Ollama fijada por versión en `docker-compose.yml`, evitando `latest` por defecto.
- Documentación actualizada: `README.md`, `INSTALACION.md`, `SECURITY.md`, `SECURITY_HARDENING.md`, `KNOWN_ISSUES.md`, `CUMPLIMIENTO.md` y `RELEASE_NOTES_0.4.1-alpha.md`.

## Comprobaciones recomendadas antes de etiquetar una release

```bash
pytest
pip-audit -r backend/requirements.txt
trivy image <imagen_construida>
```

Validación estática ya realizada durante la preparación del paquete:

```bash
find backend tests -name '*.py' -print0 | xargs -0 python -S -m py_compile
node --check frontend/static/app.js
```

## Nota sobre SHA256

El archivo `.sha256` no es necesario dentro del repositorio cuando se sustituye el código fuente. Es más útil como asset de una release, asociado a un ZIP concreto. Si se vuelve a comprimir el repositorio, el hash puede cambiar aunque el contenido sea equivalente.
