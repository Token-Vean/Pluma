"""
Cliente Ollama para PlumA.

El diseño presupone procesamiento local. Por defecto solo se permite conectar
con Ollama en loopback, host.docker.internal o el servicio Docker interno
"ollama". Si se quiere usar un endpoint remoto, debe declararse explícitamente
ALLOW_REMOTE_OLLAMA=true, porque eso puede enviar texto e imágenes de los
documentos fuera del equipo.
"""

from __future__ import annotations

import base64
import ipaddress
import logging
import os
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
ALLOW_REMOTE_OLLAMA = os.getenv("ALLOW_REMOTE_OLLAMA", "false").strip().lower() in {
    "1", "true", "yes", "si", "sí", "on",
}
TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "8192"))
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "32768"))

_HOSTS_LOCALES_PERMITIDOS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "ollama",  # nombre del servicio en la red interna de Docker Compose
}


def _validar_ollama_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.netloc:
        raise RuntimeError(
            "OLLAMA_URL debe ser una URL HTTP/HTTPS válida, por ejemplo "
            "http://localhost:11434."
        )
    if p.username or p.password:
        raise RuntimeError("OLLAMA_URL no debe incluir credenciales embebidas.")

    host = (p.hostname or "").lower()
    if ALLOW_REMOTE_OLLAMA:
        logger.warning(
            "ALLOW_REMOTE_OLLAMA=true: el contenido documental puede enviarse a %s", url
        )
        return

    if host in _HOSTS_LOCALES_PERMITIDOS:
        return

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise RuntimeError(
            "OLLAMA_URL apunta a un host no local. Por seguridad, esta herramienta "
            "solo permite Ollama local salvo que defina ALLOW_REMOTE_OLLAMA=true."
        ) from None

    if ip.is_loopback:
        return

    raise RuntimeError(
        "OLLAMA_URL apunta a una IP no local. Esto puede exfiltrar documentos. "
        "Use un Ollama local o defina ALLOW_REMOTE_OLLAMA=true bajo su responsabilidad."
    )


_validar_ollama_url(OLLAMA_URL)


# -----------------------------------------------------------------------------
# Llamadas al modelo
# -----------------------------------------------------------------------------

async def generar(
    prompt: str,
    modelo: str,
    imagenes: list[bytes] | None = None,
    formato_json: bool = True,
    temperatura: float = 0.1,
) -> str:
    """
    Llama al modelo y devuelve la respuesta como cadena.

    Si se pasan imágenes, se usa la ruta multimodal. Si formato_json=True se
    fuerza JSON nativo de Ollama. La temperatura baja privilegia salidas
    reproducibles frente a creatividad.
    """
    payload: dict[str, Any] = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperatura,
            "num_predict": NUM_PREDICT,
            "num_ctx": NUM_CTX,
        },
    }

    if formato_json:
        payload["format"] = "json"

    if imagenes:
        payload["images"] = [base64.b64encode(img).decode("ascii") for img in imagenes]

    async with httpx.AsyncClient(timeout=TIMEOUT) as cliente:
        resp = await cliente.post(f"{OLLAMA_URL}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        respuesta = data.get("response")
        if not isinstance(respuesta, str):
            raise RuntimeError("Ollama no devolvió una respuesta textual válida.")
        return respuesta


async def modelos_disponibles() -> list[str]:
    """Lista los modelos descargados localmente. Útil para la UI."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as cliente:
        resp = await cliente.get(f"{OLLAMA_URL}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", []) if isinstance(m, dict) and "name" in m]
