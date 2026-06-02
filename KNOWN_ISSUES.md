# Problemas conocidos y riesgos residuales

Este documento recoge los problemas conocidos de PlumA en su versión
**0.5.0-beta**. Está pensado para que cualquier persona que evalúe
la herramienta para un piloto, una auditoría, o un despliegue
controlado, sepa de antemano qué limitaciones existen.

La presencia de estos puntos no implica que el proyecto sea inseguro:
significa que la honestidad sobre lo que aún falta es parte del propio
proyecto. Una beta responsable los reconoce; una beta temeraria los
oculta.


## Sobre el cambio de alpha a beta en 0.5.0

PlumA ha pasado a denominarse **beta** en 0.5.0 al cumplirse los siguientes
criterios:

- Cobertura funcional completa de las normas declaradas (ISAD(G), DACS,
  ISAAR(CPF), ISDF, ISDIAH, RIC simplificado).
- Postura de seguridad endurecida: modo local estricto por defecto,
  rechazo de Ollama remoto y exposición en red, sandbox de parsers,
  CSRF con Origin/Referer + token, contexto de build Docker reducido.
- Cadena de release con auditoría: SBOM CycloneDX, workflow GHA con
  Bandit, pip-audit, Trivy y pytest.
- Documentación bilingüe del frontend, instalación visual en Windows,
  instaladores en `.bat` / `.sh` para Linux/macOS.
- Texto íntegro de la AGPL-3 incluido en `LICENSE`.

No es **release candidate** porque sigue pendiente la verificación
cruzada en Windows / macOS / Linux con archiveros reales y la
ampliación de cobertura de tests más allá del set actual. Eso se
documenta abajo.


## Resuelto en 0.5.0-beta (cambios respecto a 0.4.15-alpha)

Los siguientes puntos, listados como abiertos en versiones anteriores,
han sido cerrados en esta release:

- **Texto íntegro de la AGPL-3**: añadido a `LICENSE`. El fichero
  contiene ahora el aviso de copyright del proyecto y el texto canónico
  íntegro de la licencia tal como lo publica la FSF en
  `https://www.gnu.org/licenses/agpl-3.0.txt`.
- **Cap de tokens CSRF estrecho**: subido de 16 a 32. Tolera sesiones
  intensivas (ventana flotante + ventana principal + recargas) sin
  desalojar tokens legítimos.
- **Concurrencia en `_cache_esquemas`**: protegida con `threading.Lock`
  y patrón double-checked locking. Ya no depende del semáforo
  `MAX_PROCESAMIENTOS_SIMULTANEOS=1` para ser segura.
- **`Pillow.MAX_IMAGE_PIXELS` global del módulo**: encapsulada en un
  `contextmanager` que restaura el valor previo al salir, incluso si
  hay excepción. Elimina cualquier fuga potencial.
- **Botones de copiar en modo flotante**: el bug funcional reportado en
  el modo Picture-in-Picture (Chromium rechazaba `clipboard.writeText`
  desde la ventana flotante por checks de foco/activación) se ha
  corregido con una estrategia en cascada: `navigator.clipboard` de la
  PiP, fallback al clipboard de la ventana principal, y solo como
  último recurso `execCommand` sobre el documento principal. El estado
  visual del botón se controla por clase CSS, no por manipulación de
  `style.display`.
- **`importNode` para clonar la plantilla de campo**: sustituye a
  `cloneNode` para que el `ownerDocument` del nodo creado sea correcto
  desde el inicio sin necesidad de adopción implícita posterior.
  Funcionalmente equivalente hoy, más robusto si en el futuro se
  renderizan campos directamente en la ventana flotante.
- **Coherencia de versión en ficheros activos**: `security_static_check.py`
  verifica que la versión `APP_VERSION` aparece en `backend/app/version.py`,
  `docker-compose.yml`, `frontend/static/app.js` e `index.html`. Cualquier
  desfase futuro falla en CI antes de publicar.


## Pendientes — esperados para 0.6.0 o release candidate


### Modelo de amenaza CSRF (sin cambios respecto a 0.4)

