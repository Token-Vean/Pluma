# Cumplimiento normativo y gobierno del dato

Este documento describe cómo el PlumA trata los
documentos que se le proporcionan, con el objetivo de facilitar la
evaluación por parte de responsables de protección de datos,
delegados de protección de datos (DPD), responsables de seguridad de
la información o cualquier otra figura encargada de validar el uso de
la herramienta en una institución.

El documento está redactado en dos niveles:

- **Garantías fuertes**: afirmaciones que pueden verificarse leyendo
  el código fuente. Deben cumplirse siempre.
- **Buenas prácticas recomendadas**: aspectos que dependen del
  despliegue y de la instalación, no solo del código. Pueden no
  cumplirse en entornos mal configurados.

Esta distinción es deliberada: otras herramientas suelen hacer
afirmaciones absolutas que en la práctica dependen del despliegue, y
eso induce a error.


## Resumen ejecutivo

1. Los documentos **no se envían a servidores externos** para su
   procesamiento. El motor de IA corre en el equipo del usuario.
2. No se almacenan los documentos ni las propuestas más allá del
   tiempo estrictamente necesario para procesarlos.
3. No se genera telemetría de la aplicación (ni métricas de uso, ni
   crash reporting, ni envío automático de información al autor).
4. El código fuente es abierto (AGPL-3.0) y auditable.


## Flujo del dato, paso a paso

### Durante el procesamiento

1. El archivero sube un fichero a través de la interfaz del
   navegador. La subida viaja por la conexión local
   (`127.0.0.1:8082`) hasta el backend.
2. El backend recibe el fichero, lo mantiene en memoria del proceso,
   y lo escribe temporalmente en `/tmp` dentro del contenedor
   Docker. `/tmp` está configurado como `tmpfs`, es decir, reside
   en memoria RAM y no toca disco físico.
3. La aplicación valida el fichero por magic bytes, tamaño, tipo y
   estructura interna (por ejemplo, rechaza DOCX con macros).
4. Si procede, extrae el texto (PDF, DOCX) o convierte a imagen
   (PDF escaneado, imágenes sueltas).
5. El texto o imágenes se envían al motor de IA local (Ollama) a
   través de la red interna de Docker o a través del socket local
   del anfitrión, dependiendo del perfil de instalación.
6. El motor devuelve una propuesta estructurada en JSON.
7. El backend devuelve la propuesta al navegador del archivero.

### Al terminar la sesión

1. La variable en memoria que contenía el fichero se sobrescribe al
   salir de la función de procesamiento.
2. El fichero en `/tmp` (si llegó a escribirse) es volátil al estar
   en `tmpfs`: se pierde al reiniciar el contenedor.
3. La propuesta solo vive en la pestaña del navegador del archivero.
   Al cerrar la pestaña, desaparece.
4. No hay base de datos de documentos, propuestas, usuarios ni
   sesiones.

### Limitación reconocida

Python no ofrece garantías fuertes sobre el borrado inmediato de
memoria. Cuando el código hace `contenido = b""`, la referencia
anterior queda disponible para el recolector de basura, pero los
bytes reales pueden permanecer en la memoria del proceso hasta que
el sistema operativo los reutilice. Esto es común a cualquier
aplicación Python y no es una deficiencia específica del proyecto,
pero conviene conocerlo: **el borrado activo es "best effort", no
una garantía de overwrite inmediato**.

Para casos de uso con exigencias extremas (documentos clasificados,
datos especialmente sensibles) se recomienda complementar con
políticas operativas: reiniciar el contenedor tras sesiones con
material sensible, o desplegar la herramienta en un entorno
virtualizado dedicado.


## Red y conectividad

### Garantías fuertes

- **La aplicación escucha únicamente en `127.0.0.1`.** El binding
  explícito en `docker-compose.yml` impide que se exponga a la red
  local sin intervención deliberada. Verificable en el propio fichero.

- **El motor de IA (Ollama en contenedor) no está expuesto al
  exterior.** En el perfil `bundled`, el servicio Ollama no publica
  puertos al anfitrión; solo se accede a él desde el contenedor de
  la aplicación a través de la red interna de Docker.

