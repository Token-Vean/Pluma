#!/usr/bin/env bash
# =============================================================================
# PlumA — desinstalación
# -----------------------------------------------------------------------------
# Elimina los contenedores y, si la instalación usó el modo container, el
# volumen Docker con el modelo descargado dentro de Ollama Docker.
#
# Importante: si la instalación usó el modo host (Ollama nativo del equipo),
# NO se toca el Ollama ni los modelos del anfitrión.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if docker compose version &>/dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE="docker-compose"
else
    echo "Error: Docker Compose no está disponible." >&2
    exit 1
fi

# Recuperar modo
MODO="container"
if [[ -f .env ]]; then
    val=$(grep '^PLUMA_OLLAMA_MODE=' .env | head -1 | cut -d= -f2- || true)
    [[ -n "$val" ]] && MODO="$val"
fi

echo ""
echo "Esta operación va a eliminar:"
echo "  - Los contenedores Docker del PlumA."

if [[ "$MODO" == "container" ]]; then
    echo "  - El volumen Docker con el modelo de IA (3-5 GB)."
    echo ""
    echo "NO se eliminará:"
    echo "  - Docker ni ninguna otra aplicación del sistema."
    echo "  - La carpeta del proyecto (eso se hace a mano)."
else
    echo ""
    echo "NO se eliminará:"
    echo "  - Tu instalación de Ollama en el equipo."
    echo "  - Los modelos que tengas descargados en Ollama."
    echo "  - Docker ni ninguna otra aplicación del sistema."
    echo "  - La carpeta del proyecto (eso se hace a mano)."
fi
echo ""
read -p "¿Continuar? (escribe 'si' para confirmar): " confirmacion

if [[ "$confirmacion" != "si" ]]; then
    echo "Desinstalación cancelada."
    exit 0
fi

if [[ "$MODO" == "host" ]]; then
    export COMPOSE_PROFILES=""
else
    export COMPOSE_PROFILES="bundled"
fi

echo ""
echo "Eliminando contenedores y volúmenes..."
$COMPOSE down -v

# Imagen de la app (se regenera la próxima instalación)
docker image rm pluma-app:0.6.0-beta 2>/dev/null || true
docker image rm pluma-app 2>/dev/null || true

echo ""
echo "Desinstalación completada."
echo ""
echo "Si quieres eliminar también los ficheros del proyecto,"
echo "borra esta carpeta manualmente."
