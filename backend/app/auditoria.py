"""
Ficha técnica ligera del proceso.

La ficha no almacena ni devuelve el contenido textual del documento. Resume
metadatos de proceso, controles de seguridad y verificabilidad de evidencias
para que el usuario pueda documentar cómo se generó una propuesta.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any
from urllib.parse import urlparse

from . import router as router_entrada
from .security_policy import network_exposure_allowed, remote_ollama_allowed
from .parser_sandbox import sandbox_activo
from .version import APP_NAME, APP_VERSION

VALORES_TRUE = {"1", "true", "yes", "si", "sí", "on"}


def _env_true(nombre: str, defecto: str = "false") -> bool:
    return os.getenv(nombre, defecto).strip().lower() in VALORES_TRUE


def _host_ollama() -> str:
    url = os.getenv("OLLAMA_URL", "")
    try:
        p = urlparse(url)
    except Exception:
        return "no disponible"
    if not p.hostname:
        return "no disponible"
    puerto = f":{p.port}" if p.port else ""
    return f"{p.scheme}://{p.hostname}{puerto}"


def _estado_evidencia(campo: Any) -> str:
    estado = getattr(campo, "estado_evidencia", None)
    if estado:
        return str(estado)
    valor = getattr(campo, "valor", None)
    evidencia = getattr(campo, "evidencia", None)
    span = getattr(campo, "span", None)
    if valor in (None, "", []):
        return "sin_valor"
    if evidencia and span:
        return "localizada"
    if evidencia:
        return "no_verificable"
    return "sin_evidencia"


def generar_ficha_tecnica(
    *,
    peticion_id: str,
    documento: Any,
    esquema: Any,
    modo: str,
    idioma_salida: str,
    modelo: str,
    filtro_claves: set[str] | None,
    propuesta: Any,
    deteccion: Any,
    sha256_documento: str | None,
) -> dict[str, Any]:
    campos = list(getattr(propuesta, "campos", []) or [])
    estados = [_estado_evidencia(c) for c in campos]
    con_valor = sum(1 for c in campos if getattr(c, "valor", None) not in (None, "", []))
    con_evidencia = sum(1 for c in campos if getattr(c, "evidencia", None))

    return {
        "formato": "pluma-ficha-tecnica-v1",
        "aplicacion": {
            "nombre": APP_NAME,
            "version": APP_VERSION,
        },
        "peticion_id": peticion_id,
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "documento": {
            "nombre": getattr(documento, "nombre_original", None),
            "sha256": sha256_documento,
            "tipo_mime": getattr(documento, "tipo_mime", None),
            "tamano_bytes": getattr(documento, "tamano_bytes", None),
            "paginas": getattr(documento, "paginas", None),
            "ruta_procesamiento": getattr(documento, "ruta", None),
        },
        "configuracion": {
            "norma": getattr(esquema, "norma", None),
            "version_norma": getattr(esquema, "version", None),
            "modo": modo,
            "idioma_salida": idioma_salida,
            "modelo": modelo,
            "campos_solicitados": None if filtro_claves is None else len(filtro_claves),
            "deteccion_tipo_activada": deteccion is not None,
            "tipo_detectado": (
                {
                    "clave": deteccion.tipo.clave,
                    "nombre": deteccion.tipo.nombre,
                    "confianza": deteccion.confianza,
                }
                if deteccion else None
            ),
        },
        "controles_seguridad": {
            "procesamiento_local_previsto": True,
            "perfil": os.getenv("PERFIL", "no especificado"),
            "ollama_endpoint": _host_ollama(),
            "allow_remote_ollama": remote_ollama_allowed(),
            "allow_network_exposure": network_exposure_allowed(),
            "sandbox_parsers_activo": sandbox_activo(),
            "apagado_ui_permitido": _env_true("PERMITIR_APAGADO_UI", "false"),
        },
        "limites_aplicados": {
            "tamano_maximo_fichero_bytes": router_entrada.TAMANO_MAXIMO_BYTES,
            "paginas_maximas_pdf": router_entrada.PAGINAS_MAXIMAS_PDF,
            "paginas_pdf_vision_max": router_entrada.PAGINAS_PDF_VISION_MAX,
            "longitud_maxima_texto_extraido": router_entrada.LONGITUD_MAXIMA_TEXTO,
            "pixeles_maximos_imagen": router_entrada.PIXELS_MAXIMOS_IMAGEN,
        },
        "control_evidencia": {
            "campos_totales": len(campos),
            "campos_con_valor": con_valor,
            "campos_con_evidencia": con_evidencia,
            "evidencias_localizadas": estados.count("localizada"),
            "evidencias_no_localizadas": estados.count("no_localizada"),
            "evidencias_no_verificables_textualmente": estados.count("no_verificable"),
            "campos_sin_evidencia": estados.count("sin_evidencia"),
            "campos_sin_valor": estados.count("sin_valor"),
        },
        "resultado": {
            "advertencias": len(getattr(propuesta, "advertencias", []) or []),
            "nota": (
                "La ficha no contiene texto documental ni valores propuestos; "
                "solo metadatos técnicos y de control. El hash SHA-256 identifica "
                "el fichero procesado sin almacenar su contenido."
            ),
        },
    }
