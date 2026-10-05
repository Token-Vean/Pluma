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
import math
import os
import re
from dataclasses import dataclass
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
def _segundos_env(nombre: str, defecto: float, minimo: float, maximo: float) -> float:
    try:
        valor = float(os.getenv(nombre, str(defecto)))
    except ValueError:
        return defecto
    return max(minimo, min(maximo, valor))


# Tiempo máximo de espera de una respuesta textual de Ollama. En equipos sin
# GPU efectiva un modelo de 4-9B puede tardar varios minutos en generar el JSON
# de un documento largo; antes estaba fijado en 300 s sin poder cambiarse.
TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=_segundos_env("OLLAMA_TIMEOUT_SECONDS", 300.0, 30.0, 3600.0),
    write=30.0,
    pool=10.0,
)
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
# Hasta 0.7.2 PlumA usaba por defecto el modo JSON blando (solo instrucción en
# el prompt), y cualquier defecto de la salida —un salto de línea literal, una
# comilla sin escapar al citar el documento, una coma final— hacía que se
# descartara la propuesta entera con "JSON inválido".
#
# Desde 0.7.3 el modo por defecto es "schema": se envía a Ollama el esquema JSON
# exacto de la respuesta (salida estructurada), de modo que el muestreo queda
# restringido a JSON válido con esa forma. Si el runtime rechaza la gramática,
# se reintenta automáticamente en modo blando. Valores admitidos:
#   schema  -> format = esquema JSON de la respuesta (recomendado)
#   native  -> format = "json" (JSON genérico, sin forma)
#   soft    -> sin format; solo instrucción en el prompt y reparación posterior
OLLAMA_JSON_MODE = os.getenv("PLUMA_OLLAMA_JSON_MODE", "schema").strip().lower()
if OLLAMA_JSON_MODE in {"nativo", "strict", "estricto"}:
    OLLAMA_JSON_MODE = "native"
elif OLLAMA_JSON_MODE in {"esquema", "estructurado", "structured"}:
    OLLAMA_JSON_MODE = "schema"
elif OLLAMA_JSON_MODE not in {"schema", "native", "soft"}:
    OLLAMA_JSON_MODE = "schema"

RUNTIME_CONFIG_PATH = Path(
    os.getenv("PLUMA_RUNTIME_CONFIG", "/app/schemas/pluma-runtime.yaml")
)

validate_ollama_url(OLLAMA_URL)


# -----------------------------------------------------------------------------
# Cliente HTTP local
# -----------------------------------------------------------------------------

def cliente_local(timeout: httpx.Timeout) -> httpx.AsyncClient:
    """Crea el cliente HTTP usado para hablar con Ollama.

    Dos ajustes deliberados frente a los valores por defecto de httpx:

    - ``trust_env=False``. Por defecto httpx honra HTTP_PROXY / HTTPS_PROXY /
      ALL_PROXY del entorno. En una herramienta que garantiza procesamiento
      local, un proxy heredado del sistema (típico en equipos corporativos)
      sería el único camino por el que el texto íntegro de un documento podría
      salir del equipo pese a que ``validate_ollama_url()`` haya aprobado la
      URL. El destino ya está restringido a loopback/servicio interno; no hay
      ningún caso legítimo en el que deba atravesar un proxy.
    - ``follow_redirects=False``. Es el valor por defecto actual de httpx, pero
      se explicita para que un Ollama comprometido o suplantado no pueda
      redirigir la petición a otro host, y para que un cambio futuro de la
      librería no relaje la garantía en silencio.
    """
    return httpx.AsyncClient(
        timeout=timeout,
        trust_env=False,
        follow_redirects=False,
    )



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
# Presupuesto de la ventana de contexto
# -----------------------------------------------------------------------------
#
# Cuando el prompt supera num_ctx, Ollama no devuelve error: descarta el
# PRINCIPIO del prompt, conserva unos pocos tokens (keep=4 en su aviso
# "truncating input prompt") y responde 200 OK. En PlumA el principio es justo
# lo que no puede perderse: system prompt, reglas y descripción de los campos.
# Sin instrucciones, el modelo devuelve JSON degradado y la propuesta sale
# vacía. Si el prompt cabe pero prompt + respuesta no, Ollama desplaza el
# contexto durante la generación y el efecto es parecido.
#
# PlumA no dispone del tokenizador del modelo, así que el presupuesto es una
# estimación por caracteres. Hay dos defensas complementarias:
#
#   1. Antes de llamar, con la estimación central: si el documento no cabe,
#      se envían su principio y su final con una marca de omisión explícita.
#      La estimación central evita recortar documentos que sí caben.
#   2. Después de llamar, con datos reales: Ollama devuelve prompt_eval_count
#      y eval_count. Si revelan truncado o desplazamiento, el extractor repite
#      la llamada con una estimación prudente. Un error de estimación deja de
#      pasar en silencio.


