# PlumA v0.6.0-beta — Configuración separada del modelo y aprovechamiento de Ollama nativo

**Fecha:** [pendiente de fijar al publicar]
**Estado:** beta pública. No apto para producción sin auditoría previa.

## Resumen

Esta versión simplifica la arquitectura de integración con Ollama en dos
frentes complementarios:

1. **Separación del comportamiento del modelo**: PlumA deja de crear un
   modelo derivado en Ollama mediante `ollama create` y pasa a inyectar
   el system prompt y los parámetros de inferencia en cada petición
   desde un único fichero YAML editable (`schemas/pluma-runtime.yaml`).
2. **Detección automática de Ollama nativo**: el instalador comprueba
   si tienes Ollama instalado en el host con el modelo base ya
   descargado. Si es así, configura PlumA para usarlo vía
   `host.docker.internal:11434` y NO arranca un segundo Ollama dentro
   de Docker. Esto elimina la duplicación de 4-5 GB que ocurría en v0.5
   cuando el usuario ya tenía Ollama en el sistema.

El comportamiento del asistente es idéntico: cambian solo el lugar donde
vive el "carácter" del modelo y la forma en que se decide qué Ollama
usar.

## Contradicciones de v0.5 que se resuelven

- `MODELO_BASE` era configurable en `.env`, pero el `Modelfile` fijaba
  el base con `FROM gemma4:e2b`, así que cambiar la variable no surtía
  efecto sin parchear el `Modelfile` en `bootstrap.py`.
- El instalador y el `bootstrap.py` requerían un paso extra (`ollama
  create pluma:0.5.0`) que generaba una entrada redundante en
  `ollama list` y no aportaba nada que la API de `/api/generate` no
  pudiera hacer con el campo `system`.
