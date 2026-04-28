# Política de seguridad

Este documento describe cómo reportar vulnerabilidades de seguridad en
el **PlumA**, qué tipo de incidencias se consideran
vulnerabilidades, y qué compromisos adquiere el mantenedor al
recibirlas.

## Versiones cubiertas

Mientras el proyecto se encuentre en fase pre-1.0, solo la última
versión publicada recibe parches de seguridad.

| Versión    | Estado                      |
|------------|-----------------------------|
| 0.4.x      | Soporte activo (alpha)      |
| 0.3.x y anteriores | Sin soporte          |

## Cómo reportar una vulnerabilidad

**No abra un issue público de GitHub.** Los reportes públicos exponen
a los usuarios a ser atacados antes de que haya un parche disponible.

En su lugar:

1. Envíe un correo electrónico al mantenedor del proyecto con el
   asunto `[SEC] PlumA – <breve descripción>`.

2. Incluya, en la medida en que pueda:

   - Una descripción del problema.
   - Pasos para reproducir (en lo posible, con un documento mínimo
     que dispare el problema).
   - Impacto estimado: lectura de ficheros, ejecución de código,
     exfiltración de datos, denegación de servicio, etc.
   - Versión del PlumA y del sistema operativo en
     que se observó.
   - Cualquier propuesta de mitigación que se le ocurra.

3. Puede cifrar el correo con GPG si lo desea; la clave pública está
   disponible en los canales habituales del autor.

## Qué puede esperar

- Acuso de recibo del reporte en un plazo de **72 horas hábiles**.
- Una primera evaluación de gravedad y un plan de respuesta en un
  plazo de **7 días naturales**.
- Para vulnerabilidades confirmadas de gravedad alta, un parche en
  un plazo de **30 días** desde la confirmación.
- Para vulnerabilidades de gravedad media o baja, el parche irá en
  la siguiente release ordinaria del proyecto.
- Si el problema no es una vulnerabilidad de seguridad sino un fallo
  funcional, se redirige a los issues habituales de GitHub.

Estos plazos son compromisos de buena fe, no garantías contractuales.
El proyecto se mantiene sin dedicación a tiempo completo y podría
haber excepciones justificadas.

## Divulgación coordinada

Se prefiere un modelo de **divulgación coordinada**:

1. La vulnerabilidad se estudia y se prepara un parche en privado.
2. Se publica el parche.
3. Pasados entre 7 y 30 días desde la publicación (para dar tiempo a
   que los usuarios actualicen), se publica el detalle del problema
   en las notas de la release y, si procede, se solicita un CVE.

Si el problema ya es conocido públicamente en el momento del reporte,
o si la persona que reporta necesita hacerlo público por motivos
legítimos, no se exige este plazo.

## Crédito

Salvo petición expresa en contrario, las personas que reporten
vulnerabilidades de buena fe serán acreditadas en las notas de la
release en la que se publique el parche correspondiente.

## Superficie de ataque relevante

Para orientar a quien quiera auditar o hacer pruebas, estas son las
áreas del proyecto donde las vulnerabilidades tendrían más impacto:

### Router de entrada (`backend/app/router.py`)

Primera línea de defensa. Procesa ficheros subidos por el usuario.
Riesgos relevantes:

- Validación insuficiente de tipos y formatos.
- Bombas de descompresión (zip bomb) en DOCX.
- Ficheros malformados que exploten bugs en `pypdf`, `pypdfium2`,
  `python-docx` o `Pillow`.
- Path traversal al guardar temporales (actualmente se usa `tmpfs`
  en memoria, lo que mitiga el riesgo).

### Extractor (`backend/app/extractor.py`)

Construye y envía prompts al modelo de IA. Riesgos:

- Prompt injection desde el contenido del documento.
- Generación de JSON malformado que rompa el parseo.
- Extracción incorrecta de valores que lleguen a la salida EAD/EAC
  y, desde ahí, al sistema descriptivo de destino.

