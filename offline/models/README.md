# Modelos offline

Carpeta reservada para paquetes de distribución offline.

En el repositorio fuente debe conservarse solo este archivo marcador. No subas modelos `.gguf`, `.bin` ni pesos de modelo al repositorio.

En la arquitectura v0.7.0, PlumA no requiere un modelo derivado en Ollama para funcionar. El system prompt y los parámetros de inferencia viven en `schemas/pluma-runtime.yaml` y el backend los inyecta en cada llamada. Por tanto, esta carpeta solo tiene sentido para distribuir un blob `.gguf` que se quiera importar en Ollama Docker (proceso fuera del alcance de v0.7.0).
