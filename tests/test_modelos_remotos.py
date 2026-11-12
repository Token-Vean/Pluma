"""Detección de modelos remotos de Ollama por metadatos, no solo por nombre.

La etiqueta ``:cloud`` es una convención: ``ollama cp modelo:cloud mi-modelo``
da un modelo sin etiqueta que sigue enviando el texto fuera del equipo. Ollama
declara esos modelos con ``remote_host`` / ``remote_model`` en /api/tags y
/api/show, y PlumA debe rechazarlos se llamen como se llamen.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app import bootstrap, llm

_LOCAL = {"name": "gemma4:e2b", "model": "gemma4:e2b", "digest": "a" * 64}
_REMOTO_RENOMBRADO = {
    "name": "mi-modelo:latest",
    "model": "mi-modelo:latest",
    "remote_model": "gpt-oss:120b",
    "remote_host": "https://ollama.com:443",
}
_REMOTO_SOLO_HOST = {"name": "otro:latest", "remote_host": "https://ollama.com:443"}
_ETIQUETA_CLOUD = {"name": "qwen3-coder:480b-cloud"}


class _Respuesta:
    def __init__(self, status_code: int, datos):
        self.status_code = status_code
        self._datos = datos

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        if isinstance(self._datos, Exception):
            raise self._datos
        return self._datos


class _Ollama:
    """Ollama simulado: responde a /api/tags y /api/show y anota las llamadas."""

    def __init__(self, *, tags=None, show=(200, {}), error=None):
        self.tags = tags or []
        self.show = show
        self.error = error
        self.llamadas: list[tuple[str, str, object]] = []

    def cliente(self, timeout):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        self.llamadas.append(("GET", url, None))
        return _Respuesta(200, {"models": self.tags})

    async def post(self, url, json=None):  # noqa: A002 - firma de httpx
        self.llamadas.append(("POST", url, json))
        if self.error is not None:
            raise self.error
        return _Respuesta(*self.show)


def _instalar(monkeypatch, ollama: _Ollama) -> _Ollama:
    monkeypatch.setattr(llm, "cliente_local", ollama.cliente)
    return ollama


def test_es_entrada_remota_reconoce_los_metadatos():
    assert llm.es_entrada_remota(_REMOTO_RENOMBRADO)
    assert llm.es_entrada_remota(_REMOTO_SOLO_HOST)
    assert llm.es_entrada_remota({"name": "x", "remote_model": "y"})
    assert not llm.es_entrada_remota(_LOCAL)
    assert not llm.es_entrada_remota({"name": "x", "remote_host": "", "remote_model": None})
    assert not llm.es_entrada_remota("no es un diccionario")


def test_el_listado_excluye_modelos_remotos_aunque_no_se_llamen_cloud(monkeypatch):
    _instalar(monkeypatch, _Ollama(
        tags=[_LOCAL, _REMOTO_RENOMBRADO, _REMOTO_SOLO_HOST, _ETIQUETA_CLOUD]
    ))
    assert asyncio.run(llm.modelos_disponibles()) == ["gemma4:e2b"]
    assert asyncio.run(bootstrap._listar_modelos()) == ["gemma4:e2b"]
    assert asyncio.run(llm.modelo_disponible("mi-modelo")) is False


def test_verificar_acepta_un_modelo_local(monkeypatch):
    ollama = _instalar(monkeypatch, _Ollama(show=(200, {"details": {}, "capabilities": ["completion"]})))
    asyncio.run(llm.verificar_modelo_local("gemma4:e2b"))
    assert ollama.llamadas == [("POST", f"{llm.OLLAMA_URL}/api/show", {"model": "gemma4:e2b"})]


@pytest.mark.parametrize("show", [
    {"remote_host": "https://ollama.com:443", "remote_model": "gpt-oss:120b"},
    {"remote_host": "https://ollama.com:443"},
    {"remote_model": "gpt-oss:120b"},
])
def test_verificar_rechaza_un_modelo_remoto_renombrado(monkeypatch, show):
    _instalar(monkeypatch, _Ollama(show=(200, show)))
    with pytest.raises(RuntimeError, match="servidor externo"):
        asyncio.run(llm.verificar_modelo_local("mi-modelo:latest"))


def test_verificar_rechaza_la_etiqueta_cloud_sin_consultar(monkeypatch):
    ollama = _instalar(monkeypatch, _Ollama())
    with pytest.raises(RuntimeError, match="cloud"):
        asyncio.run(llm.verificar_modelo_local("gpt-oss:120b-cloud"))
    assert ollama.llamadas == []


@pytest.mark.parametrize("ollama", [
    _Ollama(show=(404, {"error": "model not found"})),
    _Ollama(show=(500, "error interno")),
    _Ollama(show=(200, ValueError("no es JSON"))),
    _Ollama(show=(200, ["lista", "inesperada"])),
    _Ollama(error=httpx.ConnectError("sin conexión")),
])
def test_verificar_falla_cerrado_si_ollama_no_confirma(monkeypatch, ollama):
    _instalar(monkeypatch, ollama)
    with pytest.raises(RuntimeError, match="No se pudo comprobar"):
        asyncio.run(llm.verificar_modelo_local("gemma4:e2b"))


def test_generar_no_envia_el_documento_a_un_modelo_remoto(monkeypatch):
    ollama = _instalar(monkeypatch, _Ollama(show=(200, {"remote_host": "https://ollama.com:443"})))
    monkeypatch.setattr(llm, "_RUNTIME_CFG", {"sistema": "s", "opciones": {}})
    with pytest.raises(RuntimeError, match="servidor externo"):
        asyncio.run(llm.generar("TEXTO CONFIDENCIAL DEL DOCUMENTO", modelo="mi-modelo:latest"))
    # Solo se ha consultado /api/show: el texto no ha salido hacia Ollama.
    assert [(m, u.rsplit("/api/", 1)[1]) for m, u, _ in ollama.llamadas] == [("POST", "show")]
    assert "CONFIDENCIAL" not in repr(ollama.llamadas)
