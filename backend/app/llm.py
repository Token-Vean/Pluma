"""
Cliente Ollama para PlumA.

La release pública está bloqueada para procesamiento local. En modo estricto,
Ollama debe ser el servicio Docker interno `ollama` o loopback en desarrollo
controlado. No se aceptan endpoints remotos aunque el usuario manipule `.env`.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx

from .security_policy import remote_ollama_allowed, validate_ollama_url

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
ALLOW_REMOTE_OLLAMA = remote_ollama_allowed()
TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

validate_ollama_url(OLLAMA_URL)

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
        if resp.is_error:
            detalle = (resp.text or "").strip().replace("\n", " ")[:1200]
            if resp.status_code >= 500:
                raise RuntimeError(
                    f"Ollama devolvió HTTP {resp.status_code} en /api/generate. "
                    f"La causa exacta debe comprobarse en los logs de Ollama; "
                    f"puede deberse a memoria insuficiente, formato de petición, tamaño de contexto "
                    f"o error interno del motor. Detalle: {detalle}"
                )
            raise RuntimeError(f"Ollama devolvió HTTP {resp.status_code}: {detalle}")
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
