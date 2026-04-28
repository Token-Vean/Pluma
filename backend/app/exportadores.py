"""
Exportadores de PlumA.

Cada exportador toma una propuesta editada (el JSON que la UI envía al
backend después de que el archivero haya revisado y corregido) y devuelve:

    (contenido_bytes, tipo_mime, nombre_sugerido)

listo para devolver como descarga al navegador.

Formatos soportados:

    json     → JSON limpio, legible, sin campos internos (span, extraible).
    csv      → Una fila por campo, codificación UTF-8 con BOM para Excel.
    ead      → EAD3 (Encoded Archival Description, v3) para ISAD(G).
    eac-cpf  → EAC-CPF (Encoded Archival Context) para ISAAR(CPF).

Para ISDF e ISDIAH no hay un estándar XML tan asentado; de momento se
exportan como JSON o CSV.

Nota técnica sobre XML: Python 3.12 tiene un comportamiento curioso
con ElementTree y ciertos tags (notablemente "name") que se reescriben
como "<n>" si no están namespaceados. Para evitarlo, construimos los
elementos con namespace explícito y usamos register_namespace para que
salgan sin prefijo en la serialización final.
"""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring

import yaml

from .version import APP_AGENT


# =============================================================================
# Tipos y utilidades
# =============================================================================

def _slug(texto: str, max_len: int = 60) -> str:
    """Normaliza un texto a un nombre de fichero seguro."""
    if not texto:
        return "sin-titulo"
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^\w\s-]", "", t).strip().lower()
    t = re.sub(r"[\s_]+", "-", t)
    return (t[:max_len] or "sin-titulo").rstrip("-")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _limpiar_texto_exportacion(texto: Any) -> str:
    """Elimina controles incompatibles con XML/RDF sin tocar saltos/tabuladores."""
    s = "" if texto is None else str(texto)
    return "".join(
        ch for ch in s
        if not ((ord(ch) < 32 and ch not in "\n\r\t") or ord(ch) == 127)
    )


def _limpiar_valor_exportacion(valor: Any) -> Any:
    if isinstance(valor, list):
        return [_limpiar_texto_exportacion(v) for v in valor]
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return _limpiar_texto_exportacion(valor) if valor is not None else None
    return None


def _obtener_valor(campos: list[dict], clave: str) -> Any:
    """Busca el valor de un campo por su clave en la lista de propuestos.

    Reconoce alias entre normas equivalentes (DACS <-> ISAD) para que el
    exportador EAD funcione tanto con ISAD-G como con DACS sin duplicar
    la lógica de mapeo a EAD3.
    """
    # Mapeo de alias: si buscamos una clave ISAD y no la encontramos,
    # probamos la equivalente DACS (y viceversa).
    alias = {
        "titulo": ["title"],
        "title": ["titulo"],
        "codigo_referencia": ["reference_code"],
        "reference_code": ["codigo_referencia"],
        "fechas": ["date"],
        "date": ["fechas"],
        "volumen_soporte": ["extent"],
        "extent": ["volumen_soporte"],
        "nombre_productor": ["name_of_creator"],
        "name_of_creator": ["nombre_productor"],
        "alcance_contenido": ["scope_and_content"],
        "scope_and_content": ["alcance_contenido"],
        "lengua_escritura": ["languages"],
        "languages": ["lengua_escritura"],
        "historia_institucional": ["administrative_biographical_history"],
        "administrative_biographical_history": ["historia_institucional"],
        "condiciones_acceso": ["conditions_governing_access"],
        "conditions_governing_access": ["condiciones_acceso"],
        "condiciones_reproduccion": ["conditions_governing_reproduction"],
        "conditions_governing_reproduction": ["condiciones_reproduccion"],
        "notas": ["general_note"],
        "general_note": ["notas"],
    }

    # Búsqueda directa
    for c in campos:
        if c.get("clave") == clave:
            return _limpiar_valor_exportacion(c.get("valor"))

    # Búsqueda por alias
    for alt in alias.get(clave, []):
        for c in campos:
            if c.get("clave") == alt:
                return _limpiar_valor_exportacion(c.get("valor"))

    return None



