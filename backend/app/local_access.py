"""
Protección de exposición local.

PlumA está diseñada para uso local/monousuario. Esta capa rechaza accesos
cuyo encabezado Host no apunte a loopback, salvo que se active de forma
explícita ALLOW_NETWORK_EXPOSURE=true. No sustituye autenticación; evita
que un cambio accidental en Docker/uvicorn convierta la aplicación en un
servicio de red sin controles adicionales.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "[::1]"}
VALORES_TRUE = {"1", "true", "yes", "si", "sí", "on"}


def _env_true(nombre: str, defecto: str = "false") -> bool:
    return os.getenv(nombre, defecto).strip().lower() in VALORES_TRUE


def exposicion_red_permitida() -> bool:
    return _env_true("ALLOW_NETWORK_EXPOSURE")


def _host_header_local(host_header: str | None) -> bool:
    if not host_header:
        return False
    try:
        parsed = urlparse(f"//{host_header}")
    except Exception:
        return False
    return parsed.hostname in HOSTS_LOCALES


class ProteccionAccesoLocal(BaseHTTPMiddleware):
    """Bloquea peticiones cuyo Host no sea local salvo opt-in explícito."""

    async def dispatch(self, request: Request, call_next):
        if exposicion_red_permitida():
            return await call_next(request)

        host_header = request.headers.get("host")
        if not _host_header_local(host_header):
            logger.warning(
                "Solicitud rechazada por Host no local: host=%r path=%s",
                host_header,
                request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "PlumA está configurada para uso local. "
                        "Acceda mediante http://localhost o http://127.0.0.1, "
                        "o active ALLOW_NETWORK_EXPOSURE=true bajo su responsabilidad."
                    )
                },
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )

        return await call_next(request)
