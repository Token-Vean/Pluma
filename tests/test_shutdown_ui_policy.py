from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shutdown_button_hidden_and_close_button_visible():
    html = (ROOT / "frontend" / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="boton-cerrar-interfaz"' in html
    assert 'id="boton-apagar"' in html
    assert 'style="display:none"' in html
    assert 'aria-hidden="true"' in html
    assert "function cerrarInterfaz()" in js
    assert "apagado_ui_permitido === true" in js
    assert "boton-cerrar-interfaz" in js
