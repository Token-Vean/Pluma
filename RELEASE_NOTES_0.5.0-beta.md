# PlumA v0.5.0-beta — primera beta pública

Esta versión cierra la rama `0.4.x` y abre la fase **beta pública** del
proyecto. No cambia la orientación principal de PlumA — herramienta
local-first de asistencia a la descripción archivística — sino que
consolida cobertura funcional, postura de seguridad y proceso de release
suficientes para abrir la herramienta a evaluación por archiveros fuera
del entorno de desarrollo.

PlumA sigue siendo una herramienta de **apoyo y formación**. No es apta
para producción ni para tratamiento masivo de documentación sensible sin
auditoría previa. El detalle de qué falta para subir el nivel está en
`KNOWN_ISSUES.md` y en `SECURITY_HARDENING.md`.


## Criterios de paso de alpha a beta

PlumA pasa a denominarse **beta** al cumplirse:

- Cobertura funcional completa de las normas declaradas: ISAD(G), DACS,
  ISAAR(CPF), ISDF, ISDIAH y RIC simplificado.
- Postura de seguridad endurecida: modo local estricto por defecto,
  rechazo de Ollama remoto y exposición en red, sandbox de parsers,
  CSRF con Origin/Referer + token, contexto de build Docker reducido.
- Cadena de release con auditoría: SBOM CycloneDX, workflow de GitHub
  Actions con Bandit, `pip-audit`, Trivy y `pytest`.
- Documentación bilingüe del frontend, instalación visual en Windows,
  instaladores `.bat` / `.sh` para Linux/macOS.
- Texto íntegro de la AGPL-3 incluido en `LICENSE`.

No es **release candidate** porque sigue pendiente la verificación
cruzada en Windows/macOS/Linux con archiveros reales y la ampliación de
cobertura de tests. Esos puntos están en el plan para la 0.6.0 o RC.


## Cambios principales respecto a 0.4.x

### 1. Modo local bloqueado de la release pública

La release pública fuerza `PLUMA_STRICT_LOCAL=true`, publica la interfaz
solo en `127.0.0.1:8082` y usa exclusivamente el servicio Docker interno
`ollama`. El perfil `external` no se distribuye en esta variante. Las
variables `ALLOW_REMOTE_OLLAMA` y `ALLOW_NETWORK_EXPOSURE` quedan
ignoradas mientras el modo estricto esté activo.

```env
PLUMA_STRICT_LOCAL=true       # forzado en la release pública
ALLOW_REMOTE_OLLAMA=false     # ignorado si STRICT_LOCAL=true
ALLOW_NETWORK_EXPOSURE=false  # ignorado si STRICT_LOCAL=true
```

El bloqueo se mantiene por capas: `host_ip: 127.0.0.1` en
`docker-compose.yml`, middleware `ProteccionAccesoLocal` que rechaza Host
no local y cabeceras de proxy, validación de `OLLAMA_URL` al arrancar.

### 2. Cobertura completa de las normas

Se completa la cobertura funcional de las normas anunciadas:

- **DACS** se publica como esquema editable independiente
  (`schemas/dacs.yaml`), con su propio exportador.
- **RIC simplificado** entra como cuatro perfiles separados (Record,
  RecordSet, Agent, Activity) sobre `schemas/ric.yaml`. La versión
  actual usa entidades aisladas; el grafo RIC-O completo queda fuera
  del alcance de la 0.5.x.

### 3. Interfaz bilingüe ES/EN

La cabecera incorpora un selector ES/EN. El idioma seleccionado se envía
al backend como `idioma_salida` en cada análisis y el prompt de
extracción instruye al modelo para redactar las propuestas en ese
idioma. Las **evidencias se mantienen siempre como fragmentos literales
del documento original** para preservar la trazabilidad y la
localización de spans.

La traducción cubre interfaz, botones, mensajes y etiquetas normativas
habituales. No duplica los esquemas YAML ni sustituye una localización
normativa completa de ISAD(G), ISAAR(CPF), ISDF o ISDIAH.

### 4. Ficha técnica de auditoría por procesamiento

Cada análisis genera una ficha técnica ligera que recoge metadatos del
proceso, no contenido del documento ni valores propuestos:

- versión de PlumA, identificador de petición, fecha UTC;
- nombre, tipo MIME, tamaño y hash SHA-256 del fichero (si está
  activado `INCLUIR_HASH_DOCUMENTO_AUDITORIA=true`);
- norma, modo, idioma y modelo utilizados;
- ruta de procesamiento, estado del sandbox de parsers;
- recuento de evidencias localizadas, no localizadas y no verificables.

La ficha se muestra en la interfaz y puede descargarse como JSON desde
el botón **Auditoría**.

### 5. Apagado desde la interfaz

Se añade `POST /api/apagar`, protegido por CSRF y por mismo origen
local. El endpoint **solo termina el proceso de la aplicación**; no
monta `/var/run/docker.sock`, no ejecuta Docker y no intenta controlar
el host. Esto evita convertir la aplicación web en un controlador
privilegiado del equipo.

