#!/usr/bin/env bash
# =============================================================================
# PlumA — instalador Linux/macOS en modo local bloqueado
# =============================================================================
set -euo pipefail

if [[ -t 1 ]]; then
    ROJO=$'[31m'; VERDE=$'[32m'; AMAR=$'[33m'; AZUL=$'[34m'; GRIS=$'[90m'; NEG=$'[1m'; FIN=$'[0m'
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

paso "Aplicando configuración local bloqueada"
if [[ ! -f .env && -f .env.example ]]; then
    cp .env.example .env
fi
python3 - <<'PY2'
from pathlib import Path
p=Path('.env')
content=p.read_text(encoding='utf-8') if p.exists() else ''
blocked={'OLLAMA_URL','ALLOW_REMOTE_OLLAMA','ALLOW_NETWORK_EXPOSURE','PLUMA_STRICT_LOCAL','PERFIL','COMPOSE_PROFILES'}
lines=[]
for line in content.splitlines():
    key=line.split('=',1)[0].strip() if '=' in line else ''
    if key in blocked:
        continue
    lines.append(line)
text='
'.join(lines).strip()+'
'
def ensure(k,v):
    global text
    if not any(l.startswith(k+'=') for l in text.splitlines()):
        text += f'{k}={v}
'
ensure('PUERTO','8082')
ensure('MODELO_BASE','gemma4:e2b')
ensure('MODELO_NOMBRE','pluma')
p.write_text(text, encoding='utf-8')
PY2
ok "Configuración saneada. No se permite endpoint remoto ni publicación en red."

paso "Preparando servicios"
unset COMPOSE_PROFILES || true
"${COMPOSE[@]}" up -d --build || fallar "No se pudieron arrancar los servicios."
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
[[ "$listo" == true ]] && ok "Aplicación lista" || avisar "PlumA puede seguir arrancando o descargando el modelo."

URL="http://localhost:$PUERTO"
echo ""
echo "${VERDE}${NEG}Instalación completada en modo local bloqueado.${FIN}"
echo "URL: ${NEG}$URL${FIN}"
echo ""
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "$URL"
else
    echo "Copia esta URL en tu navegador: $URL"
fi
