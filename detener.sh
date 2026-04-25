#!/usr/bin/env bash
# =============================================================================
# PlumA — detener servicios
# -----------------------------------------------------------------------------
# Detiene la aplicación (y Ollama si se instaló en el perfil "bundled")
# sin borrar nada. La próxima vez que se ejecute el instalador, todo
# estará donde lo dejaste.
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

# Recuperar el perfil guardado por el instalador
if [[ -f .env ]] && grep -q "^PERFIL=" .env; then
    PERFIL=$(grep "^PERFIL=" .env | head -1 | cut -d= -f2)
else
    # Por defecto, intentamos ambos perfiles (docker compose ignora los
    # servicios que no encajan con el perfil)
    PERFIL="bundled,external"
fi

export COMPOSE_PROFILES="$PERFIL"

echo "Deteniendo servicios..."
$COMPOSE down

echo ""
echo "Servicios detenidos."
echo ""
echo "Los datos y el modelo se conservan. Para volver a arrancar, ejecuta:"
echo "  ./instalar.sh"
echo ""
echo "Para eliminar TODO (contenedores, modelo descargado, configuración):"
echo "  ./desinstalar.sh"
