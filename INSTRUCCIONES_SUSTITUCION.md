# Correcciones para PlumA 0.7.2

## Sustitución

1. Haz una copia de seguridad del repositorio o crea una rama nueva.
2. Copia el contenido de esta carpeta sobre la raíz del repositorio PlumA,
   conservando la estructura de carpetas y aceptando la sustitución de archivos.
3. Revisa `git diff` antes de confirmar los cambios.

Cambian treinta y dos ficheros. Dieciocho llevan cambios reales de código,
configuración o documentación; el resto solo actualiza la cadena de versión.

## Verificación

Ejecuta desde la raíz del repositorio:

```bash
python scripts/security_static_check.py
python -m pytest -q
```

Si utilizas Docker:

```bash
docker compose build --no-cache app
```

Después del `push`, comprueba que los tres jobs del workflow
`security-checks` terminan correctamente: seguridad Python, dependencias y
pruebas en Windows, y escaneo del contenedor.

## Comprobaciones específicas de esta versión

- El tag de imagen sube a `pluma-app:0.7.2`. Si actualizas
  `docker-compose.yml` sin actualizar `.github/workflows/security-checks.yml`,
  el job `container-scan` construye una imagen y Trivy busca otra: falla al no
  encontrarla en local y acaba intentando descargarla de Docker Hub.
  `test_version_coherence()` cubre ahora el workflow para que esa
  desincronización se detecte antes de llegar a CI.
- Los controles de seguridad del procesamiento (`USAR_SANDBOX_PARSERS`,
  `SANDBOX_TIMEOUT_SEGUNDOS`, `SANDBOX_MEMORIA_MB`,
  `INCLUIR_HASH_DOCUMENTO_AUDITORIA`, `PERMITIR_APAGADO_UI`) dejan de leerse de
  `.env`. Si tu `.env` local los define, el saneador del instalador los
  eliminará en la próxima ejecución: es el comportamiento esperado.
- `pypdf` sube a 6.16.1. Conviene ejecutar `pip-audit` antes de etiquetar, no
  solo confiar en el resultado de la auditoría previa.

## GitHub

- No fusiones la PR de Dependabot que elimina el marcador de Windows de
  `uvloop`. Estas correcciones incorporan una prueba para impedir esa regresión.
- Cierra las PR antiguas de acciones de GitHub cuyos cambios ya estén incluidos
  en `main`.
- Cuando la CI esté en verde, crea la etiqueta `v0.7.2`, la release y su
  manifiesto SHA-256.

## Resultado esperado del instalador

- Si Ollama nativo responde y contiene algún modelo: perfil `host`.
- Si no hay un Ollama nativo utilizable: perfil `bundled`; el instalador
  arranca Ollama en Docker y descarga el modelo configurado en `MODELO_BASE`.
