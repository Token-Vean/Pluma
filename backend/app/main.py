"""
Punto de entrada de la aplicación FastAPI.

Lanza el bootstrap en segundo plano (para que el servidor responda
enseguida mientras se descarga el modelo la primera vez) y monta los
endpoints de la API más el frontend estático.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import api, bootstrap
from .local_access import ProteccionAccesoLocal
from .version import APP_NAME, APP_VERSION
from .api import CabecerasSeguridad, LimiteCuerpoPeticion
from .csrf import ProteccionCSRF

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Bootstrap en segundo plano; la UI hace polling de /api/estado."""
    tarea = asyncio.create_task(bootstrap.preparar())
    yield
    if not tarea.done():
        tarea.cancel()


app = FastAPI(
    title=APP_NAME,
    description="Descripción asistida por IA según normas del CIA",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Middlewares. Se aplican en orden inverso al de registro: el último
# añadido es el primero en procesar la petición entrante. Queremos que
# la protección CSRF se aplique primero (rechaza antes de que nada más
# procese la petición), y que las cabeceras de seguridad se añadan al
# final de la respuesta.
app.add_middleware(CabecerasSeguridad)
app.add_middleware(ProteccionCSRF)
# Último middleware registrado = primero en recibir la petición. El límite
# de cuerpo debe actuar antes del parseo multipart/JSON de FastAPI.
app.add_middleware(LimiteCuerpoPeticion)
# Defensa adicional para evitar exposición accidental fuera de localhost.
app.add_middleware(ProteccionAccesoLocal)

app.include_router(api.router, prefix="/api")


@app.get("/api/estado")
async def estado():
    """Endpoint consultado por la UI durante el arranque inicial."""
    return bootstrap.estado


# Servir el frontend estático en la raíz cuando esté disponible.
# Durante el desarrollo del backend todavía no existe el frontend real;
# en ese caso servimos una página mínima de diagnóstico para que el
# usuario vea que la aplicación está viva y qué pasos faltan.
DIR_STATIC = Path("/app/static")

if DIR_STATIC.exists():
    app.mount("/", StaticFiles(directory=str(DIR_STATIC), html=True), name="ui")
else:
    logger.warning(
        "No se ha encontrado %s; sirviendo página de diagnóstico en su lugar. "
        "La API está disponible en /api.", DIR_STATIC,
    )

    from fastapi.responses import HTMLResponse

    PAGINA_DIAGNOSTICO = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>PlumA — backend listo</title>
<style>
  body {
    font-family: system-ui, -apple-system, sans-serif;
    max-width: 680px;
    margin: 60px auto;
    padding: 0 24px;
    line-height: 1.6;
    color: #1c1a16;
    background: #f5efe4;
  }
  h1 { font-weight: 500; }
  code {
    background: #ebe2cf;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.92em;
  }
  .estado {
    padding: 16px 20px;
    background: #faf6ee;
    border-left: 3px solid #8b2820;
    margin: 20px 0;
  }
  .ok { border-left-color: #6b8e3d; }
  pre {
    background: #faf6ee;
    padding: 14px;
    overflow-x: auto;
    font-size: 0.88em;
  }
</style>
</head>
<body>
<h1>PlumA</h1>
<p>El backend está funcionando correctamente en el puerto configurado.</p>

<div class="estado ok">
  <strong>API operativa.</strong> Consulta el estado detallado en
  <a href="/api/estado">/api/estado</a> o las normas disponibles en
  <a href="/api/normas">/api/normas</a>.
</div>

<p>Esta es una <strong>página de diagnóstico temporal</strong>. La
interfaz visual completa (la que muestra los campos de las normas,
los iconos de copia, el modo flotante, etc.) se publicará en la
siguiente fase del proyecto.</p>

<p>Mientras tanto, puedes probar la API directamente con una
herramienta como <code>curl</code> o Postman:</p>

<pre>TOKEN=$(curl -s http://localhost:8082/api/csrf | sed -E 's/.*"token":"([^"]+)".*/\1/')
curl -X POST http://localhost:8082/api/describir \\
  -H "X-CSRF-Token: $TOKEN" \\
  -H "Origin: http://localhost:8082" \\
  -F fichero=@documento.pdf \\
  -F norma=isad-g \\
  -F modo=esencial</pre>

<p>Los esquemas de las normas son editables en la carpeta
<code>schemas/</code> del proyecto.</p>
</body>
</html>
"""

    @app.get("/", response_class=HTMLResponse)
    async def pagina_diagnostico():
        return PAGINA_DIAGNOSTICO
