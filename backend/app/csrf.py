"""
Protección contra Cross-Site Request Forgery (CSRF).

Capas:
    1. Origin / Referer check para peticiones mutadoras.
    2. Coincidencia exacta con el Host local de la aplicación.
    3. Token sincronizado en cabecera X-CSRF-Token.

Diseño monousuario/local: los tokens viven en memoria, tienen TTL y el
almacén está acotado para que /api/csrf no pueda crecer indefinidamente.
CSRF no es autenticación; no debe usarse como control de acceso en red.
"""

from __future__ import annotations

import hmac
import logging
import secrets
import threading
import time
from urllib.parse import urlparse

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


# =============================================================================
# Configuración
# =============================================================================

HOSTS_PERMITIDOS: set[str] = {
    "localhost",
    "127.0.0.1",
    "[::1]",
    "::1",
}

ESQUEMAS_PERMITIDOS: set[str] = {"http"}
METODOS_MUTADORES = {"POST", "PUT", "PATCH", "DELETE"}

RUTAS_EXENTAS = {
    "/api/estado",
    "/api/csrf",
}

TOKEN_TTL_SEGUNDOS = 8 * 60 * 60
MAX_TOKENS_VALIDOS = 16


def _host_local_valido(host: str | None) -> bool:
    if not host:
        return False
    try:
        p = urlparse(f"//{host}")
    except Exception:
        return False
    hostname = p.hostname
    return hostname in HOSTS_PERMITIDOS


def _origen_coincide_con_host(origen: str, request: Request) -> bool:
    """
    Exige que Origin/Referer sea exactamente el mismo origen local de la app.

    Ejemplo válido: Host localhost:8082 y Origin http://localhost:8082.
    Ejemplo rechazado: Host localhost:8082 y Origin http://localhost:9999.
    """
    try:
        origen_p = urlparse(origen)
    except Exception:
        return False

    if origen_p.scheme not in ESQUEMAS_PERMITIDOS:
        return False

    host_header = request.headers.get("host")
    if not _host_local_valido(host_header):
        return False

    host_p = urlparse(f"//{host_header}")
    if origen_p.hostname not in HOSTS_PERMITIDOS:
        return False

    if origen_p.hostname != host_p.hostname:
        return False

    # Si no hay puerto en el origen, se asume el puerto HTTP por defecto.
    origen_puerto = origen_p.port or (80 if origen_p.scheme == "http" else 443)
    host_puerto = host_p.port or (80 if origen_p.scheme == "http" else 443)
    return origen_puerto == host_puerto


# =============================================================================
# Almacén de tokens
# =============================================================================

_tokens_validos: dict[str, float] = {}
_tokens_lock = threading.Lock()


def _purgar_tokens(now: float | None = None) -> None:
    now = now or time.time()
    caducados = [
        token for token, emitido in _tokens_validos.items()
        if now - emitido > TOKEN_TTL_SEGUNDOS
    ]
    for token in caducados:
        _tokens_validos.pop(token, None)

    # Cap de memoria: conservar los más recientes.
    while len(_tokens_validos) > MAX_TOKENS_VALIDOS:
        mas_antiguo = min(_tokens_validos, key=_tokens_validos.get)
        _tokens_validos.pop(mas_antiguo, None)


def generar_token() -> str:
    """Emite un token CSRF nuevo y descarta tokens caducados/antiguos."""
    token = secrets.token_urlsafe(32)
    with _tokens_lock:
        _purgar_tokens()
        _tokens_validos[token] = time.time()
        _purgar_tokens()
    return token


def token_valido(candidato: str | None) -> bool:
    """Verifica si un token está vivo. Timing-safe frente a tokens válidos."""
    if not candidato:
        return False

    with _tokens_lock:
        _purgar_tokens()
        tokens = list(_tokens_validos.keys())

    encontrado = False
    for valido in tokens:
        if hmac.compare_digest(candidato, valido):
            encontrado = True
    return encontrado


# =============================================================================
# Comprobaciones
# =============================================================================

def _extraer_origen(request: Request) -> str | None:
    """Devuelve el origen de la petición. Prefiere Origin; usa Referer como fallback."""
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")

    referer = request.headers.get("referer")
    if referer:
        try:
            p = urlparse(referer)
            if p.scheme and p.netloc:
                return f"{p.scheme}://{p.netloc}"
        except Exception:
            pass

    return None


def _peticion_exenta(request: Request) -> bool:
    if request.method not in METODOS_MUTADORES:
        return True
    if request.url.path in RUTAS_EXENTAS:
        return True
    return False


def _respuesta_403(mensaje: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": mensaje},
        headers={"Cache-Control": "no-store"},
    )


# =============================================================================
# Middleware
# =============================================================================

class ProteccionCSRF(BaseHTTPMiddleware):
    """Rechaza peticiones mutadoras sin Origin/Referer local y token válido."""

    async def dispatch(self, request: Request, call_next):
        if _peticion_exenta(request):
            return await call_next(request)

        sec_fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if sec_fetch_site == "cross-site":
            logger.warning(
                "CSRF: petición %s %s rechazada (Sec-Fetch-Site=cross-site)",
                request.method, request.url.path,
            )
            return _respuesta_403(
                "Petición rechazada: origen cruzado no permitido. PlumA solo acepta acciones desde su propia interfaz local."
            )

        origen = _extraer_origen(request)
        if origen is None:
            logger.warning(
                "CSRF: petición %s %s rechazada (sin Origin ni Referer)",
                request.method, request.url.path,
            )
            return _respuesta_403(
                "Petición rechazada: falta cabecera Origin. "
                "Si está usando la aplicación desde el navegador en localhost, recargue la página."
            )
        if not _origen_coincide_con_host(origen, request):
            logger.warning(
                "CSRF: petición %s %s rechazada (origen no coincide: %s; host: %s)",
                request.method, request.url.path, origen, request.headers.get("host"),
            )
            return _respuesta_403(
                f"Petición rechazada: origen no permitido ({origen}). "
                "Esta aplicación solo acepta peticiones desde su propio origen local."
            )

        token = request.headers.get("x-csrf-token")
        if not token_valido(token):
            logger.warning(
                "CSRF: petición %s %s rechazada (token inválido o ausente)",
                request.method, request.url.path,
            )
            return _respuesta_403(
                "Petición rechazada: token CSRF ausente, caducado o inválido. "
                "Recargue la página para obtener un token nuevo."
            )

        return await call_next(request)
