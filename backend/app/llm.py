"""
Cliente Ollama para PlumA.

A partir de v0.6, el comportamiento del asistente (system prompt) y los
parámetros de inferencia se leen de schemas/pluma-runtime.yaml y se
inyectan en cada llamada a /api/generate. PlumA ya no requiere un modelo
derivado creado en Ollama mediante `ollama create`; basta con que el
modelo base definido en MODELO_BASE exista localmente.

La release pública está bloqueada para procesamiento local. En modo
estricto, Ollama debe ser el servicio Docker interno `ollama` o
loopback en desarrollo controlado. No se aceptan endpoints remotos
aunque el usuario manipule `.env`.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

import httpx
import yaml

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
MODELO_POR_DEFECTO = os.getenv("MODELO_BASE", "gemma4:e2b")

RUNTIME_CONFIG_PATH = Path(
    os.getenv("PLUMA_RUNTIME_CONFIG", "/app/schemas/pluma-runtime.yaml")
)

validate_ollama_url(OLLAMA_URL)


# -----------------------------------------------------------------------------
# Carga perezosa del system prompt y parámetros desde YAML
# -----------------------------------------------------------------------------

_RUNTIME_CFG: dict[str, Any] | None = None


def _cargar_runtime() -> dict[str, Any]:
    """
    Lee schemas/pluma-runtime.yaml una sola vez por proceso y lo cachea.

    Devuelve un dict con dos claves:
        sistema  → str (system prompt completo)
        opciones → dict (parámetros de inferencia para el campo `options`
                   del payload de Ollama)
    """
    global _RUNTIME_CFG
    if _RUNTIME_CFG is not None:
        return _RUNTIME_CFG

    if not RUNTIME_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"No se encuentra la configuración de runtime en {RUNTIME_CONFIG_PATH}. "
            "Este fichero sustituye al antiguo Modelfile y es obligatorio."
        )

    contenido = yaml.safe_load(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    sistema = contenido.get("sistema")
    opciones = contenido.get("opciones") or {}

    if not isinstance(sistema, str) or not sistema.strip():
        raise RuntimeError(
            f"{RUNTIME_CONFIG_PATH}: falta la clave 'sistema' o está vacía."
        )
    if not isinstance(opciones, dict):
        raise RuntimeError(
            f"{RUNTIME_CONFIG_PATH}: la clave 'opciones' debe ser un mapa."
        )

    _RUNTIME_CFG = {"sistema": sistema.strip(), "opciones": opciones}
    logger.info(
        "Configuración de runtime cargada (%d caracteres de system, %d opciones)",
        len(_RUNTIME_CFG["sistema"]), len(_RUNTIME_CFG["opciones"]),
    )
    return _RUNTIME_CFG


# -----------------------------------------------------------------------------
# Llamadas al modelo
# -----------------------------------------------------------------------------

async def generar(
    prompt: str,
    modelo: str | None = None,
    imagenes: list[bytes] | None = None,
    formato_json: bool = True,
    temperatura: float | None = None,
) -> str:
    """
    Llama al modelo y devuelve la respuesta como cadena.

    Orden de precedencia de parámetros:
        argumento de función > variable de entorno > schemas/pluma-runtime.yaml

    Comportamiento:
      - `modelo` por defecto es MODELO_BASE del entorno (gemma4:e2b si no se
        define). Si el llamador pasa un nombre, se respeta.
      - El system prompt se carga de schemas/pluma-runtime.yaml en la primera
        llamada y se cachea en memoria.
      - Las opciones (temperature, top_p, top_k, repeat_penalty, num_ctx,
        stop) parten del YAML; OLLAMA_NUM_CTX y OLLAMA_NUM_PREDICT del
        entorno las pisan; un `temperatura` explícito pisa el YAML.
      - Si formato_json=True se fuerza JSON nativo de Ollama.
      - Si se pasan imágenes, se usa la ruta multimodal.
    """
    cfg = _cargar_runtime()

    opciones: dict[str, Any] = dict(cfg["opciones"])
    opciones["num_ctx"] = NUM_CTX
    opciones["num_predict"] = NUM_PREDICT
    if temperatura is not None:
        opciones["temperature"] = temperatura

    payload: dict[str, Any] = {
        "model": modelo or MODELO_POR_DEFECTO,
        "prompt": prompt,
        "system": cfg["sistema"],
        "stream": False,
        "options": opciones,
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
