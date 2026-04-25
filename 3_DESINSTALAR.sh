#!/usr/bin/env bash
# =============================================================================
# PlumA — desinstalación
# -----------------------------------------------------------------------------
# Elimina los contenedores Docker, las imágenes y los volúmenes de PlumA.
# Los ficheros del proyecto en disco NO se borran: si quieres eliminar
# PlumA por completo, borra también la carpeta tras ejecutar este script.
# =============================================================================

set -euo pipefail

if [[ -t 1 ]]; then
    ROJO=$'\033[31m'; VERDE=$'\033[32m'; AMAR=$'\033[33m'; AZUL=$'\033[34m'
    NEG=$'\033[1m'; FIN=$'\033[0m'
else
    ROJO=''; VERDE=''; AMAR=''; AZUL=''; NEG=''; FIN=''
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
echo "${NEG}PlumA — desinstalación${FIN}"
echo ""
echo "Esta acción eliminará:"
echo "  - Los contenedores Docker de PlumA."
echo "  - Las imágenes Docker (la próxima instalación las reconstruirá)."
echo "  - Los volúmenes (modelos descargados de Ollama, ~5 GB liberados)."
echo ""
echo "${AMAR}Los ficheros del proyecto en disco NO se borran${FIN}; si quieres"
echo "eliminar PlumA por completo, borra también la carpeta del proyecto"
echo "después de ejecutar este script."
echo ""

read -p "¿Continuar? (s/N): " respuesta
if [[ ! "$respuesta" =~ ^[sSyY]$ ]]; then
    echo "Cancelado. No se ha eliminado nada."
    exit 0
fi

echo ""
echo "${AZUL}▸${FIN} ${NEG}Eliminando contenedores y volúmenes...${FIN}"
$COMPOSE down -v

echo "${AZUL}▸${FIN} ${NEG}Eliminando imágenes...${FIN}"
$COMPOSE down --rmi all 2>/dev/null || true

# Eliminación adicional por nombre, por si hay imágenes huérfanas
docker rmi pluma-app:latest 2>/dev/null || true
docker rmi pluma-app-external:latest 2>/dev/null || true

echo ""
echo "  ${VERDE}✓${FIN} PlumA desinstalada de Docker."
echo ""
echo "  Para eliminar también los ficheros del proyecto, borra esta carpeta."
echo ""
