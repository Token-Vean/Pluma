"""
Regresiones corregidas tras la revisión del código para el artículo de arXiv.

1. `extraible: no` sin comillas: PyYAML (YAML 1.1) lo carga como el booleano
   False. Los campos manuales se trataban como extraíbles: se enviaban al
   modelo sin instrucción, no recibían su valor por defecto y la interfaz no
   los marcaba como manuales.
2. Evidencias de documentos visuales: tras la lectura visual previa, las
   evidencias se cotejaban con la transcripción generada por el propio modelo
   y podían aparecer como "localizada" con confianza alta, aunque nadie las
   hubiera comparado con la imagen original.
3. Lectura visual repetida: si la lectura previa de api.py fallaba, el
   extractor la volvía a lanzar sobre las mismas imágenes.

Estos tests no necesitan Ollama: sustituyen las llamadas al modelo.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app import extractor

DIR_SCHEMAS = Path(__file__).parent.parent / "schemas"

NORMAS_PLANAS = ["isad-g.yaml", "dacs.yaml", "isaar-cpf.yaml", "isdf.yaml", "isdiah.yaml"]
PERFILES_RIC = ["record", "recordset", "agent", "activity"]


# =============================================================================
# 1. Normalización de 'extraible'
# =============================================================================

def _esquemas_enviados():
    for nombre in NORMAS_PLANAS:
        yield nombre, extractor.cargar_esquema(DIR_SCHEMAS / nombre)
    for perfil in PERFILES_RIC:
        yield f"ric.yaml#{perfil}", extractor.cargar_esquema(DIR_SCHEMAS / "ric.yaml", perfil=perfil)


def test_extraible_siempre_es_una_cadena_valida():
    for nombre, esquema in _esquemas_enviados():
        for el in esquema.elementos:
            assert el.extraible in {"si", "parcial", "no"}, (nombre, el.clave, el.extraible)


def test_isad_g_distingue_campos_manuales():
    esquema = extractor.cargar_esquema(DIR_SCHEMAS / "isad-g.yaml")
    niveles = [el.extraible for el in esquema.elementos]
    assert len(esquema.elementos) == 26
    assert niveles.count("si") == 6
    assert niveles.count("parcial") == 8
    assert niveles.count("no") == 12
    extraibles = {el.clave for el in esquema.extraibles()}
    assert len(extraibles) == 14
    for manual in ("historia_archivistica", "valoracion_seleccion", "reglas_normas", "fecha_descripcion"):
        assert manual not in extraibles


def test_los_campos_manuales_no_llegan_al_prompt():
    esquema = extractor.cargar_esquema(DIR_SCHEMAS / "isad-g.yaml")
    prompt = extractor.construir_prompt(esquema, extractor.Entrada(texto="Documento de prueba."))
    assert '"titulo"' in prompt
    assert '"valoracion_seleccion"' not in prompt
    assert '"fecha_descripcion"' not in prompt


def test_esencial_de_otras_normas_excluye_obligatorios_manuales():
    # Réplica de api._construir_filtro para modo esencial fuera de ISAD(G):
    # obligatorios y extraíbles. Antes se colaban los obligatorios manuales.
    esquema = extractor.cargar_esquema(DIR_SCHEMAS / "isaar-cpf.yaml")
    esenciales = {e.clave for e in esquema.elementos if e.obligatorio and e.extraible != "no"}
    obligatorios = {e.clave for e in esquema.elementos if e.obligatorio}
    assert len(obligatorios) == 8
    assert len(esenciales) == 3


def test_aplicar_defaults_rellena_campos_manuales():
    esquema = extractor.cargar_esquema(DIR_SCHEMAS / "isaar-cpf.yaml")
    campos = extractor.aplicar_defaults(esquema, [])
    manuales = [c for c in campos if c.extraible == "no"]
    assert len(manuales) == 15
    con_valor = [c for c in manuales if c.valor not in (None, "", [])]
    assert con_valor, "los valores por defecto de ISAAR(CPF) no se aplicaron"


def test_booleanos_yaml_se_normalizan(tmp_path):
    ruta = tmp_path / "prueba.yaml"
    ruta.write_text(
        "norma: PRUEBA\n"
        "version: '1'\n"
        "nombre: Prueba\n"
        "idioma: es\n"
        "areas:\n"
        "  - id: a\n"
        "    nombre: Área\n"
        "    elementos:\n"
        "      - {id: '1', clave: manual, nombre: M, tipo: texto, obligatorio: false, multiple: false, extraible: no}\n"
        "      - {id: '2', clave: auto, nombre: A, tipo: texto, obligatorio: false, multiple: false, extraible: yes}\n"
        "      - {id: '3', clave: tilde, nombre: T, tipo: texto, obligatorio: false, multiple: false, extraible: 'Sí'}\n"
        "      - {id: '4', clave: comillas, nombre: C, tipo: texto, obligatorio: false, multiple: false, extraible: 'no'}\n",
        encoding="utf-8",
    )
    esquema = extractor.cargar_esquema(ruta)
    assert [e.extraible for e in esquema.elementos] == ["no", "si", "si", "no"]


def test_extraible_invalido_se_rechaza(tmp_path):
    ruta = tmp_path / "invalido.yaml"
    ruta.write_text(
        "norma: PRUEBA\n"
        "version: '1'\n"
        "nombre: Prueba\n"
        "idioma: es\n"
        "areas:\n"
        "  - id: a\n"
        "    nombre: Área\n"
        "    elementos:\n"
        "      - {id: '1', clave: raro, nombre: R, tipo: texto, obligatorio: false, multiple: false, extraible: quizas}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="extraible"):
        extractor.cargar_esquema(ruta)


# =============================================================================
# 2 y 3. Documentos visuales
# =============================================================================

TRANSCRIPCION = (
    "[Imagen 1]\nOficio del Ayuntamiento de Villanueva al Gobierno Civil sobre el "
    "abastecimiento de aguas, fechado el 3 de abril de 1931."
)


def _esquema_titulo() -> extractor.Esquema:
    return extractor.Esquema(
        norma="TEST",
        version="1",
        nombre="Test",
        idioma="es",
        elementos=[
            extractor.ElementoEsquema(
                id="1.1", clave="titulo", nombre="Título", tipo="texto",
                obligatorio=True, multiple=False, extraible="si",
                instruccion="Propón un título.",
            ),
            extractor.ElementoEsquema(
                id="1.2", clave="alcance", nombre="Alcance", tipo="texto",
                obligatorio=False, multiple=False, extraible="si",
                instruccion="Resume el contenido.",
            ),
        ],
    )


def _respuesta(evidencia_titulo: str, evidencia_alcance: str) -> str:
    return json.dumps({
        "campos": {
            "titulo": {"valor": "Oficio sobre abastecimiento de aguas", "confianza": "alta",
                       "evidencia": evidencia_titulo},
            "alcance": {"valor": "Comunicación sobre aguas", "confianza": "alta",
                        "evidencia": evidencia_alcance},
        }
    })


def _instalar_simulador(monkeypatch, respuesta: str, lecturas: list[int], transcripcion: str | None):
    async def generar(*, prompt, modelo, imagenes=None, formato_json=False, diagnostico=None, **_):
        if diagnostico is not None:
            diagnostico.update({"num_ctx": 8192, "num_predict": 4096,
                                "prompt_eval_count": 1000, "eval_count": 100,
                                "done_reason": "stop", "caracteres_prompt": len(prompt)})
        return respuesta

    async def lectura(imagenes, modelo=None):
        lecturas.append(len(imagenes or []))
        return transcripcion

    monkeypatch.setattr(extractor.llm, "generar", generar)
    monkeypatch.setattr(extractor, "lectura_visual_previa", lectura)


def test_evidencia_de_lectura_visual_no_se_da_por_verificada(monkeypatch):
    lecturas: list[int] = []
    _instalar_simulador(
        monkeypatch,
        _respuesta("sobre el abastecimiento de aguas", "Texto que no figura en ninguna parte del documento"),
        lecturas,
        transcripcion=None,
    )
    # Situación de api.py tras una lectura visual previa con éxito.
    entrada = extractor.Entrada(
        texto=TRANSCRIPCION, imagenes=None,
        origen_texto="lectura_visual", lectura_visual_intentada=True,
    )
    propuesta = asyncio.run(extractor.extraer(entrada, _esquema_titulo(), "modelo"))
    campos = {c.clave: c for c in propuesta.campos}

    titulo = campos["titulo"]
    assert titulo.estado_evidencia == "no_verificable"
    assert titulo.span is None
    assert titulo.confianza == "media"

    alcance = campos["alcance"]
    assert alcance.estado_evidencia == "no_localizada"
    assert alcance.confianza == "baja"

    assert propuesta.contexto["texto_cotejo_evidencias"] == "lectura_visual"
    assert any("lectura visual previa" in a for a in propuesta.advertencias)
    assert lecturas == []


def test_texto_del_documento_sigue_verificandose(monkeypatch):
    lecturas: list[int] = []
    _instalar_simulador(
        monkeypatch,
        _respuesta("sobre el abastecimiento de aguas", "fechado el 3 de abril de 1931"),
        lecturas,
        transcripcion=None,
    )
    entrada = extractor.Entrada(texto=TRANSCRIPCION)  # origen por defecto: documento
    propuesta = asyncio.run(extractor.extraer(entrada, _esquema_titulo(), "modelo"))
    for campo in propuesta.campos:
        assert campo.estado_evidencia == "localizada"
        assert campo.confianza == "alta"
        assert campo.span is not None
    assert propuesta.contexto["texto_cotejo_evidencias"] == "documento"


def test_lectura_visual_del_extractor_marca_el_origen(monkeypatch):
    lecturas: list[int] = []
    _instalar_simulador(
        monkeypatch,
        _respuesta("sobre el abastecimiento de aguas", "fechado el 3 de abril de 1931"),
        lecturas,
        transcripcion=TRANSCRIPCION,
    )
    entrada = extractor.Entrada(texto=None, imagenes=[b"img"])
    propuesta = asyncio.run(extractor.extraer(entrada, _esquema_titulo(), "modelo"))
    assert lecturas == [1]
    for campo in propuesta.campos:
        assert campo.estado_evidencia == "no_verificable"
        assert campo.confianza == "media"
    assert propuesta.contexto["texto_cotejo_evidencias"] == "lectura_visual"


def test_lectura_visual_fallida_no_se_repite(monkeypatch):
    lecturas: list[int] = []
    _instalar_simulador(
        monkeypatch,
        _respuesta("sobre el abastecimiento de aguas", "fechado el 3 de abril de 1931"),
        lecturas,
        transcripcion=None,
    )
    # Situación de api.py tras una lectura visual previa sin resultado.
    entrada = extractor.Entrada(texto=None, imagenes=[b"img"], lectura_visual_intentada=True)
    propuesta = asyncio.run(extractor.extraer(entrada, _esquema_titulo(), "modelo"))
    assert lecturas == []
    for campo in propuesta.campos:
        assert campo.estado_evidencia == "no_verificable"
    assert propuesta.contexto["texto_cotejo_evidencias"] == "ninguno"
