#!/usr/bin/env bash
# Ejecutar solo en un runner Linux efímero de CI con Docker y tcpdump.
# Se captura desde después de la descarga del modelo hasta terminar la inferencia.
set -euo pipefail
modo="${1:?Indique bundled o host}"
case "$modo" in bundled|host) ;; *) exit 2;; esac
: "${RUNNER_TEMP:?Se requiere un runner de pruebas aislado}"
prueba="$(mktemp -d "$RUNNER_TEMP/pluma-XXXXXXXX")"
export MODELO_BASE=gemma4:e2b
export PLUMA_OLLAMA_MODE=container PLUMA_OLLAMA_URL=http://ollama:11434
docker compose build app
app="$(docker compose config --format json | jq -er '.services.app.image')"

if [[ "$modo" == bundled ]]; then
  docker compose --profile bundled up -d ollama
  motor="$(docker compose --profile bundled ps -q ollama)"
  cli=(docker exec "$motor" ollama)
else
  # El binario nativo se ejecuta directamente en Linux. Una red dedicada
  # permite medir su tráfico sin mezclarlo con el del runner de GitHub.
  imagen="$(docker compose --profile bundled config --format json | jq -er '.services.ollama.image')"
  version="${imagen#*:}"; version="${version%%@*}"
  archivo=ollama-linux-amd64.tar.zst
  curl -fsSL --retry 3 "https://github.com/ollama/ollama/releases/download/v$version/$archivo" -o "$prueba/$archivo"
  digest="$(gh api "repos/ollama/ollama/releases/tags/v$version" --jq ".assets[] | select(.name==\"$archivo\") | .digest")"
  [[ "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]
  echo "${digest#sha256:}  $prueba/$archivo" | sha256sum -c -
  tar --zstd -xf "$prueba/$archivo" -C "$prueba" --exclude='*/cuda*' --exclude='*/rocm*' --exclude='*/vulkan*'
  rm "$prueba/$archivo"
  motor="$(docker run -d --entrypoint sleep "$app" 3600)"
  netpid="$(docker inspect -f '{{.State.Pid}}' "$motor")"
  resolv="$(docker inspect -f '{{.ResolvConfPath}}' "$motor")"
  ejecutar=(sudo unshare --mount --propagation private bash -c 'mount --bind "$1" /etc/resolv.conf; shift; exec "$@"' _ "$resolv"
    nsenter -t "$netpid" -n -- runuser -u "$(id -un)" -- env "HOME=$prueba" OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1)
  cli=("${ejecutar[@]}" "$prueba/bin/ollama")
  arrancar_nativo() {
    "${ejecutar[@]}" bash -c 'echo $$ > "$1"; exec "$2" serve' _ "$prueba/servidor.pid" "$prueba/bin/ollama" >"$prueba/motor.log" 2>&1 &
  }
  arrancar_nativo
fi
for _ in {1..60}; do "${cli[@]}" list >/dev/null 2>&1 && break; sleep 1; done
"${cli[@]}" pull "$MODELO_BASE"

if [[ "$modo" == bundled ]]; then
  # Separar la descarga de la inferencia, cerrando las conexiones del registro.
  docker compose --profile bundled restart ollama
  docker compose up -d --no-build app
  cliente="$(docker compose ps -q app)"
else
  servidor="$(cat "$prueba/servidor.pid")"
  kill -TERM "$servidor"
  for _ in {1..30}; do kill -0 "$servidor" 2>/dev/null || break; sleep 1; done
  if kill -0 "$servidor" 2>/dev/null; then echo "El motor no se detuvo"; exit 1; fi
  arrancar_nativo
  cliente="$(docker run -d --network "container:$motor" -v "$PWD/schemas:/app/schemas:ro" \
    -e OLLAMA_URL=http://127.0.0.1:11434 -e PLUMA_OLLAMA_MODE=host --entrypoint sleep "$app" 3600)"
fi
# app tiene rootfs de solo lectura; ejecutar por stdin conserva su configuración.
for _ in {1..60}; do "${cli[@]}" list >/dev/null 2>&1 && break; sleep 1; done
"${cli[@]}" list >/dev/null
contenedores=("$motor")
if [[ "$modo" == bundled ]]; then contenedores+=("$cliente"); fi
filtro='(ip or ip6) and not (dst net 127.0.0.0/8 or dst host ::1'
for id in "${contenedores[@]}"; do
  while read -r ip; do
    if [[ -n "$ip" ]]; then filtro+=" or dst host $ip"; fi
  done < <(docker inspect "$id" | jq -r '.[0].NetworkSettings.Networks[] | .IPAddress, .GlobalIPv6Address' | sed '/^$/d')
done
filtro+=')'
# Los mensajes ICMPv6 de descubrimiento de vecinos/routers y pertenencia a
# grupos ff02 permanecen en el enlace local. Se contabilizan por separado.
control='ip6 protochain 58 and dst net ff02::/16'
for i in "${!contenedores[@]}"; do
  pid="$(docker inspect -f '{{.State.Pid}}' "${contenedores[$i]}")"
  sudo nsenter -t "$pid" -n -- bash -c 'echo $$ > "$1"; exec tcpdump -Z root -ni any -U -s 96 -w "$2" "ip or ip6"' \
    _ "$prueba/$i.pid" "$prueba/$i.pcap" >"$prueba/$i.log" 2>&1 &
done
for i in "${!contenedores[@]}"; do
  for _ in {1..30}; do grep -q 'listening on' "$prueba/$i.log" && break; sleep 1; done
  grep -q 'listening on' "$prueba/$i.log"
done
docker exec -i -e OLLAMA_NUM_PREDICT=64 -e OLLAMA_VISION_NUM_PREDICT=64 -e OLLAMA_NUM_CTX=4096 \
  "$cliente" python - < scripts/verificar_inferencia_local.py
exito=true
for i in "${!contenedores[@]}"; do
  sudo kill -INT "$(cat "$prueba/$i.pid")"
  for _ in {1..10}; do grep -q 'packets dropped by kernel' "$prueba/$i.log" && break; sleep 1; done
  grep -Eq '^0 packets dropped by kernel' "$prueba/$i.log"
  # En ambos sentidos se exige tráfico al motor para descartar una captura vacía.
  externos="$(sudo tcpdump -nn -r "$prueba/$i.pcap" "($filtro) and not ($control)" 2>/dev/null | wc -l)"
  locales="$(sudo tcpdump -nn -r "$prueba/$i.pcap" 'tcp port 11434' 2>/dev/null | wc -l)"
  enlace="$(sudo tcpdump -nn -r "$prueba/$i.pcap" "$control" 2>/dev/null | wc -l)"
  echo "Perfil $modo, captura $i: $locales paquetes de inferencia, $enlace de control IPv6 de enlace local y $externos a otros destinos."
  if [[ "$externos" -gt 0 ]]; then
    sudo tcpdump -nn -r "$prueba/$i.pcap" "($filtro) and not ($control)"
  fi
  if [[ "$locales" -eq 0 || "$externos" -ne 0 ]]; then exito=false; fi
done
[[ "$exito" == true ]]
