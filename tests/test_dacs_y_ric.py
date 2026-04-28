"""
Tests de integración para las normas nuevas en PlumA 0.4:

  - DACS (Describing Archives: A Content Standard, 2nd ed.)
  - RIC simplificado (Records in Contexts), perfiles Record/RecordSet/Agent/Activity
  - Exportador EAD3 funciona también para DACS
  - Exportador Turtle para todos los perfiles RIC
"""

from pathlib import Path

import pytest

from app import exportadores, extractor


# =============================================================================
# Carga de esquemas
# =============================================================================

DIR_SCHEMAS = Path(__file__).parent.parent / "schemas"


def test_dacs_se_carga_correctamente():
    """DACS es un esquema convencional (con 'areas' planas)."""
    esquema = extractor.cargar_esquema(DIR_SCHEMAS / "dacs.yaml")
    assert esquema.norma == "DACS"
    assert len(esquema.elementos) == 14
    obligatorios = [e for e in esquema.elementos if e.obligatorio]
    assert len(obligatorios) == 6


def test_ric_es_multi_perfil():
    """RIC requiere perfil; sin él falla."""
    with pytest.raises(ValueError, match="requiere especificar un perfil"):
        extractor.cargar_esquema(DIR_SCHEMAS / "ric.yaml")


def test_ric_perfiles_se_cargan_correctamente():
    """Los 4 perfiles RIC cargan y producen esquemas independientes."""
    perfiles_esperados = {
        "record": 7,
        "recordset": 7,
        "agent": 6,
        "activity": 5,
    }
    for perfil, num_elementos in perfiles_esperados.items():
        esquema = extractor.cargar_esquema(DIR_SCHEMAS / "ric.yaml", perfil=perfil)
        assert len(esquema.elementos) == num_elementos, \
            f"Perfil {perfil}: esperaba {num_elementos} elementos, encontré {len(esquema.elementos)}"
        assert "RIC" in esquema.norma


def test_ric_perfil_inexistente_falla():
    with pytest.raises(ValueError, match="no encontrado"):
        extractor.cargar_esquema(DIR_SCHEMAS / "ric.yaml", perfil="inventado")


# =============================================================================
# Exportador EAD para DACS
# =============================================================================

def _propuesta_dacs_minima():
    return {
        "propuesta": {
            "norma": "DACS",
            "campos": [
                {"id": "2.1", "clave": "reference_code",
                 "valor": "MS-2024-001", "confianza": "alta"},
                {"id": "2.3", "clave": "title",
                 "valor": "Personal papers of Maria Garcia, 1950-1985",
                 "confianza": "alta"},
                {"id": "2.4", "clave": "date",
                 "valor": ["1950/1985"], "confianza": "alta"},
                {"id": "2.5", "clave": "extent",
                 "valor": ["3 linear feet"], "confianza": "alta"},
                {"id": "2.6", "clave": "name_of_creator",
                 "valor": "Garcia, Maria", "confianza": "alta"},
                {"id": "3.1", "clave": "scope_and_content",
                 "valor": "Correspondence and personal photographs.",
                 "confianza": "alta"},
            ],
            "advertencias": [],
        }
    }


def test_dacs_exporta_a_ead_valido():
    propuesta = _propuesta_dacs_minima()
    contenido, mime, nombre = exportadores.exportar(
        "ead", propuesta, "dacs", DIR_SCHEMAS / "dacs.yaml"
    )
    assert mime == "application/xml"
    assert nombre.endswith(".ead.xml")
    # Validar XML parsea
    import xml.etree.ElementTree as ET
    root = ET.fromstring(contenido)
    assert root.tag.endswith("ead")
    # Verificar que el title aparece en el output
    assert b"Personal papers of Maria Garcia" in contenido


def test_dacs_exporta_a_json_y_csv():
    propuesta = _propuesta_dacs_minima()
    for fmt in ["json", "csv"]:
        contenido, mime, nombre = exportadores.exportar(
            fmt, propuesta, "dacs", DIR_SCHEMAS / "dacs.yaml"
        )
        assert len(contenido) > 0


# =============================================================================
# Exportador Turtle para RIC
# =============================================================================

def _propuesta_ric_record():
    return {
        "propuesta": {
            "norma": "RIC - Record",
            "campos": [
                {"id": "rico:identifier", "clave": "identifier",
                 "valor": "OFI-2024-247", "confianza": "alta"},
                {"id": "rico:name", "clave": "name",
                 "valor": "Oficio sobre obras", "confianza": "alta"},
                {"id": "rico:hasCreationDate", "clave": "creation_date",
                 "valor": ["1985-06-14"], "confianza": "alta"},
                {"id": "rico:descriptiveNote", "clave": "descriptive_note",
                 "valor": "Autoriza obras de rehabilitación.", "confianza": "alta"},
            ],
            "advertencias": [],
        }
    }


