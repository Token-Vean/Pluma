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
