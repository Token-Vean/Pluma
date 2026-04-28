# PlumA v0.4.1-alpha — hardening y ficha técnica de proceso

Esta versión consolida la rama `0.4.x` como alpha avanzada de PlumA. No cambia la orientación principal del proyecto: herramienta local-first de asistencia a la descripción archivística. La actualización se centra en robustez, trazabilidad mínima, coherencia de versión y reducción de riesgos de configuración accidental.

## Cambios principales

### 1. Coherencia de versión y denominación

- Se centraliza la versión en `backend/app/version.py`.
- La aplicación pasa a `0.4.1-alpha`.
- Se sustituyen cadenas históricas como `Asistente Archivístico v0.2` por `PlumA v0.4.1-alpha`.
- Se actualizan referencias de interfaz, API, exportadores y documentación.

### 2. Protección frente a exposición accidental en red

- Se añade el middleware `ProteccionAccesoLocal`.
- Por defecto solo se aceptan peticiones con `Host` local: `localhost`, `127.0.0.1`, `::1` o `[::1]`.
- Si se quiere exponer la aplicación fuera de loopback debe activarse explícitamente:

```env
ALLOW_NETWORK_EXPOSURE=true
```

Esta medida no sustituye una autenticación real. Su finalidad es evitar exposiciones accidentales de una herramienta pensada para uso local.

### 3. Auditoría ligera del proceso técnico

Se incorpora una ficha técnica generada en cada procesamiento. La ficha no incluye el texto del documento ni los valores descriptivos propuestos. Registra únicamente metadatos técnicos y de control:

- versión de PlumA;
- identificador de petición;
- fecha UTC de generación;
- nombre, tipo MIME, tamaño y hash SHA-256 del documento, si está activado;
- norma, modo, idioma y modelo utilizado;
- ruta de procesamiento;
- controles activos de seguridad;
- límites aplicados;
- recuentos de evidencia localizada, no localizada, no verificable, sin evidencia y sin valor.

La ficha se muestra en la interfaz y puede descargarse como JSON mediante el botón `Auditoría`.

### 4. Control de evidencia reforzado

Cada campo propuesto incorpora ahora `estado_evidencia`, con uno de estos valores:

- `localizada`: la evidencia aparece en el texto extraído;
- `no_localizada`: el modelo aportó evidencia, pero no se encontró en el texto extraído;
- `no_verificable`: la evidencia no puede verificarse, por ejemplo en ruta de visión sin capa textual;
- `sin_evidencia`: el campo tiene valor, pero no hay evidencia asociada;
- `sin_valor`: el campo no contiene valor propuesto.

Cuando el documento se procesa por visión y no existe texto extraído verificable, las confianzas altas se degradan a medias y se añade una advertencia específica.

### 5. Exportadores más resistentes

- Se eliminan caracteres de control incompatibles con XML/RDF/Turtle.
- Se refuerza la mitigación contra CSV formula injection, incluyendo casos con espacios iniciales o BOM.
- En RDF/Turtle se validan las propiedades abreviadas antes de emitirlas.
- JSON incorpora la ficha técnica de auditoría y el estado de evidencia de cada campo.

### 6. Modo personalizado más consistente

- La interfaz envía al backend la selección de campos cuando se reprocesa en modo personalizado.
- Los campos reciben metadatos de área (`area_id`, `area_nombre`), lo que mejora agrupación y presentación.
- Se actualiza la documentación de incidencias conocidas para reflejar el comportamiento actual.

### 7. Contenedores y configuración

- `docker-compose.yml` deja de usar `ollama/ollama:latest` por defecto y pasa a `ollama/ollama:0.21.2`.
- Se añaden variables de control:

```env
ALLOW_NETWORK_EXPOSURE=false
INCLUIR_HASH_DOCUMENTO_AUDITORIA=true
```

Para máxima reproducibilidad, sigue recomendándose fijar imágenes por digest SHA-256 tras validar una build concreta.

## Validación realizada

Se ha realizado validación estática de sintaxis:

```bash
find backend tests -name '*.py' -print0 | xargs -0 python -S -m py_compile
node --check frontend/static/app.js
```

No se ha ejecutado la batería completa de `pytest` ni una auditoría dinámica de dependencias en este entorno.

## Recomendación de uso

Esta versión es adecuada para demostración, formación, validación con corpus no sensibles y pruebas controladas. Para uso institucional con documentos reales o sensibles conviene completar antes:

1. ejecución completa de tests;
2. `pip-audit -r backend/requirements.txt`;
3. escaneo de imagen con Trivy;
4. validación con documentos problemáticos reales;
5. fijación de imágenes Docker por digest.
