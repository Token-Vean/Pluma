"""v0.7.4: los registros del OCR no incluyen el nombre del fichero subido.

Un nombre como «Expediente_GarciaLopez_2024.pdf» es un dato personal, y
CUMPLIMIENTO.md declara que los logs no contienen nombres de ficheros
originales. Antes, el aviso de OCR descartado por baja calidad incluía una
etiqueta derivada del nombre.
"""

from __future__ import annotations

import logging

from app import router

_NOMBRE = "Expediente_GarciaLopez_2024.pdf"
_FRAGMENTOS = ("GarciaLopez", "Expediente", "2024.pdf")


def _ocr_de_baja_calidad(monkeypatch):
    monkeypatch.setattr(router, "PLUMA_OCR_LOCAL", True)
    # Texto no vacío pero insuficiente: dispara el aviso de descarte.
    monkeypatch.setattr(router, "_ocr_imagen_tesseract", lambda img, indice=None: "x1 ~~ ,,")


def test_ocr_descartado_no_registra_el_nombre_del_fichero(monkeypatch, caplog):
    _ocr_de_baja_calidad(monkeypatch)
    with caplog.at_level(logging.INFO, logger=router.logger.name):
        resultado = router._ocr_imagenes([b"img1", b"img2"], nombre_origen=_NOMBRE)
    assert resultado == ""
    mensajes = [r.getMessage() for r in caplog.records]
    assert any("OCR local descartado" in m for m in mensajes), mensajes
    for mensaje in mensajes:
        for fragmento in _FRAGMENTOS:
            assert fragmento not in mensaje, mensaje


def test_ocr_descartado_registra_la_posicion(monkeypatch, caplog):
    _ocr_de_baja_calidad(monkeypatch)
    with caplog.at_level(logging.INFO, logger=router.logger.name):
        router._ocr_imagenes([b"img1", b"img2"], nombre_origen=_NOMBRE)
    descartes = [r.getMessage() for r in caplog.records if "OCR local descartado" in r.getMessage()]
    assert len(descartes) == 2
    assert "página/imagen 1 de 2" in descartes[0]
    assert "página/imagen 2 de 2" in descartes[1]


def test_texto_ocr_valido_conserva_la_etiqueta_en_el_prompt(monkeypatch):
    """El nombre saneado sigue identificando el tramo en el texto que recibe el
    modelo (no es un registro): solo sale de los logs."""
    monkeypatch.setattr(router, "PLUMA_OCR_LOCAL", True)
    texto = "Oficio del alcalde dirigido al secretario municipal sobre el padrón de habitantes"
    monkeypatch.setattr(router, "_ocr_imagen_tesseract", lambda img, indice=None: texto)
    resultado = router._ocr_imagenes([b"img1"], nombre_origen=_NOMBRE)
    assert texto in resultado
    assert "[OCR local - " in resultado
