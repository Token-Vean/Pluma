"""
Identificador de tipo documental.

Hace una pre-pasada ligera al LLM para determinar qué tipo documental
estamos procesando (acta, oficio, carta, escritura notarial...) antes
de lanzar la extracción principal. El tipo detectado permite:

    1. Mostrarlo en la UI como información contextual.
    2. Inyectar instrucciones específicas en la extracción principal
       para los campos que el catálogo marque como ajustables
       (título, alcance, productor, nivel).

Si el usuario desactiva la detección, se salta este paso y la
extracción se hace con las instrucciones genéricas del esquema.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import llm

logger = logging.getLogger(__name__)


# =============================================================================
# Tipos
# =============================================================================

@dataclass
class TipoDocumental:
    clave: str
    nombre: str
    familia: str
    descripcion: str
    rasgos: list[str] = field(default_factory=list)
    instrucciones: dict[str, str] = field(default_factory=dict)


@dataclass
class Catalogo:
    version: str
    idioma: str
    tipos: list[TipoDocumental]

    def por_clave(self, clave: str) -> TipoDocumental | None:
        return next((t for t in self.tipos if t.clave == clave), None)


@dataclass
class DeteccionTipo:
    tipo: TipoDocumental
    confianza: str            # "alta" | "media" | "baja"
    evidencia: str | None     # fragmento que lo justifica


# =============================================================================
# Carga del catálogo
# =============================================================================

_catalogo_cache: Catalogo | None = None


def cargar_catalogo(ruta: str | Path) -> Catalogo:
    """Carga el YAML del catálogo de tipos. Cacheado."""
    global _catalogo_cache
    if _catalogo_cache is not None:
        return _catalogo_cache

    with Path(ruta).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    tipos = [TipoDocumental(**t) for t in data["tipos"]]
    _catalogo_cache = Catalogo(
        version=str(data["version"]),
        idioma=data["idioma"],
        tipos=tipos,
    )
    return _catalogo_cache


# =============================================================================
# Construcción del prompt de detección
# =============================================================================

_PROMPT_DETECCION = """\
Identifica el tipo documental al que pertenece el documento proporcionado,
eligiendo UNO de los tipos del catálogo siguiente. Basa tu decisión en
los rasgos identificadores de cada tipo y en el contenido visible del
documento.

Reglas:
- Solo puedes elegir una clave del catálogo. No inventes tipos.
- Si ningún tipo encaja con seguridad, elige "no_identificado".
- Marca la confianza como "alta" si varios rasgos coinciden, "media" si
  coinciden algunos, "baja" si la identificación es tentativa.
- Cita un fragmento literal del documento (5-30 palabras) que justifique
  tu elección.

Devuelve EXCLUSIVAMENTE este JSON:
{{"tipo": "<clave>", "confianza": "alta|media|baja", "evidencia": "<cita>"}}

# Catálogo de tipos
{catalogo}

# Documento
<<<DOCUMENTO_INICIO>>>
{documento}
<<<DOCUMENTO_FIN>>>
"""


def _catalogo_compacto(catalogo: Catalogo) -> str:
    """
    Produce una versión textual compacta del catálogo para el prompt.
    Solo clave, nombre y rasgos: el LLM no necesita la descripción ni
    las instrucciones para identificar.
    """
    partes = []
    for t in catalogo.tipos:
        rasgos = "\n    ".join(f"- {r}" for r in t.rasgos) if t.rasgos else "(sin rasgos específicos)"
        partes.append(f'- clave: "{t.clave}"\n  nombre: {t.nombre}\n  rasgos:\n    {rasgos}')
    return "\n".join(partes)


# =============================================================================
# Función pública
# =============================================================================

async def detectar(
    texto: str | None,
    imagenes: list[bytes] | None,
    catalogo: Catalogo,
    modelo: str,
) -> DeteccionTipo | None:
    """
    Detecta el tipo documental del documento proporcionado.

    Devuelve None si el modelo falla — en ese caso la extracción
    principal se hará sin pista de tipo.
    """
    if not texto and not imagenes:
        return None

    documento = texto or "[Documento solo en imagen]"

    # El texto puede ser largo; truncamos para la detección (los rasgos
    # identificadores suelen estar en las primeras y últimas líneas).
    if len(documento) > 4000:
        documento = documento[:2500] + "\n[...]\n" + documento[-1500:]

    prompt = _PROMPT_DETECCION.format(
        catalogo=_catalogo_compacto(catalogo),
        documento=documento,
    )

    try:
        respuesta = await llm.generar(
            prompt=prompt,
            modelo=modelo,
            imagenes=imagenes,
            formato_json=True,
            temperatura=0.0,   # determinismo máximo para identificación
        )
    except Exception as e:
        logger.warning("Fallo en detección de tipo: %s", e)
        return None

    try:
        data = json.loads(respuesta)
    except json.JSONDecodeError:
        logger.warning("Detección devolvió JSON inválido: %s", respuesta[:200])
        return None

    clave = data.get("tipo")
    tipo = catalogo.por_clave(clave) if clave else None
    if tipo is None:
        logger.info("Detección sin coincidencia; clave devuelta: %r", clave)
        tipo = catalogo.por_clave("no_identificado")
        if tipo is None:
            return None

    confianza = data.get("confianza")
    if confianza not in ("alta", "media", "baja"):
        confianza = "baja"

    return DeteccionTipo(
        tipo=tipo,
        confianza=confianza,
        evidencia=data.get("evidencia"),
    )


def instrucciones_de_tipo(
    deteccion: DeteccionTipo | None,
    clave_campo: str,
) -> str | None:
    """
    Devuelve la instrucción específica del tipo detectado para un campo,
    o None si el tipo no tiene ajuste para ese campo.

    Se llama desde el extractor al construir el prompt de extracción:
    si devuelve algo, se concatena a la instrucción del esquema.
    """
    if deteccion is None:
        return None
    return deteccion.tipo.instrucciones.get(clave_campo)
