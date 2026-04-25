#!/usr/bin/env bash
# =============================================================================
# PlumA — instalador para Linux y macOS
# -----------------------------------------------------------------------------
# Este script prepara y arranca PlumA en tu equipo. Si todo va bien,
# abrirá el navegador con la aplicación lista para usar.
#
# Pre-requisito: tener Docker Desktop instalado y arrancado.
#                Descárgalo gratis desde:
#                https://www.docker.com/products/docker-desktop/
# =============================================================================

set -euo pipefail

if [[ -t 1 ]]; then
    ROJO=$'\033[31m'; VERDE=$'\033[32m'; AMAR=$'\033[33m'
    AZUL=$'\033[34m'; GRIS=$'\033[90m'; NEG=$'\033[1m'; FIN=$'\033[0m'
else
    ROJO=''; VERDE=''; AMAR=''; AZUL=''; GRIS=''; NEG=''; FIN=''
fi

paso()   { echo "${AZUL}▸${FIN} ${NEG}$1${FIN}"; }
ok()     { echo "  ${VERDE}✓${FIN} $1"; }
avisar() { echo "  ${AMAR}!${FIN} $1"; }
fallar() { echo "  ${ROJO}✗${FIN} $1" >&2; exit 1; }
nota()   { echo "    ${GRIS}$1${FIN}"; }

# Localizamos el directorio del script (la raíz del proyecto, donde está
# este fichero) y el subdirectorio sistema/ donde vive todo lo técnico.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SISTEMA_DIR="$SCRIPT_DIR/sistema"

if [[ ! -d "$SISTEMA_DIR" ]]; then
    fallar "No encuentro la carpeta 'sistema/'. ¿Has descomprimido el zip completo?"
fi

# Toda la maquinaria de Docker Compose vive dentro de sistema/.
# Cambiamos allí para que las rutas relativas funcionen.
cd "$SISTEMA_DIR"

echo ""
echo "${NEG}PlumA — instalación${FIN}"
echo "${GRIS}$(printf '%.0s─' {1..40})${FIN}"
echo ""

# -----------------------------------------------------------------------------
# 1. Docker
# -----------------------------------------------------------------------------
paso "Comprobando Docker"

if ! command -v docker &>/dev/null; then
    fallar "Docker no está instalado.
    Descárgalo desde: https://www.docker.com/products/docker-desktop/"
fi

if ! docker info &>/dev/null; then
    fallar "Docker no está arrancado. Abre Docker Desktop y vuelve a ejecutar este script."
fi

ok "Docker instalado y arrancado"

# -----------------------------------------------------------------------------
# 2. Docker Compose
# -----------------------------------------------------------------------------
paso "Comprobando Docker Compose"

if docker compose version &>/dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE="docker-compose"
else
    fallar "Docker Compose no está disponible. Actualiza Docker Desktop a una versión reciente."
fi

ok "Docker Compose disponible"

# -----------------------------------------------------------------------------
# 3. Detección de Ollama
# -----------------------------------------------------------------------------
paso "Detectando motor de IA"

PERFIL="bundled"
if command -v curl &>/dev/null; then
    if curl -sfm 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
        PERFIL="external"
    fi
fi

if [[ "$PERFIL" == "external" ]]; then
    ok "Ollama detectado en el equipo (puerto 11434)"
    nota "PlumA usará tu Ollama y los modelos que tengas."
else
    ok "No se ha detectado Ollama en el equipo"
    nota "Se instalará Ollama dentro de Docker (~4-5 GB la primera vez)."
fi

# -----------------------------------------------------------------------------
# 4. Puerto
# -----------------------------------------------------------------------------
paso "Comprobando puerto de la aplicación"

PUERTO=8082
if [[ -f .env ]] && grep -q "^PUERTO=" .env; then
    PUERTO=$(grep "^PUERTO=" .env | head -1 | cut -d= -f2)
fi

puerto_ocupado=false
if command -v lsof &>/dev/null; then
    lsof -i :"$PUERTO" &>/dev/null && puerto_ocupado=true