def _sanear_csv(valor: Any) -> str:
    """
    Mitiga CSV/Formula Injection en hojas de cálculo. Si una celda empieza
    —también tras espacios o BOM inicial— por caracteres interpretables como
    fórmula por Excel/LibreOffice, se antepone un apóstrofo.
    """
    texto = _limpiar_texto_exportacion(valor)
    normalizado_inicio = texto.lstrip(" \ufeff\t\r\n")
    if normalizado_inicio.startswith(("=", "+", "-", "@")) or texto.startswith(("\t", "\r", "\n")):
        return "'" + texto
    return texto


def _valor_como_lista(valor: Any) -> list[str]:
    """Normaliza un valor a lista de strings (para campos multiple)."""
    if valor is None or valor == "":
        return []
    if isinstance(valor, list):
        return [_limpiar_texto_exportacion(v) for v in valor if v not in (None, "")]
    return [_limpiar_texto_exportacion(valor)]


def _pretty_xml(elemento: Element) -> bytes:
    """Serializa un Element a XML indentado."""
    crudo = tostring(elemento, encoding="utf-8")
    parseado = minidom.parseString(crudo)
    pretty = parseado.toprettyxml(indent="  ", encoding="utf-8")
    # Eliminar la línea vacía que minidom añade entre declaración y raíz
    return b"\n".join(linea for linea in pretty.split(b"\n") if linea.strip())


# =============================================================================
# Carga de mapeos desde el esquema
# =============================================================================

_cache_mapeos: dict[Path, dict] = {}


# Registrar namespaces como vacíos (default) para que la serialización
# no ponga prefijos tipo ns0:. Esto se hace al importar el módulo.
register_namespace("", "http://ead3.archivists.org/schema/")
register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")


def _cargar_mapeo(ruta_esquema: Path) -> dict:
    """
    Devuelve un dict {clave_interna: info} con el mapeo a EAD/EAC del
    esquema YAML. Cacheado.
    """
    if ruta_esquema in _cache_mapeos:
        return _cache_mapeos[ruta_esquema]

    with ruta_esquema.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    mapeo = {}
    for area in data["areas"]:
        for el in area["elementos"]:
            mapeo[el["clave"]] = {
                "id": el["id"],
                "nombre": el["nombre"],
                "tipo": el["tipo"],
                "multiple": el.get("multiple", False),
                "ead": el.get("ead"),
                "eac": el.get("eac"),
            }

    _cache_mapeos[ruta_esquema] = mapeo
    return mapeo


# =============================================================================
# JSON
# =============================================================================

def exportar_json(propuesta: dict, norma: str) -> tuple[bytes, str, str]:
    """
    JSON limpio: incluye los campos editados pero no los metadatos
    internos (span, evidencia bruta, extraible). Pensado para que un
    humano lo lea cómodamente o lo procese con cualquier script.
    """
    campos_limpios = []
    for c in propuesta["propuesta"]["campos"]:
        if c.get("valor") in (None, "", []):
            continue
        campos_limpios.append({
            "id": c.get("id"),
            "clave": c.get("clave"),
            "nombre": c.get("nombre"),
            "valor": _limpiar_valor_exportacion(c.get("valor")),
            "confianza": _limpiar_texto_exportacion(c.get("confianza")),
            "evidencia": _limpiar_texto_exportacion(c.get("evidencia")),
            "estado_evidencia": _limpiar_texto_exportacion(c.get("estado_evidencia")),
        })

    salida = {
        "norma": propuesta["propuesta"].get("norma", norma),
        "generado": datetime.now().isoformat(timespec="seconds"),
        "documento": propuesta.get("documento"),
        "tipo_detectado": propuesta.get("tipo_detectado"),
        "campos": campos_limpios,
        "advertencias": [_limpiar_texto_exportacion(a) for a in propuesta["propuesta"].get("advertencias", [])],
        "auditoria": propuesta.get("auditoria"),
    }

    contenido = json.dumps(salida, ensure_ascii=False, indent=2).encode("utf-8")
    titulo = _obtener_valor(propuesta["propuesta"]["campos"], "titulo") \
             or _obtener_valor(propuesta["propuesta"]["campos"], "forma_autorizada") \
             or "descripcion"
    nombre = f"{_slug(titulo)}-{_timestamp()}.json"

    return contenido, "application/json", nombre


# =============================================================================
# CSV
# =============================================================================

