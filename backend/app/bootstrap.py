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
    3. Comprobar que la versión de Ollama no está afectada por avisos de
       seguridad conocidos (VERSION_MINIMA_OLLAMA).
    4. Comprobar que hay al menos un modelo descargado en Ollama.
    5. Elegir modelo por defecto: gemma4:e2b si existe; si no, otro local.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path

import httpx

from . import llm

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
PLUMA_OLLAMA_MODE = os.getenv("PLUMA_OLLAMA_MODE", "host")
MODELO_BASE = os.getenv("MODELO_BASE", "gemma4:e2b")

def _es_modelo_cloud(nombre: str) -> bool:
    n = (nombre or "").strip().lower()
    if ":" not in n:
        return False
    tag = n.rsplit(":", 1)[1]
    return tag == "cloud" or tag.endswith("-cloud")

# v0.7.4: versión mínima de Ollama que admite PlumA. CVE-2026-103663 (CERT
# Polska): path traversal en /api/pull que permite escribir fuera del almacén
# de modelos y, con permisos de escritura en el directorio de bibliotecas
# (caso de la imagen Docker oficial), ejecución de código como root al
# reiniciar. Afecta a las versiones anteriores a 0.35.0. PlumA no llama a
# /api/pull, pero el instalador sí descarga modelos y en modo host se reutiliza
# el Ollama del usuario: un motor vulnerable deja de ser aceptable aunque
# PlumA no sea quien lo expone. Las versiones antiguas tampoco garantizan los
# metadatos remote_host/remote_model en los que se apoya la comprobación de
# modelo local. Subir este valor cuando un aviso nuevo lo requiera.
VERSION_MINIMA_OLLAMA: tuple[int, int, int] = (0, 35, 0)
_PATRON_VERSION = re.compile(r"^\s*v?(\d+)\.(\d+)\.(\d+)")

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
    "ollama_version": None,
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
        if _es_modelo_cloud(MODELO_BASE):
            raise RuntimeError(
                "PlumA no admite modelos cloud de Ollama en la release local. "
                "Use un modelo descargado localmente sin etiqueta :cloud."
            )
        if not RUNTIME_CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"No se encuentra la configuración de runtime en {RUNTIME_CONFIG_PATH}. "
                "Este fichero (schemas/pluma-runtime.yaml) sustituye al antiguo Modelfile "
                "y es obligatorio."
            )

        await _esperar_ollama()
        await _comprobar_version_ollama()
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

    async with llm.cliente_local(_timeout_rapido()) as cliente:
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


def parsear_version(texto: object) -> tuple[int, int, int] | None:
    """Convierte «0.40.17», «v0.35.0» o «0.40.17-rc3» en una tupla comparable."""
    if not isinstance(texto, str):
        return None
    coincidencia = _PATRON_VERSION.match(texto)
    if not coincidencia:
        return None
    return tuple(int(parte) for parte in coincidencia.groups())  # type: ignore[return-value]


def _texto_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(parte) for parte in version)


async def _comprobar_version_ollama() -> None:
    """Falla cerrado si Ollama no informa de su versión o es anterior a la mínima."""
    estado.update(fase="comprobando_ollama", mensaje="Comprobando la versión del motor de IA local...")
    minima = _texto_version(VERSION_MINIMA_OLLAMA)
    try:
        async with llm.cliente_local(_timeout_rapido()) as cliente:
            r = await cliente.get(f"{OLLAMA_URL}/api/version")
        datos = r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        datos = None
    texto = datos.get("version") if isinstance(datos, dict) else None
    version = parsear_version(texto)

    if PLUMA_OLLAMA_MODE == "container":
        remedio = (
            "Vuelva a ejecutar el instalador de esta versión de PlumA para actualizar "
            "el contenedor de Ollama."
        )
    else:
        remedio = (
            f"Actualice Ollama en este equipo a la versión {minima} o posterior "
            "(https://ollama.com/download), reinícielo y vuelva a iniciar PlumA."
        )

    if version is None:
        raise RuntimeError(
            "No se pudo comprobar la versión de Ollama (/api/version no responde o no "
            f"devuelve una versión reconocible). PlumA requiere Ollama {minima} o "
            f"posterior. {remedio}"
        )
    estado["ollama_version"] = _texto_version(version)
    if version < VERSION_MINIMA_OLLAMA:
        raise RuntimeError(
            f"Ollama {_texto_version(version)} está afectado por un aviso de seguridad "
            f"(CVE-2026-103663). PlumA requiere Ollama {minima} o posterior. {remedio}"
        )
    logger.info("Ollama %s cumple la versión mínima %s", _texto_version(version), minima)


# =============================================================================
# Utilidades
# =============================================================================

async def _listar_modelos() -> list[str]:
    async with llm.cliente_local(_timeout_rapido()) as cliente:
        r = await cliente.get(f"{OLLAMA_URL}/api/tags")
        r.raise_for_status()
        modelos = []
        for m in r.json().get("models", []):
            if isinstance(m, dict) and isinstance(m.get("name"), str):
                if not _es_modelo_cloud(m["name"]) and not llm.es_entrada_remota(m):
                    modelos.append(m["name"])
        return modelos
