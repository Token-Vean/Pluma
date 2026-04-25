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

El instalador **detecta automáticamente** cómo está configurado tu
equipo y adapta la instalación en consecuencia. Hay dos escenarios:

### Escenario A: equipos sin Ollama instalado

Es el caso más común (archivero que nunca ha usado IA local). El
instalador descarga Ollama dentro de Docker y un modelo por defecto
(Gemma 3 de 4 mil millones de parámetros). Todo queda aislado dentro
de contenedores, sin interferir con el resto del sistema.

- **Descarga la primera vez**: unos 4-5 GB (motor Ollama + modelo).
- **Espacio en disco recomendado**: 8 GB libres.
- **Desinstalación**: el script `desinstalar` elimina el motor y
  el modelo descargados sin tocar nada del sistema.

### Escenario B: equipos con Ollama ya instalado

Si el instalador detecta que tienes Ollama corriendo en tu equipo
(en el puerto 11434), asume que ya sabes usarlo y tienes tus propios
modelos descargados. En este caso **no descarga nada adicional**:
la aplicación se conecta directamente a tu Ollama.

- **Descarga la primera vez**: solo la imagen ligera de la aplicación
  (unos 200 MB).
- **Modelos**: usa los que ya tienes en tu Ollama.
- **Desinstalación**: el script `desinstalar` **no toca** tu Ollama
  ni tus modelos; solo elimina la aplicación.

El instalador muestra claramente qué escenario ha detectado y actúa
en consecuencia. No tienes que elegir nada.

## Requisitos del sistema

- **Espacio en disco**: al menos 8 GB libres si no tienes Ollama, o
  2 GB si ya lo tienes.
- **Memoria RAM**: al menos 8 GB. Con 16 GB el rendimiento es mucho
  mejor.
- **Procesador**: cualquier PC moderno de los últimos 5 años sirve.
  Si tiene tarjeta gráfica NVIDIA, el asistente la usará
  automáticamente y será entre 5 y 10 veces más rápido.

## Instalación

### En Windows

1. Descomprime el fichero `pluma.zip` donde prefieras
   (por ejemplo, en tu carpeta de Documentos).
2. Entra en la carpeta `pluma` que se acaba de crear.
3. Haz doble clic en **`instalar.bat`**.
4. Una ventana de consola se abrirá. Lee los mensajes: el script
   comprobará que todo está en orden, detectará si tienes Ollama y
   arrancará el asistente.
5. Cuando termine, abre tu navegador en
   <http://localhost:8082>.

### En Linux o macOS

1. Descomprime el fichero en la carpeta que prefieras.
2. Abre una terminal en esa carpeta.
3. Ejecuta:
   ```
   chmod +x instalar.sh
   ./instalar.sh
   ```
4. Cuando termine, abre tu navegador en
   <http://localhost:8082>.

## La primera vez

- **Si no tenías Ollama**: el sistema descarga el motor y el modelo
  (4-5 GB). Según tu conexión a Internet puede tardar varios minutos.
  Es una operación que solo ocurre una vez. La interfaz muestra el
  progreso mientras termina; cuando aparezca "Listo para usar",
  podrás empezar a subir documentos.
- **Si ya tenías Ollama**: el sistema solo descarga la imagen de la
  aplicación (rápido). Abre el navegador y estará disponible casi
  inmediatamente.

### Tipografías

La interfaz usa tipografías del sistema y no necesita Google Fonts ni CDN.
Los scripts de `frontend/static/fonts/` son opcionales: solo deben ejecutarse
si se desean fuentes autohospedadas con licencias compatibles. En ese caso,
revise los ficheros descargados y active manualmente las reglas `@font-face`
en `frontend/static/styles.css`.

## Uso diario

A partir de la primera vez, cada vez que quieras usar el asistente:

- **Asegúrate de que Docker está arrancado** (y de que Ollama lo
  esté también si usaste ese escenario).
- **Vuelve a ejecutar** el instalador (`instalar.bat` o
  `./instalar.sh`). No volverá a descargar nada; solo arrancará los
  servicios. Es cuestión de segundos.
- Abre el navegador en <http://localhost:8082>.

Si prefieres que el asistente se arranque automáticamente al
encender el equipo, configura Docker para arrancar con el sistema
y los servicios se levantarán solos.

## Detener el asistente

Cuando no lo estés usando, puedes detenerlo para liberar memoria:

- Windows: doble clic en `detener.bat`.
- Linux/macOS: `./detener.sh` en la terminal.

### Apagar desde la interfaz

La cabecera de la aplicación incluye un botón **Apagar**. Este botón detiene el servidor local de la aplicación, pero no ejecuta `docker compose down` ni detiene el Docker del anfitrión por razones de seguridad. Si instalaste el perfil `bundled`, Ollama puede seguir activo hasta usar `detener.bat`, `detener.sh` o `docker compose down`.

No se pierde nada. Volver a arrancar solo requiere ejecutar el
instalador de nuevo.

## Desinstalar

Si quieres eliminar el asistente por completo:

- Windows: doble clic en `desinstalar.bat` y confirma.
- Linux/macOS: `./desinstalar.sh` y confirma.

Esto elimina los contenedores de Docker y, si habías usado el
escenario A, también el modelo de IA que se descargó para el
asistente. Si usaste el escenario B, tu Ollama y tus modelos siguen
intactos.

Si quieres eliminar también los ficheros del proyecto, borra la
carpeta manualmente después.

## Cambiar de modelo

