"""
Cliente Ollama para PlumA.

En la arquitectura v0.7.0, el comportamiento del asistente (system prompt) y los
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
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx
import yaml
from PIL import Image, ImageOps

from .security_policy import remote_ollama_allowed, validate_ollama_url

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
ALLOW_REMOTE_OLLAMA = remote_ollama_allowed()
TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
TIMEOUT_VISION = httpx.Timeout(
    connect=10.0,
    read=float(os.getenv("OLLAMA_VISION_TIMEOUT_SECONDS", "360")),
    write=60.0,
    pool=10.0,
)
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

# Perfil rápido para visión. La ruta multimodal de Ollama es mucho más costosa
# que la textual; por defecto PlumA reduce contexto, salida y tamaño de imagen
# para que el análisis visual sea operativo en equipos locales.
VISION_NUM_CTX = int(os.getenv("OLLAMA_VISION_NUM_CTX", "4096"))
VISION_NUM_PREDICT = int(os.getenv("OLLAMA_VISION_NUM_PREDICT", "350"))
VISION_MAX_LONG_EDGE = int(os.getenv("PLUMA_VISION_MAX_LONG_EDGE", "1280"))
VISION_JPEG_QUALITY = int(os.getenv("PLUMA_VISION_JPEG_QUALITY", "78"))
MODELO_POR_DEFECTO = os.getenv("MODELO_BASE", "gemma4:e2b")
MODELOS_PREFERIDOS = [
    m.strip()
    for m in os.getenv(
        "PLUMA_MODELOS_PREFERIDOS",
        "pluma-texto,gemma4:e2b,gemma3:12b,qwen2.5:7b-instruct,llama3.1:8b",
    ).split(",")
    if m.strip()
]

# Preferencias específicas para documentos visuales. No se debe inferir que un
# modelo descargado funciona correctamente con imágenes: algunos tags multimodales
# pueden responder bien a texto y fallar en visión. La lista prioriza Qwen porque
# se ha probado de forma más estable para documentos manuscritos/escaneados.
MODELOS_VISUALES_PREFERIDOS = [
    m.strip()
    for m in os.getenv(
        "PLUMA_MODELOS_VISUALES_PREFERIDOS",
        "pluma-vision,qwen3.5:latest,qwen3-vl:8b,qwen3-vl:4b,qwen2.5vl:7b,qwen2.5vl:3b,qwen2.5-vl:7b,qwen2.5-vl:3b,gemma4:e2b",
    ).split(",")
    if m.strip()
]

# Algunos modelos locales fallan en Ollama cuando se activa `format: "json"`
# porque el runtime aplica una gramática JSON estricta. En esos casos aparece
# un HTTP 500 con mensajes similares a "Unexpected empty grammar stack".
# Para priorizar compatibilidad local, PlumA usa por defecto modo JSON blando:
# instrucción estricta en prompt + validación defensiva posterior. Quien quiera
# forzar el modo nativo puede definir PLUMA_OLLAMA_JSON_MODE=native.
OLLAMA_JSON_MODE = os.getenv("PLUMA_OLLAMA_JSON_MODE", "soft").strip().lower()

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
# Optimización visual local
# -----------------------------------------------------------------------------

def _opciones_para_vision(opciones_base: dict[str, Any], temperatura: float | None) -> dict[str, Any]:
    """Devuelve opciones conservadoras para llamadas con imágenes."""
    opciones = dict(opciones_base)
    opciones["num_ctx"] = VISION_NUM_CTX
    opciones["num_predict"] = VISION_NUM_PREDICT
    opciones["temperature"] = 0.1 if temperatura is None else temperatura
    return opciones


def _optimizar_imagen_para_vision(imagen: bytes) -> bytes:
    """
    Reduce imágenes antes de enviarlas a Ollama.

    Los modelos de visión pueden funcionar con escaneos grandes, pero el coste
    local se dispara. Esta normalización mantiene legibilidad suficiente para
    cabeceras y primeras líneas, y evita enviar TIFF/PNG enormes al runtime.
    Si Pillow no puede abrir la imagen, se devuelve el binario original.
    """
    if not imagen:
        return imagen
    try:
        with Image.open(io.BytesIO(imagen)) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode not in {"RGB", "L"}:
                im = im.convert("RGB")
            elif im.mode == "L":
                im = im.convert("RGB")

            ancho, alto = im.size
            lado_mayor = max(ancho, alto)
            if lado_mayor > VISION_MAX_LONG_EDGE:
                escala = VISION_MAX_LONG_EDGE / float(lado_mayor)
                nuevo = (max(1, int(ancho * escala)), max(1, int(alto * escala)))
                im = im.resize(nuevo, Image.Resampling.LANCZOS)

            out = io.BytesIO()
            calidad = max(45, min(95, VISION_JPEG_QUALITY))
            im.save(out, format="JPEG", quality=calidad, optimize=True)
            return out.getvalue()
    except Exception as exc:
        logger.debug("No se pudo optimizar imagen para visión: %s", exc)
        return imagen


# -----------------------------------------------------------------------------
# Compatibilidad JSON
# -----------------------------------------------------------------------------

def _reforzar_prompt_json(prompt: str) -> str:
    """
    Añade una instrucción técnica para obtener JSON sin usar la gramática nativa
    de Ollama. Esto evita errores del runtime en modelos que emiten tokens
    incompatibles con `format: "json"`.
    """
    return (
        prompt.rstrip()
        + "\n\nINSTRUCCIÓN TÉCNICA DE SALIDA:\n"
        + "Responde con un único objeto JSON válido. "
        + "No añadas markdown, comentarios, explicación, texto previo ni texto posterior."
    )


def _es_error_gramatica_json_ollama(status_code: int, detalle: str) -> bool:
    if status_code < 500:
        return False
    d = (detalle or "").lower()
    patrones = (
        "grammar",
        "empty grammar stack",
        "unexpected empty grammar",
        "unused",
        "llama_decode",
    )
    return any(p in d for p in patrones)


def _respuesta_contiene_tokens_invalidos(texto: str) -> bool:
    """Detecta salidas anómalas típicas de ruta visual rota en Ollama."""
    if not isinstance(texto, str) or not texto:
        return False
    total = len(texto)
    apariciones = re.findall(r"<unused\d+>", texto)
    if not apariciones:
        return False
    longitud_tokens = sum(len(x) for x in apariciones)
    return len(apariciones) >= 3 or (total > 0 and longitud_tokens / total > 0.2)


def _validar_respuesta_modelo(texto: str, *, endpoint: str, modelo: str) -> str:
    if _respuesta_contiene_tokens_invalidos(texto):
        raise RuntimeError(
            f"El modelo {modelo} devolvió tokens internos <unused...> en {endpoint}. "
            "La ruta de visión del modelo no parece utilizable para este documento. "
            "Seleccione otro modelo multimodal de Ollama, por ejemplo qwen3.5:latest, "
            "o procese una versión con texto/OCR."
        )
    return texto


def extraer_json_texto(texto: str) -> str:
    """
    Devuelve el primer objeto JSON válido contenido en una respuesta del modelo.

    No confía en que el modelo cumpla exactamente la instrucción de salida: puede
    envolver el JSON en ```json, añadir una frase previa o texto posterior. Esta
    función localiza el primer objeto balanceado y lo valida con json.loads.
    """
    if not isinstance(texto, str):
        return texto

    limpio = texto.strip()
    if not limpio:
        return limpio

    # Caso ideal: ya es JSON válido.
    try:
        json.loads(limpio)
        return limpio
    except json.JSONDecodeError:
        pass

    # Eliminar cercas markdown frecuentes sin depender de ellas.
    limpio = re.sub(r"^```(?:json)?\s*", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\s*```$", "", limpio).strip()
    try:
        json.loads(limpio)
        return limpio
    except json.JSONDecodeError:
        pass

    inicio = limpio.find("{")
    if inicio < 0:
        return texto

    en_cadena = False
    escape = False
    profundidad = 0
    for i in range(inicio, len(limpio)):
        ch = limpio[i]
        if en_cadena:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                en_cadena = False
            continue

        if ch == '"':
            en_cadena = True
        elif ch == "{":
            profundidad += 1
        elif ch == "}":
            profundidad -= 1
            if profundidad == 0:
                candidato = limpio[inicio : i + 1]
                try:
                    json.loads(candidato)
                    return candidato
                except json.JSONDecodeError:
                    return texto

    return texto


