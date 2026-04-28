# PlumA — modo local bloqueado

Esta release pública está preparada para uso local/monousuario. La configuración
no permite convertir PlumA en un servicio de red ni conectar la aplicación a un
endpoint LLM remoto.

## Qué queda bloqueado

- La interfaz se publica solo en `127.0.0.1`.
- `OLLAMA_URL` se fuerza internamente a `http://ollama:11434`.
- `ALLOW_REMOTE_OLLAMA` y `ALLOW_NETWORK_EXPOSURE` no tienen efecto en modo público.
- Se ha eliminado el perfil `external` del `docker-compose.yml` de release.
- La aplicación rechaza cabeceras de proxy habituales en modo local estricto.
- El contenedor de la app solo está unido a una red interna de Docker sin salida directa a Internet.
- El contenedor de Ollama conserva salida a Internet únicamente para poder descargar el modelo si falta.

## Qué puede seguir saliendo a Internet

En una instalación sin caché previa puede haber tres descargas técnicas:

1. imágenes Docker necesarias;
2. dependencias durante la construcción de la imagen Python;
3. modelo Ollama configurado en `MODELO_BASE`.

Para una instalación offline completa habría que distribuir imágenes Docker
preconstruidas mediante `docker save` y el modelo ya descargado/importable.
Esta variante todavía no incluye ese paquete offline pesado.

## Límite del blindaje

Un usuario con permisos de administrador y conocimientos técnicos siempre puede
modificar código, reconstruir imágenes o editar Compose. La protección aplicada
está pensada para impedir cambios accidentales o usos no previstos en la release
pública, no para resistir a un administrador malicioso del propio equipo.
