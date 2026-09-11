"""
Ventana de contexto y respuestas degradadas del modelo.

Regresión de un fallo observado en la 0.7.2: con OLLAMA_NUM_CTX=4096 el prompt
de ISAD(G) no cabía junto al documento, Ollama descartaba en silencio el
principio del prompt (system prompt, reglas y campos) y el modelo devolvía un
JSON degradado. PlumA lo convertía en una propuesta vacía sin ninguna
advertencia: todos los campos aparecían como "Sin evidencia en el documento".

Estos tests no necesitan Ollama: sustituyen llm.generar por un simulador que
rellena las métricas que devuelve Ollama.
"""

from __future__ import annotations

import asyncio
import json
import re

from app import extractor, llm


def _esquema(*claves: str) -> extractor.Esquema:
    return extractor.Esquema(
        norma="TEST",
        version="1",
        nombre="Test",
        idioma="es",
        elementos=[
            extractor.ElementoEsquema(
                id=f"1.{i}",
                clave=clave,
                nombre=clave.replace("_", " ").capitalize(),
                tipo="texto",
                obligatorio=True,
                multiple=False,
                extraible="si",
                instruccion=f"Propón {clave}.",
            )
            for i, clave in enumerate(claves, start=1)
        ],
    )


CABECERA = "ACTA DE LA SESIÓN ORDINARIA DEL PLENO celebrada el 12 de marzo de 1987."
CIERRE = "Y no habiendo más asuntos que tratar, se levanta la sesión, de lo que doy fe."


