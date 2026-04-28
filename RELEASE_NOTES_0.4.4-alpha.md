# PlumA v0.4.14-alpha — visual installer, local locked, offline-ready

Esta versión corrige la experiencia de instalación en Windows y refuerza el objetivo local de PlumA.

## Cambios principales

- Se añade `00_INSTALAR_PLUMA_WINDOWS_SIN_CONSOLA.vbs` como vía principal de instalación visual en Windows.
- Los `.bat` de Windows se retiran de la raíz y quedan en `soporte/linea_comandos_windows/` para uso avanzado.
- El panel gráfico ejecuta comandos en segundo plano sin abrir consola visible.
- Se mantiene el modo local bloqueado: sin Ollama remoto y sin publicación de red.
- Se añade estructura `offline/` para imágenes Docker y modelos GGUF.
- El instalador carga automáticamente imágenes Docker `.tar` si existen.
- El instalador importa automáticamente un modelo `.gguf` local si existe.
- Se actualiza la versión interna a `0.4.14-alpha`.

## Limitación

El paquete no incluye imágenes Docker ni modelos LLM por tamaño. Queda preparado para integrarlos y construir una release offline completa.
