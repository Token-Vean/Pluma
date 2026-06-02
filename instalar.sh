#!/usr/bin/env bash
# =============================================================================
# PlumA — instalador Linux/macOS en modo local bloqueado
# -----------------------------------------------------------------------------
# A partir de v0.6 el instalador detecta si tienes Ollama nativo en el host
# con el modelo base ya descargado. Si lo tiene, configura PlumA para usarlo
# vía host.docker.internal:11434 y NO arranca el contenedor de Ollama. Si no
# lo tiene, activa el perfil `bundled` de Docker Compose y levanta Ollama
# dentro de Docker como antes.
#
# Esto elimina la duplicación de modelos (4-5 GB) que ocurría en v0.5 cuando
# el usuario ya tenía Ollama en el sistema.
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
echo "${NEG}PlumA — instalación local bloqueada${FIN}"
echo "${GRIS}────────────────────────────────────────${FIN}"
echo ""

paso "Comprobando Docker"
command -v docker >/dev/null 2>&1 || fallar "Docker no está instalado."
docker info >/dev/null 2>&1 || fallar "Docker no está arrancado."
ok "Docker instalado y arrancado"

paso "Comprobando Docker Compose"
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    fallar "Docker Compose no disponible."
fi
ok "Docker Compose disponible"

# -----------------------------------------------------------------------------
# Saneo de .env (eliminar variables prohibidas/obsoletas; asegurar mínimas)
# -----------------------------------------------------------------------------
paso "Aplicando configuración local bloqueada"
if [[ ! -f .env && -f .env.example ]]; then
    cp .env.example .env
fi
python3 - <<'PY2'
from pathlib import Path
p = Path('.env')
content = p.read_text(encoding='utf-8') if p.exists() else ''
# Variables que NO se pueden definir desde fuera: la release pública es estrictamente local.
# MODELO_NOMBRE y MODELFILE_PATH son obsoletas desde v0.6 (ya no hay modelo derivado).
# PLUMA_OLLAMA_MODE y PLUMA_OLLAMA_URL las fija el propio instalador según detección.
blocked = {
    'OLLAMA_URL', 'ALLOW_REMOTE_OLLAMA', 'ALLOW_NETWORK_EXPOSURE',
    'PLUMA_STRICT_LOCAL', 'PERFIL', 'COMPOSE_PROFILES',
    'MODELO_NOMBRE', 'MODELFILE_PATH',
    'PLUMA_OLLAMA_MODE', 'PLUMA_OLLAMA_URL',
}
lines = []
for line in content.splitlines():
    key = line.split('=', 1)[0].strip() if '=' in line else ''
    if key in blocked:
        continue
    lines.append(line)
text = "\n".join(lines).strip() + "\n"

def ensure(k, v):
    global text
    if not any(l.startswith(k + '=') for l in text.splitlines()):
        text += f"{k}={v}\n"

ensure('PUERTO', '8082')
ensure('MODELO_BASE', 'gemma4:e2b')
p.write_text(text, encoding='utf-8')
PY2
ok "Configuración saneada. No se permite endpoint remoto ni publicación en red."

# -----------------------------------------------------------------------------
# Detección de Ollama nativo en el host
# -----------------------------------------------------------------------------
paso "Detectando Ollama nativo en el host"

# Modelo base que se buscará. Se lee del .env recién saneado.
MODELO_BASE=$(grep '^MODELO_BASE=' .env | head -1 | cut -d= -f2- || true)
[[ -z "$MODELO_BASE" ]] && MODELO_BASE="gemma4:e2b"

USAR_HOST_OLLAMA=false
if command -v curl >/dev/null 2>&1 && curl -sfm 2 "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    if curl -sfm 2 "http://localhost:11434/api/tags" 2>/dev/null \
       | python3 -c "
import json, sys
data = json.load(sys.stdin)
modelos = [m.get('name','') for m in data.get('models', [])]
buscar = sys.argv[1]
encontrado = (buscar in modelos) or (f'{buscar}:latest' in modelos)
sys.exit(0 if encontrado else 1)
" "$MODELO_BASE" 2>/dev/null; then
        USAR_HOST_OLLAMA=true
        ok "Ollama del host responde y tiene $MODELO_BASE — se evitará descarga duplicada"
    else
        avisar "Ollama del host responde pero NO tiene $MODELO_BASE — se usará Ollama dentro de Docker"
    fi
else
    avisar "Ollama nativo no detectado en el host — se usará Ollama dentro de Docker"
fi

# -----------------------------------------------------------------------------
# Escribir el modo en .env y configurar profile de Compose
# -----------------------------------------------------------------------------
paso "Configurando modo de Ollama"
if [[ "$USAR_HOST_OLLAMA" == true ]]; then
    {
      echo ""
      echo "# Modo elegido por el instalador en función de la detección del host"
      echo "PLUMA_OLLAMA_MODE=host"
      echo "PLUMA_OLLAMA_URL=http://host.docker.internal:11434"
    } >> .env
    export COMPOSE_PROFILES=""
    ok "Modo: host (la app usará el Ollama nativo)"
else
    {
      echo ""
      echo "# Modo elegido por el instalador en función de la detección del host"
      echo "PLUMA_OLLAMA_MODE=container"
      echo "PLUMA_OLLAMA_URL=http://ollama:11434"
    } >> .env
    export COMPOSE_PROFILES="bundled"
    ok "Modo: container (Ollama se levantará dentro de Docker)"
fi

# -----------------------------------------------------------------------------
# Levantar servicios
# -----------------------------------------------------------------------------
paso "Preparando servicios"
"${COMPOSE[@]}" up -d --build || fallar "No se pudieron arrancar los servicios."
ok "Servicios arrancados"

# -----------------------------------------------------------------------------
# Espera y apertura
# -----------------------------------------------------------------------------
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
[[ "$listo" == true ]] && ok "Aplicación lista" || avisar "PlumA puede seguir arrancando o descargando el modelo."

URL="http://localhost:$PUERTO"
echo ""
echo "${VERDE}${NEG}Instalación completada en modo local bloqueado.${FIN}"
echo "URL: ${NEG}$URL${FIN}"
if [[ "$USAR_HOST_OLLAMA" == true ]]; then
    echo "Ollama: usado desde el host (sin duplicación de modelos)"
    echo ""
    echo "${AMAR}AVISO de seguridad — Ollama nativo${FIN}"
    echo "Comprueba que tu Ollama del host está escuchando SOLO en localhost."
    echo "Por defecto, Ollama escucha en 0.0.0.0:11434, lo que significa que"
    echo "cualquier dispositivo en tu red (oficina, wifi corporativa) puede"
    echo "enviarle peticiones. Para limitarlo a tu equipo:"
    echo "  Linux/macOS:  export OLLAMA_HOST=127.0.0.1  antes de 'ollama serve'"
    echo "                (o ajusta el servicio systemd; ver INSTALACION.md)"
    echo "  Windows:      ajusta la variable de entorno OLLAMA_HOST=127.0.0.1"
    echo "                en las propiedades del sistema."
    echo ""
else
    echo "Ollama: dentro de Docker (perfil bundled)"
fi
echo ""
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "$URL"
else
    echo "Copia esta URL en tu navegador: $URL"
fi
