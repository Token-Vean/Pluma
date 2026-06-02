"""
Preparación automática del entorno LLM.

Se ejecuta al arrancar la aplicación. Idempotente: si todo está ya
listo, termina en milisegundos. Si falta algo, lo prepara.

Comportamiento de la release pública:

    bundled-local-locked → Ollama corre en local. Por defecto se usa el servicio
                           Docker interno `ollama`; si el instalador detecta que
                           el modelo base ya existe en Ollama de Windows/macOS,
                           se permite `host.docker.internal` como endpoint local
                           para evitar descargas duplicadas.

A partir de v0.6 PlumA NO crea un modelo derivado en Ollama. El system
prompt y los parámetros de inferencia los inyecta el backend en cada
llamada desde schemas/pluma-runtime.yaml. Este módulo se limita a:
    1. Verificar que la configuración de runtime existe.
    2. Esperar a que Ollama responda.
    3. Garantizar que el modelo base (MODELO_BASE) está disponible.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
PLUMA_OLLAMA_MODE = os.getenv("PLUMA_OLLAMA_MODE", "container")
MODELO_BASE = os.getenv("MODELO_BASE", "gemma4:e2b")
PERFIL = os.getenv("PERFIL", "bundled-local-locked").strip().lower()
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
}


# =============================================================================
# Timeouts
# =============================================================================

def _timeout_rapido() -> httpx.Timeout:
    return httpx.Timeout(10.0)

def _timeout_largo() -> httpx.Timeout:
    # Timeout alto pero finito: evita instalaciones colgadas indefinidamente
    # si Ollama queda bloqueado durante pull.
    return httpx.Timeout(connect=10.0, read=3600.0, write=30.0, pool=10.0)


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
        await _asegurar_modelo_base()
        estado.update(fase="listo", mensaje="Todo preparado", listo=True)
        logger.info("Bootstrap completado: modelo base %s disponible", MODELO_BASE)
    except Exception as e:
        estado.update(fase="error", mensaje=str(e), listo=False)
        logger.exception("Fallo en el bootstrap")


# -----------------------------------------------------------------------------
async def _esperar_ollama(intentos: int = 30, espera: float = 2.0) -> None:
    estado.update(fase="esperando_ollama", mensaje="Esperando al motor de IA...")

    async with httpx.AsyncClient(timeout=_timeout_rapido()) as cliente:
        for _ in range(intentos):
            try:
                r = await cliente.get(f"{OLLAMA_URL}/api/tags")
                if r.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(espera)

    raise RuntimeError(f"Ollama no responde en {OLLAMA_URL} tras {intentos * espera:.0f}s")


# -----------------------------------------------------------------------------
async def _asegurar_modelo_base() -> None:
    if await _modelo_existe(MODELO_BASE):
        logger.info("Modelo base %s disponible", MODELO_BASE)
        return

    if PERFIL == "external":
        raise RuntimeError(
            "El perfil external no está disponible en la release pública de PlumA. "
            "Use el despliegue local bloqueado con Ollama dentro de Docker."
        )

    estado.update(
        fase="descargando_modelo",
        mensaje=f"Descargando {MODELO_BASE}, primera ejecución (puede tardar varios minutos)...",
    )
    logger.info("Descargando %s...", MODELO_BASE)

    async with httpx.AsyncClient(timeout=_timeout_largo()) as cliente:
        async with cliente.stream(
            "POST", f"{OLLAMA_URL}/api/pull", json={"model": MODELO_BASE}
        ) as resp:
            resp.raise_for_status()
            async for linea in resp.aiter_lines():
                if linea:
                    logger.debug("pull: %s", linea[:100])


# =============================================================================
# Utilidades
# =============================================================================

async def _modelo_existe(nombre: str) -> bool:
    modelos = await _listar_modelos()
    return nombre in modelos or f"{nombre}:latest" in modelos


async def _listar_modelos() -> list[str]:
    async with httpx.AsyncClient(timeout=_timeout_rapido()) as cliente:
        r = await cliente.get(f"{OLLAMA_URL}/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
