# Documentos de ejemplo

Esta carpeta contiene documentos de prueba que se muestran en la
pantalla de bienvenida de la aplicación para que el archivero pueda
probar el asistente en 10 segundos, sin necesidad de buscar
documentación propia.

## Criterios para los ejemplos

Los documentos incluidos deben:

- Ser de **dominio público** (documentación antigua, publicaciones
  oficiales, material ya digitalizado por archivos con acceso abierto).
- Cubrir **distintos tipos documentales** del catálogo:
  oficio administrativo, acta de sesión, carta, libro sacramental,
  escritura notarial, plano o fotografía.
- Cubrir **distintas épocas** para que las propuestas se enfrenten a
  lenguaje moderno, decimonónico y de época moderna.
- Tener un **tamaño razonable** (menos de 5 MB por documento).
- Estar en **formatos variados**: al menos un PDF con OCR bueno, un
  PDF escaneado sin OCR, y una imagen suelta.

## Propuesta de conjunto inicial

Cuando la herramienta se empiece a testear con archiveros reales,
conviene incluir aquí al menos estos documentos:

1. **Oficio administrativo (s. XX)** — PDF con OCR limpio.
2. **Acta municipal (s. XIX o XX)** — PDF con OCR mediocre, para
   probar la ruta de visión.
3. **Carta manuscrita (s. XIX)** — imagen JPG.
4. **Libro sacramental (s. XVIII)** — PDF escaneado sin OCR,
   varias páginas.
5. **Escritura notarial (s. XIX)** — PDF o imagen.
6. **Plano o fotografía de archivo (s. XX)** — imagen.

Cada documento debe ir acompañado de un fichero de texto breve con la
descripción archivística "patrón oro" (la que haría un archivero
experto), para que el usuario pueda comparar las propuestas del
asistente con una referencia humana.

Estructura sugerida:

```
ejemplos/
├── 01-oficio-administrativo.pdf
├── 01-oficio-administrativo.md
├── 02-acta-municipal.pdf
├── 02-acta-municipal.md
└── ...
```

Los `.md` contienen la descripción ISAD(G) de referencia para cada
documento.
