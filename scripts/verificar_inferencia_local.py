"""Prueba funcional de CI con dos entradas sintéticas y el cliente real de PlumA."""
import asyncio
import io
import os

from PIL import Image, ImageDraw

from app import llm


async def comprobar() -> None:
    modelo = os.environ.get("MODELO_BASE", "gemma4:e2b")
    imagen = Image.new("RGB", (160, 160), "white")
    ImageDraw.Draw(imagen).rectangle((45, 45, 115, 115), fill="blue")
    datos = io.BytesIO()
    imagen.save(datos, format="PNG")
    for ruta, mensaje, imagenes in (
        ("texto", "Di el color del papel blanco. Contesta con una palabra.", None),
        ("imagen", "¿De qué color es el cuadrado central? Contesta con una palabra.", [datos.getvalue()]),
    ):
        salida = await llm.generar(mensaje, modelo=modelo, imagenes=imagenes, formato_json=False)
        if not salida.strip():
            raise RuntimeError(f"Inferencia {ruta} vacía")
        print(f"Inferencia {ruta} completada con {modelo} ({len(salida)} caracteres).")


if __name__ == "__main__":
    asyncio.run(comprobar())