### API HTTP (`backend/app/api.py`)

Superficie expuesta al navegador. Riesgos:

- CSRF (mitigado por Origin/Referer + token local) y exposición accidental
  fuera de localhost (mitigada por comprobación de Host salvo opt-in explícito).
- Content-Type confusion en subidas.
- Exfiltración de logs si contuvieran contenido del documento (el
  logging deliberadamente NO registra contenido, solo metadatos).

### Exportadores (`backend/app/exportadores.py`)

Genera XML, JSON y CSV. Riesgos:

- Inyección XML si los valores del usuario no se escapan bien.
- CSV injection (fórmulas maliciosas que abre Excel).
- Escapado incorrecto de caracteres especiales.

### Cliente de Ollama (`backend/app/llm.py`, `backend/app/bootstrap.py`)

Comunicación con el motor de IA local. Riesgos:

- SSRF si se permitiera cambiar la URL de Ollama desde la UI
  (actualmente solo desde `.env`).
- Deserialización insegura de respuestas.

## Lo que NO se considera vulnerabilidad

Para evitar consumo inútil del canal de reporte:

- Alucinaciones del modelo de IA (propuestas incorrectas). Son una
  limitación conocida y documentada, no un fallo de seguridad. El
  flujo del producto exige revisión humana antes de exportar.

- Denegación de servicio mediante documentos muy grandes dentro de
  los límites documentados (50 MB). Los límites están pensados para
  equipos normales de archivero.

- Fallos en configuraciones no soportadas (ej. exponer el puerto
  publicado a Internet, correr sin los mitigantes de Docker por defecto).

- "Vulnerabilidades" derivadas de modificar los esquemas YAML para
  que pidan extracciones sin sentido: los esquemas son parte del
  perímetro de confianza.

## Auditoría de dependencias

El proyecto se compromete a ejecutar, al menos en cada release,
las siguientes comprobaciones:

- `pip-audit` sobre las dependencias Python.
- `trivy image` sobre la imagen Docker de la aplicación.
- Revisión manual de CVE conocidos de `pypdf`, `Pillow` y FastAPI.

Los informes de estas comprobaciones se archivan en las notas de
release.

## Contacto

Para cualquier asunto de seguridad, contactar con el mantenedor del
proyecto por la vía indicada al inicio. Para consultas sobre el uso
normal del proyecto, usar los issues públicos de GitHub.

## Nota específica sobre despliegue local

La protección CSRF incluida en la aplicación reduce ataques desde páginas web
externas contra `localhost`, pero **no es autenticación**. Si la aplicación se
expone en una interfaz de red distinta de `127.0.0.1`, cualquier cliente HTTP
podría interactuar con ella si obtiene conectividad al puerto. Los despliegues
en red no están soportados sin autenticación real, TLS y controles adicionales.

Desde esta versión, `OLLAMA_URL` también se valida al arrancar: por defecto solo
se permiten destinos locales (`localhost`, `127.0.0.1`, `::1`,
el servicio Docker interno `ollama`). Para usar un endpoint
remoto debe definirse `ALLOW_REMOTE_OLLAMA=true (solo desarrollo, sin efecto en la release pública con PLUMA_STRICT_LOCAL=true)`, lo que implica que texto e
imágenes de documentos pueden salir del equipo.

El procesamiento de PDF, DOCX e imágenes se ejecuta por defecto en un proceso
hijo con timeout y límite de memoria en sistemas POSIX. Esto reduce el impacto
de parsers bloqueados o documentos patológicos, pero no equivale a una garantía
absoluta frente a ficheros maliciosos.


## Modo local bloqueado de la release pública

La release pública de PlumA fuerza `PLUMA_STRICT_LOCAL=true`, publica la interfaz solo en `127.0.0.1` y usa exclusivamente el servicio Docker interno `ollama`. El perfil `external` no se distribuye en esta variante.
