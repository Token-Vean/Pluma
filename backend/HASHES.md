# Endurecimiento opcional: hashes de dependencias

Las dependencias en `requirements.txt` están **fijadas por versión exacta**.
Esto garantiza reproducibilidad de la imagen Docker (la misma versión hoy
y dentro de seis meses) y es lo que se documenta en `CUMPLIMIENTO.md`.

Para subir un escalón más en cadena de suministro, conviene fijar también
los **hashes SHA-256** de cada wheel/sdist y forzar a `pip` a verificarlos
antes de instalar. Esto protege contra un escenario teórico en el que el
repositorio PyPI o un mirror se vea comprometido y sirva paquetes
maliciosos con las mismas versiones que las legítimas.

## Cómo generar el fichero con hashes

Sobre una máquina con red:

```
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip pip-tools
pip-compile --generate-hashes --output-file requirements.txt requirements.in
```

`pip-compile` consulta PyPI, resuelve la transitiva, calcula los hashes
SHA-256 y produce un `requirements.txt` con líneas del tipo:

```
fastapi==0.136.0 \
    --hash=sha256:abc123... \
    --hash=sha256:def456...
```

Una entrada por hash porque cada wheel arquitectura-específico tiene su
propio hash.

## Cómo aplicar la verificación

El `Dockerfile` actual ejecuta:

```
RUN pip install --prefix=/install -r requirements.txt
```

Para forzar verificación de hashes, sustituir por:

```
RUN pip install --prefix=/install --require-hashes -r requirements.txt
```

Con `--require-hashes`, `pip` se niega a instalar cualquier paquete que
no tenga su hash documentado en `requirements.txt` o cuyo hash real no
coincida con el documentado.

## Cuándo aplicarlo

Recomendado para **cualquier release pública firmada** (v0.6.0-beta y
sucesivas). El comando no se ha aplicado aún en este repo porque
requiere acceso a red en el momento de generar el fichero (este paso es
manual y no automatizable desde el propio paquete que se distribuye).

## Coste operativo

Cada vez que se sube una versión de cualquier dependencia hay que
regenerar el fichero con `pip-compile --generate-hashes`. Es trivial
pero hay que recordarlo en el procedimiento de release. Anotarlo en
`scripts/pre_release_check.sh` evita olvidos.