- **No hay llamadas a CDNs ni a servidores externos durante el uso.**
  El frontend (HTML, CSS y JavaScript) se sirve íntegramente desde el
  propio contenedor. La interfaz usa tipografías del sistema por defecto.
  La Content Security Policy en cabeceras HTTP no permite conexiones a
  dominios distintos del propio `self`.

- **No hay telemetría**. No se registra el uso en ningún servicio
  externo. No se envían informes de errores automáticos. No hay
  pings de "equipo activo". Verificable por búsqueda simple en el
  código: no existen llamadas a dominios externos salvo las
  documentadas a continuación.

### Conexiones externas documentadas

Hay dos casos, y solo dos, en los que la herramienta contacta con
servidores externos. Ambas son opcionales en función del perfil de
instalación:

1. **Descarga inicial del modelo de IA** (solo perfil `bundled`).
   La primera vez que se arranca la aplicación sin tener Ollama
   instalado, el contenedor de Ollama descarga el modelo de IA
   desde los servidores oficiales de Ollama (Cloudflare + GitHub
   Releases). Esta operación se hace una sola vez y está documentada
   en los logs del anfitrión. Después de esa descarga, el sistema
   no vuelve a conectarse a esos servidores salvo que se cambie de
   modelo.

2. **Descarga opcional de tipografías**. La carpeta `/static/fonts/`
   incluye scripts para descargar fuentes desde repositorios oficiales
   de GitHub, pero ya no se ejecutan automáticamente en la instalación.
   Solo hay conexión externa si el administrador decide ejecutarlos.

En el perfil `external` (Ollama ya instalado por el usuario), **la
aplicación no hace ninguna conexión externa durante el arranque ni
durante el uso ordinario**.


## Logs y auditabilidad

### Qué se registra

Los logs se emiten por salida estándar del contenedor. Contienen
exclusivamente:

- Fecha y hora.
- Identificador aleatorio de sesión (ID corto de 8 caracteres).
- Evento: `describir_inicio`, `documento_procesado`,
  `tipo_detectado`, `describir_fin`, `describir_validacion_fallida`.
- Metadatos del fichero: tipo MIME, tamaño en bytes, número de
  páginas (para PDF).
- Ruta de procesamiento elegida (`texto`, `vision`, `hibrida`).
- Número de campos generados.
- Número de advertencias.
- Mensajes de error técnicos (sin datos del documento).

Ejemplo real:

```
[a3f71c8b] describir_inicio norma=isad-g tamano=84312 modo=esencial
[a3f71c8b] documento_procesado mime=application/pdf ruta=hibrida paginas=1
[a3f71c8b] tipo_detectado tipo=oficio confianza=alta
[a3f71c8b] describir_fin campos=17 advertencias=0
```

### Qué NO se registra

Los logs no contienen, deliberadamente:

- Texto extraído de los documentos.
- Valores propuestos por la IA para los campos.
- Evidencias citadas del documento.
- Nombres de ficheros originales (se registra solo su hash si es
  necesario, nunca el contenido).
- Datos personales identificados en los documentos.

Esto es verificable buscando en el código la función
`_log_peticion` de `api.py`: acepta solo argumentos con nombre, y
documenta explícitamente que no debe pasarse texto ni valores.

### Consecuencia práctica

Los logs **no constituyen una copia secundaria de los documentos
procesados**. Son útiles para diagnóstico técnico (cuántos fallos,
qué tipos de fichero, qué rutas se usaron) pero **no permiten
reconstruir qué se procesó**. Esto es importante para la
proporcionalidad (RGPD art. 5.1.c).


## Seguridad técnica del despliegue

### Garantías fuertes (verificables en el código)

- El contenedor de la aplicación corre como **usuario no
  privilegiado `uid 10001`** (ver `backend/Dockerfile`).
- El contenedor tiene `no-new-privileges` activado (ver
  `docker-compose.yml`).
- El sistema de ficheros del contenedor es de **solo lectura**,
  excepto `/tmp` que es `tmpfs` limitado a 512 MB.