def _float_env(nombre: str, defecto: float, minimo: float, maximo: float) -> float:
    try:
        valor = float(os.getenv(nombre, str(defecto)))
    except ValueError:
        logger.warning("%s no es un número válido; se usa %s", nombre, defecto)
        return defecto
    return max(minimo, min(maximo, valor))


def _int_env(nombre: str, defecto: int, minimo: int, maximo: int) -> int:
    try:
        valor = int(os.getenv(nombre, str(defecto)))
    except ValueError:
        logger.warning("%s no es un entero válido; se usa %s", nombre, defecto)
        return defecto
    return max(minimo, min(maximo, valor))


def _entero(valor: Any) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


# Caracteres por token. 4.0 es una estimación central para español con los
# tokenizadores habituales (Gemma, Qwen); el texto con ruido de OCR tokeniza
# peor. La prudente se usa solo al repetir una llamada que ya desbordó.
CARACTERES_POR_TOKEN = _float_env("PLUMA_CARACTERES_POR_TOKEN", 4.0, 2.0, 6.0)
CARACTERES_POR_TOKEN_PRUDENTE = min(3.0, CARACTERES_POR_TOKEN)
# Tokens que se dejan libres para la respuesta al calcular cuánto documento
# cabe. Nunca supera num_predict.
RESERVA_SALIDA_TOKENS = _int_env("PLUMA_RESERVA_SALIDA_TOKENS", 1024, 128, 32768)
# Coste aproximado de cada imagen en la ruta visual. Depende del modelo y de
# la resolución; solo se usa para detectar ventanas visuales insuficientes.
TOKENS_POR_IMAGEN = _int_env("PLUMA_TOKENS_POR_IMAGEN", 768, 64, 8192)
# Plantilla de chat del modelo, tokens especiales y redondeos.
MARGEN_PLANTILLA_TOKENS = 128
# Por debajo de esto no tiene sentido enviar documento: la ventana es
# insuficiente para la norma y el modo pedidos.
MIN_CARACTERES_DOCUMENTO = 600
# System prompt supuesto cuando pluma-runtime.yaml no está disponible (tests).
_CARACTERES_SISTEMA_POR_DEFECTO = 2400

ESTADOS_DESBORDAMIENTO = frozenset({"prompt_truncado", "contexto_agotado"})


@dataclass(frozen=True)
class PresupuestoDocumento:
    """Caracteres de documento que caben en una llamada."""

    caracteres: int
    num_ctx: int
    suficiente: bool


def _caracteres_sistema() -> int:
    try:
        return len(_cargar_runtime()["sistema"])
    except Exception:
        return _CARACTERES_SISTEMA_POR_DEFECTO


