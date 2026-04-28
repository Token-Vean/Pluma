# syntax=docker/dockerfile:1.7

# =============================================================================
# Imagen de la aplicación — backend FastAPI
# -----------------------------------------------------------------------------
# Multi-stage build para mantener la imagen final pequeña.
# Ejecuta como usuario no privilegiado (uid 10001).
#
# Reproducibilidad:
#   - Imagen base Python fijada por tag mayor.menor (3.12-slim).
#   - Dependencias fijadas en requirements.txt (versión exacta).
#   - Sin llamadas de red durante el runtime salvo a Ollama (ver
#     CUMPLIMIENTO.md).
# =============================================================================

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /build

# Copiar el fichero de dependencias primero (para aprovechar la caché de capas)
COPY requirements.txt /build/requirements.txt

# Instalar en prefijo aislado
RUN pip install --prefix=/install -r requirements.txt


# =============================================================================
# Imagen final
# =============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Librerías del sistema necesarias en runtime (Pillow, pypdfium2, lxml)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        libpng16-16 \
        libtiff6 \
        libwebp7 \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Usuario no privilegiado
RUN groupadd --system --gid 10001 appgroup \
 && useradd  --system --uid 10001 --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

# Dependencias Python desde el builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Código de la aplicación
COPY --chown=appuser:appgroup app /app/app

USER appuser

EXPOSE 8081

# Arranque: uvicorn con un solo worker (la app es ligera, mantiene estado
# en memoria por petición, y múltiples workers no aportan aquí).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
