"""
Política de seguridad local de PlumA.

La release pública se distribuye como herramienta local/monousuario. Este
módulo centraliza el bloqueo de configuración para que la aplicación falle de
forma cerrada si alguien intenta reutilizarla como servicio en red o conectarla
a un endpoint LLM remoto.

Principios:
    - PLUMA_STRICT_LOCAL=true por defecto y en la release pública.
    - La aplicación solo acepta acceso desde localhost/loopback.
    - En modo estricto, Ollama debe ser local: servicio Docker interno
      `ollama` o loopback en desarrollo controlado.
    - No se aceptan cabeceras de proxy/reverse proxy en modo estricto.
    - Las variables ALLOW_* se consideran de desarrollo y se ignoran cuando
      PLUMA_STRICT_LOCAL=true.
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

VALORES_TRUE = {"1", "true", "yes", "si", "sí", "on"}
HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "[::1]"}
HOSTS_OLLAMA_ESTRICTOS = {
    "ollama",               # servicio Docker interno del paquete público
    "host.docker.internal", # Ollama local instalado en Windows/macOS, accesible desde Docker
    "localhost",            # útil en desarrollo local sin contenedor
    "127.0.0.1",
    "::1",
}
CABECERAS_PROXY_PROHIBIDAS = {
    "forwarded",
    "x-forwarded-host",
    "x-forwarded-server",
    "x-forwarded-for",
    "x-real-ip",
    "x-original-host",
}


def env_true(nombre: str, defecto: str = "false") -> bool:
    return os.getenv(nombre, defecto).strip().lower() in VALORES_TRUE


def strict_local_enabled() -> bool:
    return env_true("PLUMA_STRICT_LOCAL", "true")


def remote_ollama_allowed() -> bool:
    # En la release pública, el modo local estricto prevalece siempre.
    if strict_local_enabled():
        return False
    return env_true("ALLOW_REMOTE_OLLAMA", "false")


def network_exposure_allowed() -> bool:
    # En la release pública, el modo local estricto prevalece siempre.
    if strict_local_enabled():
        return False
    return env_true("ALLOW_NETWORK_EXPOSURE", "false")


def host_header_is_local(host_header: str | None) -> bool:
    if not host_header:
        return False
    try:
        parsed = urlparse(f"//{host_header}")
    except Exception:
        return False
    hostname = parsed.hostname
    if hostname in HOSTS_LOCALES:
        return True
    try:
        ip = ipaddress.ip_address(hostname or "")
    except ValueError:
        return False
    return ip.is_loopback


def has_forbidden_proxy_headers(headers) -> bool:
    if not strict_local_enabled():
        return False
    lower = {k.lower() for k in headers.keys()}
    return any(h in lower for h in CABECERAS_PROXY_PROHIBIDAS)


def validate_ollama_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme != "http" or not p.netloc:
        raise RuntimeError(
            "OLLAMA_URL debe ser una URL HTTP local válida. En la release pública "
            "se espera http://ollama:11434."
        )
    if p.username or p.password:
        raise RuntimeError("OLLAMA_URL no debe incluir credenciales embebidas.")

    host = (p.hostname or "").lower()

    if remote_ollama_allowed():
        return

    if strict_local_enabled():
        if host in HOSTS_OLLAMA_ESTRICTOS:
            return
        raise RuntimeError(
            "Configuración bloqueada: OLLAMA_URL apunta a un host no autorizado. "
            "La release pública de PlumA solo permite Ollama local: "
            "http://ollama:11434 o http://host.docker.internal:11434."
        )

    # Desarrollo no estricto: permitir solo loopback salvo opt-in remoto.
    if host in HOSTS_OLLAMA_ESTRICTOS:
        return
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise RuntimeError(
            "OLLAMA_URL apunta a un host no local. Active explícitamente "
            "ALLOW_REMOTE_OLLAMA=true solo en compilaciones de desarrollo."
        ) from None
    if ip.is_loopback:
        return
    raise RuntimeError("OLLAMA_URL apunta a una IP no local.")


def security_status() -> dict[str, object]:
    return {
        "strict_local": strict_local_enabled(),
        "network_exposure_allowed_effective": network_exposure_allowed(),
        "remote_ollama_allowed_effective": remote_ollama_allowed(),
        "forbidden_proxy_headers_rejected": strict_local_enabled(),
        "apagado_ui_permitido": env_true("PERMITIR_APAGADO_UI", "false"),
    }