def presupuesto_documento(
    prompt_sin_documento: str,
    *,
    imagenes: int = 0,
    caracteres_por_token: float | None = None,
    reserva_salida: int | None = None,
) -> PresupuestoDocumento:
    """Estima cuántos caracteres de documento caben junto al resto del prompt.

    `prompt_sin_documento` es el prompt completo con el bloque de documento
    vacío. Se suman el system prompt, el refuerzo JSON, las imágenes, un margen
    de plantilla y la reserva para la respuesta, y lo que queda de la ventana
    se convierte a caracteres. `suficiente` es False cuando ni siquiera las
    instrucciones caben con holgura; en ese caso se devuelve el mínimo para que
    el llamador pueda seguir, pero el resultado no será fiable.
    """
    vision = imagenes > 0
    num_ctx = VISION_NUM_CTX if vision else NUM_CTX
    num_predict = VISION_NUM_PREDICT if vision else NUM_PREDICT
    ratio = caracteres_por_token or CARACTERES_POR_TOKEN
    reserva = RESERVA_SALIDA_TOKENS if reserva_salida is None else reserva_salida
    reserva = max(0, min(num_predict, reserva))

    caracteres_fijos = _caracteres_sistema() + len(_reforzar_prompt_json(prompt_sin_documento))
    ocupados = (
        math.ceil(caracteres_fijos / ratio)
        + imagenes * TOKENS_POR_IMAGEN
        + MARGEN_PLANTILLA_TOKENS
        + reserva
    )
    caracteres = int((num_ctx - ocupados) * ratio)
    return PresupuestoDocumento(
        caracteres=max(caracteres, MIN_CARACTERES_DOCUMENTO),
        num_ctx=num_ctx,
        suficiente=caracteres >= MIN_CARACTERES_DOCUMENTO,
    )


def evaluar_contexto(diagnostico: dict[str, Any] | None) -> str | None:
    """Interpreta las métricas que Ollama devuelve en cada llamada.

    Devuelve:
        "prompt_truncado"  el prompt no cabía y Ollama descartó su principio.
        "contexto_agotado" el prompt cabía, pero prompt + respuesta superaron
                           la ventana y Ollama desplazó o agotó el contexto.
        "limite_salida"    la respuesta alcanzó num_predict y puede estar
                           incompleta.
        None               sin indicios de problema, o sin métricas.

    Limitación: si Ollama reutiliza la caché de prefijo e informa solo de los
    tokens nuevos, un truncado puede no detectarse aquí. Por eso el extractor
    mantiene además el aviso de "ningún campo devuelto".
    """
    if not diagnostico:
        return None
    num_ctx = _entero(diagnostico.get("num_ctx"))
    num_predict = _entero(diagnostico.get("num_predict"))
    prompt = _entero(diagnostico.get("prompt_eval_count"))
    salida = _entero(diagnostico.get("eval_count"))

    if num_ctx > 0 and prompt >= num_ctx:
        return "prompt_truncado"
    if num_ctx > 0 and prompt > 0 and prompt + salida > num_ctx:
        return "contexto_agotado"
    if diagnostico.get("done_reason") == "length":
        if num_predict > 0 and salida >= num_predict:
            return "limite_salida"
        return "contexto_agotado"
    return None


def caracteres_por_token_observados(diagnostico: dict[str, Any] | None) -> float | None:
    """Densidad real caracteres/token de una llamada cuyo prompt no se truncó."""
    if not diagnostico:
        return None
    prompt = _entero(diagnostico.get("prompt_eval_count"))
    caracteres = _entero(diagnostico.get("caracteres_prompt"))
    num_ctx = _entero(diagnostico.get("num_ctx"))
    if prompt <= 0 or caracteres <= 0 or (num_ctx and prompt >= num_ctx):
        return None
    return max(2.0, min(6.0, caracteres / prompt))