def test_ric_record_exporta_a_turtle_valido():
    propuesta = _propuesta_ric_record()
    contenido, mime, nombre = exportadores.exportar(
        "turtle", propuesta, "ric-record", DIR_SCHEMAS / "ric.yaml",
        perfil="record",
    )
    assert "turtle" in mime
    assert nombre.endswith(".ttl")
    # Verificar prefijos y triple básica
    texto = contenido.decode("utf-8")
    assert "@prefix rico:" in texto
    assert "rico:Record" in texto
    assert "OFI-2024-247" in texto
    # Verificar tipado correcto de fecha ISO
    assert "xsd:date" in texto


def test_ric_turtle_es_parseable_por_rdflib():
    """El Turtle generado debe ser parseable por una librería RDF estándar."""
    rdflib = pytest.importorskip("rdflib")

    propuesta = _propuesta_ric_record()
    contenido, _, _ = exportadores.exportar(
        "turtle", propuesta, "ric-record", DIR_SCHEMAS / "ric.yaml",
        perfil="record",
    )
    g = rdflib.Graph()
    g.parse(data=contenido.decode("utf-8"), format="turtle")
    # Al menos 3 triples en el grafo
    assert len(g) >= 3


def test_ric_agent_exporta_a_turtle():
    propuesta = {
        "propuesta": {
            "norma": "RIC - Agent",
            "campos": [
                {"id": "rico:hasAgentType", "clave": "agent_type",
                 "valor": "CorporateBody", "confianza": "alta"},
                {"id": "rico:name", "clave": "name",
                 "valor": "Archivo Histórico Nacional", "confianza": "alta"},
                {"id": "rico:descriptiveNote", "clave": "descriptive_note",
                 "valor": "Fundado en 1866.\nCustodia documentación histórica.",
                 "confianza": "alta"},
            ],
            "advertencias": [],
        }
    }
    contenido, _, _ = exportadores.exportar(
        "turtle", propuesta, "ric-agent", DIR_SCHEMAS / "ric.yaml",
        perfil="agent",
    )
    texto = contenido.decode("utf-8")
    assert "rico:Agent" in texto
    # Multilínea correctamente con triple-comilla
    assert '"""' in texto


def test_ric_turtle_escapa_caracteres_especiales():
    """Comillas, barras invertidas y multilínea deben escaparse correctamente."""
    propuesta = {
        "propuesta": {
            "norma": "RIC - Record",
            "campos": [
                {"id": "rico:identifier", "clave": "identifier",
                 "valor": 'TEST-001', "confianza": "alta"},
                {"id": "rico:name", "clave": "name",
                 "valor": 'Documento con "comillas" y \\barras', "confianza": "alta"},
            ],
            "advertencias": [],
        }
    }
    contenido, _, _ = exportadores.exportar(
        "turtle", propuesta, "ric-record", DIR_SCHEMAS / "ric.yaml",
        perfil="record",
    )
    texto = contenido.decode("utf-8")
    # Comillas y barras deben aparecer escapadas
    assert '\\"' in texto
    assert '\\\\' in texto

    # Y el resultado debe seguir siendo Turtle válido
    rdflib = pytest.importorskip("rdflib")
    g = rdflib.Graph()
    g.parse(data=texto, format="turtle")
    assert len(g) >= 2


# =============================================================================
# Combinaciones inválidas
# =============================================================================

def test_turtle_no_aplica_a_isad():
    propuesta = {"propuesta": {"norma": "ISAD(G)", "campos": []}}
    with pytest.raises(ValueError, match="solo aplica a descripciones RIC"):
        exportadores.exportar(
            "turtle", propuesta, "isad-g", DIR_SCHEMAS / "isad-g.yaml"
        )


def test_ead_no_aplica_a_ric():
    propuesta = {"propuesta": {"norma": "RIC", "campos": []}}
    with pytest.raises(ValueError, match="descripciones archivísticas"):
        exportadores.exportar(
            "ead", propuesta, "ric-record", DIR_SCHEMAS / "ric.yaml",
            perfil="record",
        )


def test_eac_cpf_no_aplica_a_ric():
    propuesta = {"propuesta": {"norma": "RIC", "campos": []}}
    with pytest.raises(ValueError, match="ISAAR"):
        exportadores.exportar(
            "eac-cpf", propuesta, "ric-agent", DIR_SCHEMAS / "ric.yaml",
            perfil="agent",
        )


def test_turtle_sin_perfil_falla():
    propuesta = {"propuesta": {"norma": "RIC", "campos": []}}
    with pytest.raises(ValueError, match="perfil"):
        exportadores.exportar(
            "turtle", propuesta, "ric-record", DIR_SCHEMAS / "ric.yaml",
            perfil=None,
        )
