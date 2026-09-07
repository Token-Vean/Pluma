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


# Controles de seguridad del procesamiento. Desde v0.7.2 son valor literal en
# docker-compose.yml y no sustitución ${VAR:-...}: un .env manipulado o
# heredado de una instalación anterior con USAR_SANDBOX_PARSERS=false
# desactivaba el aislamiento en proceso hijo de los parsers de PDF/DOCX/imagen,
# que es la defensa central frente a entrada no confiable.
CONTROLES_SEGURIDAD_LITERALES = {
    "USAR_SANDBOX_PARSERS": "true",
    "SANDBOX_TIMEOUT_SEGUNDOS": "120",
    "SANDBOX_MEMORIA_MB": "1536",
    "INCLUIR_HASH_DOCUMENTO_AUDITORIA": "true",
    "PERMITIR_APAGADO_UI": "false",
}


def test_controles_seguridad_no_configurables_desde_env():
    data = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = data["services"]["app"]["environment"]
    for clave, valor in CONTROLES_SEGURIDAD_LITERALES.items():
        assert env[clave] == valor, (
            f"{clave} debe ser literal en docker-compose.yml, no sustituible "
            f"desde .env; valor actual: {env[clave]!r}"
        )


def test_env_example_no_declara_controles_seguridad():
    """.env.example no debe hacer creer que estas variables siguen surtiendo efecto."""
    lineas_activas = [
        linea.strip()
        for linea in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")
    ]
    for clave in CONTROLES_SEGURIDAD_LITERALES:
        assert not any(linea.startswith(f"{clave}=") for linea in lineas_activas), (
            f".env.example declara {clave} como si fuera configurable"
        )


def test_apagado_ui_desactivado_por_defecto():
    data = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert data["services"]["app"]["environment"]["PERMITIR_APAGADO_UI"] == "false"


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
