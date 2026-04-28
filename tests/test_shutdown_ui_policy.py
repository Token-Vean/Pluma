from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ui_separa_cerrar_interfaz_y_detener_servidor():
    html = (ROOT / "frontend" / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="boton-cerrar-interfaz"' in html
    assert 'data-i18n-title="closeInterface.title"' in html
    assert 'id="boton-apagar"' in html
    assert 'style="display:none"' in html
    assert "function cerrarInterfaz()" in js
    assert "apagado_ui_permitido === true" in js


def test_no_hay_artefactos_de_release_en_raiz():
    forbidden = [
        *ROOT.glob("RELEASE_NOTES_*.md"),
        *ROOT.glob("REPO_MANIFEST_*.md"),
        *ROOT.glob("GITHUB_RELEASE_TEXT_*.md"),
        *ROOT.glob("*BUILD_REPORT*.txt"),
        *ROOT.glob("*.SHA256.txt"),
    ]
    assert forbidden == []
    assert not (ROOT / "release").exists()