elif command -v ss &>/dev/null; then
    ss -tln 2>/dev/null | grep -q ":$PUERTO " && puerto_ocupado=true
fi

if [[ "$puerto_ocupado" == true ]]; then
    if docker ps --filter "name=archivo-ia-app" --format "{{.Names}}" 2>/dev/null | grep -q "archivo-ia-app"; then
        ok "Puerto $PUERTO ocupado por la propia PlumA (reinicio)"
    else
        avisar "Puerto $PUERTO en uso por otra aplicación"
        nota "Si el arranque falla, edita sistema/.env y cambia PUERTO."
    fi
else
    ok "Puerto $PUERTO disponible"
fi

# -----------------------------------------------------------------------------
# 5. Configuración (.env)
# -----------------------------------------------------------------------------
paso "Preparando configuración"

if [[ -f .env ]]; then
    ok "Configuración (.env) ya existe"
elif [[ -f .env.example ]]; then
    cp .env.example .env
    ok "Configuración inicial creada"
else
    fallar "No encuentro .env.example. Reinstala el zip completo."
fi

if grep -q "^PERFIL=" .env 2>/dev/null; then
    sed -i.bak "s/^PERFIL=.*/PERFIL=${PERFIL}/" .env && rm -f .env.bak
else
    echo "" >> .env
    echo "PERFIL=${PERFIL}" >> .env
fi

if grep -q "^MODELO_BASE=gemma3:4b$" .env 2>/dev/null; then
    sed -i.bak "s/^MODELO_BASE=gemma3:4b$/MODELO_BASE=gemma4:e2b/" .env && rm -f .env.bak
elif ! grep -q "^MODELO_BASE=" .env 2>/dev/null; then
    echo "MODELO_BASE=gemma4:e2b" >> .env
fi

# -----------------------------------------------------------------------------
# 6. Construir e iniciar
# -----------------------------------------------------------------------------
paso "Preparando PlumA (la primera vez tarda 1-3 minutos)"

export COMPOSE_PROFILES="$PERFIL"

if ! $COMPOSE build 2>/tmp/pluma_build.log; then
    echo ""
    cat /tmp/pluma_build.log
    fallar "Fallo al construir la imagen."
fi

ok "Imagen preparada"

paso "Arrancando los servicios"

$COMPOSE down &>/dev/null || true

if ! $COMPOSE up -d; then
    fallar "No se pudieron arrancar los servicios.

    Causas habituales:
      - Puerto $PUERTO en uso por otra aplicación.
      - Espacio en disco insuficiente.
      - Permisos de Docker."
fi

ok "Servicios arrancados"

# -----------------------------------------------------------------------------
# 7. Esperar a que esté listo y abrir navegador
# -----------------------------------------------------------------------------
paso "Esperando a que la aplicación esté lista"

MAX_INTENTOS=30
listo=false
for ((i=1; i<=MAX_INTENTOS; i++)); do
    if curl -sfm 2 "http://localhost:$PUERTO/api/estado" >/dev/null 2>&1; then
        listo=true
        break
    fi
    sleep 1
done

if [[ "$listo" == true ]]; then
    ok "PlumA lista"
else
    avisar "La aplicación tarda más de lo habitual; abro el navegador igualmente."
    nota "Si no carga, espera 30 segundos y refresca."
fi

echo ""
echo "${GRIS}$(printf '%.0s─' {1..40})${FIN}"
echo ""
echo "${VERDE}${NEG}PlumA está lista.${FIN}"
echo ""
echo "Abriendo el navegador en: ${NEG}http://localhost:${PUERTO}${FIN}"
echo ""
echo "Para parar PlumA:        ejecuta ${NEG}2_DETENER.sh${FIN}"
echo "Para desinstalar PlumA:  ejecuta ${NEG}3_DESINSTALAR.sh${FIN}"
echo ""

URL="http://localhost:$PUERTO"
if command -v xdg-open &>/dev/null; then
    xdg-open "$URL" &>/dev/null &
elif command -v open &>/dev/null; then
    open "$URL"
else
    echo "Copia esta URL en tu navegador: $URL"
fi
