# Instalación del PlumA

Esta guía está pensada para archiveros sin conocimientos técnicos
previos. En la mayoría de casos, solo hay que seguir dos pasos.

## Antes de empezar

El asistente usa **Docker** para aislar la aplicación del resto del
sistema. Docker es una herramienta gratuita que permite que el
programa funcione exactamente igual en cualquier ordenador.

### Paso previo: instalar Docker

Si todavía no tienes Docker en tu equipo:

- **Windows o macOS**: descarga Docker Desktop desde
  <https://www.docker.com/products/docker-desktop/>, instálalo, y
  ábrelo. Déjalo arrancado en segundo plano.
- **Linux**: instala Docker desde el gestor de paquetes de tu
  distribución (por ejemplo, `sudo apt install docker.io docker-compose-plugin`
  en Ubuntu/Debian) y asegúrate de que tu usuario está en el grupo
  `docker`.

Si no estás seguro de si tienes Docker, no pasa nada: el instalador
te lo dirá.

## Cómo funciona la instalación

El instalador configura PlumA para usar el **Ollama nativo/local del usuario**.
La aplicación no arranca Ollama dentro de Docker ni descarga modelos en un
volumen Docker por defecto.

Flujo esperado:

1. Instala e inicia Ollama en el equipo anfitrión.
2. Descarga al menos un modelo con `ollama pull`. Recomendado:
   `ollama pull gemma4:e2b`.
3. Ejecuta `instalar.bat` o `instalar.sh`. PlumA se conectará a
   `host.docker.internal:11434` desde el contenedor de la aplicación.
4. Desde la interfaz podrás elegir cualquiera de los modelos ya descargados.

Si `gemma4:e2b` no existe, PlumA elegirá otro modelo local disponible. Si
Ollama responde pero no tiene modelos, o si Ollama no está iniciado, la interfaz
mostrará un error claro y no intentará descargar modelos dentro de Docker.

3. Si el fichero contenía secretos reales (claves, tokens),
   **rótalos**. Asume que todo lo que ha estado en GitHub público,
   aunque se borre, ha podido ser visto y archivado por terceros.

Lo más fácil es prevenir: ejecutar el verificador antes de cada `push`.


## Endurecimiento de Ollama nativo (modo host)

PlumA usa el Ollama nativo/local del usuario (`PLUMA_OLLAMA_MODE=host`)
en lugar de levantar un segundo Ollama dentro de Docker. Esto evita duplicar
modelos y asegura que se trabaja con los modelos que el usuario ya tiene
descargados y controla desde su instalación de Ollama.

**Punto de atención de seguridad.** El servicio de Ollama, por defecto,
escucha en `0.0.0.0:11434`, es decir, acepta conexiones desde cualquier
interfaz de red del equipo. En una red corporativa o wifi compartida,
otros dispositivos de la misma red pueden enviar prompts a tu Ollama,
gastarle compute y, potencialmente, ver respuestas que generes mientras
procesas documentos sensibles.

PlumA no introduce esta exposición — es la configuración por defecto de
Ollama, independientemente de PlumA — pero al fomentar el modo host
conviene cerrarla explícitamente. Las tres opciones siguientes la
limitan a `localhost` (`127.0.0.1`).

### Windows

Abre **Configuración → Sistema → Información → Configuración avanzada
del sistema → Variables de entorno**, y añade una variable de **usuario**
(no del sistema, para no afectar a otros usuarios):

- **Nombre:** `OLLAMA_HOST`
- **Valor:** `127.0.0.1`

Cierra Ollama (icono en la bandeja del sistema → Quit) y vuelve a
arrancarlo. Verifica con:

```
netstat -ano | findstr :11434
```

Debes ver `127.0.0.1:11434` y no `0.0.0.0:11434`.

### macOS

Cierra Ollama desde la barra de menú (icono → Quit) y arranca desde
terminal con la variable de entorno:

```
OLLAMA_HOST=127.0.0.1 ollama serve
```

Para hacerlo permanente, edita tu `~/.zshrc` o `~/.bash_profile` y
añade `export OLLAMA_HOST=127.0.0.1`.

### Linux (systemd)

Edita el servicio de Ollama con `sudo systemctl edit ollama` y añade:

```
[Service]
Environment="OLLAMA_HOST=127.0.0.1"
```

Recarga y reinicia:

```
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

Verifica con `ss -tlnp | grep 11434`. Debe aparecer `127.0.0.1:11434`.

### Comprobación final

Tras endurecer Ollama, vuelve a ejecutar `instalar.sh`/`instalar.bat`.
El instalador comprobará si Ollama del host responde en `127.0.0.1` y volverá
a configurar el modo host. Si Ollama no responde, PlumA arrancará igualmente,
pero mostrará error hasta que Ollama esté iniciado.

### Por qué no lo hace PlumA automáticamente

Cambiar la configuración del servicio Ollama del host requiere
privilegios del usuario y depende del SO. PlumA no puede modificar
servicios del sistema del archivero ni debe hacerlo: la herramienta
asume que el usuario gestiona su propio Ollama. Lo que sí hace es
advertir cuando detecta que va a usar el Ollama nativo, para que el
usuario decida si quiere endurecerlo.