El botón está oculto por defecto (`PERMITIR_APAGADO_UI=false`). Para
liberar la RAM que ocupa Ollama hay que ejecutar `detener.bat` /
`detener.sh` o `docker compose down`.

### 6. Ajuste de longitud y contexto

Se elevan los límites de extracción para descripciones archivísticas
extensas y se parametrizan en `.env`:

```env
MAX_LONGITUD_TEXTO_EXTRAIDO=800000
OLLAMA_NUM_CTX=32768
OLLAMA_NUM_PREDICT=8192
MAX_LONGITUD_VALOR_LLM=50000
```

En `schemas/isad-g.yaml` se eliminan los límites restrictivos de 15
palabras para título y 150 palabras para alcance/contenido,
sustituyéndolos por instrucciones archivísticas más desarrolladas.

Aumentar estos valores mejora la precisión en documentos largos pero
incrementa el consumo de memoria y el tiempo de respuesta.

### 7. Coherencia de versión en CI

El `security_static_check.py` ahora verifica que la cadena `0.5.0`
aparece en `version.py`, `docker-compose.yml`, `.env.example`,
`frontend/static/app.js`, `backend/app/api.py` y `Modelfile`. Cualquier
desfase de versión futuro fallará en CI antes de publicar.


## Hardening acumulado en 0.5.0-beta

Resumen de las medidas aplicadas; el detalle vive en
`SECURITY_HARDENING.md`:

- Rechazo temprano de cuerpos HTTP grandes antes del parseo
  multipart/JSON (`LimiteCuerpoPeticion`).
- Eliminación del fallback de detección por extensión en `router.py`.
- Validación anti ZIP-bomb para DOCX (entradas, ratio, tamaño
  descomprimido, `document.xml`, multimedia).
- Límites de píxeles y bytes para imágenes y renderizado PDF.
- Procesamiento PDF/DOCX/imagen en proceso hijo con timeout y límite
  de memoria (`parser_sandbox.py`).
- Límite de concurrencia para `/api/describir`.
- Tokens CSRF con TTL, almacén acotado y comprobación de mismo origen
  local exacto.
- Restricción de `OLLAMA_URL` a destinos locales en modo estricto.
- Desactivación de `/docs`, `/redoc` y `/openapi.json`.
- Validación defensiva del JSON devuelto por el modelo.
- Sanitización de CSV frente a fórmulas (`=`, `+`, `-`, `@`, tabulador,
  salto de línea).
- `cap_drop: ALL`, `read_only: true`, `tmpfs`, `pids_limit`,
  `mem_limit`, `cpus`, `no-new-privileges` en el contenedor de
  aplicación.
- Healthcheck local en el compose.
- Workflow de seguridad con Ruff, pytest, `pip-audit`, build Docker y
  Trivy.


## Auditoría de dependencias

`python-multipart` se actualiza a la versión **0.0.27** para resolver
una alerta de denegación de servicio en el parseo de cuerpos
`multipart/form-data` (CVE de la rama 0.0.x). El riesgo práctico estaba
ya mitigado por `LimiteCuerpoPeticion`, que rechaza por `Content-Length`
antes de que multipart parsee, y por la publicación restringida a
`127.0.0.1`. Se actualiza igualmente para mantener `pip-audit` limpio
en CI.


## Validación realizada antes de etiquetar

Desde la raíz del repo:

```bash
# 1) Comprobaciones estáticas de configuración de release
python scripts/security_static_check.py

# 2) Tests
PYTHONPATH=backend pytest -q

# 3) Sintaxis Python
python -m py_compile $(find backend -name '*.py')

# 4) Sintaxis JS
node --check frontend/static/app.js

# 5) Auditoría de dependencias
pip-audit -r backend/requirements.txt

# 6) Bandit
bandit -r backend/app -ll
```

Resultado en esta release:

- `security_static_check.py`: todas las comprobaciones superadas.
- `pytest`: 30 tests pasados (más 2 saltados en entornos sin POSIX
  `resource.RLIMIT_AS`).
- `bandit`: sin issues medium/high (8 issues low de confianza alta,
  todos falsos positivos en patrones aceptados del proyecto).
- `pip-audit`: limpio tras el bump de `python-multipart`.

La validación dinámica con Trivy contra la imagen construida y la
prueba en local en Windows con Docker Desktop son parte del checklist
de release.


## Recomendación de uso

Esta versión es adecuada para:

- evaluación por archiveros y equipos de archivo;
- formación y demostraciones;
- pilotos cerrados con corpus no sensible;
- pruebas de integración con sistemas descriptivos (ArchivesSpace,
  AtoM) en entornos controlados.

**No es adecuada** para producción ni para tratamiento masivo de
documentación con datos personales o sensibles. El detalle de los
riesgos residuales aceptados está en `KNOWN_ISSUES.md`.

Las pruebas institucionales son bienvenidas por contacto directo. El
canal de reporte de vulnerabilidades sigue el procedimiento de
`SECURITY.md`.
