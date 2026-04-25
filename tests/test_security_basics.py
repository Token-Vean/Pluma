from __future__ import annotations

import io
import zipfile

import pytest

from app import extractor, router
from app.exportadores import _sanear_csv


def test_rechaza_binario_renombrado_como_pdf():
    with pytest.raises(router.ErrorValidacion):
        router.validar(b"esto no es un pdf real\x00\x01", "documento.pdf")


def test_rechaza_zip_no_docx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("archivo.txt", "hola")
    with pytest.raises(router.ErrorValidacion):
        router.validar(buf.getvalue(), "archivo.docx")


def test_rechaza_docx_con_ruta_insegura():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types />")
        z.writestr("word/document.xml", "<w:document />")
        z.writestr("../evil.txt", "x")
    with pytest.raises(router.ErrorValidacion):
        router.validar(buf.getvalue(), "x.docx")


def test_csv_formula_injection():
    assert _sanear_csv("=SUMA(1,1)").startswith("'")
    assert _sanear_csv("+cmd").startswith("'")
    assert _sanear_csv("texto") == "texto"


def test_parseo_modelo_no_dict_no_rompe():
    esquema = extractor.Esquema(
        norma="TEST",
        version="1",
        nombre="Test",
        idioma="es",
        elementos=[
            extractor.ElementoEsquema(
                id="1",
                clave="titulo",
                nombre="Título",
                tipo="texto",
                obligatorio=True,
                multiple=False,
                extraible="si",
            )
        ],
    )
    campos, advertencias = extractor.parsear_respuesta("[]", esquema)
    assert len(campos) == 1
    assert campos[0].valor is None
    assert advertencias


def test_prompt_respeta_idioma_salida():
    esquema = extractor.Esquema(
        norma="TEST",
        version="1",
        nombre="Test",
        idioma="es",
        elementos=[
            extractor.ElementoEsquema(
                id="1",
                clave="alcance_contenido",
                nombre="Alcance y contenido",
                tipo="texto",
                obligatorio=True,
                multiple=False,
                extraible="si",
                instruccion="Redacta el alcance y contenido.",
            )
        ],
    )
    prompt = extractor.construir_prompt(
        esquema,
        extractor.Entrada(texto="This is a test document."),
        idioma_salida="en",
    )
    assert "Idioma de salida de la descripción: inglés." in prompt
    assert "Redacta los valores propuestos en inglés" in prompt
    assert 'Mantén los valores de "confianza" exactamente como "alta", "media" o' in prompt
