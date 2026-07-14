"""
Preparación automática del entorno LLM.

Se ejecuta al arrancar la aplicación. Idempotente: si todo está ya
listo, termina en milisegundos. Si falta algo, informa de forma cerrada.

Comportamiento de la release pública:

    host      → PlumA usa el Ollama nativo/local del usuario.
    container → PlumA usa el Ollama incluido en el perfil bundled de Compose.

A partir de esta versión PlumA no crea modelos derivados. El instalador puede
descargar el modelo base cuando activa el perfil bundled; el system prompt y
los parámetros de inferencia se inyectan en cada llamada desde
schemas/pluma-runtime.yaml. Este módulo se limita a:
    1. Verificar que la configuración de runtime existe.
    2. Esperar a que Ollama responda.
    3. Comprobar que hay al menos un modelo descargado en Ollama.
    4. Elegir modelo por defecto: gemma4:e2b si existe; si no, otro local.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx

from . import llm

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
PLUMA_OLLAMA_MODE = os.getenv("PLUMA_OLLAMA_MODE", "host")
MODELO_BASE = os.getenv("MODELO_BASE", "gemma4:e2b")
PERFIL = os.getenv("PERFIL", "host-local-locked").strip().lower()
RUNTIME_CONFIG_PATH = Path(
    os.getenv("PLUMA_RUNTIME_CONFIG", "/app/schemas/pluma-runtime.yaml")
)

estado: dict = {
    "fase": "iniciando",
    "mensaje": "",
    "listo": False,
    "perfil": PERFIL,
    "ollama_mode": PLUMA_OLLAMA_MODE,
    "ollama_url": OLLAMA_URL,
    "modelo_base": MODELO_BASE,
    "modelo_activo": None,
    "modelos": [],
}


# =============================================================================
# Timeouts
# =============================================================================

def _timeout_rapido() -> httpx.Timeout:
    return httpx.Timeout(10.0)


# =============================================================================
# Orquestación
# =============================================================================

async def preparar() -> None:
    try:
        if not RUNTIME_CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"No se encuentra la configuración de runtime en {RUNTIME_CONFIG_PATH}. "
                "Este fichero (schemas/pluma-runtime.yaml) sustituye al antiguo Modelfile "
                "y es obligatorio."
            )

        await _esperar_ollama()
        modelos = await _listar_modelos()
        elegido = llm.elegir_nombre_preferido(modelos)
        if not elegido:
            raise RuntimeError(
                "Ollama responde, pero no tiene ningún modelo descargado. "
                "Descargue uno, preferiblemente con `ollama pull gemma4:e2b`, "
                "o vuelva a ejecutar el instalador para preparar el perfil local."
            )
        estado.update(
            fase="listo",
            mensaje="Todo preparado",
            listo=True,
            modelos=modelos,
            modelo_base=elegido,
            modelo_activo=elegido,
        )
        logger.info("Bootstrap completado: Ollama local disponible; modelo activo %s", elegido)
    except Exception as e:
        estado.update(fase="error", mensaje=str(e), listo=False)
        logger.exception("Fallo en el bootstrap")


# -----------------------------------------------------------------------------
async def _esperar_ollama(intentos: int = 30, espera: float = 2.0) -> None:
    estado.update(fase="esperando_ollama", mensaje="Esperando al motor de IA local...")

    async with httpx.AsyncClient(timeout=_timeout_rapido()) as cliente:
        for _ in range(intentos):
            try:
                r = await cliente.get(f"{OLLAMA_URL}/api/tags")
                if r.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(espera)

    raise RuntimeError(
        f"Ollama no responde en {OLLAMA_URL} tras {intentos * espera:.0f}s. "
        "Compruebe que el motor Ollama local está iniciado."
    )


# =============================================================================
# Utilidades
# =============================================================================

async def _listar_modelos() -> list[str]:
    async with httpx.AsyncClient(timeout=_timeout_rapido()) as cliente:
        r = await cliente.get(f"{OLLAMA_URL}/api/tags")
        r.raise_for_status()
        modelos = []
        for m in r.json().get("models", []):
            if isinstance(m, dict) and isinstance(m.get("name"), str):
                modelos.append(m["name"])
        return modelos
