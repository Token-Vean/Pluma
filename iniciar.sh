#!/usr/bin/env bash
# =============================================================================
# PlumA — arranque cotidiano (Linux/macOS)
# -----------------------------------------------------------------------------
# Script ligero para arrancar PlumA cuando ya está instalado. NO reconstruye
# imágenes, NO descarga modelos, NO toca el .env. Solo levanta los
# contenedores y abre el navegador.
#
# Respeta el modo elegido por el instalador (PLUMA_OLLAMA_MODE en .env):
#   - container  → activa COMPOSE_PROFILES=bundled para levantar Ollama Docker.
#   - host       → no activa profile, no se arranca Ollama del contenedor.
#
# La primera vez, usa instalar.sh.
# Para detener: detener.sh.
# =============================================================================
set -euo pipefail

if [[ -t 1 ]]; then
    ROJO=$'\033[31m'; VERDE=$'\033[32m'; AMAR=$'\033[33m'; AZUL=$'\033[34m'; GRIS=$'\033[90m'; NEG=$'\033[1m'; FIN=$'\033[0m'
else
    ROJO=''; VERDE=''; AMAR=''; AZUL=''; GRIS=''; NEG=''; FIN=''
fi
paso(){ echo "${AZUL}▸${FIN} ${NEG}$1${FIN}"; }
ok(){ echo "  ${VERDE}✓${FIN} $1"; }
avisar(){ echo "  ${AMAR}!${FIN} $1"; }
fallar(){ echo "  ${ROJO}✗${FIN} $1" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "${NEG}PlumA — arranque${FIN}"
echo "${GRIS}────────────────────${FIN}"
echo ""

paso "Comprobando Docker"
command -v docker >/dev/null 2>&1 || fallar "Docker no está instalado."
docker info >/dev/null 2>&1 || fallar "Docker no está arrancado."
ok "Docker disponible"

paso "Detectando Docker Compose"
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    fallar "Docker Compose no disponible."
fi
ok "Docker Compose disponible"

paso "Aplicando modo configurado en .env"
MODO="container"
if [[ -f .env ]]; then
    val=$(grep '^PLUMA_OLLAMA_MODE=' .env | head -1 | cut -d= -f2- || true)
    [[ -n "$val" ]] && MODO="$val"
fi
if [[ "$MODO" == "host" ]]; then
    export COMPOSE_PROFILES=""
    ok "Modo: host (la app usará el Ollama nativo)"
else
    export COMPOSE_PROFILES="bundled"
    ok "Modo: container (se levantará el Ollama de Docker)"
fi

paso "Levantando servicios"
if ! "${COMPOSE[@]}" up -d; then
    fallar "No se pudieron arrancar los servicios. Si es la primera vez, usa instalar.sh."
fi
ok "Servicios arrancados"

paso "Esperando a que la aplicación responda"
PUERTO=8082
if [[ -f .env ]]; then
    val=$(grep '^PUERTO=' .env | head -1 | cut -d= -f2- || true)
    [[ -n "$val" ]] && PUERTO="$val"
fi
listo=false
for _ in {1..30}; do
    if command -v curl >/dev/null 2>&1 && curl -sfm 2 "http://localhost:$PUERTO/api/estado" >/dev/null; then
        listo=true; break
    fi
    sleep 1
done
[[ "$listo" == true ]] && ok "Aplicación lista" || avisar "PlumA puede estar cargando el modelo."

URL="http://localhost:$PUERTO"
echo ""
echo "${VERDE}${NEG}PlumA arrancado.${FIN}"
echo "URL: ${NEG}$URL${FIN}"
echo "Para detener: ./detener.sh"
echo ""
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "$URL"
else
    echo "Copia esta URL en tu navegador: $URL"
fi