def _log_metricas_ollama(data: dict[str, Any], endpoint: str, modelo: str) -> None:
    """Registra las métricas de tiempo que devuelve Ollama en cada respuesta.
    Diagnóstico de rendimiento: 'gen' en tok/s indica si el modelo corre en
    GPU (decenas de tok/s) o CPU (unos pocos); 'carga' alto en cada llamada
    indica que el modelo se recarga entre peticiones (keep_alive no efectivo)."""
    try:
        ns = 1_000_000_000
        total = (data.get("total_duration") or 0) / ns
        carga = (data.get("load_duration") or 0) / ns
        pe_c = data.get("prompt_eval_count") or 0
        pe_d = (data.get("prompt_eval_duration") or 0) / ns
        ev_c = data.get("eval_count") or 0
        ev_d = (data.get("eval_duration") or 0) / ns
        gen_tps = (ev_c / ev_d) if ev_d else 0.0
        pe_tps = (pe_c / pe_d) if pe_d else 0.0
        logger.info(
            "Ollama %s modelo=%s total=%.1fs carga=%.1fs prompt=%d tok (%.1f tok/s) gen=%d tok (%.1f tok/s)",
            endpoint, modelo, total, carga, pe_c, pe_tps, ev_c, gen_tps,
        )
    except Exception:
        pass


