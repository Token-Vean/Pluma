#!/usr/bin/env bash
# =============================================================================
# PlumA — detener servicios
# -----------------------------------------------------------------------------
# Detiene los contenedores Docker de PlumA. Los datos no se pierden:
# la próxima vez que ejecutes 1_INSTALAR.sh, se reanudarán donde quedaron.
# =============================================================================

set -euo pipefail

if [[ -t 1 ]]; then
    VERDE=$'\033[32m'; AZUL=$'\033[34m'
    NEG=$'\033[1m'; FIN=$'\033[0m'
else
    VERDE=''; AZUL=''; NEG=''; FIN=''
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SISTEMA_DIR="$SCRIPT_DIR/sistema"

if [[ ! -d "$SISTEMA_DIR" ]]; then
    echo "ERROR: no encuentro la carpeta 'sistema/'. ¿Has descomprimido el zip completo?"
    exit 1
fi

cd "$SISTEMA_DIR"

if docker compose version &>/dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE="docker-compose"
else
    echo "ERROR: Docker Compose no disponible."
    exit 1
fi

echo ""
echo "${AZUL}▸${FIN} ${NEG}Deteniendo PlumA...${FIN}"

$COMPOSE down

echo ""
echo "  ${VERDE}✓${FIN} PlumA detenida."
echo ""
echo "  Para arrancarla de nuevo, ejecuta ${NEG}1_INSTALAR.sh${FIN}"
echo ""
