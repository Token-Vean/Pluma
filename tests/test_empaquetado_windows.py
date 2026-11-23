"""Paquete de Windows generado desde el código versionado (v0.7.4)."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("empaquetar_windows", ROOT / "scripts" / "empaquetar_windows.py")
emp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(emp)


@pytest.mark.parametrize("ruta, esperado", [
    ("docker-compose.yml", "PlumA-0.7.4/programa/docker-compose.yml"),
    ("backend/app/llm.py", "PlumA-0.7.4/programa/backend/app/llm.py"),
    ("panel/PlumAPanel.ps1", "PlumA-0.7.4/programa/panel/PlumAPanel.ps1"),
    ("tools/windows/pluma-env.bat", "PlumA-0.7.4/programa/tools/windows/pluma-env.bat"),
    (".env.example", "PlumA-0.7.4/programa/.env.example"),
    ("packaging/windows/PlumA - Instalar y abrir.vbs", "PlumA-0.7.4/PlumA - Instalar y abrir.vbs"),
    ("packaging/windows/ayuda/LEEME.txt", "PlumA-0.7.4/ayuda/LEEME.txt"),
    ("packaging/windows/ayuda/Novedades 0.7.4.txt", "PlumA-0.7.4/ayuda/Novedades 0.7.4.txt"),
    ("packaging/windows/ayuda/Novedades 0.7.3.txt", None),
    ("tests/test_security_basics.py", None),
    ("backend/tests/test_salida_json_estructurada.py", None),
    ("scripts/security_static_check.py", None),
    (".github/workflows/security-checks.yml", None),
    (".gitignore", None),
    ("INSTRUCCIONES_SUSTITUCION.md", None),
    ("tools/windows/pluma-install-core.bat", None),
])
def test_ruta_en_paquete(ruta, esperado):
    assert emp.ruta_en_paquete(ruta, "0.7.4") == esperado


def test_bat_y_ps1_con_crlf_y_bom_obligatorio():
    assert emp._ajustar_contenido("x/a.bat", b"@echo off\nexit /b 0\n") == b"@echo off\r\nexit /b 0\r\n"
    assert emp._ajustar_contenido("x/a.bat", b"a\r\nb\n") == b"a\r\nb\r\n"
    assert emp._ajustar_contenido("x/a.md", b"a\nb\n") == b"a\nb\n"
    assert emp._ajustar_contenido("panel/PlumAPanel.ps1", b"\xef\xbb\xbfa\n") == b"\xef\xbb\xbfa\r\n"
    with pytest.raises(emp.ErrorEmpaquetado, match="BOM"):
        emp._ajustar_contenido("panel/PlumAPanel.ps1", b"a\n")


def test_panel_y_backend_exigen_la_misma_version_minima_de_ollama():
    panel = (ROOT / "panel" / "PlumAPanel.ps1").read_text(encoding="utf-8-sig")
    bootstrap = (ROOT / "backend" / "app" / "bootstrap.py").read_text(encoding="utf-8")
    m_panel = re.search(r"OllamaMinVersion\s*=\s*\[version\]'(\d+)\.(\d+)\.(\d+)'", panel)
    m_back = re.search(r"VERSION_MINIMA_OLLAMA[^=]*=\s*\((\d+),\s*(\d+),\s*(\d+)\)", bootstrap)
    assert m_panel and m_back
    assert m_panel.groups() == m_back.groups()


def _repo_con_paquete() -> bool:
    if shutil.which("git") is None:
        return False
    try:
        emp._git("cat-file", "-e", "HEAD:packaging/windows/ayuda/LEEME.txt")
        return True
    except subprocess.CalledProcessError:
        return False


@pytest.mark.skipif(not _repo_con_paquete(), reason="requiere el repositorio Git con packaging/ en HEAD")
def test_construccion_desde_head(tmp_path):
    destino, resumen = emp.construir("HEAD", tmp_path / "a")
    version = emp.version_de("HEAD")
    raiz = f"PlumA-{version}"

    with zipfile.ZipFile(destino) as zf:
        nombres = set(zf.namelist())
        assert f"{raiz}/PlumA - Instalar y abrir.vbs" in nombres
        assert f"{raiz}/ayuda/Novedades {version}.txt" in nombres
        assert f"{raiz}/programa/panel/PlumAPanel.ps1" in nombres
        assert f"{raiz}/programa/docker-compose.yml" in nombres
        assert not any("/tests/" in n or "/.github/" in n or n.endswith("/.env") for n in nombres)
        # Una sola cosa que abrir en la raíz: el lanzador. El resto, en carpetas.
        en_raiz = {n[len(raiz) + 1:] for n in nombres if n.count("/") == 1}
        assert en_raiz == {"PlumA - Instalar y abrir.vbs"}
        for n in nombres:
            if n.endswith((".bat", ".ps1", ".vbs")):
                datos = zf.read(n)
                assert b"\n" not in datos.replace(b"\r\n", b""), f"{n} sin CRLF"
        assert zf.read(f"{raiz}/programa/panel/PlumAPanel.ps1").startswith(b"\xef\xbb\xbf")

    # Mismo commit, mismo paquete.
    _, resumen2 = emp.construir("HEAD", tmp_path / "b")
    assert resumen == resumen2
    assert (tmp_path / "a" / f"{destino.name}.sha256").read_text(encoding="ascii") == f"{resumen}  {destino.name}\n"
    assert emp.verificar(destino, "HEAD") == []


@pytest.mark.skipif(not _repo_con_paquete(), reason="requiere el repositorio Git con packaging/ en HEAD")
def test_verificar_detecta_un_zip_manipulado(tmp_path):
    destino, _ = emp.construir("HEAD", tmp_path)
    version = emp.version_de("HEAD")
    manipulado = tmp_path / "manipulado.zip"
    with zipfile.ZipFile(destino) as origen, zipfile.ZipFile(manipulado, "w") as zf:
        for info in origen.infolist():
            datos = origen.read(info)
            if info.filename.endswith("/programa/docker-compose.yml"):
                datos = datos.replace(b'OLLAMA_NO_CLOUD: "1"', b'OLLAMA_NO_CLOUD: "0"')
            zf.writestr(info, datos)
        zf.writestr(f"PlumA-{version}/programa/extra.bat", b"@echo off\r\n")
    diferencias = emp.verificar(manipulado, "HEAD")
    assert any("contenido distinto" in d and "docker-compose.yml" in d for d in diferencias)
    assert any("sobra en el ZIP" in d and "extra.bat" in d for d in diferencias)