- El README prometía detección de Ollama nativo del host
  ("Si **ya** tienes Ollama con modelos descargados, la aplicación se
  conecta directamente a él sin duplicar nada"), pero esa detección no
  estaba implementada: el instalador siempre levantaba el Ollama del
  contenedor y `bootstrap.py` siempre hacía pull del modelo, incluso si
  el host ya lo tenía.

## Cambios

### Eliminado

- `Modelfile` en la raíz del repo.
- `offline/models/Modelfile.template.parameters` (vestigio del flujo
  v0.5 de importación de modelo GGUF como derivado).
- `tools/windows/pluma-import-offline-model.bat` (obsoleto en v0.6).
- `MODELO_NOMBRE` y `MODELFILE_PATH` como variables de entorno
  (`docker-compose.yml`, `.env.example`).
- El paso de creación de modelo derivado en `bootstrap.py`
  (`_crear_modelo_derivado`, `_parsear_modelfile`, `_leer_bloque`,
  `_convertir_valor_parametro`).
- La entrada `pluma:0.5.0` en `ollama list` tras desinstalar la versión
  anterior (ver sección de migración).
- Parches intermedios `PARCHE_README.md` y `PARCHE_CUMPLIMIENTO.md` que
  habían quedado en el repo (ya estaban aplicados sobre los ficheros
  finales).

### Añadido

- `schemas/pluma-runtime.yaml`: fichero único que contiene el system
  prompt completo y los parámetros de inferencia (temperature, top_p,
  top_k, repeat_penalty, num_ctx, stop). Editable en caliente: basta
  con reiniciar el contenedor de la aplicación para que se relea.
- Carga perezosa cacheada del runtime en `llm.py` mediante
  `_cargar_runtime()`, con validación estricta de la estructura del
  YAML al primer uso.
- Verificación temprana en `bootstrap.py`: si el YAML de runtime no
  existe, el backend falla con un mensaje explícito antes de aceptar
  peticiones.
- **Detección automática de Ollama nativo en `instalar.sh` y
  `enforce-local-config.ps1`**. El instalador hace `curl
  http://localhost:11434/api/tags`, comprueba si el modelo base está
  presente, y si lo está fija `PLUMA_OLLAMA_MODE=host` y
  `PLUMA_OLLAMA_URL=http://host.docker.internal:11434` en `.env`.
- `iniciar.sh` e `iniciar.bat`: scripts de arranque cotidiano ligero.
  Resuelven el hueco del flujo v0.5, donde no había forma documentada
  de relanzar la aplicación tras un `detener` o tras reiniciar el
  equipo sin pasar por `instalar.*` (que reconstruye innecesariamente).
  No reconstruyen imagen, no descargan modelos, no tocan `.env`.
  Respetan el modo elegido por el instalador.

### Modificado

- `backend/app/llm.py`: la función pública `generar()` ahora inyecta
  el campo `system` y el bloque `options` en cada llamada a
  `/api/generate`. Firma retrocompatible: `modelo` y `temperatura`
  pasan a ser opcionales; si no se proporcionan, se usan el `MODELO_BASE`
  del entorno y la `temperature` del YAML.
- `backend/app/bootstrap.py`: reducido de ~280 a ~110 líneas. Mantiene
  el dict `estado` con la misma forma para no romper `/api/estado` ni
  el frontend. Sigue garantizando que el modelo base existe en Ollama
  (sea el del host o el del contenedor).
- `backend/app/api.py`: una línea (constante `MODELO`) pasa de leer
  `MODELO_NOMBRE` a leer `MODELO_BASE`.
- `backend/app/version.py`: versión a `0.6.0-beta`.
- `docker-compose.yml`: el servicio `ollama` está bajo `profiles:
  [bundled]`, lo que permite no arrancarlo cuando el instalador detecta
  Ollama nativo. El servicio `app` declara `extra_hosts:
  host.docker.internal:host-gateway` para que `host.docker.internal`
  resuelva también en Linux (Windows/macOS ya lo hacen de fábrica).
- `instalar.sh`, `instalar.bat`, `enforce-local-config.ps1`: lógica de
  detección añadida. El profile `bundled` se activa o no según el
  resultado. El `.env` se sanea como antes y se elimina cualquier
  `MODELO_NOMBRE` / `MODELFILE_PATH` heredado de v0.5.
- `detener.sh`/`.bat` y `desinstalar.sh`/`.bat`: leen
  `PLUMA_OLLAMA_MODE` (en lugar de la antigua variable `PERFIL`) para
  decidir si activar el profile `bundled`. En modo host nunca tocan el
  Ollama nativo.
- `tools/windows/pluma-install-core.bat`: variante de instalador
  offline alineada con el nuevo flujo.
- `frontend/static/app.js` e `index.html`: subtítulo de marca con
  v0.6.0-beta.
- `.github/workflows/security-checks.yml`: la imagen escaneada por
  Trivy pasa a `pluma-app:0.6.0-beta`.
- `scripts/security_static_check.py`: ahora exige que el `Modelfile`
  esté eliminado, que exista `schemas/pluma-runtime.yaml`, que el
  servicio Ollama esté bajo `profiles: [bundled]` y que el servicio
  app declare `extra_hosts: host.docker.internal:host-gateway`.

## Migración desde v0.5

Para colegas que ya tengan PlumA v0.5 instalado:

1. Ejecutar `desinstalar.bat` o `desinstalar.sh` de la instalación
   antigua. Esto detiene los contenedores y elimina los datos asociados.
2. Eliminar manualmente el modelo derivado de Ollama si quedó
   colgado: `ollama rm pluma:0.5.0` (o el nombre que tuviera la
   instalación local). Este paso solo es necesario si conservas un
   Ollama externo al contenedor; en el perfil bundled, al detener los
   contenedores el volumen de Ollama se conserva pero el modelo derivado
   ya no se usa.
3. Sustituir la copia local del repo por la v0.6 (clonado limpio o `git
   pull` sobre la rama correspondiente).
4. Ejecutar `instalar.bat` o `instalar.sh` como en una instalación
   limpia. El `.env` heredado se sanea automáticamente y se detecta el
   Ollama nativo si está presente.

Tras la migración:

- `ollama list` mostrará únicamente el modelo base (`gemma4:e2b` por
  defecto), sin el alias `pluma:0.5.0`.
- Si ya tenías Ollama instalado en Windows/macOS/Linux con el modelo
  descargado, PlumA usará ese Ollama. No se duplicará el modelo dentro
  de Docker.
- El system prompt vive ahora en `schemas/pluma-runtime.yaml`.

## Impacto en auditoría

La ficha técnica de auditoría (`auditoria.generar_ficha_tecnica`) sigue
registrando el campo `modelo`. A partir de v0.6 ese campo contiene el
nombre del modelo base real utilizado (por ejemplo `gemma4:e2b`) en
lugar del alias derivado `pluma:0.5.0`. Esto mejora la trazabilidad:
el registro de auditoría refleja literalmente qué pesos del modelo se
invocaron, sin la capa de indirección que introducía el Modelfile.

Para auditorías de coherencia entre ejecuciones, el system prompt
exacto utilizado en una versión dada queda fijado en
`schemas/pluma-runtime.yaml` del commit correspondiente del repo. Es
recomendable que toda evaluación institucional registre el SHA del
commit junto con el SHA-256 del documento procesado.

## Sin cambios funcionales

- El procesamiento sigue siendo local. Los documentos no salen del
  equipo.
- Las medidas de seguridad de la v0.5 (CSRF, límites pre-parseo,
  sandbox de parsers, validación anti zip-bomb e image-bomb,
  restricción de Ollama remoto, desactivación de `/docs`,
  sanitización CSV) están todas vigentes y sin modificación.
- La política de Ollama local sigue siendo estricta. `host.docker.internal`
  ya estaba en la lista blanca de `security_policy.py` desde v0.5; el
  cambio de v0.6 es que ahora el instalador realmente la usa cuando
  corresponde, en lugar de levantar siempre Ollama Docker.
- La interfaz, las normas soportadas (ISAD(G), DACS, ISAAR(CPF), ISDF,
  ISDIAH, RIC simplificado), los modos de extracción (esencial,
  completo, personalizado) y los formatos de exportación son
  idénticos.
- La detección automática de tipo documental sigue funcionando con la
  misma lógica.

## Ficheros afectados

```
backend/app/llm.py                          modificado
backend/app/bootstrap.py                    modificado (reducido ~60%)
backend/app/api.py                          modificado (1 línea)
backend/app/version.py                      modificado (0.5.0 → 0.6.0)
schemas/pluma-runtime.yaml                  añadido
Modelfile                                   eliminado
offline/models/Modelfile.template.parameters eliminado
tools/windows/pluma-import-offline-model.bat eliminado
PARCHE_README.md                            eliminado
PARCHE_CUMPLIMIENTO.md                      eliminado
docker-compose.yml                          modificado (profiles, extra_hosts)
instalar.sh                                 modificado (detección de host)
instalar.bat                                modificado (detección de host)
iniciar.sh                                  añadido
iniciar.bat                                 añadido
detener.sh                                  modificado (usa PLUMA_OLLAMA_MODE)
detener.bat                                 modificado (usa PLUMA_OLLAMA_MODE)
desinstalar.sh                              modificado (usa PLUMA_OLLAMA_MODE)
desinstalar.bat                             modificado (usa PLUMA_OLLAMA_MODE)
tools/windows/enforce-local-config.ps1      modificado (detección integrada)
tools/windows/pluma-install-core.bat        modificado
.env.example                                modificado
README.md                                   modificado
CUMPLIMIENTO.md                             modificado
frontend/static/app.js                      modificado (subtítulo de marca)
frontend/static/index.html                  modificado (subtítulo de marca)
.github/workflows/security-checks.yml       modificado (imagen escaneada)
scripts/security_static_check.py            modificado
tests/test_offline_paths_policy.py          modificado
```

## Estado del proyecto

Sigue siendo una herramienta local de apoyo y formación, no una solución
certificada para producción. Las pruebas institucionales son bienvenidas
por contacto directo. Los riesgos residuales reconocidos en
`KNOWN_ISSUES.md` no se ven afectados por este cambio arquitectónico.