async def _post_generate(cliente: httpx.AsyncClient, payload: dict[str, Any]) -> str:
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
    _log_metricas_ollama(data, "/api/generate", str(payload.get("model") or ""))
    respuesta = data.get("response")
    if not isinstance(respuesta, str):
        raise RuntimeError("Ollama no devolvió una respuesta textual válida.")
    return _validar_respuesta_modelo(
        respuesta,
        endpoint="/api/generate",
        modelo=str(payload.get("model") or ""),
    )


async def _post_chat(cliente: httpx.AsyncClient, payload: dict[str, Any]) -> str:
    resp = await cliente.post(f"{OLLAMA_URL}/api/chat", json=payload)
    if resp.is_error:
        detalle = (resp.text or "").strip().replace("\n", " ")[:1200]
        if resp.status_code >= 500:
            raise RuntimeError(
                f"Ollama devolvió HTTP {resp.status_code} en /api/chat. "
                f"La causa exacta debe comprobarse en los logs de Ollama; "
                f"puede deberse a memoria insuficiente, formato de petición, tamaño de contexto "
                f"o error interno del motor. Detalle: {detalle}"
            )
        raise RuntimeError(f"Ollama devolvió HTTP {resp.status_code}: {detalle}")
    data = resp.json()
    _log_metricas_ollama(data, "/api/chat", str(payload.get("model") or ""))
    mensaje = data.get("message")
    respuesta = mensaje.get("content") if isinstance(mensaje, dict) else None
    if not isinstance(respuesta, str):
        raise RuntimeError("Ollama no devolvió una respuesta de chat textual válida.")
    return _validar_respuesta_modelo(
        respuesta,
        endpoint="/api/chat",
        modelo=str(payload.get("model") or ""),
    )


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
      - Si formato_json=True se pide JSON estricto. Por defecto se hace en modo
        blando para evitar errores de gramática de Ollama; el modo nativo se
        puede forzar con PLUMA_OLLAMA_JSON_MODE=native.
      - Si se pasan imágenes, se usa la ruta multimodal.
    """
    cfg = _cargar_runtime()

    opciones: dict[str, Any] = dict(cfg["opciones"])
    opciones["num_ctx"] = NUM_CTX
    opciones["num_predict"] = NUM_PREDICT
    if temperatura is not None:
        opciones["temperature"] = temperatura

    modelo_final = modelo or await elegir_modelo_por_defecto(vision=bool(imagenes))

    # Ruta visual segura. En visión no usamos `format: "json"`: algunos modelos
    # multimodales funcionan bien con imágenes, pero fallan cuando Ollama aplica
    # gramática JSON estricta. Además /api/chat se comporta mejor que /api/generate
    # para modelos de visión como Qwen.
    if imagenes:
        prompt_visual = _reforzar_prompt_json(prompt) if formato_json else prompt
        imagenes_optimizadas = [_optimizar_imagen_para_vision(img) for img in imagenes]
        opciones_vision = _opciones_para_vision(cfg["opciones"], temperatura)
        payload_chat: dict[str, Any] = {
            "model": modelo_final,
            "messages": [
                {"role": "system", "content": cfg["sistema"]},
                {
                    "role": "user",
                    "content": prompt_visual,
                    "images": [base64.b64encode(img).decode("ascii") for img in imagenes_optimizadas],
                },
            ],
            "stream": False,
            "think": False,
            "keep_alive": KEEP_ALIVE,
            "options": opciones_vision,
        }
        logger.info(
            "Llamada visual rápida a Ollama por /api/chat modelo=%s imagenes=%d num_ctx=%s num_predict=%s format_json_nativo=false",
            modelo_final, len(imagenes_optimizadas), opciones_vision.get("num_ctx"), opciones_vision.get("num_predict"),
        )
        async with httpx.AsyncClient(timeout=TIMEOUT_VISION) as cliente:
            return await _post_chat(cliente, payload_chat)

    modo_json = OLLAMA_JSON_MODE if formato_json else "off"
    usar_json_nativo = formato_json and modo_json in {"native", "nativo", "strict", "estricto"}

    payload: dict[str, Any] = {
        "model": modelo_final,
        "prompt": prompt if usar_json_nativo or not formato_json else _reforzar_prompt_json(prompt),
        "system": cfg["sistema"],
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": opciones,
    }

    if usar_json_nativo:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=TIMEOUT) as cliente:
        if not usar_json_nativo:
            return await _post_generate(cliente, payload)

        # Modo nativo solicitado por entorno: si Ollama falla por gramática JSON,
        # reintentamos automáticamente en modo blando para no bloquear el proceso.
        resp = await cliente.post(f"{OLLAMA_URL}/api/generate", json=payload)
        if resp.is_error:
            detalle = (resp.text or "").strip().replace("\n", " ")[:1200]
            if _es_error_gramatica_json_ollama(resp.status_code, detalle):
                logger.warning(
                    "Ollama falló con gramática JSON nativa; reintentando sin format=json: %s",
                    detalle[:300],
                )
                payload_blando = dict(payload)
                payload_blando.pop("format", None)
                payload_blando["prompt"] = _reforzar_prompt_json(prompt)
                return await _post_generate(cliente, payload_blando)
            if resp.status_code >= 500:
                raise RuntimeError(
                    f"Ollama devolvió HTTP {resp.status_code} en /api/generate. "
                    f"La causa exacta debe comprobarse en los logs de Ollama; "
                    f"puede deberse a memoria insuficiente, formato de petición, tamaño de contexto "
                    f"o error interno del motor. Detalle: {detalle}"
                )
            raise RuntimeError(f"Ollama devolvió HTTP {resp.status_code}: {detalle}")
        data = resp.json()
        _log_metricas_ollama(data, "/api/generate", str(payload.get("model") or ""))
        respuesta = data.get("response")
        if not isinstance(respuesta, str):
            raise RuntimeError("Ollama no devolvió una respuesta textual válida.")
        return _validar_respuesta_modelo(
            respuesta,
            endpoint="/api/generate",
            modelo=str(payload.get("model") or ""),
        )


async def modelos_disponibles() -> list[str]:
    """Lista los modelos descargados localmente en el Ollama nativo/local."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as cliente:
        resp = await cliente.get(f"{OLLAMA_URL}/api/tags")
        resp.raise_for_status()
        modelos = []
        for m in resp.json().get("models", []):
            if isinstance(m, dict) and isinstance(m.get("name"), str):
                modelos.append(m["name"])
        return modelos