def _registrar_diagnostico(
    diagnostico: dict[str, Any] | None,
    *,
    payload: dict[str, Any],
    data: dict[str, Any],
    respuesta: Any,
    thinking: Any,
    caracteres_prompt: int,
    endpoint: str,
) -> None:
    """Anota métricas de la llamada. Solo metadatos, nunca contenido."""
    opciones = payload.get("options") or {}
    registro = {
        "modelo": str(payload.get("model") or ""),
        "num_ctx": opciones.get("num_ctx"),
        "num_predict": opciones.get("num_predict"),
        "prompt_eval_count": data.get("prompt_eval_count"),
        "eval_count": data.get("eval_count"),
        "done_reason": data.get("done_reason"),
        "caracteres_prompt": caracteres_prompt,
        "solo_razonamiento": (
            isinstance(thinking, str)
            and bool(thinking.strip())
            and not (respuesta.strip() if isinstance(respuesta, str) else "")
        ),
    }
    estado = evaluar_contexto(registro)
    if estado:
        logger.warning(
            "Ollama %s modelo=%s: %s (prompt=%s tok, salida=%s tok, num_ctx=%s, num_predict=%s)",
            endpoint, registro["modelo"], estado, registro["prompt_eval_count"],
            registro["eval_count"], registro["num_ctx"], registro["num_predict"],
        )
    if diagnostico is not None:
        diagnostico.update(registro)


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
    """¿El error de Ollama se debe a la salida estructurada (format)?

    - 5xx con mensajes de gramática: el runtime no pudo aplicar la gramática
      JSON a este modelo.
    - 400 que mencionan format/schema/grammar: versiones de Ollama que no
      aceptan un esquema JSON en `format`, o esquemas que no saben convertir.
    En ambos casos tiene sentido reintentar sin `format`.
    """
    d = (detalle or "").lower()
    if status_code >= 500:
        patrones = (
            "grammar",
            "empty grammar stack",
            "unexpected empty grammar",
            "unused",
            "llama_decode",
        )
        return any(p in d for p in patrones)
    if status_code == 400:
        return any(p in d for p in ("format", "schema", "grammar"))
    return False


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


def _cargar_json(texto: str) -> Any:
    """json.loads tolerante a caracteres de control dentro de cadenas.

    `strict=False` acepta saltos de línea y tabuladores literales dentro de
    los valores, el defecto más frecuente de los modelos locales cuando
    redactan campos largos como "alcance y contenido".
    """
    return json.loads(texto, strict=False)


def _primer_objeto_balanceado(texto: str) -> str | None:
    """Devuelve el primer objeto {...} balanceado, respetando cadenas."""
    inicio = texto.find("{")
    if inicio < 0:
        return None
    en_cadena = False
    escape = False
    profundidad = 0
    for i in range(inicio, len(texto)):
        ch = texto[i]
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
                return texto[inicio : i + 1]
    return None


_LITERALES_PYTHON = {"None": "null", "True": "true", "False": "false"}


def reparar_json(texto: str) -> str:
    """Repara los defectos de sintaxis más habituales de los modelos locales.

    No inventa contenido: solo corrige la forma.
      - comillas dobles internas sin escapar (citas literales del documento);
      - saltos de línea, retornos y tabuladores literales dentro de cadenas;
      - comas finales antes de } o ];
      - literales de Python (None, True, False) fuera de cadenas.

    Para distinguir una comilla de cierre de una comilla interna se mira el
    primer carácter significativo que la sigue: si es , } ] o : la comilla
    cierra la cadena; en otro caso es una comilla del texto citado y se
    escapa. Es una heurística: si el resultado sigue sin ser JSON válido, el
    llamador lo trata como inválido igual que antes.
    """
    inicio = texto.find("{")
    if inicio < 0:
        return texto
    fin = texto.rfind("}")
    if fin > inicio:
        texto = texto[inicio : fin + 1]
    else:
        texto = texto[inicio:]

    salida: list[str] = []
    en_cadena = False
    escape = False
    n = len(texto)
    i = 0
    while i < n:
        ch = texto[i]
        if en_cadena:
            if escape:
                salida.append(ch)
                escape = False
            elif ch == "\\":
                salida.append(ch)
                escape = True
            elif ch == '"':
                j = i + 1
                while j < n and texto[j] in " \t\r\n":
                    j += 1
                siguiente = texto[j] if j < n else ""
                if siguiente in {",", "}", "]", ":", ""}:
                    salida.append(ch)
                    en_cadena = False
                else:
                    salida.append('\\"')
            elif ch == "\n":
                salida.append("\\n")
            elif ch == "\r":
                salida.append("\\r")
            elif ch == "\t":
                salida.append("\\t")
            else:
                salida.append(ch)
            i += 1
            continue

        if ch == '"':
            en_cadena = True
            salida.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and texto[j] in " \t\r\n":
                j += 1
            if j < n and texto[j] in "}]":
                i += 1
                continue
        if ch.isalpha():
            j = i
            while j < n and texto[j].isalpha():
                j += 1
            palabra = texto[i:j]
            salida.append(_LITERALES_PYTHON.get(palabra, palabra))
            i = j
            continue
        salida.append(ch)
        i += 1
    return "".join(salida)


