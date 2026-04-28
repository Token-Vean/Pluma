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

API de creación de modelos:
    Ollama 0.5+ cambió el formato de POST /api/create. Ya no acepta
    el Modelfile como texto en un parámetro "modelfile". Ahora espera
    los campos desagregados: from (modelo base), system (prompt),
    parameters (dict), messages (few-shot). Este módulo parsea el
    Modelfile localmente y lo envía en el formato nuevo.
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
MODELO_NOMBRE = os.getenv("MODELO_NOMBRE", "pluma:0.5.0")
MODELFILE_PATH = Path(os.getenv("MODELFILE_PATH", "/app/Modelfile"))
PERFIL = os.getenv("PERFIL", "bundled-local-locked").strip().lower()

estado: dict = {
    "fase": "iniciando",
    "mensaje": "",
    "listo": False,
    "perfil": PERFIL,
    "ollama_mode": PLUMA_OLLAMA_MODE,
    "ollama_url": OLLAMA_URL,
    "modelo_base": MODELO_BASE,
    "modelo_nombre": MODELO_NOMBRE,
}


# =============================================================================
# Timeouts
# =============================================================================

def _timeout_rapido() -> httpx.Timeout:
    return httpx.Timeout(10.0)

def _timeout_largo() -> httpx.Timeout:
    # Timeout alto pero finito: evita instalaciones colgadas indefinidamente
    # si Ollama queda bloqueado durante pull/create.
    return httpx.Timeout(connect=10.0, read=3600.0, write=30.0, pool=10.0)


# =============================================================================
# Orquestación
# =============================================================================

async def preparar() -> None:
    try:
        await _esperar_ollama()

        # Si el modelo especializado ya existe (por ejemplo, importado desde
        # GGUF offline o creado previamente en Ollama local del usuario), no
        # forzamos la descarga del modelo base. Esto evita descargas duplicadas
        # y respeta instalaciones locales ya preparadas.
        if await _modelo_existe(MODELO_NOMBRE):
            estado.update(
                fase="listo",
                mensaje=f"Modelo especializado {MODELO_NOMBRE} disponible",
                listo=True,
            )
            logger.info("Bootstrap omitido: %s ya existe", MODELO_NOMBRE)
            return

        await _asegurar_modelo_base()
        await _crear_modelo_derivado()
        estado.update(fase="listo", mensaje="Todo preparado", listo=True)
        logger.info("Bootstrap completado: %s disponible", MODELO_NOMBRE)
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
# Parseo del Modelfile y creación del modelo derivado
# =============================================================================

def _parsear_modelfile(texto: str) -> dict:
    """
    Parsea un Modelfile y devuelve un dict con las claves que espera la
    API nueva de Ollama:

        from        → modelo base (string)
        system      → system prompt (string)
        parameters  → dict de parámetros (temperature, top_p, etc.)
        messages    → lista de mensajes few-shot [{role, content}, ...]

    Soporta las directivas Modelfile que usamos: FROM, SYSTEM, PARAMETER,
    MESSAGE. Las líneas que empiezan por # se ignoran.

    Los bloques SYSTEM y MESSAGE pueden ir entre triples comillas (\"\"\") o
    en una sola línea.
    """
    resultado: dict = {
        "from": None,
        "system": None,
        "parameters": {},
        "messages": [],
    }

    i = 0
    lineas = texto.splitlines()

    while i < len(lineas):
        linea = lineas[i].strip()

        # Ignorar comentarios y líneas vacías a nivel de directiva
        if not linea or linea.startswith("#"):
            i += 1
            continue

        partes = linea.split(None, 1)
        directiva = partes[0].upper()
        resto = partes[1] if len(partes) > 1 else ""

        if directiva == "FROM":
            resultado["from"] = resto.strip()
            i += 1

        elif directiva == "PARAMETER":
            # PARAMETER nombre valor
            partes_param = resto.split(None, 1)
            if len(partes_param) == 2:
                nombre, valor = partes_param
                resultado["parameters"].setdefault(nombre, [])
                # Convertir a tipo apropiado
                valor_conv = _convertir_valor_parametro(valor.strip())
                # Ollama soporta que el mismo parámetro aparezca varias veces
                # (ej. múltiples `stop`). Acumulamos en lista.
                if isinstance(resultado["parameters"][nombre], list):
                    resultado["parameters"][nombre].append(valor_conv)
                else:
                    resultado["parameters"][nombre] = [resultado["parameters"][nombre], valor_conv]
            i += 1

        elif directiva == "SYSTEM":
            contenido, i = _leer_bloque(resto, lineas, i)
            resultado["system"] = contenido.strip()

        elif directiva == "MESSAGE":
            # MESSAGE rol contenido
            partes_msg = resto.split(None, 1)
            if not partes_msg:
                i += 1
                continue
            rol = partes_msg[0]
            contenido_inicial = partes_msg[1] if len(partes_msg) > 1 else ""
            contenido, i = _leer_bloque(contenido_inicial, lineas, i)
            resultado["messages"].append({
                "role": rol,
                "content": contenido.strip(),
            })

        else:
            # Directiva no reconocida: la saltamos con un warning
            logger.warning("Directiva Modelfile no reconocida: %s", directiva)
            i += 1

    # Colapsar parámetros con un único valor: la API admite escalar o lista
    for k, v in list(resultado["parameters"].items()):
        if isinstance(v, list) and len(v) == 1:
            resultado["parameters"][k] = v[0]

    return resultado