def exportar_csv(propuesta: dict, norma: str) -> tuple[bytes, str, str]:
    """
    CSV con una fila por campo. Codificación UTF-8 con BOM para que
    Excel lo abra directamente con las tildes bien.
    """
    buffer = io.StringIO()
    # BOM para Excel
    buffer.write("\ufeff")

    writer = csv.writer(buffer, delimiter=",", quoting=csv.QUOTE_ALL)
    writer.writerow(["codigo", "clave", "nombre", "valor", "confianza", "evidencia"])

    for c in propuesta["propuesta"]["campos"]:
        valor = c.get("valor")
        if valor in (None, "", []):
            continue
        if isinstance(valor, list):
            valor = " · ".join(str(v) for v in valor)
        writer.writerow([
            _sanear_csv(c.get("id", "")),
            _sanear_csv(c.get("clave", "")),
            _sanear_csv(c.get("nombre", "")),
            _sanear_csv(valor),
            _sanear_csv(c.get("confianza") or ""),
            _sanear_csv(c.get("evidencia") or ""),
        ])

    contenido = buffer.getvalue().encode("utf-8")
    titulo = _obtener_valor(propuesta["propuesta"]["campos"], "titulo") \
             or _obtener_valor(propuesta["propuesta"]["campos"], "forma_autorizada") \
             or "descripcion"
    nombre = f"{_slug(titulo)}-{_timestamp()}.csv"

    return contenido, "text/csv; charset=utf-8", nombre


# =============================================================================
# EAD3 (para ISAD(G))
# =============================================================================

