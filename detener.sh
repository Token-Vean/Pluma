#!/usr/bin/env bash
# =============================================================================
# PlumA — detener servicios
# -----------------------------------------------------------------------------
# Detiene la aplicación (y Ollama si se instaló en modo container) sin
# borrar nada. La próxima vez que se ejecute iniciar.sh, todo estará donde
# lo dejaste.
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

# Recuperar el modo guardado por el instalador. Si la instalación dejó el
# servicio Ollama corriendo (modo container), necesitamos pasar el profile
# para que `docker compose down` también lo pare.
MODO="container"
if [[ -f .env ]]; then
    val=$(grep '^PLUMA_OLLAMA_MODE=' .env | head -1 | cut -d= -f2- || true)
    [[ -n "$val" ]] && MODO="$val"
fi
if [[ "$MODO" == "host" ]]; then
    export COMPOSE_PROFILES=""
else
    export COMPOSE_PROFILES="bundled"
fi

echo "Deteniendo servicios..."
$COMPOSE down

echo ""
echo "Servicios detenidos."
echo ""
echo "Los datos y el modelo se conservan. Para volver a arrancar:"
echo "  ./iniciar.sh"
echo ""
echo "Para eliminar TODO (contenedores, modelo descargado, configuración):"
echo "  ./desinstalar.sh"
