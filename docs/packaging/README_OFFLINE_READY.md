# PlumA offline-ready

Esta variante prepara la instalación offline, pero no incluye archivos pesados.

## Qué está preparado

- Carpeta `offline/images/` para imágenes Docker exportadas con `docker image save`.
- Carpeta `offline/models/` para modelos locales `.gguf`.
- Carga automática de imágenes Docker antes de iniciar PlumA.
- Importación automática del primer modelo `.gguf` encontrado.
- Modo local bloqueado para evitar endpoints remotos o publicación en red.

## Qué falta para una release offline completa

Debes añadir manualmente, por peso y licencia:

```text
offline/images/pluma-app-0.4.16-alpha.tar
offline/images/ollama-0.21.2.tar
offline/models/<modelo>.gguf
```

Después, vuelve a comprimir el paquete y genera un nuevo SHA256.