La protección CSRF implementada (`backend/app/csrf.py`) defiende
correctamente contra el caso clásico de **pestaña vecina maliciosa**:
un archivero tiene PlumA abierta y, en otra pestaña, visita una web
comprometida que intenta hacer peticiones a `localhost:8082` desde
JavaScript. La combinación Origin-check + token sincronizado bloquea
esto en navegadores modernos.

Lo que CSRF **no** protege es el caso de **malware ya instalado en
el equipo**. Si otro proceso del sistema operativo accede a
`localhost:8082` directamente (no a través de un navegador), puede
solicitar un token y operar normalmente. Esto es coherente con el
modelo de amenaza de una aplicación local monousuario, pero conviene
documentarlo.

**Consecuencia práctica**: PlumA debe correr en equipos con antivirus
actualizado, sin software de origen desconocido, y bajo el control
del archivero que la usa. No debe exponerse a redes locales con
varios usuarios sin antes añadir autenticación real.


### Imágenes Docker no fijadas por digest

El `Dockerfile` actual referencia las imágenes base por tag:

```
FROM python:3.12-slim AS builder
```

Y `docker-compose.yml` referencia Ollama con un parámetro:

```
OLLAMA_IMAGE: ${OLLAMA_IMAGE:-ollama/ollama:0.21.2}
```

Si las imágenes en Docker Hub se actualizan o se ven comprometidas,
el siguiente `docker compose build` producirá una imagen distinta
sin que el usuario lo note.

**Mitigación pendiente**: una vez exista un build "bueno conocido"
de la beta, fijar las imágenes por su digest SHA256:

```
FROM python:3.12-slim@sha256:XXXXXXXXX...
OLLAMA_IMAGE=ollama/ollama:0.21.2@sha256:YYYYYYYYY...
```

Esto se hará tras el primer ciclo de pruebas con archiveros reales
para fijar versiones validadas en la release candidate.


### Falta de fuzzing y cobertura ampliada de tests

Los tests actuales (`tests/`) son **30 tests** que pasan en CI (más
2 saltados en entornos sin POSIX `resource.RLIMIT_AS`, esperado en
Windows nativo y en algunos contenedores) y cubren los vectores de
ataque más obvios y la configuración de release:

- Extensión falseada (binario llamado `.pdf`).
- ZIP no-DOCX rechazado.
- DOCX con ruta path-traversal.
- CSV injection con `=` y `+`.
- JSON malformado del LLM.
- Idioma del prompt.
- Política de modo local estricto.
- Configuración de release.
- Exportadores básicos para DACS y RIC.

Para una release candidate harían falta:

- Tests de regresión completos sobre los exportadores (EAD3, EAC-CPF, JSON, CSV).
- Fuzzing con corpus de PDFs, DOCX e imágenes patológicos.
- Tests de integración con un Ollama real en CI.
- Cobertura de los casos edge del extractor (LLM devolviendo tipos raros).

Esto está en el plan para la 0.6.0 o release candidate.


### Verificación cruzada en Windows / macOS / Linux

PlumA se ha desarrollado y probado primariamente en **Windows con
Docker Desktop**. La compatibilidad con Linux y macOS está basada en
que el código y la infraestructura (Docker, Python) son
multiplataforma, pero **la beta es el primer momento en el que se
abre a probar activamente en estos sistemas**.

Casos previsibles donde podría haber problemas:

- En macOS con Docker Desktop, los `tmpfs` pueden comportarse de
  forma distinta.
- En Linux nativo, sin Docker Desktop, el perfil bundled puede
  necesitar ajustes en el routing de red entre contenedores.
- Los scripts `.sh` están escritos pensando en `bash` 4+, pero podrían
  tener incompatibilidades sutiles en macOS (que usa `bash` 3.2 por
  defecto).

**Plan**: durante el ciclo beta se invitará a archiveros con los tres
sistemas a un piloto cerrado, recoger feedback, ajustar.


### Apagado de Ollama en perfil bundled

El endpoint `POST /api/apagar` solo termina el proceso de la
aplicación. **No detiene el contenedor de Ollama** en el perfil
bundled.

Es una decisión de diseño (no queremos que la app web tenga
permisos para controlar Docker), pero significa que tras pulsar
"apagar" en la interfaz, Ollama sigue corriendo en segundo plano
hasta que el usuario ejecute `detener.bat` / `detener.sh` o
`docker compose down`.

