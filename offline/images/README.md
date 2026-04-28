# Imágenes Docker offline

Coloca aquí imágenes Docker exportadas con `docker image save` si quieres que PlumA se instale sin descargar imágenes desde Internet.

Nombres recomendados:

```text
pluma-app-0.4.16-alpha.tar
ollama-0.21.2.tar
```

Generación orientativa en una máquina con Docker e Internet:

```bat
docker compose build app
docker image save -o offline\images\pluma-app-0.4.16-alpha.tar pluma-app:0.4.16-alpha
docker image pull ollama/ollama:0.21.2
docker image save -o offline\images\ollama-0.21.2.tar ollama/ollama:0.21.2
```

El instalador visual cargará automáticamente los `.tar` de esta carpeta antes de iniciar PlumA.
