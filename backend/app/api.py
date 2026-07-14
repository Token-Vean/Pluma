"""
API REST de la aplicación.

Endpoints de la versión libre:
    GET  /api/estado                → estado del bootstrap
    GET  /api/normas                → normas disponibles
    GET  /api/tipos                 → catálogo de tipos documentales
    POST /api/describir             → procesar documento y devolver propuesta
    POST /api/exportar/{formato}    → exportar propuesta editada

El módulo incluye defensas de borde: cabeceras de seguridad, límite de
cuerpo antes del parseo de FastAPI, validación de payload de exportación
y limitación de concurrencia para operaciones pesadas.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from . import auditoria, extractor, identificador_tipo, llm, router as router_entrada
from .router import ErrorValidacion
from .version import APP_VERSION
from .security_policy import security_status

logger = logging.getLogger(__name__)


# =============================================================================
# Configuración
# =============================================================================

MODELO = os.getenv("MODELO_BASE", "gemma4:e2b")
MAX_DESCRIBIR_FILES = max(1, int(os.getenv("MAX_DESCRIBIR_FILES", "10")))
MAX_DESCRIBIR_TOTAL_BYTES = int(os.getenv("MAX_DESCRIBIR_TOTAL_BYTES", str(150 * 1024 * 1024)))
MAX_IMAGENES_DOCUMENTO_COMPUESTO = max(1, int(os.getenv("MAX_IMAGENES_DOCUMENTO_COMPUESTO", "30")))
# Por defecto, la ruta híbrida evita reenviar imágenes si ya hay texto.
# La visión directa queda reservada para documentos sin capa textual.
PLUMA_HIBRIDO_USAR_VISION = os.getenv("PLUMA_HIBRIDO_USAR_VISION", "false").strip().lower() in {"1", "true", "yes", "si", "sí", "on"}
DIR_ESQUEMAS = Path(os.getenv("DIR_ESQUEMAS", "/app/schemas"))
RUTA_CATALOGO_TIPOS = DIR_ESQUEMAS / "tipos-documentales.yaml"

# El multipart añade cabeceras y límites alrededor del fichero. En documentos
# compuestos permitimos varios ficheros, pero mantenemos límite total explícito.
MAX_DESCRIBIR_BODY_BYTES = int(
    os.getenv("MAX_DESCRIBIR_BODY_BYTES", str(MAX_DESCRIBIR_TOTAL_BYTES + 4 * 1024 * 1024))
)
MAX_EXPORT_BODY_BYTES = int(os.getenv("MAX_EXPORT_BODY_BYTES", str(15 * 1024 * 1024)))
MAX_CAMPOS_EXPORTACION = int(os.getenv("MAX_CAMPOS_EXPORTACION", "250"))
MAX_LONGITUD_VALOR_EXPORTACION = int(os.getenv("MAX_LONGITUD_VALOR_EXPORTACION", "50000"))
MAX_LONGITUD_EVIDENCIA_EXPORTACION = int(os.getenv("MAX_LONGITUD_EVIDENCIA_EXPORTACION", "8000"))
MAX_ITEMS_LISTA_EXPORTACION = int(os.getenv("MAX_ITEMS_LISTA_EXPORTACION", "100"))
MAX_PROCESAMIENTOS_SIMULTANEOS = max(
    1, int(os.getenv("MAX_PROCESAMIENTOS_SIMULTANEOS", "1"))
)
PERMITIR_APAGADO_UI = os.getenv("PERMITIR_APAGADO_UI", "false").strip().lower() in {
    "1", "true", "yes", "si", "sí", "on"
}
INCLUIR_HASH_DOCUMENTO_AUDITORIA = os.getenv(
    "INCLUIR_HASH_DOCUMENTO_AUDITORIA", "true"
).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}

IDIOMAS_SALIDA_ADMITIDOS = {"es", "en"}

_SEM_PROCESAMIENTO = asyncio.Semaphore(MAX_PROCESAMIENTOS_SIMULTANEOS)

NORMAS_DISPONIBLES = {
    "isad-g":    {"archivo": "isad-g.yaml",    "nombre": "ISAD(G)",    "titulo": "Descripción archivística"},
    "dacs":      {"archivo": "dacs.yaml",      "nombre": "DACS",       "titulo": "Describing Archives - Content Standard"},
    "isaar-cpf": {"archivo": "isaar-cpf.yaml", "nombre": "ISAAR(CPF)", "titulo": "Registros de autoridad"},
    "isdf":      {"archivo": "isdf.yaml",      "nombre": "ISDF",       "titulo": "Descripción de funciones"},
    "isdiah":    {"archivo": "isdiah.yaml",    "nombre": "ISDIAH",     "titulo": "Instituciones de archivo"},
    # RIC simplificado: una entrada por perfil. Internamente apuntan al
    # mismo YAML pero con un perfil distinto.
    "ric-record":     {"archivo": "ric.yaml", "perfil": "record",     "nombre": "RIC Record",     "titulo": "RIC - Documento (Record)"},
    "ric-recordset":  {"archivo": "ric.yaml", "perfil": "recordset",  "nombre": "RIC RecordSet",  "titulo": "RIC - Conjunto documental (RecordSet)"},
    "ric-agent":      {"archivo": "ric.yaml", "perfil": "agent",      "nombre": "RIC Agent",      "titulo": "RIC - Agente (Agent)"},
    "ric-activity":   {"archivo": "ric.yaml", "perfil": "activity",   "nombre": "RIC Activity",   "titulo": "RIC - Actividad (Activity)"},
}

# Campos del modo "Esencial" — los 6 que todo archivero quiere siempre
CAMPOS_ESENCIALES_ISAD = {
    "codigo_referencia",
    "titulo",
    "fechas",
    "nivel_descripcion",
    "nombre_productor",
    "alcance_contenido",
}


# =============================================================================
# Middleware de seguridad
# =============================================================================

class LimiteCuerpoPeticion:
    """
    Rechaza cuerpos HTTP excesivos antes de que FastAPI/Starlette parseen
    multipart o JSON.

    Esta defensa evita que el límite de tamaño del router llegue tarde: si
    Content-Length supera el máximo de la ruta, se responde 413 sin leer el
    cuerpo. Para rutas protegidas que reciben cuerpo se exige Content-Length;
    si falta, se responde 411. Los navegadores y fetch/form-data normales lo
    envían siempre, por lo que esta restricción no afecta al uso esperado.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        metodo = scope.get("method", "").upper()
        ruta = scope.get("path", "")
        limite = self._limite_para(metodo, ruta)
        if limite is None:
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        raw_len = headers.get(b"content-length")
        if raw_len is None:
            await self._enviar_json(send, 411, "Content-Length requerido para esta operación.")
            return

        try:
            longitud = int(raw_len.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            await self._enviar_json(send, 400, "Content-Length inválido.")
            return

        if longitud > limite:
            await self._enviar_json(
                send,
                413,
                f"Cuerpo de petición demasiado grande. Máximo: {limite} bytes.",
            )
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _limite_para(metodo: str, ruta: str) -> int | None:
        if metodo not in {"POST", "PUT", "PATCH"}:
            return None
        if ruta == "/api/describir":
            return MAX_DESCRIBIR_BODY_BYTES
        if ruta.startswith("/api/exportar/"):
            return MAX_EXPORT_BODY_BYTES
        return None

    @staticmethod
    async def _enviar_json(send: Send, status_code: int, detail: str) -> None:
        cuerpo = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        })
        await send({"type": "http.response.body", "body": cuerpo})



