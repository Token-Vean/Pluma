#!/usr/bin/env bash
# =============================================================================
# Comprobación pre-subida a GitHub
# -----------------------------------------------------------------------------
# Ejecutar ANTES de hacer git push, para verificar que no se cuela nada
# de las pruebas locales (ficheros .env, documentos personales, caches,
# logs con datos sensibles).
# =============================================================================
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ROJO='\033[0;31m'
VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
SIN='\033[0m'

problemas=0

echo "═══════════════════════════════════════════════════════════════════════════"
echo "  Comprobación pre-subida a GitHub"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# 1. Comprobar si estamos en un repo git
if [ ! -d ".git" ]; then
    echo -e "${ROJO}ERROR${SIN}: no estás en la raíz de un repositorio git."
    exit 1
fi

# 2. Mostrar ficheros que git va a subir (nuevos o modificados)
echo "── Ficheros que git ve como cambios pendientes ──────────────────"
git status --short
echo ""

# 3. Comprobar que .env no está rastreado
echo "── Comprobación de secretos ─────────────────────────────────────"
if git ls-files | grep -E "^\.env$|/\.env$" > /dev/null; then
    echo -e "${ROJO}PELIGRO${SIN}: hay ficheros .env rastreados por git:"
    git ls-files | grep -E "^\.env$|/\.env$"
    echo "  Ejecuta: git rm --cached .env"
    problemas=$((problemas+1))
else
    echo -e "${VERDE}OK${SIN}: ningún .env rastreado"
fi

# 4. Comprobar claves o certificados
if git ls-files | grep -iE "\.(key|pem|p12|pfx)$" > /dev/null; then
    echo -e "${ROJO}PELIGRO${SIN}: hay claves o certificados rastreados:"
    git ls-files | grep -iE "\.(key|pem|p12|pfx)$"
    problemas=$((problemas+1))
else
    echo -e "${VERDE}OK${SIN}: sin claves ni certificados rastreados"
fi

# 5. Comprobar __pycache__
if git ls-files | grep -E "__pycache__|\.pyc$" > /dev/null; then
    echo -e "${AMARILLO}AVISO${SIN}: hay __pycache__ o .pyc rastreados:"
    git ls-files | grep -E "__pycache__|\.pyc$" | head -5
    echo "  Ejecuta: git rm --cached -r --ignore-unmatch '*__pycache__*' '*.pyc'"
    problemas=$((problemas+1))
else
    echo -e "${VERDE}OK${SIN}: sin caché Python rastreada"
fi

# 6. Documentos de prueba en /ejemplos
echo ""
echo "── Comprobación de documentos de prueba ─────────────────────────"
ejemplos_extra=$(git ls-files ejemplos/ 2>/dev/null | grep -vE "\.md$" || true)
if [ -n "$ejemplos_extra" ]; then
    echo -e "${AMARILLO}AVISO${SIN}: hay ficheros en ejemplos/ que NO son .md:"
    echo "$ejemplos_extra"
    echo ""
    echo "  Si son documentos de DOMINIO PÚBLICO que quieres incluir como"
    echo "  ejemplos, perfecto. Si son documentos reales de pruebas, MUY"
    echo "  IMPORTANTE: quítalos antes de subir:"
    echo "    git rm --cached ejemplos/<fichero>"
    problemas=$((problemas+1))
else
    echo -e "${VERDE}OK${SIN}: ejemplos/ contiene solo documentación"
fi

# 7. Buscar palabras clave sospechosas en ficheros nuevos/modificados
echo ""
echo "── Comprobación de contenido (cabezadas de secretos) ────────────"
patrones_secretos="password|secret|api_key|apikey|token|auth_key"
sospechosos=$(git diff --cached --name-only 2>/dev/null | xargs -r grep -liE "$patrones_secretos" 2>/dev/null | grep -vE "\.(md|example|gitignore)$|test_security|csrf\.py|llm\.py" || true)
if [ -n "$sospechosos" ]; then
    echo -e "${AMARILLO}REVISAR${SIN}: ficheros que mencionan secretos:"
    echo "$sospechosos"
    echo "  Inspecciona manualmente si contienen valores reales o solo nombres de variables."
else
    echo -e "${VERDE}OK${SIN}: sin patrones obvios de secretos en ficheros con cambios"
fi

# 8. Tamaño de los ficheros que se van a subir
echo ""
echo "── Tamaño total del commit pendiente ────────────────────────────"
tam_total=$(git diff --cached --numstat 2>/dev/null | awk '{sum+=$1+$2} END {print sum}')
echo "  Líneas añadidas + eliminadas en staging: ${tam_total:-0}"

ficheros_grandes=$(git diff --cached --name-only 2>/dev/null | xargs -r -I {} sh -c '[ -f "{}" ] && find "{}" -size +1M 2>/dev/null' | head -5)
if [ -n "$ficheros_grandes" ]; then
    echo -e "${AMARILLO}AVISO${SIN}: ficheros grandes (>1 MB):"
    echo "$ficheros_grandes"
fi

# 9. Resumen
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
if [ $problemas -eq 0 ]; then
    echo -e "${VERDE}Listo para subir.${SIN} No se han detectado problemas evidentes."
    echo ""
    echo "Recordatorio: este script no garantiza que no se cuele algo. Revisa"
    echo "siempre 'git status' y 'git diff --cached' antes de hacer push."
else
    echo -e "${ROJO}Se han detectado ${problemas} problema(s).${SIN}"
    echo "Resuélvelos antes de hacer git push."
fi
echo "═══════════════════════════════════════════════════════════════════════════"

exit $problemas