EAD3_NS = "http://ead3.archivists.org/schema/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def exportar_ead(propuesta: dict, ruta_esquema: Path) -> tuple[bytes, str, str]:
    """
    Genera un fichero EAD3 válido para la descripción archivística.
    Solo aplica a ISAD(G). Usa el mapeo `ead` declarado en el esquema YAML.

    El resultado es un documento EAD3 mínimo pero bien formado, importable
    en AtoM (vía "Import XML → EAD 2002 / 3") y en ArchivesSpace.
    """
    campos = propuesta["propuesta"]["campos"]
    _cargar_mapeo(ruta_esquema)

    # Raíz EAD
    ead = Element("ead", {
        "xmlns": EAD3_NS,
        "xmlns:xsi": XSI_NS,
        "audience": "external",
    })

    # control: metadatos del registro (no de la unidad)
    control = SubElement(ead, "control")
    recordid = SubElement(control, "recordid")
    recordid.text = (
        _obtener_valor(campos, "codigo_referencia")
        or f"asistente-{_timestamp()}"
    )

    filedesc = SubElement(control, "filedesc")
    titlestmt = SubElement(filedesc, "titlestmt")
    titleproper = SubElement(titlestmt, "titleproper")
    titleproper.text = _obtener_valor(campos, "titulo") or "Descripción archivística"

    # maintenancestatus / maintenanceagency (obligatorios en EAD3)
    SubElement(control, "maintenancestatus", {"value": "new"})
    magency = SubElement(control, "maintenanceagency")
    SubElement(magency, "agencyname").text = "PlumA (borrador)"

    # languagedeclaration
    langs = _valor_como_lista(_obtener_valor(campos, "lengua_escritura"))
    if langs:
        langdecl = SubElement(control, "languagedeclaration")
        SubElement(langdecl, "language", {"langcode": langs[0]}).text = langs[0]
        SubElement(langdecl, "script", {"scriptcode": "Latn"}).text = "Latino"

    # maintenancehistory
    mhistory = SubElement(control, "maintenancehistory")
    mevent = SubElement(mhistory, "maintenanceevent")
    SubElement(mevent, "eventtype", {"value": "created"})
    SubElement(mevent, "eventdatetime").text = datetime.now().isoformat(timespec="seconds")
    SubElement(mevent, "agenttype", {"value": "machine"})
    SubElement(mevent, "agent").text = APP_AGENT

    # archdesc: la descripción propiamente dicha
    nivel = _obtener_valor(campos, "nivel_descripcion") or "item"
    nivel_ead = _mapear_nivel_a_ead(nivel)
    archdesc = SubElement(ead, "archdesc", {"level": nivel_ead})

    did = SubElement(archdesc, "did")

    # Código de referencia
    cod = _obtener_valor(campos, "codigo_referencia")
    if cod:
        for valor in _valor_como_lista(cod):
            SubElement(did, "unitid").text = valor

    # Título
    titulo = _obtener_valor(campos, "titulo")
    if titulo:
        SubElement(did, "unittitle").text = titulo

    # Fechas
    for fecha in _valor_como_lista(_obtener_valor(campos, "fechas")):
        normal = _normalizar_fecha_ead(fecha)
        attrs = {"normal": normal} if normal else {}
        SubElement(did, "unitdate", attrs).text = fecha

    # Volumen / soporte
    vol = _obtener_valor(campos, "volumen_soporte")
    if vol:
        physdesc = SubElement(did, "physdesc")
        for v in _valor_como_lista(vol):
            SubElement(physdesc, "extent").text = v

    # Productor
    # Usamos <persname> para nombres que parezcan personas, <corpname>
    # para instituciones. Esta heurística es grosera pero preferible al
    # tag genérico <name>, que además dispara un bug de serialización en
    # Python 3.12 (lo reescribe como <n>).
    prod = _obtener_valor(campos, "nombre_productor")
    if prod:
        for p in _valor_como_lista(prod):
            origination = SubElement(did, "origination")
            tag = "persname" if _parece_persona(p) else "corpname"
            SubElement(origination, tag).text = p

    # Lengua
    if langs:
        langmat = SubElement(did, "langmaterial")
        for lang in langs:
            SubElement(langmat, "language", {"langcode": lang}).text = lang

    # Campos que van fuera del <did>
    _anadir_elemento_si_hay(archdesc, campos, "historia_institucional", "bioghist", "p")
    _anadir_elemento_si_hay(archdesc, campos, "historia_archivistica", "custodhist", "p")
    _anadir_elemento_si_hay(archdesc, campos, "forma_ingreso", "acqinfo", "p")
    _anadir_elemento_si_hay(archdesc, campos, "alcance_contenido", "scopecontent", "p")
    _anadir_elemento_si_hay(archdesc, campos, "valoracion_seleccion", "appraisal", "p")
    _anadir_elemento_si_hay(archdesc, campos, "nuevos_ingresos", "accruals", "p")
    _anadir_elemento_si_hay(archdesc, campos, "organizacion", "arrangement", "p")
    _anadir_elemento_si_hay(archdesc, campos, "condiciones_acceso", "accessrestrict", "p")
    _anadir_elemento_si_hay(archdesc, campos, "condiciones_reproduccion", "userestrict", "p")
    _anadir_elemento_si_hay(archdesc, campos, "caracteristicas_fisicas", "phystech", "p")
    _anadir_elemento_si_hay(archdesc, campos, "instrumentos_descripcion", "otherfindaid", "p")
    _anadir_elemento_si_hay(archdesc, campos, "existencia_originales", "originalsloc", "p")
    _anadir_elemento_si_hay(archdesc, campos, "existencia_copias", "altformavail", "p")
    _anadir_elemento_si_hay(archdesc, campos, "unidades_relacionadas", "relatedmaterial", "p")
    _anadir_elemento_si_hay(archdesc, campos, "nota_publicaciones", "bibliography", "p")
    _anadir_elemento_si_hay(archdesc, campos, "notas", "odd", "p")
    _anadir_elemento_si_hay(archdesc, campos, "nota_archivero", "processinfo", "p")

    contenido = _pretty_xml(ead)
    titulo_salida = _obtener_valor(campos, "titulo") or "descripcion"
    nombre = f"{_slug(titulo_salida)}-{_timestamp()}.ead.xml"

    return contenido, "application/xml", nombre


def _mapear_nivel_a_ead(nivel: str) -> str:
    """Traduce los niveles del esquema (en español, con guiones bajos) a
    los valores del atributo level de EAD."""
    mapa = {
        "fondo": "fonds",
        "subfondo": "subfonds",
        "serie": "series",
        "subserie": "subseries",
        "unidad_documental_compuesta": "file",
        "unidad_documental_simple": "item",
    }
    return mapa.get(nivel, "item")


