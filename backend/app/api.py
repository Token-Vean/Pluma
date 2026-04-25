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
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from . import auditoria, extractor, identificador_tipo, router as router_entrada
from .router import ErrorValidacion
from .version import APP_VERSION

logger = logging.getLogger(__name__)


# =============================================================================
# Configuración
# =============================================================================

MODELO = os.getenv("MODELO_NOMBRE", "pluma")
DIR_ESQUEMAS = Path(os.getenv("DIR_ESQUEMAS", "/app/schemas"))
RUTA_CATALOGO_TIPOS = DIR_ESQUEMAS / "tipos-documentales.yaml"

# El multipart añade cabeceras y límites alrededor del fichero. Permitimos
# 2 MB de margen sobre el tamaño documental admitido por router.py.
MAX_DESCRIBIR_BODY_BYTES = int(
    os.getenv("MAX_DESCRIBIR_BODY_BYTES", str(router_entrada.TAMANO_MAXIMO_BYTES + 2 * 1024 * 1024))
)
MAX_EXPORT_BODY_BYTES = int(os.getenv("MAX_EXPORT_BODY_BYTES", str(15 * 1024 * 1024)))
MAX_CAMPOS_EXPORTACION = int(os.getenv("MAX_CAMPOS_EXPORTACION", "250"))
MAX_LONGITUD_VALOR_EXPORTACION = int(os.getenv("MAX_LONGITUD_VALOR_EXPORTACION", "50000"))
MAX_LONGITUD_EVIDENCIA_EXPORTACION = int(os.getenv("MAX_LONGITUD_EVIDENCIA_EXPORTACION", "8000"))
MAX_ITEMS_LISTA_EXPORTACION = int(os.getenv("MAX_ITEMS_LISTA_EXPORTACION", "100"))
MAX_PROCESAMIENTOS_SIMULTANEOS = max(
    1, int(os.getenv("MAX_PROCESAMIENTOS_SIMULTANEOS", "1"))
)
PERMITIR_APAGADO_UI = os.getenv("PERMITIR_APAGADO_UI", "true").strip().lower() in {
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
    fichero: UploadFile = File(...),
    norma: str = Form(...),
    modo: str = Form("esencial"),
    campos: str | None = Form(None),
    detectar_tipo: bool = Form(True),
    idioma_salida: str = Form("es"),
):
    """Procesa un documento y devuelve la propuesta de descripción."""
    peticion_id = str(uuid.uuid4())[:8]

    if norma not in NORMAS_DISPONIBLES:
        raise HTTPException(400, f"Norma desconocida: {norma}")
    if modo not in ("esencial", "completo", "personalizado"):
        raise HTTPException(400, f"Modo desconocido: {modo}")

    idioma_salida = (idioma_salida or "es").strip().lower()
    if idioma_salida not in IDIOMAS_SALIDA_ADMITIDOS:
        raise HTTPException(400, f"Idioma de salida no admitido: {idioma_salida}")

    async with _SEM_PROCESAMIENTO:
        contenido = await fichero.read()
        sha256_documento = (
            hashlib.sha256(contenido).hexdigest()
            if INCLUIR_HASH_DOCUMENTO_AUDITORIA else None
        )
        _log_peticion(
            "describir_inicio",
            peticion_id,
            norma=norma,
            modo=modo,
            tamano=len(contenido),
            detectar_tipo=detectar_tipo,
            idioma_salida=idioma_salida,
        )

        try:
            doc = router_entrada.procesar(contenido, fichero.filename or "sin_nombre")
        except ErrorValidacion as e:
            _log_peticion("describir_validacion_fallida", peticion_id, error=str(e))
            raise HTTPException(400, str(e)) from None
        except Exception as err:
            logger.exception("[%s] Error inesperado en router", peticion_id)
            raise HTTPException(500, "Error al procesar el fichero.") from err
        finally:
            # No es borrado seguro de memoria en Python; solo elimina la referencia
            # local lo antes posible. La documentación evita prometer borrado seguro.
            contenido = b""

        _log_peticion(
            "documento_procesado",
            peticion_id,
            mime=doc.tipo_mime,
            ruta=doc.ruta,
            paginas=doc.paginas,
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
                deteccion = await identificador_tipo.detectar(
                    texto=doc.entrada.texto,
                    imagenes=doc.entrada.imagenes,
                    catalogo=catalogo,
                    modelo=MODELO,
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
                modelo=MODELO,
                filtro_claves=filtro_claves,
                idioma_salida=idioma_salida,
            )
        except Exception as err:
            logger.exception("[%s] Error en extracción", peticion_id)
            raise HTTPException(500, "Error al generar la propuesta de descripción.") from err

        _log_peticion(
            "describir_fin",
            peticion_id,
            campos=len(propuesta.campos),
            advertencias=len(propuesta.advertencias),
        )

    ficha_tecnica = auditoria.generar_ficha_tecnica(
        peticion_id=peticion_id,
        documento=doc,
        esquema=esquema,
        modo=modo,
        idioma_salida=idioma_salida,
        modelo=MODELO,
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
