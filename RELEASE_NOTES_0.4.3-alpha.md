# PlumA v0.4.14-alpha — visual installer + local locked

Versión alpha orientada a mejorar la instalación Windows y reforzar el carácter
local de la herramienta.

## Cambios principales

- Panel gráfico Windows para instalación y gestión sin consola visible.
- Proyecto NSIS preparado para generar instalador `.exe`.
- Modo local bloqueado activado por defecto.
- Eliminado el perfil `external` de Docker Compose en la release pública.
- `OLLAMA_URL` queda forzado a `http://ollama:11434` dentro del contenedor.
- La app se publica únicamente en `127.0.0.1:${PUERTO:-8082}`.
- La app queda en una red Docker interna sin salida directa a Internet.
- Ollama conserva salida a Internet para descarga explícita del modelo.
- Rechazo de cabeceras de proxy/reverse proxy en modo estricto.
- `.env.example` saneado: no expone `ALLOW_REMOTE_OLLAMA`, `ALLOW_NETWORK_EXPOSURE` ni `OLLAMA_URL`.
- Fuentes locales incluidas; no hay descarga de fuentes en la release.

## Limitación conocida

No es todavía un paquete offline total: si el equipo no tiene caché previa, Docker
puede descargar imágenes/dependencias y Ollama puede descargar el modelo base.
