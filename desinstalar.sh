#!/usr/bin/env bash
# =============================================================================
# PlumA — desinstalación
# -----------------------------------------------------------------------------
# Elimina los contenedores y, si procede, el volumen con el modelo
# descargado dentro de Docker.
#
# Importante: si la instalación usó el perfil "external" (Ollama del
# equipo), NO se toca el Ollama ni los modelos del anfitrión.
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

# Recuperar perfil
if [[ -f .env ]] && grep -q "^PERFIL=" .env; then
    PERFIL=$(grep "^PERFIL=" .env | head -1 | cut -d= -f2)
else
    PERFIL="bundled,external"
fi

echo ""
echo "Esta operación va a eliminar:"
echo "  - Los contenedores Docker del PlumA."

if [[ "$PERFIL" == "bundled" ]]; then
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

export COMPOSE_PROFILES="$PERFIL"

echo ""
echo "Eliminando contenedores y volúmenes..."
$COMPOSE down -v

# Imagen de la app (se regenera la próxima instalación)
docker image rm pluma-app 2>/dev/null || true

echo ""
echo "Desinstalación completada."
echo ""
echo "Si quieres eliminar también los ficheros del proyecto,"
echo "borra esta carpeta manualmente."
