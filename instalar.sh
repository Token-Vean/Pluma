#!/usr/bin/env bash
# =============================================================================
# PlumA — instalador para Linux y macOS
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "${NEG}PlumA — instalación${FIN}"
echo "${GRIS}$(printf '%.0s─' {1..40})${FIN}"
echo ""

# -----------------------------------------------------------------------------
# 1. Docker
# -----------------------------------------------------------------------------
paso "Comprobando Docker"

if ! command -v docker &>/dev/null; then
    fallar "Docker no está instalado. Descárgalo desde https://www.docker.com/products/docker-desktop/"
fi

if ! docker info &>/dev/null; then
    fallar "Docker no está arrancado. Arráncalo y vuelve a ejecutar este script."
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
    fallar "Docker Compose no disponible."
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
    nota "La aplicación usará tu Ollama y los modelos que tengas."
else
    ok "No se ha detectado Ollama en el equipo"
    nota "Se instalará Ollama dentro de Docker (~4-5 GB la primera vez)."
fi

# -----------------------------------------------------------------------------
# 4. Puerto configurado (del .env)
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
    # ¿Es nuestro propio contenedor?
    if docker ps --filter "name=archivo-ia-app" --format "{{.Names}}" | grep -q "archivo-ia-app"; then
        ok "Puerto $PUERTO ocupado por la propia aplicación (reinicio)"
    else
        avisar "Puerto $PUERTO en uso por otra aplicación"
        nota "Si el arranque falla, cambia PUERTO en .env a otro libre."
    fi
else
    ok "Puerto $PUERTO disponible"
fi

# -----------------------------------------------------------------------------
# 5. .env
# -----------------------------------------------------------------------------
paso "Preparando configuración"

if [[ -f .env ]]; then
    ok "Fichero .env ya existe"
elif [[ -f .env.example ]]; then
    cp .env.example .env
    ok "Fichero .env creado"
fi

if grep -q "^PERFIL=" .env 2>/dev/null; then
    sed -i.bak "s/^PERFIL=.*/PERFIL=${PERFIL}/" .env && rm -f .env.bak
else
    echo "" >> .env
    echo "PERFIL=${PERFIL}" >> .env
fi

# Actualización segura del modelo por defecto: solo cambia el valor antiguo
# del paquete anterior; respeta cualquier modelo personalizado por el usuario.
if grep -q "^MODELO_BASE=gemma3:4b$" .env 2>/dev/null; then
    sed -i.bak "s/^MODELO_BASE=gemma3:4b$/MODELO_BASE=gemma4:e2b/" .env && rm -f .env.bak
elif ! grep -q "^MODELO_BASE=" .env 2>/dev/null; then
    echo "MODELO_BASE=gemma4:e2b" >> .env
fi

# -----------------------------------------------------------------------------
# 5.5. Tipografías
# -----------------------------------------------------------------------------
paso "Comprobando tipografías"
nota "La interfaz usa tipografías del sistema. Las fuentes autohospedadas son opcionales."
nota "Si quieres instalarlas, ejecuta frontend/static/fonts/descargar-fuentes.sh manualmente."

# -----------------------------------------------------------------------------
# 6. Reconstruir imagen
# -----------------------------------------------------------------------------
paso "Preparando la imagen de la aplicación"
nota "(si has actualizado el código, esto tardará ~30s)"

export COMPOSE_PROFILES="$PERFIL"

if ! $COMPOSE build 2>/tmp/build.log; then
    echo ""
    cat /tmp/build.log
    fallar "Fallo al construir la imagen."
fi

ok "Imagen preparada"

# -----------------------------------------------------------------------------
# 7. Arrancar servicios
# -----------------------------------------------------------------------------
paso "Arrancando los servicios"

$COMPOSE down &>/dev/null || true

if ! $COMPOSE up -d; then
    fallar "No se pudieron arrancar los servicios.

    Causas habituales:
      - Puerto $PUERTO en uso por otra aplicación.
      - Espacio en disco insuficiente."
fi

ok "Servicios arrancados"

# -----------------------------------------------------------------------------
# 8. Esperar y abrir navegador
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
    ok "Aplicación lista"
else
    avisar "La aplicación tarda más de lo habitual; abro el navegador igualmente"
fi

echo ""
echo "${GRIS}$(printf '%.0s─' {1..40})${FIN}"
echo ""
echo "${VERDE}${NEG}Instalación completada.${FIN}"
echo ""
echo "Abriendo el navegador en: ${NEG}http://localhost:${PUERTO}${FIN}"
echo ""
echo "Modo de despliegue activo:   ${NEG}${PERFIL}${FIN}"
echo "Para detener la aplicación:  ${NEG}./detener.sh${FIN}"
echo "Para ver los logs:           ${NEG}$COMPOSE logs -f${FIN}"
echo ""

# Abrir el navegador según el sistema
URL="http://localhost:$PUERTO"
if command -v xdg-open &>/dev/null; then
    xdg-open "$URL" &>/dev/null &
elif command -v open &>/dev/null; then
    # macOS
    open "$URL"
else
    echo "Copia esta URL en tu navegador: $URL"
fi