- La aplicación aplica cabeceras HTTP de seguridad estrictas:
  - `Content-Security-Policy` que solo permite recursos del propio
    origen (`self`).
  - `X-Frame-Options: DENY`.
  - `X-Content-Type-Options: nosniff`.
  - `Referrer-Policy: no-referrer`.
  - `Permissions-Policy` restrictiva (sin cámara, sin micrófono,
    sin geolocalización).
- Los ficheros subidos se validan por firma (magic bytes), no solo
  por extensión (ver `router.py`, función `_detectar_mime_real`).
- DOCX con macros (`vbaProject`) se rechazan con error explícito.
- Hay límites duros de tamaño (50 MB de fichero; corte temprano del cuerpo HTTP), páginas PDF (200), píxeles y
  dimensiones de imagen (6.000 px).
- **Protección CSRF activa** en todos los endpoints mutadores. Dos
  capas: (a) comprobación de cabecera Origin/Referer contra los
  orígenes permitidos `http://localhost:<puerto>` y
  `http://127.0.0.1:<puerto>`; (b) token sincronizado (synchronizer
  token pattern) que el frontend pide al arrancar y envía en cada
  POST/PUT/PATCH/DELETE. Ver `backend/app/csrf.py`. Una web de
  terceros visitada por el archivero no puede hacer peticiones
  mutadoras contra la aplicación aunque la tenga abierta en otra
  pestaña.

### Limitaciones conocidas del despliegue actual

En el estado actual del proyecto (versión 0.2, alpha), estas
limitaciones se reconocen y se abordarán en versiones futuras:

- **El contenedor de Ollama en perfil `bundled` corre como root**
  por la configuración por defecto de la imagen oficial
  `ollama/ollama:latest`. Esto es visible por cualquiera que
  inspeccione el contenedor; aunque no compromete los datos del
  anfitrión (Docker aísla el espacio de nombres), sí es un aspecto
  a mejorar. No aplica al perfil `external`, donde no gestionamos
  el proceso de Ollama.

- **El límite de tamaño se comprueba antes y después del parseo**:
  `api.LimiteCuerpoPeticion` corta por `Content-Length` antes de que
  FastAPI procese multipart/JSON, y `router.py` vuelve a validar el
  tamaño real del fichero documental.

- **Los mitigantes contra ficheros-bomba son conservadores**: límites
  de tamaño, páginas, píxeles, bytes renderizados y validación DOCX
  contra ratios de compresión anómalos. Sigue pendiente aislar parsers
  PDF/DOCX en procesos separados con timeout y límite de memoria por tarea.

- **La aplicación se entrega sin fijación de hashes criptográficos
  de las dependencias** (aunque sí con versiones exactas en
  `requirements.txt`). Esto depende del pipeline de CI, pendiente
  de configurar.


## Datos personales

El asistente puede procesar documentos que contengan datos
personales, incluyendo datos especialmente protegidos (salud,
religión, ideología, origen racial o étnico, datos judiciales, datos
de menores).

### Lo que hace la herramienta

- **No almacena** esos datos más allá del tiempo necesario para
  procesarlos (limitación reconocida arriba sobre la volatilidad
  real de la memoria Python).
- **No transmite** esos datos fuera del equipo del archivero. El
  motor de IA es local.
- **Muestra advertencias** cuando el contenido contiene marcas de
  clasificación de seguridad (`Secreto`, `Reservado`, `Confidencial`)
  o indicadores de datos sensibles, para que el archivero lo
  revise antes de cualquier difusión.

### Lo que no hace

- **No anonimiza automáticamente** los documentos. Los valores que
  propone para la descripción pueden incluir nombres de personas y
  otros datos personales extraídos del documento. La anonimización,
  si procede, es responsabilidad del archivero antes de publicar
  la descripción.
- **No cifra los documentos en tránsito interno**. La conexión
  navegador ↔ backend va por `127.0.0.1` en claro (HTTP, no HTTPS).
  En un equipo local esto no es un problema práctico, pero en
  despliegues que expongan la herramienta a una red local con
  varios usuarios, se recomienda añadir un proxy TLS por delante.