class CabecerasSeguridad(BaseHTTPMiddleware):
    """Aplica cabeceras de seguridad HTTP a todas las respuestas."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        respuesta = await call_next(request)
        respuesta.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )
        if request.url.path.startswith("/api/"):
            respuesta.headers["Cache-Control"] = "no-store"
        return respuesta


# =============================================================================
# Logging sin contenido (metadatos únicamente)
# =============================================================================

def _log_peticion(evento: str, peticion_id: str, **kwargs: Any) -> None:
    """
    Log de eventos con metadatos únicamente. NUNCA debe incluir texto del
    documento ni valores de propuestas. Los logs no pueden convertirse en
    una segunda copia de los documentos procesados.
    """
    extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info("[%s] %s %s", peticion_id, evento, extras)


# =============================================================================
# Router de la versión libre
# =============================================================================

router = APIRouter()


@router.get("/csrf")
async def emitir_token_csrf():
    """
    Emite un token CSRF nuevo. El frontend lo pide al arrancar y lo
    envía en la cabecera X-CSRF-Token en cada petición mutadora.
    """
    from . import csrf
    return {"token": csrf.generar_token()}


@router.get("/normas")
async def listar_normas():
    return {
        "normas": [
            {"clave": clave, **datos}
            for clave, datos in NORMAS_DISPONIBLES.items()
        ]
    }


@router.get("/tipos")
async def listar_tipos():
    try:
        catalogo = identificador_tipo.cargar_catalogo(RUTA_CATALOGO_TIPOS)
    except FileNotFoundError:
        raise HTTPException(500, "Catálogo de tipos no encontrado en el servidor.") from None

    return {
        "version": catalogo.version,
        "tipos": [
            {"clave": t.clave, "nombre": t.nombre, "familia": t.familia}
            for t in catalogo.tipos
        ],
    }


@router.get("/modelos")
async def listar_modelos_ollama():
    """Lista los modelos descargados en Ollama y elige uno por defecto."""
    try:
        modelos = await llm.modelos_disponibles()
    except Exception as err:
        logger.warning("No se pudieron listar modelos de Ollama: %s", err)
        raise HTTPException(503, "No se pudieron consultar los modelos locales de Ollama.") from err

    elegido_texto = llm.elegir_nombre_preferido(modelos, vision=False)
    elegido_vision = llm.elegir_nombre_preferido(modelos, vision=True)
    return {
        "modelos": modelos,
        "por_defecto": elegido_texto,
        "por_defecto_texto": elegido_texto,
        "por_defecto_vision": elegido_vision,
        "preferidos": [MODELO, *llm.MODELOS_PREFERIDOS],
        "preferidos_vision": llm.MODELOS_VISUALES_PREFERIDOS,
        "ollama_url": llm.OLLAMA_URL,
    }


async def _resolver_modelo_solicitado(modelo: str | None, *, requiere_vision: bool = False) -> str:
    """Valida el modelo elegido por la interfaz o selecciona uno local."""
    modelos = await llm.modelos_disponibles()
    if not modelos:
        raise HTTPException(503, "No hay modelos descargados en Ollama.")

    solicitado = (modelo or "").strip()
    if solicitado:
        for disponible in modelos:
            if llm._equivale_modelo(solicitado, disponible):
                return disponible
        raise HTTPException(400, f"Modelo no disponible en Ollama: {solicitado}")

    elegido = llm.elegir_nombre_preferido(modelos, vision=requiere_vision)
    if not elegido:
        raise HTTPException(503, "No hay modelos descargados en Ollama.")
    return elegido


def _archivos_de_peticion(
    fichero: UploadFile | None,
    ficheros: list[UploadFile] | None,
) -> list[UploadFile]:
    archivos: list[UploadFile] = []
    if ficheros:
        archivos.extend([a for a in ficheros if a is not None])
    if fichero is not None:
        archivos.append(fichero)

    if not archivos:
        raise HTTPException(400, "Debe subir al menos un fichero.")
    if len(archivos) > MAX_DESCRIBIR_FILES:
        raise HTTPException(
            400,
            f"Demasiados ficheros para un documento compuesto. Máximo: {MAX_DESCRIBIR_FILES}.",
        )
    return archivos


def _combinar_documentos(docs: list[router_entrada.DocumentoProcesado]) -> router_entrada.DocumentoProcesado:
    """Crea una única entrada lógica a partir de varios ficheros ordenados."""
    if len(docs) == 1:
        return docs[0]

    partes_texto: list[str] = []
    imagenes: list[bytes] = []
    rutas: set[str] = set()
    paginas_total = 0
    paginas_conocidas = False
    tamano_total = 0
    nombres: list[str] = []
    tipos: set[str] = set()

    for i, doc in enumerate(docs, start=1):
        nombre = doc.nombre_original or f"archivo_{i}"
        nombres.append(nombre)
        rutas.add(doc.ruta)
        tipos.add(doc.tipo_mime)
        tamano_total += doc.tamano_bytes

        if doc.paginas is not None:
            paginas_total += doc.paginas
            paginas_conocidas = True

        if doc.entrada.texto:
            partes_texto.append(
                f"[Archivo {i} de {len(docs)}: {nombre}]\n" + doc.entrada.texto.strip()
            )
        if doc.entrada.imagenes:
            imagenes.extend(doc.entrada.imagenes)

    if len(imagenes) > MAX_IMAGENES_DOCUMENTO_COMPUESTO:
        raise HTTPException(
            400,
            "El documento compuesto genera demasiadas imágenes para análisis visual. "
            f"Máximo: {MAX_IMAGENES_DOCUMENTO_COMPUESTO}.",
        )

    texto = "\n\n---\n\n".join(partes_texto).strip() or None
    ruta: router_entrada.Ruta
    if texto and imagenes:
        ruta = "hibrida"
    elif imagenes:
        ruta = "vision"
    else:
        ruta = "texto"

    nombre_compuesto = "Documento compuesto (" + str(len(docs)) + " archivos): " + "; ".join(nombres)
    if len(nombre_compuesto) > 500:
        nombre_compuesto = "Documento compuesto (" + str(len(docs)) + " archivos)"

    entrada = extractor.Entrada(texto=texto, imagenes=imagenes or None)
    return router_entrada.DocumentoProcesado(
        entrada=entrada,
        ruta=ruta,
        nombre_original=nombre_compuesto,
        tipo_mime="multipart/mixed" if len(tipos) > 1 else next(iter(tipos), "multipart/mixed"),
        tamano_bytes=tamano_total,
        paginas=paginas_total if paginas_conocidas else None,
    )


def _actualizar_hash_documento(h, indice: int, nombre: str, contenido: bytes) -> None:
    h.update(str(indice).encode("utf-8"))
    h.update(b"\0")
    h.update(nombre.encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(contenido)


async def _procesar_archivos_subidos(
    archivos: list[UploadFile],
    peticion_id: str,
    preferencia_entrada: str = "auto",
) -> tuple[router_entrada.DocumentoProcesado, str | None, list[dict[str, Any]]]:
    """Lee, valida y combina uno o varios ficheros subidos."""
    docs: list[router_entrada.DocumentoProcesado] = []
    archivos_meta: list[dict[str, Any]] = []
    total = 0
    h = hashlib.sha256() if INCLUIR_HASH_DOCUMENTO_AUDITORIA else None

    for i, archivo in enumerate(archivos, start=1):
        contenido = await archivo.read()
        total += len(contenido)
        if total > MAX_DESCRIBIR_TOTAL_BYTES:
            raise HTTPException(
                413,
                f"El conjunto de ficheros supera el tamaño máximo total "
                f"({MAX_DESCRIBIR_TOTAL_BYTES} bytes).",
            )

        nombre = archivo.filename or f"archivo_{i}"
        if h is not None:
            # En hilo aparte: sha256 sobre ficheros de decenas de MB bloquearía
            # el event loop y con él el polling de /api/estado de la interfaz.
            await asyncio.to_thread(_actualizar_hash_documento, h, i, nombre, contenido)

        try:
            # procesar() es síncrono y puede tardar (spawn del sandbox, parseo,
            # OCR local). Se delega a un hilo para no congelar el event loop.
            doc = await asyncio.to_thread(
                router_entrada.procesar, contenido, nombre, preferencia_entrada
            )
        except ErrorValidacion as e:
            _log_peticion("describir_validacion_fallida", peticion_id, archivo=i, error=str(e))
            raise HTTPException(400, f"Archivo {i} ({nombre}): {e}") from None
        except Exception as err:
            logger.exception("[%s] Error inesperado en router para archivo %d", peticion_id, i)
            raise HTTPException(500, f"Error al procesar el archivo {i} ({nombre}).") from err
        finally:
            contenido = b""

        docs.append(doc)
        archivos_meta.append({
            "orden": i,
            "nombre": doc.nombre_original,
            "tipo_mime": doc.tipo_mime,
            "tamano_bytes": doc.tamano_bytes,
            "paginas": doc.paginas,
            "ruta_procesamiento": doc.ruta,
        })

    doc_compuesto = _combinar_documentos(docs)
    sha256_documento = h.hexdigest() if h is not None else None
    return doc_compuesto, sha256_documento, archivos_meta


async def _apagar_proceso_app() -> None:
    """Detiene únicamente el proceso de la aplicación tras enviar la respuesta HTTP."""
    await asyncio.sleep(0.35)
    logger.info("Apagado solicitado desde la interfaz local")
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except Exception:
        logger.exception("No se pudo enviar SIGTERM; salida forzada")
        os._exit(0)


@router.post("/apagar")
async def apagar_desde_interfaz():
    """Apaga el servidor local de la aplicación desde la interfaz.

    No monta el socket de Docker ni ejecuta comandos del host: por seguridad,
    este endpoint solo termina el proceso de la app. En el perfil bundled, el
    contenedor de Ollama puede quedar vivo hasta que se ejecute detener.bat/sh
    o docker compose down.
    """
    if not PERMITIR_APAGADO_UI:
        raise HTTPException(403, "El apagado desde la interfaz está desactivado.")

    asyncio.create_task(_apagar_proceso_app())
    return {
        "ok": True,
        "mensaje": "Apagado iniciado. La aplicación local se detendrá en unos segundos.",
    }


@router.post("/describir")
async def describir(
    ficheros: list[UploadFile] | None = File(None),
    fichero: UploadFile | None = File(None),
    norma: str = Form(...),
    modo: str = Form("esencial"),
    campos: str | None = Form(None),
    detectar_tipo: bool = Form(False),
    idioma_salida: str = Form("es"),
    modelo: str | None = Form(None),
    preferencia_entrada: str = Form("auto"),
):
    """Procesa uno o varios ficheros que forman una única unidad documental."""
    peticion_id = str(uuid.uuid4())[:8]
    _t_inicio = time.monotonic()

    if norma not in NORMAS_DISPONIBLES:
        raise HTTPException(400, f"Norma desconocida: {norma}")
    if modo not in ("esencial", "completo", "personalizado"):
        raise HTTPException(400, f"Modo desconocido: {modo}")

    try:
        preferencia = router_entrada.normalizar_preferencia_entrada(preferencia_entrada)
    except ErrorValidacion as e:
        raise HTTPException(400, str(e)) from None

    idioma_salida = (idioma_salida or "es").strip().lower()
    if idioma_salida not in IDIOMAS_SALIDA_ADMITIDOS:
        raise HTTPException(400, f"Idioma de salida no admitido: {idioma_salida}")

    archivos = _archivos_de_peticion(fichero=fichero, ficheros=ficheros)

    async with _SEM_PROCESAMIENTO:
        _log_peticion(
            "describir_inicio",
            peticion_id,
            norma=norma,
            modo=modo,
            num_archivos=len(archivos),
            detectar_tipo=detectar_tipo,
            idioma_salida=idioma_salida,
            modelo_solicitado=(modelo or "auto"),
            preferencia_entrada=preferencia,
        )

        doc, sha256_documento, archivos_meta = await _procesar_archivos_subidos(
            archivos, peticion_id, preferencia_entrada=preferencia
        )
        requiere_vision = bool(doc.entrada.imagenes)
        modelo_seleccionado = await _resolver_modelo_solicitado(
            modelo,
            requiere_vision=requiere_vision,
        )
        modelo_visual = modelo_seleccionado
        modelo_manual = bool((modelo or "").strip())

        advertencias_preproceso: list[str] = []

        # v4: no reenviar imágenes varias veces al LLM. Si no hay capa textual,
        # se hace una lectura visual rápida una sola vez y el resto del flujo
        # trabaja sobre ese texto consolidado. Esto evita que la detección de
        # tipo y la extracción archivística hagan llamadas multimodales largas.
        if doc.entrada.imagenes and not doc.entrada.texto:
            _log_peticion(
                "lectura_visual_previa_inicio",
                peticion_id,
                imagenes=len(doc.entrada.imagenes),
                modelo=modelo_seleccionado,
            )
            lectura_visual = await extractor.lectura_visual_previa(
                doc.entrada.imagenes,
                modelo=modelo_seleccionado,
            )
            if lectura_visual:
                doc.entrada = extractor.Entrada(texto=lectura_visual, imagenes=None)
                if not modelo_manual:
                    # Dos perfiles: visión para leer la imagen y texto para la extracción.
                    # Esto recupera la agilidad del antiguo modelo PlumA especializado
                    # sin depender de una única llamada multimodal pesada.
                    modelo_seleccionado = await _resolver_modelo_solicitado(
                        None,
                        requiere_vision=False,
                    )
                advertencias_preproceso.append(
                    "Documento visual procesado en modo rápido: PlumA realizó una lectura/transcripción "
                    f"preliminar local de las imágenes con {modelo_visual} y generó la descripción "
                    f"archivística con {modelo_seleccionado}. Revise visualmente los datos antes de usar la propuesta."
                )
                _log_peticion(
                    "lectura_visual_previa_fin",
                    peticion_id,
                    caracteres=len(lectura_visual),
                    imagenes_restantes=0,
                    modelo_extraccion=modelo_seleccionado,
                )
            else:
                advertencias_preproceso.append(
                    "No se obtuvo lectura visual suficiente. Para evitar llamadas multimodales largas, "
                    "PlumA puede devolver una propuesta incompleta; pruebe otro modelo visual u OCR local."
                )
                _log_peticion("lectura_visual_previa_sin_resultado", peticion_id)

        elif doc.entrada.imagenes and doc.entrada.texto and not PLUMA_HIBRIDO_USAR_VISION:
            # En PDFs híbridos el texto suele ser suficiente y muchísimo más rápido.
            doc.entrada = extractor.Entrada(
                texto=doc.entrada.texto,
                imagenes=None,
                plantilla=doc.entrada.plantilla,
                instrucciones_tipo=doc.entrada.instrucciones_tipo,
            )
            advertencias_preproceso.append(
                "Documento híbrido procesado en modo texto para acelerar el análisis local; "
                "las imágenes no se reenviaron al modelo. Active PLUMA_HIBRIDO_USAR_VISION=true "
                "solo si necesita análisis visual adicional."
            )

        requiere_vision_final = bool(doc.entrada.imagenes)

        _log_peticion(
            "documento_procesado",
            peticion_id,
            mime=doc.tipo_mime,
            ruta=doc.ruta,
            paginas=doc.paginas,
            tamano=doc.tamano_bytes,
            num_archivos=len(archivos_meta),
            requiere_vision=requiere_vision_final,
            modelo=modelo_seleccionado,
        )

        ruta_esquema = DIR_ESQUEMAS / NORMAS_DISPONIBLES[norma]["archivo"]
        perfil = NORMAS_DISPONIBLES[norma].get("perfil")
        try:
            esquema = extractor.cargar_esquema(ruta_esquema, perfil=perfil)
        except FileNotFoundError:
            raise HTTPException(500, f"Esquema de norma no disponible: {norma}") from None
        except ValueError as e:
            raise HTTPException(500, f"Esquema inválido: {e}") from None

        filtro_claves = _construir_filtro(modo, campos, norma, esquema)

        # Pre-pasada: detección de tipo documental
        deteccion = None
        if detectar_tipo:
            try:
                catalogo = identificador_tipo.cargar_catalogo(RUTA_CATALOGO_TIPOS)
                if doc.entrada.imagenes and not doc.entrada.texto:
                    _log_peticion(
                        "tipo_deteccion_omitida",
                        peticion_id,
                        motivo="solo_imagen_sin_lectura_visual",
                    )
                    deteccion = None
                else:
                    deteccion = await identificador_tipo.detectar(
                        texto=doc.entrada.texto,
                        imagenes=doc.entrada.imagenes,
                        catalogo=catalogo,
                        modelo=modelo_seleccionado,
                    )
                if deteccion:
                    _log_peticion(
                        "tipo_detectado",
                        peticion_id,
                        tipo=deteccion.tipo.clave,
                        confianza=deteccion.confianza,
                    )
                    doc.entrada.plantilla = deteccion.tipo.clave
                    doc.entrada.instrucciones_tipo = {
                        clave: instruccion
                        for clave, instruccion in deteccion.tipo.instrucciones.items()
                        if filtro_claves is None or clave in filtro_claves
                    }
            except Exception:
                logger.exception(
                    "[%s] Error en detección de tipo; sigue sin plantilla", peticion_id
                )

        # Extracción principal
        try:
            propuesta = await extractor.extraer(
                entrada=doc.entrada,
                esquema=esquema,
                modelo=modelo_seleccionado,
                filtro_claves=filtro_claves,
                idioma_salida=idioma_salida,
            )
            if advertencias_preproceso:
                propuesta.advertencias = advertencias_preproceso + propuesta.advertencias
        except Exception as err:
            logger.exception("[%s] Error en extracción", peticion_id)
            raise HTTPException(500, "Error al generar la propuesta de descripción.") from err

        _log_peticion(
            "describir_fin",
            peticion_id,
            campos=len(propuesta.campos),
            advertencias=len(propuesta.advertencias),
            segundos=round(time.monotonic() - _t_inicio, 1),
        )

    ficha_tecnica = auditoria.generar_ficha_tecnica(
        peticion_id=peticion_id,
        documento=doc,
        esquema=esquema,
        modo=modo,
        idioma_salida=idioma_salida,
        modelo=modelo_seleccionado,
        filtro_claves=filtro_claves,
        propuesta=propuesta,
        deteccion=deteccion,
        sha256_documento=sha256_documento,
    )

    return {
        "peticion": peticion_id,
        "idioma_salida": idioma_salida,
        "version_pluma": APP_VERSION,
        "documento": {
            "nombre": doc.nombre_original,
            "sha256": sha256_documento,
            "tipo_mime": doc.tipo_mime,
            "tamano_bytes": doc.tamano_bytes,
            "paginas": doc.paginas,
            "ruta_procesamiento": doc.ruta,
            "preferencia_entrada": preferencia,
            "num_archivos": len(archivos_meta),
            "archivos": archivos_meta,
        },
        "tipo_detectado": (
            {
                "clave": deteccion.tipo.clave,
                "nombre": deteccion.tipo.nombre,
                "familia": deteccion.tipo.familia,
                "confianza": deteccion.confianza,
                "evidencia": deteccion.evidencia,
            } if deteccion else None
        ),
        "auditoria": ficha_tecnica,
        "propuesta": propuesta.to_dict(),
    }


def _construir_filtro(
    modo: str,
    campos_str: str | None,
    norma: str,
    esquema: extractor.Esquema,
) -> set[str] | None:
    """Traduce el modo solicitado en un conjunto de claves, o None si es 'completo'."""
    if modo == "completo":
        return None

    if modo == "esencial":
        if norma == "isad-g":
            return CAMPOS_ESENCIALES_ISAD
        return {e.clave for e in esquema.elementos if e.obligatorio and e.extraible != "no"}

    if modo == "personalizado":
        if not campos_str:
            raise HTTPException(400, "Modo personalizado requiere el parámetro 'campos'.")
        claves = {c.strip() for c in campos_str.split(",") if c.strip()}
        claves_validas = {e.clave for e in esquema.elementos}
        desconocidas = claves - claves_validas
        if desconocidas:
            raise HTTPException(400, f"Campos desconocidos: {', '.join(sorted(desconocidas))}")
        return claves

    return None


@router.post("/exportar/{formato}")
async def exportar(formato: str, payload: dict):
    """Exporta una propuesta editada en el formato solicitado."""
    formatos_validos = {"json", "csv", "ead", "eac-cpf", "turtle"}
    if formato not in formatos_validos:
        raise HTTPException(400, f"Formato no soportado: {formato}")

    payload = _validar_payload_exportacion(payload)

    norma_nombre = payload.get("propuesta", {}).get("norma")
    if not norma_nombre:
        raise HTTPException(400, "El payload no incluye información de norma.")

    norma_clave = None
    for clave, datos in NORMAS_DISPONIBLES.items():
        if datos["nombre"] == norma_nombre:
            norma_clave = clave
            break
    if norma_clave is None:
        raise HTTPException(400, f"Norma no reconocida: {norma_nombre}")

    ruta_esquema = DIR_ESQUEMAS / NORMAS_DISPONIBLES[norma_clave]["archivo"]
    perfil = NORMAS_DISPONIBLES[norma_clave].get("perfil")

    try:
        from . import exportadores
        contenido, mime, nombre = exportadores.exportar(
            formato=formato,
            propuesta=payload,
            norma=norma_clave,
            ruta_esquema=ruta_esquema,
            perfil=perfil,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    except Exception as err:
        logger.exception("Error al generar exportación %s", formato)
        raise HTTPException(500, f"Error al generar el fichero {formato.upper()}.") from err

    return Response(
        content=contenido,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# =============================================================================
# Validación del payload de exportación
# =============================================================================

def _validar_payload_exportacion(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(400, "Payload inválido: se esperaba un objeto JSON.")

    propuesta = payload.get("propuesta")
    if not isinstance(propuesta, dict):
        raise HTTPException(400, "Payload inválido: falta el objeto 'propuesta'.")

    campos = propuesta.get("campos")
    if not isinstance(campos, list):
        raise HTTPException(400, "Payload inválido: 'propuesta.campos' debe ser una lista.")
    if len(campos) > MAX_CAMPOS_EXPORTACION:
        raise HTTPException(
            400,
            f"Demasiados campos para exportar: {len(campos)}; máximo {MAX_CAMPOS_EXPORTACION}.",
        )

    # Limita tamaño lógico adicional al Content-Length. json.dumps actúa como
    # contador aproximado de la estructura ya parseada.
    try:
        tamano_logico = len(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError):
        raise HTTPException(400, "Payload inválido: contiene valores no serializables.") from None
    if tamano_logico > MAX_EXPORT_BODY_BYTES:
        raise HTTPException(413, "Payload de exportación demasiado grande.")

    for idx, campo in enumerate(campos):
        if not isinstance(campo, dict):
            raise HTTPException(400, f"Campo #{idx + 1} inválido: debe ser un objeto.")
        _validar_cadena_corta(campo.get("id"), "id", idx, 128)
        _validar_cadena_corta(campo.get("clave"), "clave", idx, 128)
        _validar_cadena_corta(campo.get("nombre"), "nombre", idx, 512)
        _validar_cadena_corta(campo.get("confianza"), "confianza", idx, 32, permitir_none=True)
        _validar_valor_exportacion(campo.get("valor"), idx)
        _validar_cadena_corta(
            campo.get("evidencia"),
            "evidencia",
            idx,
            MAX_LONGITUD_EVIDENCIA_EXPORTACION,
            permitir_none=True,
        )

    return payload


def _validar_cadena_corta(
    valor: Any,
    nombre: str,
    idx: int,
    max_len: int,
    *,
    permitir_none: bool = False,
) -> None:
    if valor is None and permitir_none:
        return
    if valor is None:
        return
    if not isinstance(valor, str):
        raise HTTPException(400, f"Campo #{idx + 1}: '{nombre}' debe ser texto.")
    if len(valor) > max_len:
        raise HTTPException(
            400,
            f"Campo #{idx + 1}: '{nombre}' supera la longitud máxima de {max_len} caracteres.",
        )
    _validar_sin_controles_peligrosos(valor, nombre, idx)


def _validar_valor_exportacion(valor: Any, idx: int) -> None:
    if valor in (None, ""):
        return
    if isinstance(valor, str):
        if len(valor) > MAX_LONGITUD_VALOR_EXPORTACION:
            raise HTTPException(
                400,
                f"Campo #{idx + 1}: valor demasiado largo; máximo "
                f"{MAX_LONGITUD_VALOR_EXPORTACION} caracteres.",
            )
        _validar_sin_controles_peligrosos(valor, "valor", idx)
        return
    if isinstance(valor, list):
        if len(valor) > MAX_ITEMS_LISTA_EXPORTACION:
            raise HTTPException(
                400,
                f"Campo #{idx + 1}: lista demasiado larga; máximo "
                f"{MAX_ITEMS_LISTA_EXPORTACION} elementos.",
            )
        for item in valor:
            if not isinstance(item, str):
                raise HTTPException(400, f"Campo #{idx + 1}: los valores de lista deben ser texto.")
            if len(item) > MAX_LONGITUD_VALOR_EXPORTACION:
                raise HTTPException(
                    400,
                    f"Campo #{idx + 1}: elemento de lista demasiado largo; máximo "
                    f"{MAX_LONGITUD_VALOR_EXPORTACION} caracteres.",
                )
            _validar_sin_controles_peligrosos(item, "valor", idx)
        return
    if isinstance(valor, (int, float, bool)):
        return
    raise HTTPException(400, f"Campo #{idx + 1}: tipo de valor no admitido.")


def _validar_sin_controles_peligrosos(valor: str, nombre: str, idx: int) -> None:
    """Rechaza caracteres de control incompatibles con XML/RDF/JSON seguro."""
    for ch in valor:
        code = ord(ch)
        if (code < 32 and ch not in "\n\r\t") or code == 127:
            raise HTTPException(
                400,
                f"Campo #{idx + 1}: '{nombre}' contiene caracteres de control no admitidos.",
            )


# =============================================================================
# Punto de extensión para la futura versión Pro
# =============================================================================
# Los endpoints Pro vivirán en un módulo separado y se montarán con:
#     app.include_router(router_pro, prefix="/api/pro")
# Nada de este fichero cambia.


@router.get("/seguridad-local")
async def seguridad_local():
    """Estado efectivo del bloqueo local de la release pública."""
    return security_status()
