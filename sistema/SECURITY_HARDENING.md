# Endurecimiento de seguridad aplicado

Fecha: 2026-04-24

Este paquete incorpora una fase adicional de endurecimiento sobre la versión
revisada previamente. No sustituye una auditoría profesional ni pruebas de
fuzzing, pero reduce los riesgos principales para una release pública local y
formativa.

## Cambios principales acumulados

1. **Corte temprano de cuerpos HTTP**
   - Middleware `LimiteCuerpoPeticion`.
   - Rechaza `/api/describir` y `/api/exportar/*` por `Content-Length` antes
     de que FastAPI/Starlette parseen multipart o JSON.
   - Responde `411` si falta `Content-Length` y `413` si se excede el límite.

2. **Limitación de concurrencia**
   - `/api/describir` queda protegido por `asyncio.Semaphore`.
   - Por defecto solo se procesa un documento simultáneamente.
   - Configurable con `MAX_PROCESAMIENTOS_SIMULTANEOS`.

3. **Parsers documentales en proceso aislado**
   - Nuevo módulo `backend/app/parser_sandbox.py`.
   - El procesamiento PDF/DOCX/imagen se ejecuta, por defecto, en un proceso
     hijo.
   - Timeout configurable con `SANDBOX_TIMEOUT_SEGUNDOS`.
   - Límite de memoria en sistemas POSIX con `SANDBOX_MEMORIA_MB`.
   - Desactivable solo para depuración con `USAR_SANDBOX_PARSERS=false`.

4. **Router de entrada reforzado**
   - Eliminado el fallback por extensión.
   - Detección de tipo basada en firma/contenido.
   - DOCX validado contra macros, ZIP-bomb, rutas internas anómalas, tamaño
     descomprimido, ratio de compresión, `document.xml` enorme y multimedia
     embebida excesiva.
   - PDF con límites de páginas, píxeles renderizados y bytes por imagen.
   - Imágenes con límites de píxeles, dimensión, frame único y tamaño
     normalizado.
   - Texto máximo reducido a 200.000 caracteres.

5. **Extractor más defensivo**
   - El JSON del modelo se trata como no confiable.
   - Se validan tipos y longitudes antes de construir la propuesta.
   - Si la evidencia textual no se localiza literalmente, la confianza se
     degrada a baja y se añade advertencia.

6. **Exportación reforzada**
   - Validación de estructura y tamaño del payload de exportación.
   - Mitigación de CSV injection ante valores que empiezan por `=`, `+`, `-`,
     `@`, tabulador o salto de línea.

7. **CSRF acotado y más estricto**
   - Tokens con TTL.
   - Almacén máximo de tokens en memoria.
   - Comprobación Origin/Referer contra el mismo origen local exacto de la app.
   - CSRF no se documenta como autenticación; no protege despliegues en red.

8. **Restricción de Ollama remoto**
   - `OLLAMA_URL` se valida al arrancar.
   - Por defecto solo se permiten `localhost`, `127.0.0.1`, `::1`,
     `host.docker.internal` y el servicio Docker `ollama`.
   - Un endpoint remoto requiere `ALLOW_REMOTE_OLLAMA=true`, porque puede enviar
     texto e imágenes documentales fuera del equipo.

9. **FastAPI con superficie reducida**
   - Desactivados `/docs`, `/redoc` y `/openapi.json` en la aplicación final.

10. **Docker más restrictivo**
   - `cap_drop: ALL` en el contenedor de aplicación.
   - `read_only: true`, `tmpfs`, `pids_limit`, `mem_limit`, `cpus`.
   - Healthcheck local.
   - Eliminado `--proxy-headers` de Uvicorn.
   - `OLLAMA_IMAGE` parametrizable para poder fijar versión o digest probado.

11. **Higiene de release y CI**
   - Eliminado `.env` del paquete.
   - Eliminado `frontend/mockup.html` del paquete distribuible.
   - Sin Google Fonts ni CDN en la interfaz real.
   - Añadido workflow `.github/workflows/security.yml` con Ruff, pytest,
     `pip-audit`, build Docker y Trivy.
   - Añadidas pruebas básicas de validación de router, extractor y CSV.

## Pendiente para subir el nivel a auditoría profesional

- Ejecutar fuzzing con corpus de PDFs, DOCX e imágenes patológicos.
- Generar un `requirements.lock` con hashes mediante
  `pip-compile --generate-hashes` en un entorno con acceso a PyPI.
- Fijar `python:3.12-slim` y `ollama/ollama` por digest tras probar una build
  concreta.
- Hacer escaneo Trivy real de la imagen construida y archivar informe en la
  release.
- Realizar prueba dinámica con Docker Compose en Windows, Linux y macOS.
- Añadir autenticación real si se permite cualquier despliegue distinto de
  `127.0.0.1`.

## Ajuste posterior: límites de contexto y descripción extensa

Se han ampliado y parametrizado los límites que afectaban a la extracción y a la salida textual:

- `MAX_LONGITUD_TEXTO_EXTRAIDO` pasa a ser configurable y queda por defecto en 800.000 caracteres.
- `OLLAMA_NUM_CTX` pasa a 32.768 tokens por defecto.
- `OLLAMA_NUM_PREDICT` pasa a 8.192 tokens por defecto.
- `MAX_LONGITUD_VALOR_LLM` pasa a 50.000 caracteres por campo.
- Los límites de exportación se elevan para no bloquear campos largos.
- En `schemas/isad-g.yaml` se eliminan los límites restrictivos de 15 palabras para título y 150 palabras para alcance/contenido, sustituyéndolos por instrucciones archivísticas más desarrolladas.

Estos cambios favorecen descripciones más precisas, pero aumentan coste computacional. Si el equipo tiene poca memoria o el modelo local no soporta contexto amplio, deben rebajarse en `.env`.


## Corrección de visualización de campos largos — v4

Se corrige el autoajuste de altura de los campos editables de la interfaz. En versiones anteriores, los `textarea` podían calcular su altura mientras la pantalla de sesión seguía oculta (`display: none`), por lo que textos largos de campos como `Título` o `Alcance y contenido` podían quedar visualmente recortados aunque el backend hubiera devuelto el valor completo. Ahora la altura se recalcula después de mostrar la pantalla, en el siguiente frame de renderizado y también al enfocar o editar el campo.


## Apagado desde interfaz y alcance de seguridad

Se añade `POST /api/apagar`, protegido por CSRF y por el mismo origen local. El endpoint solo termina el proceso de la aplicación; no monta `/var/run/docker.sock`, no ejecuta Docker y no intenta controlar el host. Esto evita convertir la aplicación web en un controlador privilegiado del equipo.

Para que el botón funcione, los servicios `app` y `app-external` usan `restart: "no"`. El servicio `ollama` del perfil `bundled` puede permanecer vivo hasta que el usuario ejecute los scripts `detener.*` o `docker compose down`.

## Interfaz bilingüe

La traducción ES/EN se realiza en el frontend para la interfaz y en el backend para la salida del modelo. El idioma activo se envía como `idioma_salida` en cada análisis, y el prompt de extracción instruye al modelo para redactar los valores propuestos en ese idioma. Las evidencias se mantienen como fragmentos literales del documento original para no romper la trazabilidad ni la localización de spans.

Esto no duplica los esquemas YAML ni sustituye una localización normativa completa de ISAD(G), ISAAR(CPF), ISDF o ISDIAH; los campos y las instrucciones base siguen definidos en los YAML, pero la redacción de las propuestas se controla por el idioma seleccionado en la interfaz.