def extraer_json_texto(texto: str) -> str:
    """
    Devuelve el primer objeto JSON válido contenido en una respuesta del modelo.

    No confía en que el modelo cumpla exactamente la instrucción de salida: puede
    envolver el JSON en ```json, añadir una frase previa o texto posterior, o
    cometer errores de sintaxis menores. Se prueba, por este orden: la respuesta
    tal cual, sin cercas markdown, el primer objeto balanceado y, por último,
    una reparación sintáctica conservadora (`reparar_json`).

    Si un candidato ya es JSON estricto se devuelve tal cual (comportamiento
    anterior). Si solo es válido de forma tolerante o tras la reparación, se
    devuelve normalizado con json.dumps, de modo que el llamador puede seguir
    usando json.loads estricto. Si ninguna vía lo consigue, se devuelve el
    texto original para que el llamador informe del JSON inválido.
    """
    if not isinstance(texto, str):
        return texto

    limpio = texto.strip()
    if not limpio:
        return limpio

    candidatos: list[str] = [limpio]
    sin_cercas = re.sub(r"^```(?:json)?\s*", "", limpio, flags=re.IGNORECASE)
    sin_cercas = re.sub(r"\s*```\s*$", "", sin_cercas).strip()
    candidatos.append(sin_cercas)
    balanceado = _primer_objeto_balanceado(sin_cercas)
    if balanceado:
        candidatos.append(balanceado)
    candidatos.append(reparar_json(sin_cercas))

    for candidato in candidatos:
        try:
            json.loads(candidato)
            return candidato
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    for candidato in candidatos:
        try:
            datos = _cargar_json(candidato)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        return json.dumps(datos, ensure_ascii=False)

    return texto


def describir_error_json(texto: Any) -> str:
    """Diagnóstico de un JSON inválido sin incluir contenido del documento.

    Solo metadatos: longitud, mensaje del parser y posición. Sirve para el log
    del contenedor sin romper la regla de no registrar contenido documental.
    """
    if not isinstance(texto, str):
        return f"respuesta no textual ({type(texto).__name__})"
    if not texto.strip():
        return "respuesta vacía"
    candidato = reparar_json(texto.strip())
    try:
        _cargar_json(candidato)
        return f"longitud={len(texto)}; reparable"
    except json.JSONDecodeError as e:
        return (
            f"longitud={len(texto)}; {e.msg} en posición {e.pos} de {len(candidato)} "
            f"tras reparación; empieza por llave={texto.lstrip().startswith('{')}"
        )


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


async def _post_generate(
    cliente: httpx.AsyncClient,
    payload: dict[str, Any],
    diagnostico: dict[str, Any] | None = None,
) -> str:
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
    _registrar_diagnostico(
        diagnostico, payload=payload, data=data, respuesta=respuesta,
        thinking=data.get("thinking"),
        caracteres_prompt=len(str(payload.get("system") or "")) + len(str(payload.get("prompt") or "")),
        endpoint="/api/generate",
    )
    if not isinstance(respuesta, str):
        raise RuntimeError("Ollama no devolvió una respuesta textual válida.")
    return _validar_respuesta_modelo(
        respuesta,
        endpoint="/api/generate",
        modelo=str(payload.get("model") or ""),
    )


