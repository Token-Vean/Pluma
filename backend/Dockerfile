# syntax=docker/dockerfile:1.7

# =============================================================================
# Imagen de la aplicación — backend FastAPI
# -----------------------------------------------------------------------------
# Multi-stage build para mantener la imagen final pequeña.
# Ejecuta como usuario no privilegiado (uid 10001).
#
# Reproducibilidad:
#   - Imagen base Python fijada por tag de rama estable (3.12-slim-bookworm).
#   - Dependencias fijadas en requirements.txt (versión exacta).
#   - Sin llamadas de red durante el runtime salvo a Ollama (ver
#     CUMPLIMIENTO.md).
# =============================================================================

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS builder

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
FROM ${PYTHON_IMAGE}

LABEL org.opencontainers.image.title="PlumA" \
      org.opencontainers.image.version="0.7.0" \
      org.opencontainers.image.description="PlumA local-first archival description assistant"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Librerías del sistema necesarias en runtime (Pillow, pypdfium2, lxml)
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        libpng16-16 \
        libtiff6 \
        libwebp7 \
        libxml2 \
        libxslt1.1 \
        tesseract-ocr \
        tesseract-ocr-spa \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Usuario no privilegiado
RUN groupadd --system --gid 10001 appgroup \
 && useradd  --system --uid 10001 --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

# Dependencias Python desde el builder
COPY --from=builder /install /usr/local

# Hardening v0.7.0:
# La aplicación no instala paquetes en runtime. Se elimina pip/setuptools/wheel
# de la imagen final para reducir superficie y resolver las vulnerabilidades
# corregibles detectadas por Docker Scout en pip.
RUN python -m pip uninstall -y pip setuptools wheel 2>/dev/null || true \
 && rm -rf \
      /usr/local/bin/pip* \
      /usr/local/bin/wheel \
      /usr/local/lib/python*/site-packages/pip \
      /usr/local/lib/python*/site-packages/pip-* \
      /usr/local/lib/python*/site-packages/setuptools \
      /usr/local/lib/python*/site-packages/setuptools-* \
      /usr/local/lib/python*/site-packages/wheel \
      /usr/local/lib/python*/site-packages/wheel-* \
      /root/.cache/pip

WORKDIR /app

# Código de la aplicación
COPY --chown=appuser:appgroup app /app/app

USER appuser

EXPOSE 8081

# Arranque: uvicorn con un solo worker (la app es ligera, mantiene estado
# en memoria por petición, y múltiples workers no aportan aquí).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
