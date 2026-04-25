# Problemas conocidos y riesgos residuales

Este documento recoge los problemas conocidos de PlumA en su versión
**0.3.0-alpha**. Está pensado para que cualquier persona que evalúe
la herramienta para un piloto, una auditoría, o un despliegue
controlado, sepa de antemano qué limitaciones existen.

La presencia de estos puntos no implica que el proyecto sea inseguro:
significa que la honestidad sobre lo que aún falta es parte del propio
proyecto. Una alpha responsable los reconoce; una alpha temeraria los
oculta.


## Modelo de amenaza CSRF

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


## Concurrencia en `_cache_esquemas`

El extractor (`backend/app/extractor.py`) cachea los esquemas YAML
parseados en un diccionario en memoria. Este diccionario no tiene
lock de threading.

En la práctica esto **no es explotable** porque:

1. El endpoint `/api/describir` está protegido por un semáforo
   (`MAX_PROCESAMIENTOS_SIMULTANEOS=1` por defecto), así que solo
   hay una petición activa a la vez.
2. Si cambia ese valor a >1, sigue siendo una race condition trivial
   que como mucho causa lectura repetida del fichero YAML.

Pero un fuzzer cuidadoso podría detectarlo y reportarlo como hallazgo.
La solución (añadir un `threading.Lock`) es trivial; está pendiente
de aplicarse.


## Cap de tokens CSRF en uso intensivo

El almacén de tokens CSRF está limitado a `MAX_TOKENS_VALIDOS = 16`
para evitar que un atacante haga crecer el set sin tope pidiendo
`/api/csrf` en bucle.

En uso intensivo (ventana flotante + ventana principal + recargas
+ reintentos en una sesión larga) este cap podría desalojar tokens
legítimos antiguos antes de que el usuario los use. La aplicación
detecta el caso (responde 403) y el frontend pide un token nuevo
automáticamente, así que el efecto es transparente. Pero podría
producir mensajes de "petición rechazada" transitorios molestos
en sesiones intensas.

**Mitigación pendiente**: subir el cap a 32-64 o implementar
expiración por LRU consciente del uso.


## `Pillow.MAX_IMAGE_PIXELS` como variable global

El módulo `router.py` configura `Image.MAX_IMAGE_PIXELS` antes de
abrir cada imagen. Esta variable es **global del módulo PIL**, no
por instancia.

Esto **no es problemático en el diseño actual** porque el
procesamiento de imágenes ocurre dentro del sandbox (proceso hijo
con `multiprocessing.spawn`), que tiene su propia copia de la
variable.

Sin embargo, si en una versión futura se desactivara el sandbox
(`USAR_SANDBOX_PARSERS=false`) y se procesara más de una imagen
simultáneamente desde el proceso principal, podría haber
condiciones de carrera al modificar la variable. Es un riesgo
hipotético, no actual.

**Mitigación pendiente**: encapsular la asignación en un
`contextmanager` con `try/finally` que restaure el valor anterior.


## Imágenes Docker no fijadas por digest

El `Dockerfile` actual referencia las imágenes base por tag:

```
FROM python:3.12-slim AS builder
```

Y `docker-compose.yml` referencia Ollama con un parámetro:

```
OLLAMA_IMAGE: ${OLLAMA_IMAGE:-ollama/ollama:latest}
```

Si las imágenes en Docker Hub se actualizan o se ven comprometidas,
el siguiente `docker compose build` producirá una imagen distinta
sin que el usuario lo note.

**Mitigación pendiente**: una vez exista un build "bueno conocido",
fijar las imágenes por su digest SHA256:

```
FROM python:3.12-slim@sha256:XXXXXXXXX...
OLLAMA_IMAGE=ollama/ollama:0.5.7@sha256:YYYYYYYYY...
```

Esto se hará tras el primer ciclo de pruebas con archiveros reales
para fijar versiones validadas.


## Texto íntegro de la AGPL-3 incompleto

El fichero `LICENSE` contiene el aviso de copyright correcto y la
referencia a la AGPL-3, pero **NO incluye el texto íntegro** de la
licencia. Hay una nota explícita en el propio fichero indicando que
debe completarse antes de hacer pública una release.

**Acción pendiente del mantenedor**: descargar el texto completo
desde `https://www.gnu.org/licenses/agpl-3.0.txt` y pegarlo en
`LICENSE` antes de etiquetar la versión `v0.3.0-alpha` en GitHub.


## Falta de fuzzing y tests profundos

Los tests actuales (`tests/test_security_basics.py`) son **6 tests
mínimos** que cubren los vectores de ataque más obvios:

- Extensión falseada (binario llamado `.pdf`).
- ZIP no-DOCX rechazado.
- DOCX con ruta path-traversal.
- CSV injection con `=` y `+`.
- JSON malformado del LLM.
- Idioma del prompt.

Para una release pública estable harían falta:

- Tests de regresión sobre los exportadores (EAD3, EAC-CPF, JSON, CSV).
- Fuzzing con corpus de PDFs, DOCX e imágenes patológicos.
- Tests de integración con un Ollama real en CI.
- Cobertura de los casos edge del extractor (LLM devolviendo tipos raros).

Esto está fuera del alcance de la alpha y previsto para versiones
posteriores.


## No verificado en Windows ni macOS

PlumA se ha desarrollado y probado primariamente en **Windows con
Docker Desktop**. La compatibilidad declarada con Linux y macOS está
basada en que el código y la infraestructura (Docker, Python) son
multiplataforma, pero **no se ha probado activamente en estos
sistemas**.

Casos previsibles donde podría haber problemas:

- En macOS con Docker Desktop, los `tmpfs` pueden comportarse de
  forma distinta.
- En Linux nativo, sin Docker Desktop, el perfil bundled puede
  necesitar ajustes en el routing de red entre contenedores.
- Los scripts `.sh` están escritos pensando en `bash` 4+, pero podrían
  tener incompatibilidades sutiles en macOS (que usa `bash` 3.2 por
  defecto).

**Mitigación pendiente**: alpha cerrado con archiveros que usen los
tres sistemas, recoger feedback, ajustar.


## Apagado de Ollama en perfil bundled

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


## Modelo personalizado con cuadrícula de checkboxes

El frontend tiene tres modos de selección de campos: **esencial**,
**estándar** y **personalizado**. Los dos primeros funcionan; el
tercero **está comentado en el código** como pendiente de
implementación.

Por ahora, "personalizado" se comporta como "estándar". La
implementación completa (cuadrícula con checkbox por área de la
norma activa) requiere trabajo adicional de UI que se hará tras el
feedback de la alpha.


## Conclusión

Ninguno de los problemas listados aquí es bloqueante para alpha
pública. Todos están reconocidos, ninguno permite ejecución de
código remoto ni exfiltración de datos en condiciones de uso normal,
y todos tienen mitigación planificada.

Si encuentras un problema no listado aquí, repórtalo según las
instrucciones de `SECURITY.md` (si es de seguridad) o abre un issue
público en GitHub (si es funcional).