def _parece_persona(nombre: str) -> bool:
    """
    Heurística sencilla para decidir si un productor es persona física
    o entidad colectiva. Conservadora: ante la duda, devuelve False
    (corpname), que es el caso más habitual en fondos institucionales.

    Un nombre se considera persona si:
      - Tiene 2-5 palabras Y ninguna es una palabra típica de institución
      - No contiene cifras, paréntesis, siglas de más de 3 letras en
        mayúsculas, ni comas (que suelen indicar denominaciones legales)
    """
    if not nombre:
        return False
    palabras = nombre.strip().split()
    if len(palabras) < 2 or len(palabras) > 5:
        return False

    # Señales fuertes de institución
    marcadores_institucion = {
        "ministerio", "ayuntamiento", "dirección", "secretaría",
        "subsecretaría", "consejería", "delegación", "diputación",
        "gobierno", "universidad", "escuela", "instituto", "real",
        "iglesia", "parroquia", "obispado", "diócesis", "archidiócesis",
        "hermandad", "cofradía", "congregación", "orden", "fundación",
        "asociación", "sociedad", "empresa", "compañía", "cooperativa",
        "sindicato", "partido", "archivo", "biblioteca", "museo",
        "consejo", "comisión", "junta", "tribunal", "juzgado", "notaría",
        "federación", "confederación", "patronato",
    }
    minusculas = nombre.lower()
    if any(m in minusculas for m in marcadores_institucion):
        return False

    # Contiene paréntesis o comas: denominación legal compleja
    if "," in nombre or "(" in nombre or "S.A." in nombre or "S.L." in nombre:
        return False

    # Siglas largas
    if re.search(r"\b[A-Z]{4,}\b", nombre):
        return False

    # Si todas las palabras empiezan por mayúscula, es antropónimo probable
    if all(p[0].isupper() for p in palabras if p):
        return True

    return False


def _normalizar_fecha_ead(fecha: str) -> str:
    """
    Intenta producir una representación normalizada ISO 8601 para el
    atributo @normal. Si no se puede, devuelve cadena vacía.

    Acepta: "1985-06-14", "1985-06-14/1987-12-31", "1985".
    """
    if not fecha:
        return ""
    fecha = fecha.strip()
    # Ya ISO
    if re.match(r"^\d{4}(-\d{2}(-\d{2})?)?(/\d{4}(-\d{2}(-\d{2})?)?)?$", fecha):
        return fecha.replace("/", "/")
    return ""


def _anadir_elemento_si_hay(
    padre: Element,
    campos: list[dict],
    clave: str,
    tag: str,
    envolver: str | None = None,
) -> None:
    """Añade un elemento XML al padre si el campo tiene valor."""
    valor = _obtener_valor(campos, clave)
    if valor in (None, "", []):
        return
    for v in _valor_como_lista(valor):
        el = SubElement(padre, tag)
        if envolver:
            SubElement(el, envolver).text = v
        else:
            el.text = v


# =============================================================================
# EAC-CPF (para ISAAR(CPF))
# =============================================================================

EAC_NS = "urn:isbn:1-931666-33-4"


