from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_publica_solo_loopback():
    data = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    app = data["services"]["app"]
    port = app["ports"][0]
    assert port["host_ip"] == "127.0.0.1"
    assert str(port["published"]) == "8082"
    assert int(port["target"]) == 8081


def test_apagado_ui_desactivado_por_defecto():
    data = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = data["services"]["app"]["environment"]
    assert env["PERMITIR_APAGADO_UI"] == "${PERMITIR_APAGADO_UI:-false}"
    assert "PERMITIR_APAGADO_UI=false" in (ROOT / ".env.example").read_text(encoding="utf-8")


def test_contexto_docker_minimo():
    text = (ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8")
    assert "*" in text
    assert "!requirements.txt" in text
    assert "!app/" in text
    assert "*.pyc" in text
    assert ".env" in text


def test_uvloop_no_se_instala_en_windows():
    marker = 'uvloop==0.22.1 ; sys_platform != "win32"'
    assert marker in (ROOT / "backend" / "requirements.in").read_text(encoding="utf-8")
    assert marker in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")


def test_instaladores_conservan_fallback_bundled():
    sh = (ROOT / "instalar.sh").read_text(encoding="utf-8")
    bat = (ROOT / "instalar.bat").read_text(encoding="utf-8")
    ps1 = (ROOT / "tools" / "windows" / "enforce-local-config.ps1").read_text(encoding="utf-8")
    assert "http://ollama:11434" in sh
    assert "http://ollama:11434" in ps1
    for text in (sh, bat, ps1):
        assert "bundled" in text
    assert 'ollama pull "$MODELO_BASE"' in sh
    assert 'ollama pull "!MODELO_BASE!"' in bat
