# PlumA v0.4.16-alpha

Release orientada a instalación sencilla en Windows mediante panel gráfico sin consola.

Entrada recomendada en Windows:

```text
00_INSTALAR_PLUMA_WINDOWS_SIN_CONSOLA.vbs
```

La instalación Linux/macOS se conserva en la carpeta `instalacion_linux_mac/`.

## Cambios de esta versión

- Plantilla estructural segura para mantener la forma de salida sin ejemplos documentales copiables.
- Control antieco para evitar que el modelo reutilice datos de ejemplos internos antiguos.
- Corrección de comprobaciones Docker en el panel gráfico.
- Mensajes más claros sobre uso de Ollama local del usuario frente a Ollama Docker.
- Mejora de selección de ficheros en modo flotante.

## Seguridad local

PlumA se publica solo en `127.0.0.1:8082` y bloquea endpoints remotos.
