"""
Regresión: «El modelo devolvió JSON inválido; se omiten propuestas».

Hasta 0.7.2 la extracción pedía JSON en modo blando y cualquier defecto de
sintaxis del modelo descartaba la propuesta entera. Estas pruebas cubren:

- la reparación sintáctica de llm.extraer_json_texto() / llm.reparar_json();
- el esquema JSON de respuesta que se envía como salida estructurada;
- el envío de `format` en llm.generar() y el reintento sin él cuando Ollama
  rechaza la gramática;
- el reintento de la extracción monolítica (modo esencial) ante JSON inválido.

No requieren Ollama: el cliente HTTP se sustituye por uno simulado.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app import extractor, llm

RAIZ = Path(__file__).resolve().parents[2]
ESQUEMA_ISAD = RAIZ / "schemas" / "isad-g.yaml"
CAMPOS_ESENCIALES = {
    "codigo_referencia",
    "titulo",
    "fechas",
    "nivel_descripcion",
    "nombre_productor",
    "alcance_contenido",
}


# -----------------------------------------------------------------------------
# Reparación sintáctica
# -----------------------------------------------------------------------------

def _cargar(texto: str):
    return json.loads(llm.extraer_json_texto(texto))


def test_json_estricto_se_devuelve_intacto():
    original = '{"campos": {"t": {"valor": "Dijo \\"hola\\"", "confianza": "alta", "evidencia": null}}}'
    assert llm.extraer_json_texto(original) == original


def test_salto_de_linea_literal_en_valor():
    datos = _cargar('{"campos": {"t": {"valor": "línea 1\nlínea 2", "confianza": "alta", "evidencia": null}}}')
    assert datos["campos"]["t"]["valor"] == "línea 1\nlínea 2"


def test_comillas_internas_sin_escapar_conservan_la_cita():
    texto = (
        '{"campos": {"a": {"valor": "Aprobación del presupuesto", "confianza": "media", '
        '"evidencia": "según consta en el acta, "se aprobó por unanimidad el presupuesto""}}}'
    )
    datos = _cargar(texto)
    assert datos["campos"]["a"]["evidencia"] == 'según consta en el acta, "se aprobó por unanimidad el presupuesto"'


def test_coma_final_sobrante():
    datos = _cargar('{"campos": {"t": {"valor": "Carta", "confianza": "alta", "evidencia": "x",},}}')
    assert datos["campos"]["t"]["valor"] == "Carta"


def test_literales_python():
    datos = _cargar('{"campos": {"t": {"valor": None, "confianza": None, "evidencia": None}}}')
    assert datos["campos"]["t"] == {"valor": None, "confianza": None, "evidencia": None}


def test_markdown_y_texto_posterior():
    datos = _cargar('```json\n{"campos": {}}\n```\nEspero que sea útil.')
    assert datos == {"campos": {}}


def test_respuesta_sin_json_sigue_siendo_invalida():
    texto = "No puedo ayudar con eso."
    assert llm.extraer_json_texto(texto) == texto
    assert llm.extraer_json_texto("") == ""


def test_diagnostico_sin_contenido():
    secreto = "DATO_CONFIDENCIAL_DEL_DOCUMENTO"
    diagnostico = llm.describir_error_json(f"texto {secreto} sin llaves")
    assert secreto not in diagnostico
    assert llm.describir_error_json("") == "respuesta vacía"


# -----------------------------------------------------------------------------
# Esquema JSON de respuesta
# -----------------------------------------------------------------------------

def test_esquema_respuesta_refleja_campos_y_catalogos():
    esquema = extractor.cargar_esquema(ESQUEMA_ISAD)
    extraibles = esquema.extraibles(CAMPOS_ESENCIALES)
    sch = extractor.esquema_json_respuesta(extraibles)

    campos = sch["properties"]["campos"]
    assert set(campos["required"]) == {el.clave for el in extraibles}
    assert campos["additionalProperties"] is False

    for el in extraibles:
        prop = campos["properties"][el.clave]
        assert prop["required"] == ["valor", "confianza", "evidencia"]
        valor = prop["properties"]["valor"]["anyOf"][0]
        if el.multiple:
            assert valor["type"] == "array"
            valor = valor["items"]
        if el.tipo == "lista" and el.valores:
            assert valor["enum"] == list(el.valores)


# -----------------------------------------------------------------------------
# llm.generar con cliente simulado
# -----------------------------------------------------------------------------

class _Respuesta:
    def __init__(self, status_code: int, datos):
        self.status_code = status_code
        self._datos = datos

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400

    @property
    def text(self) -> str:
        return self._datos if isinstance(self._datos, str) else json.dumps(self._datos)

    def json(self):
        return self._datos


class _ClienteSimulado:
    def __init__(self, guion: list[tuple[int, object]], llamadas: list[dict]):
        self._guion = guion
        self._llamadas = llamadas

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):  # noqa: A002 - firma de httpx
        self._llamadas.append(json)
        codigo, datos = self._guion.pop(0)
        return _Respuesta(codigo, datos)


_OK = {"response": '{"campos": {}}', "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 5}


_RUNTIME_PRUEBA = {"sistema": "Sistema de prueba.", "opciones": {"temperature": 0.1}}


def _instalar_cliente(monkeypatch, guion):
    llamadas: list[dict] = []
    # Configuración de runtime en memoria: la prueba no depende de dónde esté
    # schemas/pluma-runtime.yaml en el entorno que la ejecuta.
    monkeypatch.setattr(llm, "_RUNTIME_CFG", _RUNTIME_PRUEBA)
    monkeypatch.setattr(llm, "cliente_local", lambda timeout: _ClienteSimulado(guion, llamadas))
    return llamadas


def test_generar_envia_esquema_en_format(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_JSON_MODE", "schema")
    llamadas = _instalar_cliente(monkeypatch, [(200, _OK)])
    sch = {"type": "object"}
    asyncio.run(llm.generar("p", modelo="m", esquema_json=sch))
    assert llamadas[0]["format"] == sch
    assert llamadas[0]["think"] is False


def test_generar_reintenta_sin_format_si_falla_la_gramatica(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_JSON_MODE", "schema")
    llamadas = _instalar_cliente(
        monkeypatch, [(500, "unexpected empty grammar stack"), (200, _OK)]
    )
    asyncio.run(llm.generar("p", modelo="m", esquema_json={"type": "object"}))
    assert len(llamadas) == 2
    assert "format" in llamadas[0]
    assert "format" not in llamadas[1]


def test_generar_modo_soft_no_envia_format(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_JSON_MODE", "soft")
    llamadas = _instalar_cliente(monkeypatch, [(200, _OK)])
    asyncio.run(llm.generar("p", modelo="m", esquema_json={"type": "object"}))
    assert "format" not in llamadas[0]


def test_generar_texto_libre_no_envia_format(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_JSON_MODE", "schema")
    llamadas = _instalar_cliente(monkeypatch, [(200, _OK)])
    asyncio.run(llm.generar("p", modelo="m", formato_json=False))
    assert "format" not in llamadas[0]


# -----------------------------------------------------------------------------
# Extracción monolítica: reintento ante JSON inválido
# -----------------------------------------------------------------------------

def test_modo_esencial_reintenta_tras_json_invalido(monkeypatch):
    esquema = extractor.cargar_esquema(ESQUEMA_ISAD)
    texto = (
        "Sr. D. Tomás Ferrer Lago, alcalde de Villanueva del Prado. Muy señor mío: "
        "le remito el inventario de la documentación municipal solicitado."
    )
    entrada = extractor.Entrada(texto=texto)

    respuestas = [
        "Lo siento, aquí tienes:",
        json.dumps({"campos": {"titulo": {
            "valor": "Remisión del inventario al alcalde", "confianza": "alta",
            "evidencia": "le remito el inventario de la documentación municipal",
        }}}),
    ]
    llamadas: list[dict] = []

    async def generar_simulado(prompt, modelo=None, imagenes=None, formato_json=True,
                               temperatura=None, diagnostico=None, esquema_json=None):
        llamadas.append({"prompt": prompt, "esquema_json": esquema_json})
        if diagnostico is not None:
            diagnostico.update(num_ctx=8192, num_predict=3000, prompt_eval_count=900,
                               eval_count=100, done_reason="stop")
        return respuestas.pop(0)

    monkeypatch.setattr(llm, "generar", generar_simulado)
    propuesta = asyncio.run(extractor.extraer(entrada, esquema, "m", CAMPOS_ESENCIALES, "es"))

    assert len(llamadas) == 2
    assert llamadas[0]["esquema_json"] is not None
    assert "REINTENTO POR JSON INVÁLIDO" in llamadas[1]["prompt"]
    titulo = next(c for c in propuesta.campos if c.clave == "titulo")
    assert titulo.valor == "Remisión del inventario al alcalde"
    assert titulo.estado_evidencia == "localizada"
    assert not any("json inválido; se omiten" in a.lower() for a in propuesta.advertencias)