def exportar_eac_cpf(propuesta: dict, ruta_esquema: Path) -> tuple[bytes, str, str]:
    """
    Genera un fichero EAC-CPF válido para un registro de autoridad.
    Solo aplica a ISAAR(CPF).
    """
    campos = propuesta["propuesta"]["campos"]
    _cargar_mapeo(ruta_esquema)

    eac = Element("eac-cpf", {
        "xmlns": EAC_NS,
        "xmlns:xsi": XSI_NS,
    })

    # --- control ---
    control = SubElement(eac, "control")
    SubElement(control, "recordId").text = (
        _obtener_valor(campos, "identificador_registro") or f"asistente-{_timestamp()}"
    )

    mstatus = SubElement(control, "maintenanceStatus")
    mstatus.text = _obtener_valor(campos, "estado_elaboracion") or "new"

    magency = SubElement(control, "maintenanceAgency")
    SubElement(magency, "agencyName").text = "PlumA (borrador)"

    # languageDeclaration
    langs = _valor_como_lista(_obtener_valor(campos, "lenguas_escrituras")) or ["spa"]
    langdecl = SubElement(control, "languageDeclaration")
    SubElement(langdecl, "language", {"languageCode": langs[0]}).text = langs[0]
    SubElement(langdecl, "script", {"scriptCode": "Latn"}).text = "Latino"

    # conventionDeclaration
    convd = SubElement(control, "conventionDeclaration")
    SubElement(convd, "citation").text = "ISAAR(CPF), 2ª ed., 2004"

    # maintenanceHistory
    mhistory = SubElement(control, "maintenanceHistory")
    mevent = SubElement(mhistory, "maintenanceEvent")
    SubElement(mevent, "eventType").text = "created"
    SubElement(mevent, "eventDateTime").text = datetime.now().isoformat(timespec="seconds")
    SubElement(mevent, "agentType").text = "machine"
    SubElement(mevent, "agent").text = APP_AGENT

    # Fuentes
    fuentes = _valor_como_lista(_obtener_valor(campos, "fuentes"))
    if fuentes:
        sources = SubElement(control, "sources")
        for f in fuentes:
            source = SubElement(sources, "source")
            SubElement(source, "sourceEntry").text = f

    # --- cpfDescription ---
    cpfdesc = SubElement(eac, "cpfDescription")

    # identity
    identity = SubElement(cpfdesc, "identity")
    tipo = _obtener_valor(campos, "tipo_entidad") or "institucion"
    SubElement(identity, "entityType").text = _mapear_tipo_entidad(tipo)

    forma_autorizada = _obtener_valor(campos, "forma_autorizada")
    if forma_autorizada:
        nameentry = SubElement(identity, "nameEntry")
        SubElement(nameentry, "part").text = forma_autorizada
        SubElement(nameentry, "authorizedForm").text = "ISAAR(CPF)"

    # Formas paralelas
    for fp in _valor_como_lista(_obtener_valor(campos, "formas_paralelas")):
        ne = SubElement(identity, "nameEntryParallel")
        SubElement(ne, "part").text = fp

    # Otras formas
    for otra in _valor_como_lista(_obtener_valor(campos, "otras_formas")):
        ne = SubElement(identity, "nameEntry")
        SubElement(ne, "part").text = otra
        SubElement(ne, "alternativeForm").text = "variant"

    # Identificadores
    for idf in _valor_como_lista(_obtener_valor(campos, "identificadores")):
        SubElement(identity, "entityId").text = idf

    # description
    description = SubElement(cpfdesc, "description")

    # Fechas de existencia
    fechas = _valor_como_lista(_obtener_valor(campos, "fechas_existencia"))
    if fechas:
        exists = SubElement(description, "existDates")
        for f in fechas:
            SubElement(exists, "dateRange").text = f

    # Lugares
    lugares = _valor_como_lista(_obtener_valor(campos, "lugares"))
    if lugares:
        places = SubElement(description, "places")
        for lugar in lugares:
            p = SubElement(places, "place")
            SubElement(p, "placeEntry").text = lugar

    # Estatuto jurídico
    estatuto = _obtener_valor(campos, "estatuto_juridico")
    if estatuto:
        leg = SubElement(description, "legalStatuses")
        ls = SubElement(leg, "legalStatus")
        SubElement(ls, "term").text = estatuto

    # Funciones
    funciones = _valor_como_lista(_obtener_valor(campos, "funciones_actividades"))
    if funciones:
        fns = SubElement(description, "functions")
        for fn in funciones:
            f_el = SubElement(fns, "function")
            SubElement(f_el, "term").text = fn

    # Historia
    historia = _obtener_valor(campos, "historia")
    if historia:
        bioghist = SubElement(description, "biogHist")
        SubElement(bioghist, "p").text = historia

    # Contexto general
    ctx = _obtener_valor(campos, "contexto_general")
    if ctx:
        gc = SubElement(description, "generalContext")
        SubElement(gc, "p").text = ctx

    # Relaciones
    relacionadas = _valor_como_lista(_obtener_valor(campos, "entidades_relacionadas"))
    if relacionadas:
        rels = SubElement(cpfdesc, "relations")
        for r in relacionadas:
            rel = SubElement(rels, "cpfRelation")
            rel_entry = SubElement(rel, "relationEntry")
            rel_entry.text = r

    contenido = _pretty_xml(eac)
    titulo_salida = forma_autorizada or "autoridad"
    nombre = f"{_slug(titulo_salida)}-{_timestamp()}.eac-cpf.xml"

    return contenido, "application/xml", nombre


def _mapear_tipo_entidad(tipo: str) -> str:
    """Traduce los tipos de entidad del esquema al vocabulario de EAC-CPF."""
    mapa = {
        "persona": "person",
        "familia": "family",
        "institucion": "corporateBody",
    }
    return mapa.get(tipo, "corporateBody")


# =============================================================================
# RDF / Turtle (para RIC simplificado)
# =============================================================================

# Namespaces RIC-O 1.0 oficiales del CIA-EGAD.
# https://www.ica.org/standards/RiC/ontology
RICO_NS = "https://www.ica.org/standards/RiC/ontology#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"