async def _post_chat(
    cliente: httpx.AsyncClient,
    payload: dict[str, Any],
    diagnostico: dict[str, Any] | None = None,
) -> str:
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
    _registrar_diagnostico(
        diagnostico, payload=payload, data=data, respuesta=respuesta,
        thinking=mensaje.get("thinking") if isinstance(mensaje, dict) else None,
        caracteres_prompt=sum(
            len(str(m.get("content") or ""))
            for m in payload.get("messages") or []
            if isinstance(m, dict)
        ),
        endpoint="/api/chat",
    )
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
    formato_json: bool | dict[str, Any] = True,
    temperatura: float | None = None,
    diagnostico: dict[str, Any] | None = None,
) -> str:
    """
    Llama al modelo y devuelve la respuesta como cadena.

    Si se pasa `diagnostico`, se rellena con las métricas de Ollama de la
    llamada que produjo la respuesta (num_ctx, num_predict, prompt_eval_count,
    eval_count, done_reason...). Ver `evaluar_contexto()`.

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
      - `formato_json` sigue el campo `format` de la API de Ollama: True pide
        JSON genérico y un dict pide JSON con ese esquema. Con
        PLUMA_OLLAMA_JSON_MODE=schema (por defecto) el esquema se envía en
        `format` y Ollama restringe la salida a JSON válido con esa forma; con
        True se envía `format: "json"`. Si Ollama rechaza la gramática, se
        reintenta una vez sin `format` (modo blando). Con
        PLUMA_OLLAMA_JSON_MODE=soft nunca se envía `format`. El esquema viaja
        por este parámetro, y no por uno nuevo, para no cambiar la firma de
        generar(): los dobles de prueba que la sustituyen siguen siendo válidos.
      - Si se pasan imágenes, se usa la ruta multimodal.
    """
    esquema_json = formato_json if isinstance(formato_json, dict) and formato_json else None
    formato_json = bool(formato_json)

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
        async with cliente_local(TIMEOUT_VISION) as cliente:
            return await _post_chat(cliente, payload_chat, diagnostico)

    modo_json = OLLAMA_JSON_MODE if formato_json else "off"
    formato: Any = None
    if modo_json == "schema" and esquema_json:
        formato = esquema_json
    elif modo_json in {"schema", "native"}:
        formato = "json"

    payload: dict[str, Any] = {
        "model": modelo_final,
        "prompt": _reforzar_prompt_json(prompt) if formato_json else prompt,
        "system": cfg["sistema"],
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": opciones,
    }
    if formato is not None:
        payload["format"] = formato

    async with cliente_local(TIMEOUT) as cliente:
        if formato is None:
            return await _post_generate(cliente, payload, diagnostico)

        # Salida estructurada: si Ollama no puede aplicar la gramática a este
        # modelo, se reintenta una vez en modo blando para no bloquear el
        # proceso. La reparación de extraer_json_texto() cubre ese caso.
        resp = await cliente.post(f"{OLLAMA_URL}/api/generate", json=payload)
        if resp.is_error:
            detalle = (resp.text or "").strip().replace("\n", " ")[:1200]
            if _es_error_gramatica_json_ollama(resp.status_code, detalle):
                logger.warning(
                    "Ollama rechazó la salida estructurada (%s) con modelo=%s; "
                    "reintentando sin format: %s",
                    "esquema" if isinstance(formato, dict) else "json",
                    modelo_final,
                    detalle[:300],
                )
                payload_blando = dict(payload)
                payload_blando.pop("format", None)
                return await _post_generate(cliente, payload_blando, diagnostico)
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
        _registrar_diagnostico(
            diagnostico, payload=payload, data=data, respuesta=respuesta,
            thinking=data.get("thinking"),
            caracteres_prompt=len(str(payload.get("system") or "")) + len(str(payload.get("prompt") or "")),
            endpoint="/api/generate",
        )
        if not isinstance(respuesta, str):
            raise RuntimeError("Ollama no devolvió una respuesta textual válida.")
        return _validar_respuesta_modelo(
            respuesta,
            endpoint="/api/generate",
            modelo=str(payload.get("model") or ""),
        )


async def modelos_disponibles() -> list[str]:
    """Lista los modelos descargados localmente en el Ollama nativo/local."""
    async with cliente_local(TIMEOUT) as cliente:
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
