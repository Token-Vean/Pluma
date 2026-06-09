# Changelog

Todos los cambios relevantes de PlumA se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado es SemVer con sufijos `-alpha` / `-beta`. Las notas íntegras
de cada versión publicada, junto con su manifiesto SHA-256, están adjuntas a
la entrada correspondiente de
[GitHub Releases](https://github.com/Token-Vean/Pluma/releases).

## [0.6.0-beta] — en desarrollo

### Cambiado

- Eliminado `Modelfile` y el modelo derivado creado con `ollama create`. El
  comportamiento del asistente (system prompt y parámetros de inferencia)
  vive ahora en `schemas/pluma-runtime.yaml` y se inyecta en cada llamada a
  Ollama desde el backend. Cambiar de modelo (`MODELO_BASE`) ya no requiere
  reconstruir nada en Ollama.
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