## Relación con el tratamiento

La institución que utiliza el PlumA actúa como
**responsable del tratamiento** de los documentos que se procesan.
No hay encargado del tratamiento externo, porque no hay terceros
implicados en el procesamiento.

El autor del software proporciona la herramienta pero **no tiene
acceso** a los datos que se procesen con ella. No es necesario
firmar un contrato de encargado del tratamiento con el autor para
usar la versión libre.

(Esto podría cambiar en futuras versiones con modalidades de soporte
técnico o despliegue gestionado. Cuando así sea, se formalizará la
relación correspondiente.)


## Adecuación al Esquema Nacional de Seguridad

El código está diseñado con principios compatibles con el ENS
(Real Decreto 311/2022), pero **no ha superado una adecuación
formal**. Una adecuación al nivel BÁSICO del ENS está en el roadmap
del proyecto como documento separado y requiere, además, acciones
por parte de la institución desplegadora.


## Verificación independiente

El código fuente está disponible bajo licencia AGPL-3.0. Cualquier
responsable de seguridad puede inspeccionar:

- `docker-compose.yml` — configuración de red y endurecimiento.
- `backend/Dockerfile` — usuario no privilegiado, dependencias.
- `backend/requirements.txt` — versiones exactas de dependencias.
- `backend/app/router.py` — validación de entrada.
- `backend/app/api.py` — cabeceras HTTP y logging sin contenido.
- `frontend/static/styles.css` — ausencia de dependencias externas.
- Este documento `CUMPLIMIENTO.md` contrastado con el código.


## Contacto

Para preguntas de cumplimiento normativo o para solicitar
evaluaciones específicas previas a un despliegue institucional,
contactar con el autor del proyecto. Para vulnerabilidades de
seguridad, ver `SECURITY.md`.


## Cambios de endurecimiento incorporados

- `api.LimiteCuerpoPeticion`: rechaza `/api/describir` y `/api/exportar/*`
  por `Content-Length` antes de que FastAPI parse el cuerpo.
- `router.py`: ya no acepta tipos por extensión; exige firma/contenido.
- `router.py`: validación DOCX previa contra ZIP-bomb, macros, rutas internas
  anómalas, tamaño descomprimido y multimedia embebida.
- `router.py`: límites de píxeles y bytes para imágenes y PDF renderizado.
- `extractor.py`: validación defensiva del JSON del modelo y degradación de
  confianza cuando la evidencia textual no se localiza literalmente.
- `exportadores.py`: mitigación de CSV injection ante fórmulas.
- `csrf.py`: tokens con TTL y almacén máximo acotado.

## Matización operativa de privacidad y seguridad

Las garantías de no persistencia en disco se refieren al despliegue Docker
recomendado, donde `/tmp` se monta como `tmpfs` y el sistema de ficheros del
contenedor de aplicación es de solo lectura. Si se ejecuta FastAPI fuera de
Docker, el comportamiento temporal depende del sistema operativo, del servidor
ASGI y de la configuración de `UploadFile`.

La herramienta no promete borrado seguro de memoria. Durante el procesamiento
pueden existir copias transitorias en memoria de Python, en el navegador y en el
proceso de Ollama. Lo que se garantiza en el diseño es no persistir
deliberadamente documentos o propuestas en una base de datos o carpeta de
trabajo de la aplicación.

Las advertencias sobre clasificación, restricciones o datos sensibles son
ayudas generadas por el modelo y por el esquema archivístico; no constituyen un
detector determinista de secretos ni sustituyen la revisión profesional.


## Apagado desde la interfaz

La interfaz incorpora un botón de apagado local. Este botón detiene el proceso del servidor de la aplicación mediante un endpoint protegido por CSRF y comprobación de origen local. Por seguridad, la aplicación no tiene acceso al socket Docker del anfitrión y no ejecuta `docker compose down`; en el perfil bundled, el contenedor de Ollama puede seguir activo hasta usar los scripts de detención o Docker Compose.