def _leer_bloque(inicio: str, lineas: list[str], i: int) -> tuple[str, int]:
    """
    Lee un valor que puede ser de una línea o de un bloque entre triples
    comillas. Devuelve (contenido, nuevo_índice).

    Soporta:
        DIRECTIVA \"\"\"
        contenido
        multilinea
        \"\"\"
    Y también:
        DIRECTIVA \"\"\"contenido en una línea\"\"\"
    Y también:
        DIRECTIVA contenido simple
    """
    # Caso 1: empieza con triples comillas
    if inicio.startswith('"""'):
        despues = inicio[3:]
        # Caso 1a: triples comillas de cierre en la misma línea
        if despues.endswith('"""') and len(despues) >= 3:
            return despues[:-3], i + 1
        # Caso 1b: bloque multilínea
        partes = [despues] if despues else []
        i += 1
        while i < len(lineas):
            linea = lineas[i]
            if linea.rstrip().endswith('"""'):
                # Quitar las comillas finales y añadir el resto
                partes.append(linea.rstrip()[:-3].rstrip() if linea.rstrip() != '"""' else "")
                i += 1
                return "\n".join(partes), i
            partes.append(linea)
            i += 1
        # EOF sin cierre: devolvemos lo que haya
        return "\n".join(partes), i

    # Caso 2: valor en la misma línea, sin comillas triples
    return inicio, i + 1


def _convertir_valor_parametro(v: str):
    """Convierte el string de un parámetro al tipo apropiado."""
    # Quitar comillas si las hay
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    # Numérico
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


async def _crear_modelo_derivado() -> None:
    """
    Crea el modelo especializado a partir del Modelfile, usando el
    formato nuevo de la API de Ollama (0.5+).
    """
    if await _modelo_existe(MODELO_NOMBRE):
        logger.info("Modelo derivado %s ya existe", MODELO_NOMBRE)
        return

    if not MODELFILE_PATH.exists():
        raise FileNotFoundError(f"No se encuentra el Modelfile en {MODELFILE_PATH}")

    estado.update(
        fase="creando_modelo",
        mensaje=f"Creando modelo especializado {MODELO_NOMBRE}...",
    )
    logger.info("Creando %s desde %s", MODELO_NOMBRE, MODELFILE_PATH)

    contenido = MODELFILE_PATH.read_text(encoding="utf-8")
    parsed = _parsear_modelfile(contenido)

    # MODELO_BASE del .env tiene prioridad sobre el FROM del Modelfile,
    # porque es la elección explícita del usuario. El FROM del Modelfile
    # queda como valor por defecto si MODELO_BASE no está definido.
    modelo_base = MODELO_BASE or parsed["from"]
    if parsed["from"] and parsed["from"] != modelo_base:
        logger.info(
            "Usando MODELO_BASE=%s del .env (el Modelfile sugería %s)",
            modelo_base, parsed["from"],
        )

    payload: dict = {
        "model": MODELO_NOMBRE,
        "from": modelo_base,
    }
    if parsed["system"]:
        payload["system"] = parsed["system"]
    if parsed["parameters"]:
        payload["parameters"] = parsed["parameters"]
    if parsed["messages"]:
        payload["messages"] = parsed["messages"]

    logger.info("Creando modelo con: from=%s, system=%d chars, params=%d, messages=%d",
                modelo_base,
                len(payload.get("system", "")),
                len(payload.get("parameters", {})),
                len(payload.get("messages", [])))

    async with httpx.AsyncClient(timeout=_timeout_largo()) as cliente:
        async with cliente.stream(
            "POST",
            f"{OLLAMA_URL}/api/create",
            json=payload,
        ) as resp:
            if resp.status_code >= 400:
                # Capturar el cuerpo del error para dar un mensaje útil
                cuerpo = b""
                async for chunk in resp.aiter_bytes():
                    cuerpo += chunk
                    if len(cuerpo) > 2000:
                        break
                raise RuntimeError(
                    f"Error {resp.status_code} creando el modelo derivado: "
                    f"{cuerpo.decode('utf-8', errors='replace')[:500]}"
                )

            async for linea in resp.aiter_lines():
                if linea:
                    logger.debug("create: %s", linea[:150])


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
