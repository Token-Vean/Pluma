#!/usr/bin/env bash
# =============================================================================
# PlumA — instalador Linux/macOS en modo local bloqueado
# -----------------------------------------------------------------------------
# PlumA reutiliza el Ollama nativo si responde y contiene algún modelo. En caso
# contrario activa el perfil bundled, levanta Ollama en Docker y descarga el
# modelo base antes de arrancar la aplicación.
#
# NOTA (compatibilidad macOS): este instalador NO depende de `python3` en el
# host. El saneo de `.env` y la detección del modelo en Ollama se hacen con
# `grep`/`sed` y expansiones de parámetro de bash, disponibles de fábrica en
# macOS (incluido desde Monterey, donde ya no se incluye Python), Linux y
# Git-Bash/WSL. El único requisito real sigue siendo Docker.
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
# Reimplementado sin python3, solo con utilidades POSIX + bash.
#
# Variables que NO se pueden definir desde fuera: la release pública es
# estrictamente local. MODELO_NOMBRE y MODELFILE_PATH son obsoletas desde la arquitectura v0.7.0
# (ya no hay modelo derivado). PLUMA_OLLAMA_MODE y PLUMA_OLLAMA_URL las fija el
# propio instalador según la detección del host.
# -----------------------------------------------------------------------------
paso "Aplicando configuración local bloqueada"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
fi

# Claves prohibidas/obsoletas que se eliminan del .env si aparecen.
CLAVES_BLOQUEADAS="OLLAMA_URL ALLOW_REMOTE_OLLAMA ALLOW_NETWORK_EXPOSURE \
PLUMA_STRICT_LOCAL PERFIL COMPOSE_PROFILES MODELO_NOMBRE MODELFILE_PATH \
PLUMA_OLLAMA_MODE PLUMA_OLLAMA_URL"

# Recorta espacios al inicio y final de una cadena (equivalente a .strip()).
recortar(){
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"   # quita espacios iniciales
  s="${s%"${s##*[![:space:]]}"}"   # quita espacios finales
  printf '%s' "$s"
}

ENV_TMP="$(mktemp)"
trap 'rm -f "$ENV_TMP"' EXIT

if [[ -f .env ]]; then
  # Se procesa línea a línea preservando el contenido permitido. La última
  # línea sin salto final también se procesa gracias a la condición del while.
  while IFS= read -r linea || [[ -n "$linea" ]]; do
    clave=""
    case "$linea" in
      *=*) clave="$(recortar "${linea%%=*}")" ;;
    esac
    saltar=false
    if [[ -n "$clave" ]]; then
      for b in $CLAVES_BLOQUEADAS; do
        if [[ "$clave" == "$b" ]]; then saltar=true; break; fi
      done
    fi
    if [[ "$saltar" == false ]]; then
      printf '%s\n' "$linea" >> "$ENV_TMP"
    fi
  done < .env
fi

# Asegura que una clave exista; si no, la añade con su valor por defecto.
# La comprobación replica startswith("CLAVE="): la línea debe empezar por la
# clave seguida de '=', sin espacios delante.
asegurar(){
  local k="$1" v="$2"
  if ! grep -qE "^${k}=" "$ENV_TMP" 2>/dev/null; then
    printf '%s=%s\n' "$k" "$v" >> "$ENV_TMP"
  fi
}

asegurar 'PUERTO' '8082'
asegurar 'MODELO_BASE' 'gemma4:e2b'

mv "$ENV_TMP" .env
trap - EXIT

ok "Configuración saneada. No se permite endpoint remoto ni publicación en red."

# -----------------------------------------------------------------------------
# Detección de Ollama nativo en el host
# -----------------------------------------------------------------------------
paso "Detectando Ollama nativo en el host"

# Modelo base que se buscará como preferido. Se lee del .env recién saneado.
MODELO_BASE=$(grep '^MODELO_BASE=' .env | head -1 | cut -d= -f2- || true)
[[ -z "$MODELO_BASE" ]] && MODELO_BASE="gemma4:e2b"

extraer_modelos(){
  grep -oE '"name"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | sed -E 's/^"name"[[:space:]]*:[[:space:]]*"(.*)"$/\1/' || true
}

modelo_presente(){
  local buscar="$1" n=""
  while IFS= read -r n; do
    [[ -z "$n" ]] && continue
    if [[ "$n" == "$buscar" || "$n" == "${buscar}:latest" ]]; then
      return 0
    fi
  done
  return 1
}

