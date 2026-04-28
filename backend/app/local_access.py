"""
Protección de acceso local.

PlumA se distribuye como herramienta local/monousuario. Esta capa rechaza
accesos cuyo encabezado Host no apunte a loopback y, en modo estricto, rechaza
cabeceras típicas de proxy inverso para evitar reutilizaciones accidentales como
servicio publicado en red.
"""

from __future__ import annotations

import logging

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .security_policy import (
    has_forbidden_proxy_headers,
    host_header_is_local,
    network_exposure_allowed,
    security_status,
)

logger = logging.getLogger(__name__)


def _respuesta_403(mensaje: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": mensaje, "security": security_status()},
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


class ProteccionAccesoLocal(BaseHTTPMiddleware):
    """Bloquea peticiones no locales salvo compilaciones de desarrollo no estrictas."""

    async def dispatch(self, request: Request, call_next):
        if network_exposure_allowed():
            return await call_next(request)

        if has_forbidden_proxy_headers(request.headers):
            logger.warning(
                "Solicitud rechazada por cabeceras de proxy en modo local estricto: path=%s",
                request.url.path,
            )
            return _respuesta_403(
                "PlumA está en modo local estricto y no acepta acceso mediante proxy, "
                "túnel o publicación en red. Abra la aplicación desde http://localhost."
            )

        host_header = request.headers.get("host")
        if not host_header_is_local(host_header):
            logger.warning(
                "Solicitud rechazada por Host no local: host=%r path=%s",
                host_header,
                request.url.path,
            )
            return _respuesta_403(
                "PlumA está bloqueada para uso local. Acceda mediante "
                "http://localhost o http://127.0.0.1. La release pública no está "
                "preparada para funcionar como servicio de red."
            )

        return await call_next(request)
