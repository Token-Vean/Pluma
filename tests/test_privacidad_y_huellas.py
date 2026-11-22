"""Comprobaciones de privacidad del OCR y de integridad de los documentos."""
import asyncio
import hashlib
import io
import logging

from starlette.datastructures import UploadFile

from app import api, auditoria, router


def test_descarte_ocr_solo_registra_indice_y_longitud(monkeypatch, caplog):
    monkeypatch.setattr(router, "PLUMA_OCR_LOCAL", True)
    monkeypatch.setattr(router, "_ocr_imagen_tesseract", lambda *args, **kwargs: "xy")
    with caplog.at_level(logging.INFO, logger=router.__name__):
        router._ocr_imagenes([b"sintetico"], nombre_origen="EXPEDIENTE_SINTETICO.pdf")
    assert "imagen 1 (2 caracteres)" in caplog.text
    assert "EXPEDIENTE" not in caplog.text
    assert "xy" not in caplog.text


def test_huella_del_original_y_del_envio(monkeypatch):
    monkeypatch.setattr(api, "INCLUIR_HASH_DOCUMENTO_AUDITORIA", True)
    datos = b"Documento de prueba."
    def procesar(nombres):
        archivos = [UploadFile(io.BytesIO(datos), filename=nombre) for nombre in nombres]
        return asyncio.run(api._procesar_archivos_subidos(archivos, "prueba"))

    doc, envio, archivos = procesar(["uno.txt", "dos.txt"])
    assert [a["sha256"] for a in archivos] == [hashlib.sha256(datos).hexdigest()] * 2
    legado = hashlib.sha256(b"1\x00uno.txt\x00" + datos + b"2\x00dos.txt\x00" + datos)
    assert envio == legado.hexdigest()
    assert procesar(["dos.txt", "uno.txt"])[1] != envio
    assert procesar(["copia.txt"])[2][0]["sha256"] == archivos[0]["sha256"]
    ficha = auditoria.generar_ficha_tecnica(
        peticion_id="prueba", documento=doc, esquema=None, modo="esencial",
        idioma_salida="es", modelo="modelo", filtro_claves=None,
        propuesta=None, deteccion=None, sha256_documento=envio, archivos=archivos,
    )["documento"]
    assert ficha["sha256_envio"] == ficha["sha256"] == envio
    assert ficha["archivos"] == archivos
    monkeypatch.setattr(api, "INCLUIR_HASH_DOCUMENTO_AUDITORIA", False)
    _, envio, archivos = procesar(["uno.txt"])
    assert envio is None and archivos[0]["sha256"] is None
