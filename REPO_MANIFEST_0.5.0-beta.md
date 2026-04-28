# PlumA — manifiesto del repositorio (v0.5.0-beta)

Este documento describe **qué se sube al repositorio público de GitHub
y qué no**. Se actualiza con cada release que cambie la estructura.

## Qué es lo que estás viendo

Si has descargado el zip `PlumA-v0.5.0-beta-source.zip` para distribuir
PlumA a usuarios finales, ese zip contiene **dos cosas distintas**:

```
PlumA-v0.5.0-beta/
├── pluma/                ← contenido del repositorio (sube esto a GitHub)
├── installer/            ← instalador gráfico Windows (puede ir al repo o publicarse aparte)
├── instalacion_linux_mac/ ← scripts de instalación Linux/macOS
├── documentacion/        ← documentación de instalación para el usuario final
├── offline/              ← carpetas vacías para imágenes Docker o modelos GGUF
├── soporte/              ← scripts avanzados de línea de comandos para Windows
├── release/              ← release notes, SBOM, checklist de seguridad
└── 00_INSTALAR_PLUMA_WINDOWS_SIN_CONSOLA.vbs   ← lanzador del instalador visual
```

La carpeta `pluma/` **es** el repositorio. El resto es el envoltorio
de distribución para usuarios no técnicos. Los release notes y el SBOM
son assets de la release de GitHub, no necesariamente del repo.

## Qué subir como contenido del repositorio

Sube el contenido de la carpeta `pluma/` como **raíz del repositorio**.
Es decir, en GitHub deben quedar en la raíz archivos como:

- `README.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `CLA.md`
- `KNOWN_ISSUES.md`
- `SECURITY.md`
- `SECURITY_HARDENING.md`
- `CUMPLIMIENTO.md`
- `INSTALACION.md`
- `Modelfile`
- `docker-compose.yml`
- `instalar.bat` / `instalar.sh`
- `detener.bat` / `detener.sh`
- `desinstalar.bat` / `desinstalar.sh`
- `.env.example`
- `.gitignore`
- `.github/workflows/security-checks.yml`
- `backend/`
- `frontend/`
- `schemas/`
- `scripts/`
- `tests/`
- `tools/`
- `ejemplos/` (sin documentos reales; el `.gitignore` los excluye)
- `RELEASE_NOTES_0.4.x-alpha.md` (histórico que se conserva como
  registro de versiones)

**NO subas la carpeta `pluma/` como subcarpeta dentro del repositorio.**
La raíz del repo debe ser el contenido de `pluma/`, no `pluma/pluma/`.

## Qué NO subir al repositorio

- `installer/`, `instalacion_linux_mac/`, `documentacion/`, `offline/`,
  `soporte/`, `00_INSTALAR_PLUMA_WINDOWS_SIN_CONSOLA.vbs`: van como
  assets adicionales de la release de GitHub o en un repositorio
  hermano de distribución, no en el repo del código.
- `release/RELEASE_NOTES_0.5.0-beta.md`,
  `release/SECURITY_RELEASE_CHECKLIST_0.5.0-beta.md`,
  `release/SBOM_MINIMAL_0.5.0-beta.cdx.json`: son assets de la release
  pública en GitHub. Se publican en la pestaña "Releases", no en el
  árbol de fuentes. (Las release notes históricas que sí se conservan
  como `RELEASE_NOTES_0.4.x-alpha.md` en el repo son las antiguas, ya
  fijadas; las nuevas se gestionan vía la pestaña Releases.)
- Documentos de prueba, `.env` reales, modelos `.gguf`: cubiertos por
  `.gitignore`.

## Comprobaciones antes de hacer `git push` y `git tag v0.5.0-beta`

Desde la raíz del repo (es decir, desde la carpeta que en local se
llama `pluma/`):

```bash
# 1) Comprobaciones estáticas de configuración de release
python scripts/security_static_check.py

# 2) Tests
PYTHONPATH=backend pytest -q

# 3) Sintaxis Python
python -m py_compile $(find backend -name '*.py')

# 4) Sintaxis JS
node --check frontend/static/app.js
```

Las cuatro deben pasar limpias antes de etiquetar.

## Comprobaciones que solo se pueden hacer en local Windows

```bash
docker compose build app
docker compose ps    # debe mostrar 127.0.0.1:8082->8081/tcp
```

Y la prueba manual del modo flotante: procesar un documento, abrir la
ventana flotante, copiar valores de campos, verificar que se pegan en
otra aplicación. La consola del navegador debe quedar limpia salvo,
como mucho, un `console.debug` informativo si la PiP rechaza el
clipboard y se cae al fallback.

## Cambios estructurales respecto a versiones anteriores

- El workflow de GitHub Actions ya no tiene `working-directory: pluma`.
  Antes era incorrecto porque la raíz del repo es **el contenido** de
  `pluma/`, no una subcarpeta `pluma/`.
- `pyproject.toml`: `Development Status` cambia de `3 - Alpha` a
  `4 - Beta`.
- `LICENSE` contiene ahora el texto íntegro de la AGPL-3.
- `CLA.md` está en la versión 2.0, con relicenciamiento explícito y
  Anexo A para contribuciones corporativas.

## Nota sobre SHA256

El archivo `.sha256` no es necesario dentro del repositorio cuando se
sustituye el código fuente. Es más útil como asset de una release,
asociado a un ZIP concreto. Si se vuelve a comprimir el repositorio,
el hash puede cambiar aunque el contenido sea equivalente.
