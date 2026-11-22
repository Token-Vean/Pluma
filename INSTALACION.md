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

Ejecuta `instalar.bat` en Windows o `./instalar.sh` en Linux/macOS. El
instalador elige automáticamente uno de estos perfiles:

1. **Host**. Si Ollama ya responde en `127.0.0.1:11434` y contiene al menos un
   modelo, PlumA reutiliza esa instalación. Si está disponible `gemma4:e2b`, lo
   selecciona como preferido; si no, permite elegir otro modelo local.
2. **Bundled**. Si no hay un Ollama nativo utilizable, el instalador arranca
   Ollama dentro de Docker, descarga `gemma4:e2b` y conserva el modelo en un
   volumen local. La descarga inicial puede ocupar varios gigabytes y tardar.

En ambos perfiles la interfaz queda disponible únicamente en
<http://127.0.0.1:8082> y los documentos se procesan localmente. El perfil
`bundled` necesita conexión a Internet durante la descarga inicial del modelo;
después puede utilizarse sin conexión.


## Endurecimiento de Ollama nativo (modo host)

Desde PlumA 0.7.4 el servicio nativo debe ejecutar Ollama estable 0.35.0 o posterior y tener desactivada la nube. En Windows, cierra Ollama desde el área de notificación, establece la variable de usuario `OLLAMA_NO_CLOUD` con valor `1` y vuelve a abrir Ollama. En macOS, ejecuta `launchctl setenv OLLAMA_NO_CLOUD 1` antes de volver a abrir la aplicación. En Linux con systemd, añade `Environment="OLLAMA_NO_CLOUD=1"` a la sección `[Service]` mediante `systemctl edit ollama`, ejecuta `systemctl daemon-reload` y reinicia el servicio. En un arranque manual se puede usar `OLLAMA_NO_CLOUD=1 ollama serve`.

Comprueba `http://127.0.0.1:11434/api/version` y que `http://127.0.0.1:11434/api/status` devuelve `cloud.disabled` con el valor booleano `true`. Si el instalador no puede verificar el motor o sus modelos, selecciona el motor de Docker.

PlumA carece de cuentas individuales. En escritorios remotos o equipos con sesiones simultáneas, cada persona debe trabajar en una instancia aislada, por ejemplo, una máquina virtual de uso individual.



Cuando el instalador selecciona el perfil host, PlumA usa el Ollama
nativo/local del usuario (`PLUMA_OLLAMA_MODE=host`) en lugar de levantar un
segundo Ollama dentro de Docker. Esto evita duplicar modelos y asegura que se
trabaja con los modelos que el usuario ya tiene descargados y controla.

**Punto de atención de seguridad.** Ollama escucha por defecto en
`127.0.0.1:11434` (loopback). La exposición a la red aparece si el usuario
cambia `OLLAMA_HOST` a `0.0.0.0`, a una IP de la LAN o configura un
servicio equivalente. En ese caso, otros equipos podrían alcanzar el motor.

PlumA comprueba que el endpoint configurado sea local y, además, rechaza
modelos de Ollama con etiquetas cloud. Aun así, si reutilizas un Ollama nativo
conviene verificar su configuración antes de procesar documentación sensible.

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

En Linux, un Ollama nativo limitado a `127.0.0.1` no es accesible desde el
contenedor a través de `host.docker.internal`, porque esa dirección apunta a
la pasarela del puente Docker y no al loopback del host. Para un despliegue
simple y cerrado, usa el perfil `bundled` de PlumA.

Solo si administras conscientemente la red Docker, puedes publicar Ollama en
una dirección del host alcanzable desde el puente y limitarla mediante firewall.
No se recomienda `OLLAMA_HOST=0.0.0.0` en equipos con documentación sensible.

### Comprobación final

Tras endurecer Ollama, vuelve a ejecutar `instalar.sh`/`instalar.bat`.
El instalador comprobará si Ollama del host responde en `127.0.0.1` y contiene
algún modelo. Si es así, configurará el modo host; si no, ofrecerá el entorno
`bundled` administrado mediante Docker.

### Por qué no lo hace PlumA automáticamente

Cambiar la configuración del servicio Ollama del host requiere
privilegios del usuario y depende del SO. PlumA no puede modificar
servicios del sistema del archivero ni debe hacerlo: la herramienta
asume que el usuario gestiona su propio Ollama. Lo que sí hace es
advertir cuando detecta que va a usar el Ollama nativo, para que el
usuario decida si quiere endurecerlo.


## Verificar el ZIP de Windows

En PowerShell, ejecuta `Get-FileHash .\PlumA-0_7_4-windows.zip -Algorithm SHA256` y compara la huella completa con el archivo `.sha256` de la misma publicación. Dentro del ZIP, `REVISION.txt` identifica el commit de origen. Para reproducirlo con Git y Python desde el repositorio, ejecuta `python scripts/empaquetar_windows.py --ref <commit>`. El resultado queda en `dist/`.