def _equivale_modelo(nombre: str, candidato: str) -> bool:
    """Compara nombres de modelos aceptando la variante :latest."""
    return candidato == nombre or candidato == f"{nombre}:latest" or f"{candidato}:latest" == nombre


def elegir_nombre_preferido(modelos: list[str], *, vision: bool = False) -> str | None:
    """Elige un modelo descargado, con preferencias distintas para texto y visión."""
    if not modelos:
        return None

    preferencias = (
        MODELOS_VISUALES_PREFERIDOS if vision else [MODELO_POR_DEFECTO, *MODELOS_PREFERIDOS]
    )
    vistos: set[str] = set()
    for preferido in preferencias:
        if preferido in vistos:
            continue
        vistos.add(preferido)
        for disponible in modelos:
            if _equivale_modelo(preferido, disponible):
                return disponible

    return modelos[0]


async def elegir_modelo_por_defecto(*, vision: bool = False) -> str:
    """Devuelve el modelo local que debe usarse por defecto."""
    modelos = await modelos_disponibles()
    elegido = elegir_nombre_preferido(modelos, vision=vision)
    if elegido:
        return elegido
    raise RuntimeError(
        "No hay ningún modelo descargado en Ollama. "
        "Instale uno con `ollama pull qwen3.5:latest` para visión "
        "o `ollama pull gemma4:e2b` para texto."
    )


async def modelo_disponible(nombre: str) -> bool:
    """Comprueba si un modelo solicitado por la interfaz existe en Ollama."""
    if not nombre or not nombre.strip():
        return False
    nombre = nombre.strip()
    modelos = await modelos_disponibles()
    return any(_equivale_modelo(nombre, m) for m in modelos)