def _escape_turtle_literal(texto: str) -> str:
    """Escapa una cadena para usarla como literal Turtle.

    Reglas Turtle (W3C Rec 2014):
      - " y \\ deben escaparse.
      - Tab, LF, CR como \\t \\n \\r si queremos one-line literal.
      - Para textos largos con saltos, usamos triple-comilla.
    """
    texto = _limpiar_texto_exportacion(texto)
    if not texto:
        return '""'
    # Si tiene saltos de línea, usamos triple-comilla
    if "\n" in texto or "\r" in texto:
        # En triple-comilla, escapamos solo \ y """
        escaped = texto.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        return f'"""{escaped}"""'
    # Una sola línea: escapado estándar
    escaped = (
        texto.replace("\\", "\\\\")
             .replace('"', '\\"')
             .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _es_fecha_iso(valor: str) -> bool:
    """Comprueba si la cadena parece una fecha ISO 8601 (year, year-month,
    year-month-day, o intervalo year/year)."""
    if not isinstance(valor, str):
        return False
    return bool(re.match(
        r"^\d{4}(-\d{2}(-\d{2})?)?(/\d{4}(-\d{2}(-\d{2})?)?)?$",
        valor.strip(),
    ))


def _iri_turtle_seguro(iri: str) -> bool:
    """Admite solo prefijos Turtle controlados y nombres locales seguros."""
    if not isinstance(iri, str):
        return False
    return bool(re.match(r"^(rico|rdf|rdfs|xsd):[A-Za-z_][A-Za-z0-9_.-]*$", iri))


def exportar_turtle(propuesta: dict, ruta_esquema: Path,
                    perfil: str | None) -> tuple[bytes, str, str]:
    """
    Genera un fichero RDF/Turtle compatible con RIC-O 1.0 a partir de
    una propuesta RIC simplificada.

    Solo se exporta UNA entidad por fichero (la propia descrita). Las
    relaciones a otras entidades RIC se podrán expresar en versiones
    futuras; en esta versión, los nombres de productores/agentes
    asociados se anotan como literales (rico:descriptiveNote o
    rico:title sobre nodos en blanco).
    """
    if not perfil:
        raise ValueError(
            "El formato Turtle solo aplica a esquemas RIC, que requieren "
            "indicar el perfil (record, recordset, agent o activity)."
        )

    # Cargar el YAML completo para tener los IRIs por elemento
    with ruta_esquema.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data.get("multi_perfil"):
        raise ValueError(
            "El formato Turtle solo se soporta para esquemas RIC multi-perfil."
        )

    perfil_data = None
    for p in data.get("perfiles", []):
        if p.get("id") == perfil:
            perfil_data = p
            break
    if perfil_data is None:
        raise ValueError(f"Perfil RIC desconocido: {perfil!r}")

    # Mapeo clave_interna -> IRI completo desde el YAML
    iris_propiedades: dict[str, str] = {}
    for area in perfil_data.get("areas", []):
        for el in area.get("elementos", []):
            iris_propiedades[el["clave"]] = el["id"]  # ej. "rico:identifier"

    clase = perfil_data["clase"]  # "Record", "Agent", etc.

    campos = propuesta["propuesta"]["campos"]

    # Construir el IRI del sujeto
    identificador = _obtener_valor(campos, "identifier") or _obtener_valor(campos, "name")
    if isinstance(identificador, list):
        identificador = identificador[0] if identificador else None
    if not identificador:
        identificador = f"pluma-{_timestamp()}"
    sujeto_local = re.sub(r"[^A-Za-z0-9_-]+", "-", str(identificador)).strip("-")[:40]
    if not sujeto_local:
        sujeto_local = f"pluma-{_timestamp()}"

    lineas = []

    # Cabecera: prefijos
    lineas.append("@prefix rico: <https://www.ica.org/standards/RiC/ontology#> .")
    lineas.append("@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
    lineas.append("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
    lineas.append("@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .")
    lineas.append("@prefix :     <urn:pluma:export#> .")
    lineas.append("")

    # Cabecera de comentario
    fecha_gen = datetime.now().isoformat(timespec="seconds")
    lineas.append(f"# Generado por PlumA — {fecha_gen}")
    lineas.append(f"# Norma: RIC simplificado, perfil: {clase}")
    lineas.append("# IMPORTANTE: esta exportación describe UNA ÚNICA entidad RIC.")
    lineas.append("# Las relaciones a otros Records/Agents/Activities deben")
    lineas.append("# añadirse posteriormente en una herramienta nativa RIC.")
    lineas.append("")

    # Sujeto principal
    lineas.append(f":{sujeto_local} a rico:{clase} ;")

    # Propiedades del sujeto
    triples_pendientes = []
    for c in campos:
        clave = c.get("clave")
        valor = c.get("valor")
        if valor in (None, "", []):
            continue
        if clave not in iris_propiedades:
            continue  # campo no mapeado; lo ignoramos

        iri = iris_propiedades[clave]
        if not _iri_turtle_seguro(iri):
            continue
        valores = _valor_como_lista(valor)

        for v in valores:
            v_str = str(v).strip()
            if not v_str:
                continue

            # Las fechas ISO se tipan como xsd:date o xsd:gYear
            if _es_fecha_iso(v_str):
                if "/" in v_str:
                    # Intervalo: lo dejamos como literal sin tipo
                    literal = _escape_turtle_literal(v_str)
                else:
                    # Fecha simple
                    if len(v_str) == 4:
                        literal = f'"{v_str}"^^xsd:gYear'
                    elif len(v_str) == 7:
                        literal = f'"{v_str}"^^xsd:gYearMonth'
                    else:
                        literal = f'"{v_str}"^^xsd:date'
            else:
                literal = _escape_turtle_literal(v_str)

            triples_pendientes.append((iri, literal))

    # Escribir las triples con el último cerrando con punto
    for i, (iri, literal) in enumerate(triples_pendientes):
        terminator = " ." if i == len(triples_pendientes) - 1 else " ;"
        lineas.append(f"    {iri} {literal}{terminator}")

    # Si no hay propiedades, cerrar con un rdfs:comment vacío
    if not triples_pendientes:
        # Sustituir el ; del sujeto principal por .
        lineas[-1] = lineas[-1].rstrip(";").rstrip() + "."

    contenido = "\n".join(lineas).encode("utf-8") + b"\n"

    nombre_titulo = _obtener_valor(campos, "name") or sujeto_local
    if isinstance(nombre_titulo, list):
        nombre_titulo = nombre_titulo[0] if nombre_titulo else "ric-entity"
    nombre = f"{_slug(str(nombre_titulo))}-{clase.lower()}-{_timestamp()}.ttl"

    return contenido, "text/turtle; charset=utf-8", nombre


# =============================================================================
# Despachador
# =============================================================================

def exportar(
    formato: str,
    propuesta: dict,
    norma: str,
    ruta_esquema: Path,
    perfil: str | None = None,
) -> tuple[bytes, str, str]:
    """
    Punto de entrada único para los exportadores. Despacha al formato
    solicitado y comprueba compatibilidad entre norma y formato.

    Devuelve: (bytes, mime, nombre_sugerido)
    Lanza ValueError si la combinación norma/formato no es válida.
    """
    formato = formato.lower().strip()

    if formato == "json":
        return exportar_json(propuesta, norma)

    if formato == "csv":
        return exportar_csv(propuesta, norma)

    if formato == "ead":
        # EAD aplica a ISAD(G) y a DACS (ambas son normas de descripción
        # archivística que mapean a EAD3).
        if norma not in {"isad-g", "dacs"}:
            raise ValueError(
                "El formato EAD solo aplica a descripciones archivísticas "
                "(ISAD(G) o DACS). Para otras normas use JSON, CSV, "
                "EAC-CPF (si procede) o Turtle (RIC)."
            )
        return exportar_ead(propuesta, ruta_esquema)

    if formato == "eac-cpf":
        if norma != "isaar-cpf":
            raise ValueError(
                "El formato EAC-CPF solo aplica a registros de autoridad "
                "ISAAR(CPF). Para otras normas use JSON, CSV o Turtle (RIC)."
            )
        return exportar_eac_cpf(propuesta, ruta_esquema)

    if formato == "turtle":
        # Turtle/RDF aplica a RIC simplificado.
        if not norma.startswith("ric-"):
            raise ValueError(
                "El formato Turtle (RDF) solo aplica a descripciones RIC. "
                "Para otras normas use JSON, CSV, EAD o EAC-CPF según corresponda."
            )
        return exportar_turtle(propuesta, ruta_esquema, perfil)

    raise ValueError(f"Formato desconocido: {formato!r}")
