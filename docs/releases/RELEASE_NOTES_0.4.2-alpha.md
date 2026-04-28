# PlumA v0.4.14-alpha — release de instalación sencilla multiplataforma

## Tipo de release

Alpha pública para instalación local con Docker. Preparada para Windows, Linux y macOS dentro de un único paquete de release.

## Cambios principales respecto a v0.4.1-alpha

- Paquete reorganizado para usuarios no técnicos: los scripts de instalación, parada y desinstalación quedan claramente identificados en la raíz del paquete.
- Compatibilidad de instalación en una misma release: scripts `.bat` para Windows y `.sh` para Linux/macOS.
- Corrección funcional del botón de copia en modo flotante: la copia usa el `document` y el `window` propietarios del botón para conservar la activación de usuario en Document Picture-in-Picture y añade fallback con `execCommand('copy')`.
- Se mantiene la ejecución local mediante Docker y los dos perfiles de despliegue: `bundled` (Ollama en Docker) y `external` (Ollama ya instalado en el equipo).
- Se conserva el endurecimiento incorporado en v0.4.1-alpha: sandbox de parsers, límites de tamaño, CSRF, restricción local de red, contenedor de aplicación no privilegiado, lectura de volúmenes en modo solo lectura y exportación CSV saneada.
- Versión interna actualizada a `0.4.14-alpha` en backend, frontend y documentación activa.

## Archivos de instalación visibles en la raíz del paquete

- `01_INSTALAR_WINDOWS.bat`
- `02_DETENER_WINDOWS.bat`
- `03_DESINSTALAR_WINDOWS.bat`
- `01_INSTALAR_LINUX_MAC.sh`
- `02_DETENER_LINUX_MAC.sh`
- `03_DESINSTALAR_LINUX_MAC.sh`

## Requisito

Docker debe estar instalado y arrancado. En equipos sin Ollama local, el perfil `bundled` descargará el modelo configurado la primera vez. En equipos con Ollama activo en `localhost:11434`, el perfil `external` reutilizará esa instalación.

## Advertencia de estado

PlumA sigue siendo una herramienta alpha de apoyo profesional y formativo. Las propuestas descriptivas deben revisarse siempre por personal competente. No debe exponerse en red ni usarse como servicio de producción sin controles adicionales.