**Acción del usuario**: si se quiere liberar la RAM que ocupa Ollama
(varios GB con un modelo cargado), hay que ejecutar el script de
detención manualmente.

Nota: desde 0.4.15 el botón de apagado UI está desactivado por
defecto (`PERMITIR_APAGADO_UI=false`), así que en una instalación
estándar este comportamiento no se manifiesta — el usuario apaga
PlumA con los scripts.


### Modo personalizado

El modo personalizado permite seleccionar campos visibles y exportables
desde la interfaz. Si se aplica después de procesar un documento, actúa
como filtro visual y de exportación. Si se pulsa **Reprocesar** con el
modo personalizado activo, la selección se envía al backend para
limitar también la extracción del modelo.

Limitación conocida: si se cambia de norma, conviene reprocesar antes
de reutilizar una selección personalizada, porque las claves de campo
pueden no coincidir entre normas.


## Cómo reportar nuevos problemas

Los issues van al repositorio público de GitHub. Si el problema tiene
implicaciones de seguridad, ver `SECURITY.md` para el procedimiento
de divulgación responsable.


## Riesgos residuales reconocidos en 0.6.0-beta

### Sandbox de parsers en Windows: sin `RLIMIT_AS`

El módulo `parser_sandbox.py` aplica límites POSIX (`RLIMIT_AS` para
memoria, `RLIMIT_CPU` para tiempo de CPU) cuando el módulo `resource`
de Python está disponible. En **Windows**, `resource` no existe, así
que esos límites no se aplican al proceso hijo. El aislamiento se
mantiene por tres vías:

- Proceso hijo separado con `multiprocessing` (modo `spawn`).
- Timeout duro (`SANDBOX_TIMEOUT_SEGUNDOS=90` por defecto) que mata
  el proceso si tarda demasiado.
- `mem_limit: 2g` aplicado al contenedor de la aplicación en
  `docker-compose.yml`, que acota el daño máximo dentro del
  contenedor independientemente del SO host.

En la práctica, en el despliegue Docker recomendado el contenedor
corre Linux dentro de la VM de Docker Desktop, por lo que `resource`
sí está disponible. La advertencia aplica si alguien ejecuta el
backend directamente sobre Windows fuera de Docker.

### Concurrencia limitada solo en `/api/describir`

El semáforo `_SEM_PROCESAMIENTO` (variable `MAX_PROCESAMIENTOS_SIMULTANEOS`,
por defecto 1) limita la concurrencia del endpoint pesado
`/api/describir`. El endpoint `/api/exportar/{formato}` no usa ese
semáforo; teóricamente, un usuario podría disparar varias
exportaciones a la vez. La superficie de daño está acotada por
`MAX_EXPORT_BODY_BYTES=15 MB` y por el `mem_limit` del contenedor,
pero no por un límite de concurrencia explícito. En uso monousuario
local no representa un problema real; documentado por transparencia.

### `host.docker.internal` y endurecimiento de Ollama nativo

A partir de v0.6, cuando el instalador detecta Ollama nativo en el
host (modo `PLUMA_OLLAMA_MODE=host`), la app del contenedor se
conecta a `host.docker.internal:11434`. PlumA no introduce
exposición de red — Ollama escucha en `0.0.0.0:11434` por defecto
independientemente de PlumA — pero el modo host hace más probable
que un archivero esté usando un Ollama nativo expuesto sin saberlo.
La sección "Endurecimiento de Ollama nativo" de `INSTALACION.md`
documenta cómo limitarlo a `localhost` con `OLLAMA_HOST=127.0.0.1`.

### Imagen oficial `ollama/ollama` no escaneada

El workflow `.github/workflows/security-checks.yml` ejecuta Trivy
sobre `pluma-app:0.6.0-beta` (la imagen que construimos). La imagen
`ollama/ollama:0.21.2` que se usa en el perfil bundled no se
escanea: es upstream y no la construimos nosotros. Los CVEs de
Ollama deben monitorizarse en sus releases. Mantener la versión
fijada en `docker-compose.yml` permite cambiarla deliberadamente
cuando upstream publique parches relevantes.
