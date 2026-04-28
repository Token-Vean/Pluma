from __future__ import annotations

import importlib

import pytest


def test_strict_local_ignores_remote_flags(monkeypatch):
    monkeypatch.setenv("PLUMA_STRICT_LOCAL", "true")
    monkeypatch.setenv("ALLOW_REMOTE_OLLAMA", "true")
    monkeypatch.setenv("ALLOW_NETWORK_EXPOSURE", "true")
    import app.security_policy as sp
    importlib.reload(sp)
    assert sp.remote_ollama_allowed() is False
    assert sp.network_exposure_allowed() is False


def test_strict_local_rejects_remote_ollama(monkeypatch):
    monkeypatch.setenv("PLUMA_STRICT_LOCAL", "true")
    import app.security_policy as sp
    importlib.reload(sp)
    with pytest.raises(RuntimeError):
        sp.validate_ollama_url("https://api.example.com")
    with pytest.raises(RuntimeError):
        sp.validate_ollama_url("http://192.168.1.10:11434")


def test_strict_local_allows_docker_ollama(monkeypatch):
    monkeypatch.setenv("PLUMA_STRICT_LOCAL", "true")
    import app.security_policy as sp
    importlib.reload(sp)
    sp.validate_ollama_url("http://ollama:11434")


def test_host_header_must_be_loopback():
    from app.security_policy import host_header_is_local
    assert host_header_is_local("localhost:8082")
    assert host_header_is_local("127.0.0.1:8082")
    assert not host_header_is_local("192.168.1.100:8082")
    assert not host_header_is_local("example.com")
