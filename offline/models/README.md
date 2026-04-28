# Modelos offline GGUF

Coloca aquí un modelo local en formato `.gguf` si quieres evitar `ollama pull` durante la instalación.

Funcionamiento:

1. El instalador busca el primer archivo `*.gguf` de esta carpeta.
2. Genera automáticamente `Modelfile.offline.generated`.
3. Ejecuta `ollama create` dentro del contenedor `pluma-ollama`.
4. El modelo resultante se registra con el nombre configurado en `.env` (`MODELO_NOMBRE=pluma` por defecto).

Si no hay `.gguf`, PlumA usará el flujo normal de Ollama y podrá descargar el modelo base configurado si no existe ya localmente.
