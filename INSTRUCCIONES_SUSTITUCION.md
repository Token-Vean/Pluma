# Correcciones para PlumA 0.7.1

## Sustitución

1. Haz una copia de seguridad del repositorio o crea una rama nueva.
2. Copia el contenido de esta carpeta sobre la raíz del repositorio PlumA,
   conservando la estructura de carpetas y aceptando la sustitución de archivos.
3. Revisa `git diff` antes de confirmar los cambios.

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

## GitHub

- No fusiones la PR de Dependabot que elimina el marcador de Windows de
  `uvloop`. Estas correcciones incorporan una prueba para impedir esa regresión.
- Cierra las PR antiguas de acciones de GitHub cuyos cambios ya estén incluidos
  en `main`.
- Cuando la CI esté en verde, crea la etiqueta `v0.7.1`, la release y su
  manifiesto SHA-256.

## Resultado esperado del instalador

- Si Ollama nativo responde y contiene algún modelo: perfil `host`.
- Si no hay un Ollama nativo utilizable: perfil `bundled`; el instalador
  arranca Ollama en Docker y descarga el modelo configurado en `MODELO_BASE`.