TAGS_JSON=""
MODELOS_DESCARGADOS=""
PERFIL_ELEGIDO="bundled"
if command -v curl >/dev/null 2>&1 && curl -sfm 2 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  TAGS_JSON="$(curl -sfm 2 "http://127.0.0.1:11434/api/tags" 2>/dev/null || true)"
  MODELOS_DESCARGADOS="$(printf '%s' "$TAGS_JSON" | extraer_modelos)"
  if [[ -n "$MODELOS_DESCARGADOS" ]]; then
    PERFIL_ELEGIDO="host"
    if printf '%s\n' "$MODELOS_DESCARGADOS" | modelo_presente "$MODELO_BASE"; then
      ok "Ollama del host responde y tiene $MODELO_BASE"
    else
      PRIMERO_MODELO="$(printf '%s\n' "$MODELOS_DESCARGADOS" | head -1)"
      avisar "Ollama del host responde, pero no tiene $MODELO_BASE. PlumA usará otro modelo local disponible: $PRIMERO_MODELO"
    fi
  else
    avisar "Ollama del host responde, pero no hay modelos. Se usará el perfil bundled."
  fi
else
  avisar "Ollama nativo no responde. Se usará el perfil bundled administrado por Docker."
fi

# -----------------------------------------------------------------------------
# Escribir el modo en .env y configurar Compose
# -----------------------------------------------------------------------------
paso "Configurando modo de Ollama"
if [[ "$PERFIL_ELEGIDO" == "host" ]]; then
  {
    echo ""
    echo "# Modo elegido automáticamente por el instalador"
    echo "PLUMA_OLLAMA_MODE=host"
    echo "PLUMA_OLLAMA_URL=http://host.docker.internal:11434"
  } >> .env
  export COMPOSE_PROFILES=""
  "${COMPOSE[@]}" --profile bundled stop ollama >/dev/null 2>&1 || true
  ok "Modo: host (se reutiliza el Ollama nativo/local)"
else
  {
    echo ""
    echo "# Modo elegido automáticamente por el instalador"
    echo "PLUMA_OLLAMA_MODE=container"
    echo "PLUMA_OLLAMA_URL=http://ollama:11434"
  } >> .env
  export COMPOSE_PROFILES="bundled"
  ok "Modo: bundled (Ollama se ejecutará dentro de Docker)"
fi

# -----------------------------------------------------------------------------
# Levantar servicios
# -----------------------------------------------------------------------------
paso "Preparando servicios"
if [[ "$PERFIL_ELEGIDO" == "bundled" ]]; then
  "${COMPOSE[@]}" up -d ollama || fallar "No se pudo arrancar Ollama en Docker."
  listo_ollama=false
  for _ in {1..30}; do
    if "${COMPOSE[@]}" exec -T ollama ollama list >/dev/null 2>&1; then
      listo_ollama=true
      break
    fi
    sleep 1
  done
  [[ "$listo_ollama" == true ]] || fallar "Ollama no ha respondido dentro del tiempo esperado."
  paso "Descargando o verificando el modelo $MODELO_BASE (puede tardar)"
  "${COMPOSE[@]}" exec -T ollama ollama pull "$MODELO_BASE" \
    || fallar "No se pudo descargar el modelo $MODELO_BASE."
fi
"${COMPOSE[@]}" up -d --build app || fallar "No se pudo arrancar la aplicación."
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
[[ "$listo" == true ]] && ok "Aplicación lista" || avisar "PlumA puede seguir arrancando o esperando a Ollama."

URL="http://localhost:$PUERTO"
echo ""
echo "${VERDE}${NEG}Instalación completada en modo local bloqueado.${FIN}"
echo "URL: ${NEG}$URL${FIN}"
if [[ "$PERFIL_ELEGIDO" == "host" ]]; then
  echo "Ollama: instalación nativa del host"
else
  echo "Ollama: perfil bundled administrado por Docker"
fi
echo ""
if [[ "$PERFIL_ELEGIDO" == "host" ]]; then
  echo "${AMAR}AVISO de seguridad — Ollama nativo${FIN}"
  echo "Comprueba que tu Ollama del host está escuchando SOLO en localhost."
  echo "Para limitarlo a tu equipo:"
  echo "  Linux/macOS: export OLLAMA_HOST=127.0.0.1 antes de 'ollama serve'"
  echo "             (o ajusta el servicio systemd; ver INSTALACION.md)"
  echo "  Windows: ajusta la variable de entorno OLLAMA_HOST=127.0.0.1"
  echo "           en las propiedades del sistema."
  echo ""
fi
echo ""
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
  open "$URL"
else
  echo "Copia esta URL en tu navegador: $URL"
fi
