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

    def __init__(self, *, tags=None, show=(200, {}), error=None, version="0.40.17", estado=None):
        self.tags = tags or []
        self.version = version
        self.estado = {"cloud": {"disabled": True}} if estado is None else estado
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
        if url.endswith("/version"):
            return _Respuesta(200, {"version": self.version})
        if url.endswith("/status"):
            return _Respuesta(200, self.estado)
        assert url.endswith("/tags")
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


@pytest.mark.parametrize("datos", [
    {"details": {"format": "gguf", "family": "gemma4"}},
    {"details": {"family": "gemma4"}, "model_info": {"general.architecture": "gemma4"}},
])
def test_verificar_acepta_un_modelo_local(monkeypatch, datos):
    ollama = _instalar(monkeypatch, _Ollama(show=(200, datos)))
    asyncio.run(llm.verificar_modelo_local("gemma4:e2b"))
    assert [url.rsplit("/", 1)[1] for _, url, _ in ollama.llamadas] == ["version", "status", "show"]
    assert ollama.llamadas[-1][2] == {"model": "gemma4:e2b"}


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
    _Ollama(show=(200, {})),
    _Ollama(show=(200, {"details": {}, "capabilities": ["completion"]})),
    _Ollama(show=(200, {"details": {"format": "  ", "family": "gemma4"}})),
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
    # Solo se consultan metadatos del motor y del modelo.
    assert [(m, u.rsplit("/api/", 1)[1]) for m, u, _ in ollama.llamadas] == [("GET", "version"), ("GET", "status"), ("POST", "show")]
    assert "CONFIDENCIAL" not in repr(ollama.llamadas)

@pytest.mark.parametrize("motor", [
    _Ollama(version="0.21.2"), _Ollama(version=None), _Ollama(version="0.35.0-rc1"),
    _Ollama(estado={}), _Ollama(estado={"cloud": {"disabled": False}}),
    _Ollama(estado={"cloud": {"disabled": "true"}}),
])
@pytest.mark.parametrize("imagenes", [None, [b"imagen sintetica"]])
def test_motor_incompatible_detiene_texto_e_imagen_antes_del_envio(monkeypatch, motor, imagenes):
    motor.llamadas.clear()
    _instalar(monkeypatch, motor)
    monkeypatch.setattr(llm, "_RUNTIME_CFG", {"sistema": "s", "opciones": {}})
    with pytest.raises(RuntimeError):
        asyncio.run(llm.generar("texto sintetico", modelo="gemma4:e2b", imagenes=imagenes))
    assert all(metodo == "GET" for metodo, _, _ in motor.llamadas)