def _documento(caracteres: int) -> str:
    relleno = "Se acuerda aprobar el proyecto técnico y autorizar el gasto correspondiente. "
    cuerpo = (relleno * (caracteres // len(relleno) + 1))[: caracteres - len(CABECERA) - len(CIERRE) - 2]
    return f"{CABECERA}\n{cuerpo}\n{CIERRE}"


class _OllamaSimulado:
    """Imita a Ollama: trunca el prompt que no cabe y el modelo responde basura."""

    def __init__(self, num_ctx: int, densidad: float, salida: int = 400) -> None:
        self.num_ctx = num_ctx
        self.densidad = densidad
        self.salida = salida
        self.prompts: list[str] = []

    async def __call__(self, prompt, modelo=None, imagenes=None, formato_json=True,
                       temperatura=None, diagnostico=None):
        self.prompts.append(prompt)
        # Ollama cuenta también el system prompt que llm.generar envía aparte.
        caracteres = len(prompt) + llm._caracteres_sistema()
        tokens = int(caracteres / self.densidad) + 64
        if diagnostico is not None:
            diagnostico.update({
                "num_ctx": self.num_ctx,
                "num_predict": 2048,
                "prompt_eval_count": min(tokens, self.num_ctx),
                "eval_count": self.salida,
                "done_reason": "stop",
                "caracteres_prompt": caracteres,
            })
        if tokens + self.salida > self.num_ctx:
            return "{}"
        claves = re.findall(r'## Campo "([^"]+)"', prompt)
        return json.dumps({"campos": {
            c: {"valor": "Acta del Pleno", "confianza": "alta", "evidencia": CABECERA}
            for c in claves
        }}, ensure_ascii=False)


def _con_contexto(num_ctx: int, simulador) -> tuple:
    anterior = (llm.NUM_CTX, llm.NUM_PREDICT, llm.generar)
    llm.NUM_CTX, llm.NUM_PREDICT, llm.generar = num_ctx, 2048, simulador
    return anterior


def _restaurar(anterior: tuple) -> None:
    llm.NUM_CTX, llm.NUM_PREDICT, llm.generar = anterior


# =============================================================================
# Ajuste del documento
# =============================================================================

def test_documento_que_cabe_no_se_toca():
    texto = _documento(3000)
    ajustado, recortado = extractor.ajustar_documento_a_contexto(texto, 5000)
    assert ajustado == texto
    assert recortado is False


def test_recorte_conserva_principio_y_final_con_marca():
    texto = _documento(20000)
    ajustado, recortado = extractor.ajustar_documento_a_contexto(texto, 4000)
    assert recortado is True
    assert len(ajustado) <= 4000
    assert ajustado.startswith(CABECERA)
    assert ajustado.endswith(CIERRE)
    assert "omitidos aquí por el límite de la ventana de contexto" in ajustado


def test_presupuesto_crece_con_la_ventana():
    base = extractor.construir_prompt(
        _esquema("titulo", "fechas"), extractor.Entrada(texto=""), None, "es"
    )
    anterior = llm.NUM_CTX
    try:
        llm.NUM_CTX = 4096
        pequeno = llm.presupuesto_documento(base)
        llm.NUM_CTX = 8192
        grande = llm.presupuesto_documento(base)
    finally:
        llm.NUM_CTX = anterior
    assert grande.caracteres > pequeno.caracteres
    assert grande.suficiente


# =============================================================================
# Lectura de las métricas de Ollama
# =============================================================================

def test_evaluar_contexto():
    assert llm.evaluar_contexto({"num_ctx": 4096, "prompt_eval_count": 4096, "eval_count": 10}) == "prompt_truncado"
    assert llm.evaluar_contexto({"num_ctx": 4096, "prompt_eval_count": 3900, "eval_count": 400}) == "contexto_agotado"
    assert llm.evaluar_contexto({
        "num_ctx": 8192, "num_predict": 300, "prompt_eval_count": 2000,
        "eval_count": 300, "done_reason": "length",
    }) == "limite_salida"
    assert llm.evaluar_contexto({"num_ctx": 8192, "prompt_eval_count": 3000, "eval_count": 500, "done_reason": "stop"}) is None
    assert llm.evaluar_contexto({}) is None


# =============================================================================
# Respuestas degradadas: ya no pasan en silencio
# =============================================================================

def test_campos_en_la_raiz_sin_envoltorio():
    respuesta = json.dumps({"titulo": {"valor": "Acta", "confianza": "alta", "evidencia": CABECERA}})
    campos, avisos = extractor.parsear_respuesta(respuesta, _esquema("titulo"))
    assert campos[0].valor == "Acta"
    assert extractor.AVISO_ESTRUCTURA_ALTERNATIVA in avisos


def test_claves_por_nombre_o_id():
    respuesta = json.dumps({"campos": {
        "Título": {"valor": "Acta", "confianza": "alta", "evidencia": CABECERA},
        "1.2": {"valor": "1987", "confianza": "media", "evidencia": "1987"},
    }})
    campos, _ = extractor.parsear_respuesta(respuesta, _esquema("titulo", "fechas"))
    assert {c.clave: c.valor for c in campos} == {"titulo": "Acta", "fechas": "1987"}


def test_alias_no_roba_la_clave_exacta_de_otro_campo():
    esquema = _esquema("titulo", "titulo_formal")
    # Las claves exactas se asignan antes que cualquier alias: "titulo" nunca
    # puede acabar en otro campo, y "Titulo formal" llega a "titulo_formal"
    # por su nombre normalizado.
    respuesta = json.dumps({"campos": {
        "titulo": {"valor": "A", "confianza": "alta", "evidencia": "A"},
        "Titulo formal": {"valor": "B", "confianza": "alta", "evidencia": "B"},
    }})
    campos, _ = extractor.parsear_respuesta(respuesta, esquema)
    assert {c.clave: c.valor for c in campos} == {"titulo": "A", "titulo_formal": "B"}


def test_respuesta_sin_ningun_campo_avisa():
    campos, avisos = extractor.parsear_respuesta("{}", _esquema("titulo"))
    assert campos[0].valor is None
    assert extractor.AVISO_SIN_CAMPOS in avisos
    # No debe confundirse con JSON inválido: reintentar no arregla un desbordamiento.
    assert not extractor._hay_advertencia_json_invalido(avisos)


def test_plantilla_devuelta_con_nulls_avisa():
    simulado_nulls = json.dumps({"campos": {"titulo": {"valor": None, "confianza": None, "evidencia": None}}})

    async def generar(prompt, **kwargs):
        return simulado_nulls

    anterior = llm.generar
    llm.generar = generar
    try:
        propuesta = asyncio.run(extractor.extraer(
            extractor.Entrada(texto=_documento(1000)), _esquema("titulo"), "sim", None, "es"
        ))
    finally:
        llm.generar = anterior
    assert extractor.AVISO_SIN_VALORES in propuesta.advertencias


# =============================================================================
# Extracción completa con contexto limitado
# =============================================================================

def test_documento_que_cabe_se_envia_integro_en_una_llamada():
    simulador = _OllamaSimulado(num_ctx=8192, densidad=4.0)
    anterior = _con_contexto(8192, simulador)
    try:
        propuesta = asyncio.run(extractor.extraer(
            extractor.Entrada(texto=_documento(6000)), _esquema("titulo"), "sim", None, "es"
        ))
    finally:
        _restaurar(anterior)
    assert len(simulador.prompts) == 1
    assert propuesta.contexto["documento_recortado"] is False
    assert propuesta.campos[0].estado_evidencia == "localizada"


def test_documento_largo_se_recorta_y_avisa():
    simulador = _OllamaSimulado(num_ctx=4096, densidad=4.0)
    anterior = _con_contexto(4096, simulador)
    try:
        propuesta = asyncio.run(extractor.extraer(
            extractor.Entrada(texto=_documento(30000)), _esquema("titulo"), "sim", None, "es"
        ))
    finally:
        _restaurar(anterior)
    assert propuesta.campos[0].valor == "Acta del Pleno"
    assert propuesta.contexto["documento_recortado"] is True
    assert any("no cabe entero en la ventana de contexto" in a for a in propuesta.advertencias)
    # La evidencia se verifica contra el texto completo, no contra el recortado.
    assert propuesta.campos[0].estado_evidencia == "localizada"


def test_desbordamiento_detectado_se_repite_con_documento_menor():
    # Densidad real peor que la estimada: el recorte preventivo no basta.
    simulador = _OllamaSimulado(num_ctx=4096, densidad=2.6)
    anterior = _con_contexto(4096, simulador)
    try:
        propuesta = asyncio.run(extractor.extraer(
            extractor.Entrada(texto=_documento(30000)), _esquema("titulo"), "sim", None, "es"
        ))
    finally:
        _restaurar(anterior)
    assert len(simulador.prompts) == 2
    assert len(simulador.prompts[1]) < len(simulador.prompts[0])
    assert propuesta.contexto["reintentos_por_desbordamiento"] == 1
    assert propuesta.campos[0].valor == "Acta del Pleno"
    assert any("PlumA lo repitió con el documento recortado" in a for a in propuesta.advertencias)
