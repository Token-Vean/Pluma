# Changelog

## 0.4.16-alpha

- Se separa el cierre de la interfaz del apagado del servidor local.
- El botón visible por defecto ahora es **Cerrar**, que solo cierra o indica cerrar la pestaña/ventana.
- El botón **Detener PlumA** queda oculto por defecto y solo aparece si el backend informa `apagado_ui_permitido=true`.
- Se eliminan del árbol fuente las notas e informes generados de release.
- Se corrige el workflow de GitHub Actions para ejecutarse desde la raíz real del repositorio.
- Se añade Dependabot para GitHub Actions y dependencias Python.
- Se refuerzan las comprobaciones estáticas para detectar artefactos generados, publicación no local y regresiones en la política de apagado.

## 0.4.15-alpha

- Instalador visual Windows consolidado.
- Modo local bloqueado.
- Botón de apagado desde la interfaz desactivado por defecto.
- Añadidas comprobaciones de seguridad estáticas y workflow inicial.

## 0.4.14-alpha

- Mejora de lectura visual previa para imágenes.
- Uso directo del modelo base multimodal para transcripción visual preliminar.
- Extracción archivística posterior con modelo especializado local.