El modelo por defecto es `gemma4:e2b`. Si quieres usar otro:

1. Edita el fichero `.env` en la raíz del proyecto.
2. Cambia la línea `MODELO_BASE=gemma4:e2b` por el modelo que quieras
   (por ejemplo `gemma4:e4b` para mayor calidad, o `qwen2.5vl:7b`
   para documentos con tablas).
3. Ejecuta `desinstalar` y vuelve a instalar.

Si usas el escenario B (Ollama propio), asegúrate de que el modelo
indicado esté descargado en tu Ollama antes de reiniciar. Puedes
descargarlo con `ollama pull gemma4:e4b` desde la terminal.

## Problemas frecuentes

### "Docker no está instalado" o "Docker no está arrancado"

El instalador comprueba antes de nada que Docker está funcionando.
Si aparece este mensaje, instálalo o arráncalo como se explica más
arriba y vuelve a ejecutar el instalador.

### "El puerto 8082 está en uso"

Alguna otra aplicación de tu equipo está usando ese puerto. Suele
pasar si tienes AtoM instalado, porque comparten puerto. Opciones:

- Cierra la otra aplicación mientras uses el asistente.
- Cambia el puerto del asistente: edita el fichero `.env` y cambia
  la línea `PUERTO=8082` por otro puerto libre (por ejemplo, 8090).
  Luego accede al asistente en <http://localhost:8090>.

### El instalador no detecta mi Ollama aunque lo tengo arrancado

Comprueba que Ollama está escuchando en el puerto por defecto:

```
curl http://localhost:11434/api/tags
```

Debería responder con un JSON con tus modelos. Si no responde:

- En macOS/Windows: abre la aplicación Ollama.
- En Linux: arranca el servicio (`ollama serve` o
  `sudo systemctl start ollama`).

Si Ollama escucha en otro puerto, de momento el instalador solo
detecta el puerto estándar. Apáñatelo arrancando Ollama en 11434
temporalmente, o contacta con el autor para que lo haga configurable.

### "Error al generar la propuesta" o respuestas muy lentas

Si el equipo tiene poca memoria RAM, el modelo por defecto puede ir
justo. Puedes usar un modelo más ligero editando `.env`:

```
MODELO_BASE=moondream
```

Luego desinstala y vuelve a instalar. Perderás algo de calidad en las
propuestas pero ganarás mucha velocidad en equipos modestos.

### La aplicación no abre en el navegador

Asegúrate de que:

1. Docker Desktop está realmente arrancado (icono activo en la barra
   de tareas).
2. Han pasado al menos unos segundos desde que ejecutaste el
   instalador.
3. Estás escribiendo la dirección correcta: **http://localhost:8082**
   (con http, no https).

Si nada funciona, ejecuta `docker compose logs -f` en la carpeta del
proyecto para ver los mensajes de error detallados.

## Dónde pedir ayuda

Para problemas técnicos, usa los issues del repositorio del proyecto
en GitHub. Para consultas sobre uso archivístico, contacta con el
autor por correo electrónico.


## Pruebas locales sin contaminar el repositorio

Cuando uses PlumA para probar con documentos reales, conviene tener
en cuenta qué ficheros se generan localmente y cuáles **no deben
acabar en GitHub** si publicas tu fork del proyecto.

### Qué se genera en pruebas locales (y se ignora automáticamente)

El `.gitignore` del proyecto cubre estos casos automáticamente:

- `.env` real (creado al ejecutar el instalador desde `.env.example`).
- `__pycache__/` y ficheros `.pyc` (caché de Python).
- `.pytest_cache/` (caché de tests).
- Documentos en `ejemplos/` que no sean `.md` (para que no subas
  por error escaneados de prueba).
- Carpetas comunes de pruebas: `/tmp/`, `/pruebas/`, `/test_documents/`.
- Logs (`*.log`), backups (`*.bak`, `*~`), ficheros temporales (`*.tmp`).
- Modelos descargados de Ollama (`*.gguf`, `*.bin`).

### Antes de hacer git push: ejecuta el verificador

Para tener la certeza de que no se cuela nada, antes de subir cambios
a GitHub ejecuta el script de verificación:

**Linux/macOS:**

```
bash scripts/comprobar_antes_de_subir.sh
```

**Windows:**

```
scripts\comprobar_antes_de_subir.bat
```

El script:

- Comprueba que `.env` no está rastreado.
- Detecta claves o certificados (`.key`, `.pem`, `.p12`).
- Avisa si hay caché de Python rastreada.
- Avisa si hay documentos no-Markdown en `ejemplos/`.
- Busca patrones sospechosos en los cambios pendientes.
- Lista ficheros grandes (>1 MB).

Si todo está bien, sale en verde. Si detecta algo, te dice qué hacer.

### Si descubres que has subido algo por error

Si después de hacer push descubres que se ha colado un `.env` o un
documento de pruebas:

1. **Borra inmediatamente el fichero** del repo: `git rm fichero && git commit -m "..." && git push`.
2. **Pero el fichero sigue en el historial.** Para borrarlo del
   historial completamente, usa
   [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) o
   [git filter-repo](https://github.com/newren/git-filter-repo). Es
   un proceso delicado; lee la documentación.
3. Si el fichero contenía secretos reales (claves, tokens),
   **rótalos**. Asume que todo lo que ha estado en GitHub público,
   aunque se borre, ha podido ser visto y archivado por terceros.

Lo más fácil es prevenir: ejecutar el verificador antes de cada `push`.
