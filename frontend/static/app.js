/* =============================================================================
   PlumA — JavaScript del frontend
   -----------------------------------------------------------------------------
   Vanilla JS, sin frameworks. Secciones:

     1. Estado global y utilidades
     2. Pantallas (motor, bienvenida, sesión)
     3. Estado del motor (polling de /api/estado)
     4. Normas (carga inicial del selector)
     5. Drop zone y selección de fichero
     6. Procesamiento de un documento
     7. Render de la propuesta (campos y evidencias)
     8. Copia al portapapeles
     9. Modo flotante (Picture-in-Picture)
    10. Toasts
    11. Arranque
   ========================================================================== */


/* =============================================================================
   1. Estado global y utilidades
   ========================================================================== */

const documentoPrincipal = document;

const estado = {
  uiDocument: documentoPrincipal,
  motorListo: false,
  normas: [],
  normaActual: null,
  modoActual: 'esencial',
  ficheroActual: null,
  propuestaActual: null,
  tipoDetectado: null,
  campos: [],       // todos los campos (extraibles + no extraibles)
  camposOcultos: [],
  camposPersonalizados: null,  // Set<clave> con los campos seleccionados en modo personalizado, o null si está desactivado
  csrfToken: null,  // token anti-CSRF, se pide al backend al arrancar
  idioma: localStorage.getItem('idioma-ui') || 'es',
};

function documentoActivo() {
  return estado.uiDocument || documentoPrincipal;
}

function $(id) {
  const doc = documentoActivo();
  return doc.getElementById(id) || documentoPrincipal.getElementById(id);
}

function $$(selector) {
  return Array.from(documentoActivo().querySelectorAll(selector));
}

function crearElemento(tag) {
  return documentoActivo().createElement(tag);
}

function cuerpoActivo() {
  return documentoActivo().body || documentoPrincipal.body;
}

function mostrarPantalla(nombre) {
  $$('.pantalla').forEach(p => p.classList.remove('activa'));
  const pantalla = $('pantalla-' + nombre);
  if (pantalla) pantalla.classList.add('activa');
}

function formatearBytes(n) {
  if (n < 1024) return n + ' B';
  if (n < 1_048_576) return (n / 1024).toFixed(1) + ' KB';
  return (n / 1_048_576).toFixed(1) + ' MB';
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}


/* =============================================================================
   1a. Internacionalización de interfaz
   -----------------------------------------------------------------------------
   Traduce la interfaz y determina el idioma de salida de la descripción.
   El idioma seleccionado se envía al backend en cada análisis; para regenerar
   una descripción en otro idioma es necesario reprocesar el documento.
   Los esquemas archivísticos siguen siendo la fuente normativa de campos.
   ========================================================================== */

const I18N = {
  es: {
    'brand.title': 'PlumA',
    'brand.subtitle': 'Descripción asistida · v0.5.0-beta',
    'language.label': 'Idioma',
    'language.title': 'Idioma de la interfaz',
    'engine.statusTitle': 'Estado del motor de IA',
    'engine.checking': 'comprobando…',
    'engine.checkingFull': 'Comprobando el motor de IA',
    'engine.ready': 'motor listo',
    'engine.errorShort': 'error',
    'engine.errorTitle': 'El motor de IA no ha podido arrancar',
    'engine.errorDetails': 'Detalles:',
    'engine.preparingShort': 'preparando…',
    'engine.preparingTitle': 'Preparando el asistente…',
    'engine.loading': 'Cargando',
    'engine.disconnectedTitle': 'Sin conexión con el servidor',
    'engine.disconnectedMessage': 'Comprueba que la aplicación está arrancada.',
    'welcome.title': 'Descripción archivística asistida,<br>en su propio equipo.',
    'welcome.description': 'Suba un documento y reciba propuestas de descripción según las normas del Consejo Internacional de Archivos. Todo el procesamiento ocurre localmente, sin conexión a servicios externos.',
    'drop.aria': 'Arrastre un documento o haga clic para seleccionarlo',
    'drop.title': 'Arrastre aquí un documento',
    'drop.subtitle': 'o haga clic para seleccionarlo',
    'privacy.local': 'Los documentos no salen de este equipo — procesamiento 100% local',
    'outputLanguage.note': 'Idioma de salida: la descripción se generará en el idioma seleccionado en la interfaz.',
    'outputLanguage.reprocessHint': 'Para generar la descripción en el nuevo idioma, pulsa “Reprocesar”.',
    'detectedType.label': 'Tipo documental detectado',
    'otherDocument.title': 'Procesar otro documento',
    'otherDocument.button': 'Otro documento',
    'controls.standard': 'Norma',
    'controls.mode': 'Modo',
    'mode.essential': 'Esencial',
    'mode.complete': 'Completo',
    'mode.custom': 'Personalizado',
    'group.description': 'Descripción archivística',
    'group.authorities': 'Autoridades, funciones e instituciones',
    'group.ric': 'RIC (simplificado)',
    'export.turtle.title': 'Descargar como RDF/Turtle (RIC-O)',
    'custom.button': 'Personalizar campos',
    'custom.title': 'Selección de campos a mostrar y exportar',
    'custom.description': 'Elige qué campos quieres mantener visibles y exportables. Si reprocesas en modo personalizado, la selección se enviará al backend para limitar los campos solicitados al modelo.',
    'custom.selectAll': 'Seleccionar todos',
    'custom.selectNone': 'Deseleccionar todos',
    'custom.essentialOnly': 'Solo esenciales',
    'custom.apply': 'Aplicar',
    'custom.cancel': 'Cancelar',
    'custom.atLeastOne': 'Selecciona al menos un campo.',
    'custom.needsProcessing': 'Procesa primero un documento para personalizar los campos.',
    'custom.toggleArea': 'Marcar/desmarcar área',
    'reprocess.title': 'Volver a procesar con la configuración actual',
    'reprocess.button': 'Reprocesar',
    'progress.empty': '— campos',
    'progress.extracted': '{extraidos} de {total} campos extraídos',
    'hidden.showBefore': 'Mostrar los',
    'hidden.showAfter': 'campos restantes para cumplimentar manualmente',
    'status.ready': 'Listo',
    'status.processing': 'Procesando…',
    'status.draft': 'Borrador',
    'status.error': 'Error',
    'footer.local': '· los datos no salen de este equipo',
    'footer.developedBy': 'Desarrollado por',
    'footer.license': 'Licencia AGPL-3.0',
    'float.title': 'Abrir en ventana flotante sobre otras aplicaciones',
    'float.button': 'Ventana flotante',
    'shutdown.title': 'Apagar el servidor local',
    'shutdown.button': 'Apagar',
    'shutdown.confirm': 'Se detendrá el servidor local de la aplicación. En modo bundled, Ollama puede seguir activo hasta ejecutar detener.bat/detener.sh. ¿Continuar?',
    'shutdown.sending': 'Apagando…',
    'shutdown.done': 'Apagado iniciado. Puede cerrar esta pestaña.',
    'shutdown.error': 'No se pudo apagar desde la interfaz: {mensaje}',
    'processing.overlay': 'Analizando el documento…',
    'processing.notReady': 'El motor de IA todavía no está listo.',
    'processing.success': 'Documento procesado correctamente',
    'processing.error': 'Error: {mensaje}',
    'export.json': 'Descargar como JSON',
    'export.csv': 'Descargar como CSV (compatible con Excel)',
    'export.ead': 'Descargar como EAD3 XML (para ArchivesSpace, AtoM)',
    'export.eac': 'Descargar como EAC-CPF XML (solo ISAAR)',
    'export.none': 'No hay propuesta para exportar',
    'export.downloaded': 'Descargado {nombre}',
    'export.error': 'Error al exportar: {mensaje}',
    'copy.title': 'Copiar al portapapeles',
    'copy.empty': 'Este campo está vacío; no hay nada que copiar.',
    'copy.error': 'No se pudo copiar al portapapeles',
    'floating.error': 'Tu navegador no permite abrir ventana flotante',
    'norms.loadError': 'No se pudieron cargar las normas: {mensaje}',
    'norms.reprocessHint': 'Pulsa “Reprocesar” para aplicar la nueva norma.',
    'document.pagesShort': 'pág.',
    'document.routePrefix': 'ruta',
    'field.manual': 'manual',
    'field.noProposal': 'sin propuesta',
    'field.placeholderManual': 'Pendiente de cumplimentar por el archivero',
    'field.placeholderNoEvidence': 'Sin evidencia en el documento; editar manualmente',
    'warnings.title': 'Advertencias del análisis:',
    'audit.title': 'Ficha técnica del proceso',
    'audit.summary': 'ID {id} · {ruta} · {localizadas}/{conEvidencia} evidencias verificadas',
    'audit.downloadTitle': 'Descargar ficha técnica del proceso',
    'audit.downloaded': 'Ficha técnica descargada',
    'audit.noData': 'No hay ficha técnica disponible.',
    'audit.version': 'Versión',
    'audit.model': 'Modelo',
    'audit.standard': 'Norma',
    'audit.mode': 'Modo',
    'audit.sandbox': 'Sandbox de parsers',
    'audit.sha256': 'SHA-256',
    'audit.evidence': 'Control de evidencias',
    'evidence.localizada': 'evidencia verificada en texto',
    'evidence.no_localizada': 'evidencia no localizada en texto',
    'evidence.no_verificable': 'evidencia no verificable textualmente',
    'evidence.sin_evidencia': 'sin evidencia literal',
    'evidence.sin_valor': 'sin valor propuesto',
  },
  en: {
    'brand.title': 'PlumA',
    'brand.subtitle': 'Assisted description · v0.5.0-beta',
    'language.label': 'Language',
    'language.title': 'Interface language',
    'engine.statusTitle': 'AI engine status',
    'engine.checking': 'checking…',
    'engine.checkingFull': 'Checking the AI engine',
    'engine.ready': 'engine ready',
    'engine.errorShort': 'error',
    'engine.errorTitle': 'The AI engine could not start',
    'engine.errorDetails': 'Details:',
    'engine.preparingShort': 'preparing…',
    'engine.preparingTitle': 'Preparing the assistant…',
    'engine.loading': 'Loading',
    'engine.disconnectedTitle': 'No connection to the server',
    'engine.disconnectedMessage': 'Check that the application is running.',
    'welcome.title': 'Assisted archival description,<br>on your own computer.',
    'welcome.description': 'Upload a document and receive description proposals according to International Council on Archives standards. All processing runs locally, without external services.',
    'drop.aria': 'Drag a document or click to select it',
    'drop.title': 'Drag a document here',
    'drop.subtitle': 'or click to select one',
    'privacy.local': 'Documents do not leave this computer — 100% local processing',
    'outputLanguage.note': 'Output language: the description will be generated in the language selected in the interface.',
    'outputLanguage.reprocessHint': 'To generate the description in the new language, click “Reprocess”.',
    'detectedType.label': 'Detected documentary type',
    'otherDocument.title': 'Process another document',
    'otherDocument.button': 'Another document',
    'controls.standard': 'Standard',
    'controls.mode': 'Mode',
    'mode.essential': 'Essential',
    'mode.complete': 'Complete',
    'mode.custom': 'Custom',
    'group.description': 'Archival description',
    'group.authorities': 'Authorities, functions and institutions',
    'group.ric': 'RIC (simplified)',
    'export.turtle.title': 'Download as RDF/Turtle (RIC-O)',
    'custom.button': 'Customize fields',
    'custom.title': 'Select fields to display and export',
    'custom.description': 'Choose which fields you want to keep visible and exportable. If you reprocess in custom mode, the selection is sent to the backend to limit the fields requested from the model.',
    'custom.selectAll': 'Select all',
    'custom.selectNone': 'Deselect all',
    'custom.essentialOnly': 'Essentials only',
    'custom.apply': 'Apply',
    'custom.cancel': 'Cancel',
    'custom.atLeastOne': 'Select at least one field.',
    'custom.needsProcessing': 'Process a document first before customizing fields.',
    'custom.toggleArea': 'Toggle area',
    'reprocess.title': 'Process again with the current settings',
    'reprocess.button': 'Reprocess',
    'progress.empty': '— fields',
    'progress.extracted': '{extraidos} of {total} fields extracted',
    'hidden.showBefore': 'Show the',
    'hidden.showAfter': 'remaining fields for manual completion',
    'status.ready': 'Ready',
    'status.processing': 'Processing…',
    'status.draft': 'Draft',
    'status.error': 'Error',
    'footer.local': '· data does not leave this computer',
    'footer.developedBy': 'Developed by',
    'footer.license': 'AGPL-3.0 license',
    'float.title': 'Open as a floating window over other applications',
    'float.button': 'Floating window',
    'shutdown.title': 'Shut down the local server',
    'shutdown.button': 'Shut down',
    'shutdown.confirm': 'This will stop the local application server. In bundled mode, Ollama may remain running until detener.bat/detener.sh is executed. Continue?',
    'shutdown.sending': 'Shutting down…',
    'shutdown.done': 'Shutdown started. You may close this tab.',
    'shutdown.error': 'The application could not be shut down from the interface: {mensaje}',
    'processing.overlay': 'Analysing the document…',
    'processing.notReady': 'The AI engine is not ready yet.',
    'processing.success': 'Document processed successfully',
    'processing.error': 'Error: {mensaje}',
    'export.json': 'Download as JSON',
    'export.csv': 'Download as CSV (Excel-compatible)',
    'export.ead': 'Download as EAD3 XML (for ArchivesSpace, AtoM)',
    'export.eac': 'Download as EAC-CPF XML (ISAAR only)',
    'export.none': 'There is no proposal to export',
    'export.downloaded': 'Downloaded {nombre}',
    'export.error': 'Export error: {mensaje}',
    'copy.title': 'Copy to clipboard',
    'copy.empty': 'This field is empty; there is nothing to copy.',
    'copy.error': 'Could not copy to clipboard',
    'floating.error': 'Your browser does not allow floating windows',
    'norms.loadError': 'The standards could not be loaded: {mensaje}',
    'norms.reprocessHint': 'Click “Reprocess” to apply the new standard.',
    'document.pagesShort': 'pp.',
    'document.routePrefix': 'route',
    'field.manual': 'manual',
    'field.noProposal': 'no proposal',
    'field.placeholderManual': 'Pending manual completion by the archivist',
    'field.placeholderNoEvidence': 'No evidence in the document; edit manually',
    'warnings.title': 'Analysis warnings:',
    'audit.title': 'Technical process sheet',
    'audit.summary': 'ID {id} · {ruta} · {localizadas}/{conEvidencia} evidence snippets verified',
    'audit.downloadTitle': 'Download technical process sheet',
    'audit.downloaded': 'Technical sheet downloaded',
    'audit.noData': 'No technical sheet available.',
    'audit.version': 'Version',
    'audit.model': 'Model',
    'audit.standard': 'Standard',
    'audit.mode': 'Mode',
    'audit.sandbox': 'Parser sandbox',
    'audit.sha256': 'SHA-256',
    'audit.evidence': 'Evidence control',
    'evidence.localizada': 'evidence verified in text',
    'evidence.no_localizada': 'evidence not found in text',
    'evidence.no_verificable': 'evidence not text-verifiable',
    'evidence.sin_evidencia': 'no literal evidence',
    'evidence.sin_valor': 'no proposed value',
  },
};

const TRADUCCIONES_DINAMICAS_EN = {
  'Descripción archivística': 'Archival description',
  'Registros de autoridad': 'Authority records',
  'Descripción de funciones': 'Description of functions',
  'Instituciones de archivo': 'Archival institutions',
  'Área de identificación': 'Identity area',
  'Área de contexto': 'Context area',
  'Área de contenido y estructura': 'Content and structure area',
  'Área de condiciones de acceso y uso': 'Conditions of access and use area',
  'Área de documentación asociada': 'Allied materials area',
  'Área de notas': 'Notes area',
  'Área de control': 'Description control area',
  'Área de descripción / contexto': 'Description / context area',
  'Área de descripción': 'Description area',
  'Área de relaciones': 'Relationships area',
  'Área de contacto': 'Contact area',
  'Área de acceso': 'Access area',
  'Área de servicios': 'Services area',
  'Código de referencia': 'Reference code',
  'Título': 'Title',
  'Fechas': 'Dates',
  'Nivel de descripción': 'Level of description',
  'Volumen y soporte de la unidad de descripción': 'Extent and medium of the unit of description',
  'Nombre del/los productor/es': 'Name of creator(s)',
  'Historia institucional / Reseña biográfica': 'Administrative / biographical history',
  'Historia archivística': 'Archival history',
  'Forma de ingreso': 'Immediate source of acquisition or transfer',
  'Alcance y contenido': 'Scope and content',
  'Valoración, selección y eliminación': 'Appraisal, destruction and scheduling',
  'Nuevos ingresos': 'Accruals',
  'Organización (Sistema de organización)': 'System of arrangement',
  'Condiciones de acceso': 'Conditions governing access',
  'Condiciones de reproducción': 'Conditions governing reproduction',
  'Lengua/escritura(s) de los documentos': 'Language/scripts of material',
  'Características físicas y requisitos técnicos': 'Physical characteristics and technical requirements',
  'Instrumentos de descripción': 'Finding aids',
  'Existencia y localización de los originales': 'Existence and location of originals',
  'Existencia y localización de copias': 'Existence and location of copies',
  'Unidades de descripción relacionadas': 'Related units of description',
  'Nota de publicaciones': 'Publication note',
  'Notas': 'Notes',
  'Nota del archivero': "Archivist's note",
  'Reglas o normas': 'Rules or conventions',
  'Fecha(s) de la(s) descripción(es)': 'Date(s) of descriptions',
  'Tipo de entidad': 'Type of entity',
  'Forma(s) autorizada(s) del nombre': 'Authorized form(s) of name',
  'Forma(s) paralela(s) del nombre': 'Parallel form(s) of name',
  'Forma(s) normalizada(s) del nombre según otras reglas': 'Standardized form(s) of name according to other rules',
  'Otra(s) forma(s) del nombre': 'Other form(s) of name',
  'Identificadores para instituciones': 'Identifiers for corporate bodies',
  'Fechas de existencia': 'Dates of existence',
  'Historia': 'History',
  'Lugares': 'Places',
  'Estatuto jurídico': 'Legal status',
  'Funciones, ocupaciones y actividades': 'Functions, occupations and activities',
  'Atribuciones / Fuentes legales': 'Mandates / sources of authority',
  'Estructura interna / Genealogía': 'Internal structure / genealogy',
  'Contexto general': 'General context',
  'Nombres / Identificadores de entidades relacionadas': 'Names / identifiers of related entities',
  'Naturaleza de la relación': 'Nature of relationship',
  'Descripción de la relación': 'Description of relationship',
  'Fechas de la relación': 'Dates of relationship',
  'Identificador del registro de autoridad': 'Authority record identifier',
  'Identificadores de la institución (responsable del registro)': 'Institution identifiers (responsible for the record)',
  'Estado de elaboración': 'Status',
  'Nivel de detalle': 'Level of detail',
  'Fechas de creación, revisión o eliminación': 'Dates of creation, revision or deletion',
  'Lengua(s) y escritura(s) del registro': 'Language(s) and script(s) of the record',
  'Fuentes': 'Sources',
  'Notas de mantenimiento': 'Maintenance notes',
  'Tipo': 'Type',
  'Clasificación': 'Classification',
  'Descripción': 'Description',
  'Legislación': 'Legislation',
  'Nombres / Identificadores de funciones relacionadas': 'Names / identifiers of related functions',
  'Categoría': 'Category',
  'Identificador de la descripción de la función': 'Function description identifier',
  'Lengua(s) y escritura(s)': 'Language(s) and script(s)',
  'Identificador': 'Identifier',
  'Tipo de institución que custodia los fondos de archivo': 'Type of archival institution',
  'Localización y dirección(es)': 'Location and address(es)',
  'Teléfono, fax y correo electrónico': 'Telephone, fax and email',
  'Personas de contacto': 'Contact persons',
  'Historia de la institución que custodia los fondos': 'History of the archival institution',
  'Contexto geográfico y cultural': 'Geographical and cultural context',
  'Estructura administrativa': 'Administrative structure',
  'Gestión de documentos y política de ingresos': 'Records management and collecting policies',
  'Edificio(s)': 'Building(s)',
  'Fondos y otras colecciones custodiadas': 'Archival and other holdings',
  'Instrumentos de descripción, guías y publicaciones': 'Finding aids, guides and publications',
  'Horarios de apertura': 'Opening times',
  'Condiciones y requisitos para el uso y el acceso': 'Conditions and requirements for access and use',
  'Accesibilidad': 'Accessibility',
  'Servicios de ayuda a la investigación': 'Research services',
  'Servicios de reproducción': 'Reproduction services',
  'Espacios públicos': 'Public areas',
  'Identificador de la descripción': 'Description identifier',
  'Identificador de la institución (responsable del registro)': 'Institution identifier (responsible for the record)',
};

const TIPOS_DOCUMENTALES_EN = {
  'Oficio': 'Official letter',
  'Expediente administrativo': 'Administrative file',
  'Resolución': 'Resolution',
  'Memoria': 'Report / memorandum',
  'Informe': 'Report',
  'Acta de sesión': 'Minutes',
  'Carta': 'Letter',
  'Telegrama': 'Telegram',
  'Sentencia': 'Judgment',
  'Escritura notarial': 'Notarial deed',
  'Testamento': 'Will',
  'Protocolo notarial': 'Notarial protocol',
  'Libro sacramental': 'Sacramental register',
  'Visita pastoral': 'Pastoral visitation',
  'Bula': 'Bull',
  'Libro de registro': 'Register book',
  'Libro contable': 'Account book',
  'Padrón': 'Register / census',
  'Plano': 'Plan',
  'Mapa': 'Map',
  'Fotografía': 'Photograph',
  'Disposición normativa': 'Regulatory provision',
  'Tipo no identificado': 'Unidentified type',
};

function t(clave, params = {}) {
  const dic = I18N[estado.idioma] || I18N.es;
  let texto = dic[clave] || I18N.es[clave] || clave;
  for (const [k, v] of Object.entries(params)) {
    texto = texto.replaceAll('{' + k + '}', String(v));
  }
  return texto;
}

function traducirDinamico(texto) {
  if (estado.idioma !== 'en' || !texto) return texto;
  return TRADUCCIONES_DINAMICAS_EN[texto] || TIPOS_DOCUMENTALES_EN[texto] || texto;
}

function traducirConfianza(confianza) {
  if (!confianza) return '';
  if (estado.idioma !== 'en') return confianza;
  return { alta: 'high', media: 'medium', baja: 'low' }[confianza] || confianza;
}

function tituloNorma(n) {
  return traducirDinamico(n.titulo || '');
}

function textoOpcionNorma(n) {
  return n.nombre + ' — ' + tituloNorma(n);
}

function aplicarIdioma(idioma) {
  estado.idioma = idioma === 'en' ? 'en' : 'es';
  localStorage.setItem('idioma-ui', estado.idioma);
  documentoActivo().documentElement.lang = estado.idioma;
  documentoActivo().title = estado.idioma === 'en' ? 'PlumA' : 'PlumA';

  $$('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  $$('[data-i18n-html]').forEach(el => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  $$('[data-i18n-title]').forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });
  $$('[data-i18n-aria-label]').forEach(el => {
    el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
  });

  const selector = $('selector-idioma');
  if (selector) selector.value = estado.idioma;

  if (estado.normas.length) actualizarSelectorNormas();
  if (estado.propuestaActual) renderSesion();
}

function actualizarSelectorNormas() {
  const selector = $('selector-norma');
  if (!selector) return;
  const valorPrevio = selector.value || estado.normaActual;
  selector.innerHTML = '';

  // Agrupamos visualmente por familia. Las claves se reconocen por prefijo
  // o por estar en una lista conocida.
  const grupos = {
    descripcion: { label: t('group.description') || 'Descripción archivística', claves: ['isad-g', 'dacs'] },
    autoridades: { label: t('group.authorities') || 'Autoridades, funciones e instituciones', claves: ['isaar-cpf', 'isdf', 'isdiah'] },
    ric:         { label: t('group.ric') || 'RIC (simplificado)', claves: ['ric-record', 'ric-recordset', 'ric-agent', 'ric-activity'] },
  };

  // Indexamos las normas que vienen del backend
  const normasPorClave = {};
  for (const n of estado.normas) normasPorClave[n.clave] = n;

  // Renderizamos cada grupo si tiene al menos una norma disponible
  let primeraClave = null;
  for (const grupoId of ['descripcion', 'autoridades', 'ric']) {
    const grupo = grupos[grupoId];
    const normasGrupo = grupo.claves
      .map(c => normasPorClave[c])
      .filter(Boolean);
    if (normasGrupo.length === 0) continue;

    const og = crearElemento('optgroup');
    og.label = grupo.label;
    for (const n of normasGrupo) {
      const op = crearElemento('option');
      op.value = n.clave;
      op.textContent = textoOpcionNorma(n);
      og.appendChild(op);
      if (!primeraClave) primeraClave = n.clave;
    }
    selector.appendChild(og);
  }

  // Cualquier norma que no caiga en los grupos conocidos va al final, suelta
  const clavesEnGrupos = new Set();
  for (const g of Object.values(grupos)) g.claves.forEach(c => clavesEnGrupos.add(c));
  for (const n of estado.normas) {
    if (!clavesEnGrupos.has(n.clave)) {
      const op = crearElemento('option');
      op.value = n.clave;
      op.textContent = textoOpcionNorma(n);
      selector.appendChild(op);
      if (!primeraClave) primeraClave = n.clave;
    }
  }

  estado.normaActual = valorPrevio || primeraClave;
  selector.value = estado.normaActual;
}


/* =============================================================================
   1b. Protección CSRF
   -----------------------------------------------------------------------------
   El backend exige un token CSRF en la cabecera X-CSRF-Token para todas
   las peticiones mutadoras (POST, PUT, PATCH, DELETE). Lo pedimos una
   vez al arrancar y lo guardamos en memoria; fetchProtegido lo añade
   automáticamente en cada llamada.
   ========================================================================== */

async function obtenerTokenCSRF() {
  try {
    const r = await fetch('/api/csrf');
    if (!r.ok) throw new Error('respuesta ' + r.status);
    const data = await r.json();
    estado.csrfToken = data.token;
    return true;
  } catch (err) {
    console.error('No se pudo obtener token CSRF:', err);
    return false;
  }
}

/**
 * Envuelve fetch(). Inyecta la cabecera X-CSRF-Token en métodos
 * mutadores. Si el servidor devuelve 403 por token caducado, lo pide
 * de nuevo y reintenta la petición una sola vez.
 */
async function fetchProtegido(url, opciones = {}) {
  const metodo = (opciones.method || 'GET').toUpperCase();
  const esMutador = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(metodo);

  if (esMutador) {
    if (!estado.csrfToken) {
      await obtenerTokenCSRF();
    }
    opciones.headers = {
      ...(opciones.headers || {}),
      'X-CSRF-Token': estado.csrfToken || '',
    };
  }

  const r = await fetch(url, opciones);

  // Si el token ha caducado (contenedor reiniciado), pedimos uno nuevo
  // y reintentamos una vez
  if (r.status === 403 && esMutador) {
    const texto = await r.clone().text();
    if (texto.includes('CSRF') || texto.includes('csrf')) {
      const ok = await obtenerTokenCSRF();
      if (ok) {
        opciones.headers['X-CSRF-Token'] = estado.csrfToken;
        return await fetch(url, opciones);
      }
    }
  }

  return r;
}

async function aplicarPoliticaSeguridadUI() {
  try {
    const r = await fetch('/api/seguridad-local');
    if (!r.ok) return;
    const data = await r.json();
    const boton = $('boton-apagar');
    if (boton && data.apagado_ui_permitido === false) {
      boton.style.display = 'none';
      boton.disabled = true;
      boton.setAttribute('aria-hidden', 'true');
    }
  } catch (err) {
    console.warn('No se pudo consultar la política local de seguridad:', err);
  }
}


/* =============================================================================
   2. Pantallas
   ========================================================================== */

function irABienvenida() {
  mostrarPantalla('bienvenida');
  $('acciones-pie').style.display = 'none';
  estado.ficheroActual = null;
  estado.propuestaActual = null;
  $('estado-trabajo-texto').textContent = t('status.ready');
}

function irASesion() {
  mostrarPantalla('sesion');
  $('acciones-pie').style.display = 'flex';
}


/* =============================================================================
   3. Estado del motor
   ========================================================================== */

async function comprobarEstadoMotor() {
  try {
    const r = await fetch('/api/estado');
    if (!r.ok) throw new Error('respuesta ' + r.status);
    const s = await r.json();

    // Actualizar indicador de la cabecera
    const punto = $('estado-punto');
    const texto = $('estado-texto');
    punto.className = 'estado-punto';

    if (s.listo) {
      punto.classList.add('ok');
      texto.textContent = s.modelo_base || t('engine.ready');
      estado.motorListo = true;
      return true;
    }

    if (s.fase === 'error') {
      punto.classList.add('error');
      texto.textContent = t('engine.errorShort');
      $('motor-titulo').textContent = t('engine.errorTitle');
      $('motor-mensaje').textContent = t('engine.errorDetails');
      $('motor-error').style.display = 'block';
      $('motor-error').textContent = s.mensaje;
      return false;
    }

    // Todavía trabajando
    punto.classList.add('trabajando');
    texto.textContent = t('engine.preparingShort');
    $('motor-titulo').textContent = t('engine.preparingTitle');
    $('motor-mensaje').textContent = s.mensaje || t('engine.loading');
    $('motor-error').style.display = 'none';
    return false;

  } catch (err) {
    console.error('Error consultando /api/estado:', err);
    $('estado-punto').className = 'estado-punto error';
    $('estado-texto').textContent = estado.idioma === 'en' ? 'offline' : 'sin conexión';
    $('motor-titulo').textContent = t('engine.disconnectedTitle');
    $('motor-mensaje').textContent = t('engine.disconnectedMessage');
    return false;
  }
}

async function esperarMotorYArrancar() {
  mostrarPantalla('motor');

  let listo = await comprobarEstadoMotor();
  while (!listo) {
    await new Promise(r => setTimeout(r, 1500));
    listo = await comprobarEstadoMotor();
    // Salida: si el estado pasa a error definitivo, mostramos el mensaje
    // y el usuario puede recargar o cambiar config. No bucleamos infinito.
    const s = await fetch('/api/estado').then(r => r.json()).catch(() => ({}));
    if (s.fase === 'error') return;
  }

  await cargarNormas();
  irABienvenida();
}


/* =============================================================================
   4. Normas
   ========================================================================== */

async function cargarNormas() {
  try {
    const r = await fetch('/api/normas');
    const data = await r.json();
    estado.normas = data.normas;

    // Norma por defecto: la primera (ISAD-G)
    estado.normaActual = estado.normas[0].clave;
    actualizarSelectorNormas();
  } catch (err) {
    toast(t('norms.loadError', { mensaje: err.message }), 'error');
  }
}


/* =============================================================================
   5. Drop zone y selección de fichero
   ========================================================================== */

function inicializarDropZone() {
  const dz = $('drop-zone');
  const input = $('selector-fichero');

  // En modo flotante (Document Picture-in-Picture) el <body> se mueve a otro
  // document/window. Algunos navegadores abren el selector de fichero pero no
  // propagan bien el cambio si el input oculto pertenece al documento original
  // o conserva el mismo valor. Por eso se crea un input temporal en el
  // ownerDocument real del botón pulsado. También soluciona la selección
  // repetida del mismo fichero.
  dz.addEventListener('click', (e) => abrirSelectorFichero(e.currentTarget));
  dz.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      abrirSelectorFichero(e.currentTarget);
    }
  });

  dz.addEventListener('dragover', (e) => {
    e.preventDefault();
    dz.classList.add('activa');
  });
  dz.addEventListener('dragleave', () => dz.classList.remove('activa'));
  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    dz.classList.remove('activa');
    if (e.dataTransfer.files.length > 0) {
      procesarFichero(e.dataTransfer.files[0]);
    }
  });

  // Conservamos el input fijo como fallback de accesibilidad si alguna extensión
  // o navegador antiguo lo activa directamente.
  input.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      procesarFichero(e.target.files[0]);
      e.target.value = '';
    }
  });

  $('boton-otro-documento').addEventListener('click', irABienvenida);
  $('boton-reprocesar').addEventListener('click', () => {
    if (estado.ficheroActual) procesarFichero(estado.ficheroActual);
  });
}

async function abrirSelectorFichero(origen) {
  const docActivo = (origen && origen.ownerDocument) || documentoActivo();
  const winActivo = docActivo.defaultView || window;
  const accept = '.pdf,.docx,.txt,.jpg,.jpeg,.png,.tif,.tiff,.webp';
  const pickerTypes = [{
    description: 'Documentos admitidos',
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/tiff': ['.tif', '.tiff'],
      'image/webp': ['.webp'],
    },
  }];

  // En Document Picture-in-Picture el DOM visible está en otra ventana, pero la
  // lógica de red y estado sigue viviendo en la ventana principal. Para no
  // perder el fichero seleccionado, probamos primero el File System Access API
  // de la ventana principal y después el de la ventana activa.
  const candidatosPicker = [];
  if (typeof window.showOpenFilePicker === 'function') candidatosPicker.push(window);
  if (winActivo !== window && typeof winActivo.showOpenFilePicker === 'function') candidatosPicker.push(winActivo);

  for (const win of candidatosPicker) {
    try {
      const handles = await win.showOpenFilePicker({ multiple: false, types: pickerTypes });
      if (handles && handles.length > 0) {
        const file = await handles[0].getFile();
        if (file) {
          await procesarFichero(file);
          return;
        }
      }
    } catch (err) {
      if (err && err.name === 'AbortError') return;
      console.warn('showOpenFilePicker falló; probando alternativa:', err);
    }
  }

  // Fallback deliberadamente anclado al documento principal. En algunas
  // versiones de Chromium el input creado dentro del documento PiP abre el
  // selector, pero no conserva correctamente FileList al volver al callback.
  await abrirSelectorConInputTemporal(documentoPrincipal, accept);
}

function abrirSelectorConInputTemporal(doc, accept) {
  return new Promise((resolve) => {
    const temporal = doc.createElement('input');
    temporal.type = 'file';
    temporal.accept = accept;
    temporal.style.position = 'fixed';
    temporal.style.left = '-10000px';
    temporal.style.top = '0';
    temporal.style.width = '1px';
    temporal.style.height = '1px';
    temporal.style.opacity = '0';
    temporal.setAttribute('aria-hidden', 'true');

    let resuelto = false;
    const limpiar = () => {
      temporal.value = '';
      setTimeout(() => temporal.remove(), 0);
    };
    const terminar = () => {
      if (!resuelto) {
        resuelto = true;
        limpiar();
        resolve();
      }
    };

    temporal.addEventListener('change', async () => {
      try {
        if (temporal.files && temporal.files.length > 0) {
          await procesarFichero(temporal.files[0]);
        }
      } finally {
        terminar();
      }
    }, { once: true });

    // Si el usuario cancela, algunos navegadores no disparan change. No afecta
    // a la selección normal y evita inputs huérfanos.
    window.setTimeout(() => {
      if (!resuelto && (!temporal.files || temporal.files.length === 0)) terminar();
    }, 60000);

    (doc.body || doc.documentElement).appendChild(temporal);
    temporal.click();
  });
}


/* =============================================================================
   6. Procesamiento
   ========================================================================== */

async function procesarFichero(fichero) {
  if (!estado.motorListo) {
    toast(t('processing.notReady'), 'error');
    return;
  }

  estado.ficheroActual = fichero;

  const overlay = $('overlay-procesando');
  overlay.classList.add('activo');
  $('overlay-mensaje').textContent = t('processing.overlay');
  $('overlay-meta').textContent =
    fichero.name + ' · ' + formatearBytes(fichero.size);
  $('estado-trabajo-texto').textContent = t('status.processing');

  const fd = new FormData();
  fd.append('fichero', fichero);
  fd.append('norma', estado.normaActual);
  fd.append('modo', estado.modoActual);
  if (estado.modoActual === 'personalizado' && estado.camposPersonalizados) {
    fd.append('campos', Array.from(estado.camposPersonalizados).join(','));
  }
  fd.append('detectar_tipo', 'true');
  fd.append('idioma_salida', estado.idioma);

  try {
    const r = await fetchProtegido('/api/describir', { method: 'POST', body: fd });

    if (!r.ok) {
      let mensaje = 'Error ' + r.status;
      try {
        const err = await r.json();
        mensaje = err.detail || mensaje;
      } catch {}
      throw new Error(mensaje);
    }

    const data = await r.json();
    estado.propuestaActual = data;
    estado.tipoDetectado = data.tipo_detectado;
    estado.campos = data.propuesta.campos;

    // Mantener la selección personalizada solo si se reprocesó explícitamente
    // en modo personalizado. En los demás casos se vuelve al modo activo normal.
    if (estado.modoActual !== 'personalizado') {
      estado.camposPersonalizados = null;
    }
    $$('#selector-modo .modo').forEach(b => {
      if (b.id === 'boton-personalizar') {
        b.classList.toggle('activo', estado.modoActual === 'personalizado');
      } else {
        b.classList.toggle('activo', b.dataset.modo === estado.modoActual);
      }
    });

    renderSesion();
    irASesion();
    // La sesión estaba oculta durante el render inicial; los textarea
    // necesitan recalcular su altura cuando ya tienen ancho real.
    ajustarAlturasCamposVisibles();
    requestAnimationFrame(ajustarAlturasCamposVisibles);
    toast(t('processing.success'), 'ok');
    $('estado-trabajo-texto').textContent = t('status.draft');

  } catch (err) {
    console.error('Error procesando fichero:', err);
    toast(t('processing.error', { mensaje: err.message }), 'error');
    $('estado-trabajo-texto').textContent = t('status.error');
  } finally {
    overlay.classList.remove('activo');
  }
}


/* =============================================================================
   7. Render de la propuesta
   ========================================================================== */

function renderSesion() {
  const data = estado.propuestaActual;
  if (!data) return;

  // Datos del documento
  $('documento-nombre').textContent = data.documento.nombre;
  const partes = [
    data.documento.tipo_mime.replace('application/', '').replace('image/', ''),
  ];
  if (data.documento.paginas) partes.push(data.documento.paginas + ' ' + t('document.pagesShort'));
  partes.push(formatearBytes(data.documento.tamano_bytes));
  partes.push(t('document.routePrefix') + ': ' + data.documento.ruta_procesamiento);
  $('documento-meta').textContent = partes.join(' · ');

  // Tipo documental detectado
  const td = estado.tipoDetectado;
  if (td) {
    $('tipo-detectado').style.display = 'flex';
    $('tipo-nombre').textContent = traducirDinamico(td.nombre);
    $('tipo-confianza-texto').textContent = traducirConfianza(td.confianza);
    $('tipo-confianza').className = 'tipo-confianza ' + td.confianza;
  } else {
    $('tipo-detectado').style.display = 'none';
  }

  // Cabecera de norma
  const norma = estado.normas.find(n => n.clave === estado.normaActual);
  $('norma-codigo').textContent = norma.nombre;
  $('norma-nombre').textContent = tituloNorma(norma);

  // Render de los campos
  renderCampos();

  // Advertencias y ficha técnica
  renderAdvertencias(data.propuesta.advertencias || []);
  renderAuditoria(data.auditoria || null);

  // Visibilidad de botones de exportación según norma
  actualizarBotonesExportacion();
}

function renderCampos() {
  const contenedor = $('lista-campos');
  contenedor.innerHTML = '';

  const campos = estado.campos;

  // Reglas de visibilidad:
  //   - Si hay filtro personalizado activo, solo mostrar los marcados.
  //   - Si no, en modo esencial ocultamos los que no llegaron procesados.
  //   - En modo completo, mostrar todo.
  let campoActivo;
  if (estado.camposPersonalizados) {
    const sel = estado.camposPersonalizados;
    campoActivo = c => sel.has(c.clave);
  } else {
    campoActivo = c =>
      c.extraible === 'no' ||             // siempre mostrar los manuales
      c.valor !== null ||                 // con propuesta
      estado.modoActual === 'completo';   // modo completo: mostrar todo
  }

  const activos = campos.filter(campoActivo);
  const ocultos = campos.filter(c => !campoActivo(c));
  estado.camposOcultos = ocultos;

  // Agrupar por área (inferida del id del campo, ej. 3.1.1 → área 3.1)
  const grupos = agruparPorArea(activos);
  let extraidos = 0;

  for (const [etiqueta, items] of grupos) {
    const h = crearElemento('div');
    h.className = 'area-titulo';
    h.textContent = traducirDinamico(etiqueta);
    contenedor.appendChild(h);

    for (const c of items) {
      contenedor.appendChild(crearElementoCampo(c));
      if (c.valor !== null && c.extraible !== 'no') extraidos++;
    }
  }

  // Contador de progreso
  const totalExtraibles = campos.filter(c => c.extraible !== 'no').length;
  $('progreso').textContent = t('progress.extracted', { extraidos, total: totalExtraibles });

  // Enlace "mostrar ocultos"
  const mostrar = $('mostrar-ocultos');
  if (ocultos.length > 0) {
    mostrar.style.display = 'block';
    $('n-ocultos').textContent = ocultos.length;
    mostrar.onclick = () => {
      estado.modoActual = 'completo';
      estado.camposPersonalizados = null;
      $$('.modo').forEach(b => {
        b.classList.toggle('activo', b.dataset.modo === 'completo');
      });
      renderCampos();
    };
  } else {
    mostrar.style.display = 'none';
  }

  // Ajustar después de insertar todos los campos. Si se calcula cuando la
  // pantalla está oculta, scrollHeight puede quedarse en una sola línea.
  requestAnimationFrame(ajustarAlturasCamposVisibles);
}

function agruparPorArea(campos) {
  // Preferimos el área enviada por el backend. Si falta, agrupamos por
  // el prefijo normativo del id del campo (X.Y.Z → X.Y).
  const nombres = {
    // ISAD(G)
    '3.1': 'Área de identificación',
    '3.2': 'Área de contexto',
    '3.3': 'Área de contenido y estructura',
    '3.4': 'Área de condiciones de acceso y uso',
    '3.5': 'Área de documentación asociada',
    '3.6': 'Área de notas',
    '3.7': 'Área de control',
    // ISAAR / ISDF / ISDIAH comparten estructura 5.x
    '5.1': 'Área de identificación',
    '5.2': 'Área de descripción / contexto',
    '5.3': 'Área de relaciones',
    '5.4': 'Área de control',
    '5.5': 'Área de servicios',
    '5.6': 'Área de control',
  };

  const mapa = new Map();
  for (const c of campos) {
    const clave = (c.id || '').split('.').slice(0, 2).join('.');
    const etiqueta = c.area_nombre || nombres[clave] || ((estado.idioma === 'en' ? 'Area ' : 'Área ') + clave);
    if (!mapa.has(etiqueta)) mapa.set(etiqueta, []);
    mapa.get(etiqueta).push(c);
  }
  return mapa;
}

function crearElementoCampo(c) {
  const tpl = $('plantilla-campo');
  // Usamos importNode sobre el documento activo (principal o PiP) para que el
  // ownerDocument del nodo creado sea correcto sin necesidad de adopción
  // implícita posterior. Funcionalmente equivalente a cloneNode cuando
  // se renderiza desde el documento principal (caso habitual).
  const fragmento = documentoActivo().importNode(tpl.content, true);
  const nodo = fragmento.firstElementChild;

  // Clave del campo en dataset (para sincronización fiable al exportar)
  nodo.dataset.clave = c.clave;

  // Clase de confianza
  if (c.confianza) nodo.classList.add('confianza-' + c.confianza);
  if (c.extraible === 'no') nodo.classList.add('manual');

  // Cabecera
  nodo.querySelector('.campo-codigo').textContent = c.id;
  const nombreEl = nodo.querySelector('.campo-nombre');
  nombreEl.textContent = traducirDinamico(c.nombre);

  // Meta (confianza)
  const metaEl = nodo.querySelector('.campo-meta');
  if (c.confianza) {
    metaEl.querySelector('.confianza-texto').textContent = traducirConfianza(c.confianza);
  } else if (c.extraible === 'no') {
    metaEl.innerHTML = '<span>' + t('field.manual') + '</span>';
  } else {
    metaEl.innerHTML = '<span>' + t('field.noProposal') + '</span>';
  }

  // Valor editable
  const valorEl = nodo.querySelector('.campo-valor');
  let valorTexto = '';
  if (c.valor !== null && c.valor !== undefined) {
    valorTexto = Array.isArray(c.valor) ? c.valor.join(' · ') : String(c.valor);
  }
  valorEl.value = valorTexto;
  valorEl.placeholder = c.extraible === 'no'
    ? t('field.placeholderManual')
    : t('field.placeholderNoEvidence');

  // Autoajuste de altura según contenido. El ajuste definitivo se
  // recalcula tras insertar el campo en el DOM, cuando el ancho ya es real.
  valorEl.rows = 1;
  valorEl.addEventListener('input', () => ajustarAlturaTextarea(valorEl));
  valorEl.addEventListener('focus', () => ajustarAlturaTextarea(valorEl));

  // Guardar valor editado en el estado
  valorEl.addEventListener('input', () => {
    c.valor = valorEl.value;
  });
  valorEl.addEventListener('change', () => {
    c.valor = valorEl.value;
  });

  // Evidencia y estado de verificación
  if (c.evidencia) {
    const ev = nodo.querySelector('.campo-evidencia');
    ev.style.display = 'block';
    ev.textContent = '«' + c.evidencia + '»';
  }
  if (c.estado_evidencia) {
    const evEstado = nodo.querySelector('.campo-evidencia-estado');
    evEstado.style.display = 'inline-flex';
    evEstado.className = 'campo-evidencia-estado estado-' + c.estado_evidencia;
    evEstado.textContent = t('evidence.' + c.estado_evidencia) || c.estado_evidencia;
  }

  // Copiar
  const btn = nodo.querySelector('.boton-copiar');
  btn.title = t('copy.title');
  btn.addEventListener('click', () => copiarTexto(btn, valorEl.value));

  return nodo;
}

function ajustarAlturasCamposVisibles() {
  $$('.campo-valor').forEach(ajustarAlturaTextarea);
}

function ajustarAlturaTextarea(el) {
  if (!el) return;

  // Si el elemento o alguno de sus padres está oculto, el navegador no puede
  // calcular scrollHeight de forma fiable. Se reintenta en el siguiente frame.
  if (el.offsetParent === null) {
    requestAnimationFrame(() => ajustarAlturaTextarea(el));
    return;
  }

  el.style.height = 'auto';
  const altura = Math.max(el.scrollHeight, 28);
  el.style.height = (altura + 6) + 'px';
}

function renderAdvertencias(lista) {
  const contenedor = $('advertencias');
  contenedor.innerHTML = '';
  if (!lista || lista.length === 0) return;

  const div = crearElemento('div');
  div.className = 'aviso-advertencia';
  div.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8 1.5 L14.5 13.5 L1.5 13.5 Z"/>
      <line x1="8" y1="6" x2="8" y2="9.5"/>
      <circle cx="8" cy="11.5" r="0.5" fill="currentColor"/>
    </svg>
    <span><strong>${escapeHtml(t('warnings.title'))}</strong><br>${lista.map(escapeHtml).join('<br>')}</span>
  `;
  contenedor.appendChild(div);
}

function renderAuditoria(auditoria) {
  const box = $('ficha-auditoria');
  const resumen = $('ficha-auditoria-resumen');
  const detalle = $('ficha-auditoria-detalle');
  if (!box || !resumen || !detalle) return;

  if (!auditoria) {
    box.style.display = 'none';
    detalle.innerHTML = '';
    return;
  }

  const ce = auditoria.control_evidencia || {};
  const doc = auditoria.documento || {};
  const cfg = auditoria.configuracion || {};
  const seg = auditoria.controles_seguridad || {};
  const app = auditoria.aplicacion || {};

  resumen.textContent = t('audit.summary', {
    id: auditoria.peticion_id || '—',
    ruta: doc.ruta_procesamiento || '—',
    localizadas: ce.evidencias_localizadas || 0,
    conEvidencia: ce.campos_con_evidencia || 0,
  });

  const filas = [
    [t('audit.version'), `${app.nombre || 'PlumA'} ${app.version || ''}`.trim()],
    [t('audit.standard'), `${cfg.norma || '—'} ${cfg.version_norma ? '(' + cfg.version_norma + ')' : ''}`.trim()],
    [t('audit.mode'), cfg.modo || '—'],
    [t('audit.model'), cfg.modelo || '—'],
    [t('audit.sandbox'), seg.sandbox_parsers_activo ? 'activo' : 'inactivo'],
    [t('audit.sha256'), doc.sha256 || '—'],
    [t('audit.evidence'), `${ce.evidencias_localizadas || 0} localizadas · ${ce.evidencias_no_localizadas || 0} no localizadas · ${ce.evidencias_no_verificables_textualmente || 0} no verificables`],
  ];

  detalle.innerHTML = filas.map(([k, v]) => `
    <div class="ficha-auditoria-fila">
      <span>${escapeHtml(k)}</span>
      <strong>${escapeHtml(v)}</strong>
    </div>
  `).join('');

  box.style.display = 'block';
}

function descargarAuditoria() {
  const auditoria = estado.propuestaActual && estado.propuestaActual.auditoria;
  if (!auditoria) {
    toast(t('audit.noData'), 'error');
    return;
  }
  const blob = new Blob([JSON.stringify(auditoria, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = crearElemento('a');
  a.href = url;
  a.download = `pluma-ficha-tecnica-${auditoria.peticion_id || 'proceso'}.json`;
  cuerpoActivo().appendChild(a);
  a.click();
  cuerpoActivo().removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(t('audit.downloaded'), 'ok');
}


/* =============================================================================
   8. Copia al portapapeles
   ========================================================================== */

async function copiarTexto(boton, texto) {
  const doc = (boton && boton.ownerDocument) ? boton.ownerDocument : document;
  const winLocal = (doc && doc.defaultView) ? doc.defaultView : window;
  const winPrincipal = documentoPrincipal.defaultView || window;

  if (!texto) {
    toast(t('copy.empty'), '', doc);
    return;
  }

  // Estado visual mediante clase CSS, no manipulando style.display directamente.
  // Evita que un fallo dentro del setTimeout deje los iconos en estado inconsistente.
  const marcarComoCopiado = () => {
    boton.classList.add('copiado');
    setTimeout(() => boton.classList.remove('copiado'), 1500);
  };

  // Estrategia en cascada: el clipboard de la PiP a veces falla por checks de
  // foco/activación en Chromium (DOMException "Document is not focused" o
  // NotAllowedError). Si pasa, intentamos con el clipboard de la ventana
  // principal (mismo origen, mismo contexto seguro). Solo como último recurso
  // caemos a execCommand sobre el documento principal, donde el check de foco
  // suele pasar.
  let errPip = null;
  let errPrincipal = null;

  // 1) navigator.clipboard del documento del botón (PiP o principal).
  if (winLocal.navigator && winLocal.navigator.clipboard
      && typeof winLocal.navigator.clipboard.writeText === 'function') {
    try {
      await winLocal.navigator.clipboard.writeText(texto);
      marcarComoCopiado();
      return;
    } catch (e) {
      errPip = e;
    }
  }

  // 2) navigator.clipboard de la ventana principal, si es distinta.
  if (winPrincipal !== winLocal
      && winPrincipal.navigator && winPrincipal.navigator.clipboard
      && typeof winPrincipal.navigator.clipboard.writeText === 'function') {
    try {
      await winPrincipal.navigator.clipboard.writeText(texto);
      marcarComoCopiado();
      return;
    } catch (e) {
      errPrincipal = e;
    }
  }

  // 3) Fallback execCommand sobre el documento principal.
  try {
    const docFallback = documentoPrincipal;
    const ta = docFallback.createElement('textarea');
    ta.value = texto;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
    docFallback.body.appendChild(ta);
    try {
      ta.focus();
      ta.select();
      const ok = docFallback.execCommand('copy');
      if (!ok) throw new Error('execCommand copy devolvió false');
      marcarComoCopiado();
    } finally {
      if (ta.parentNode) ta.parentNode.removeChild(ta);
    }
  } catch (fallbackErr) {
    console.error('No se pudo copiar al portapapeles:',
      { errPip, errPrincipal, fallbackErr });
    toast(t('copy.error'), 'error', doc);
  }
}


/* =============================================================================
   8b. Exportación (JSON, CSV, EAD, EAC-CPF)
   ========================================================================== */

async function exportar(formato) {
  if (!estado.propuestaActual) {
    toast(t('export.none'), 'error');
    return;
  }

  // Sincronizar los valores editados en la UI con la estructura en memoria.
  // Cada elemento .campo tiene un dataset.clave con la clave del campo;
  // así no dependemos del orden de los elementos en el DOM (que puede
  // estar filtrado por el modo personalizado).
  $$('.campo').forEach((elCampo) => {
    const clave = elCampo.dataset.clave;
    const ta = elCampo.querySelector('.campo-valor');
    if (!clave || !ta) return;
    const campo = estado.campos.find(c => c.clave === clave);
    if (campo) {
      const valorActual = ta.value;
      if (valorActual !== (campo.valor || '')) {
        campo.valor = valorActual;
      }
    }
  });

  // Si hay filtro personalizado activo, solo se exportan los campos
  // seleccionados. El resto se omite del payload.
  let camposParaExportar = estado.campos;
  if (estado.camposPersonalizados) {
    const sel = estado.camposPersonalizados;
    camposParaExportar = estado.campos.filter(c => sel.has(c.clave));
  }

  // Construir payload sin mutar la propuesta original
  const payload = {
    ...estado.propuestaActual,
    propuesta: {
      ...estado.propuestaActual.propuesta,
      campos: camposParaExportar,
    },
  };

  try {
    const r = await fetchProtegido('/api/exportar/' + formato, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!r.ok) {
      let mensaje = 'Error ' + r.status;
      try {
        const err = await r.json();
        mensaje = err.detail || mensaje;
      } catch {}
      throw new Error(mensaje);
    }

    // Descargar el fichero devuelto
    const blob = await r.blob();
    const disposition = r.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const nombre = match ? match[1] : 'export.' + formato;

    const url = URL.createObjectURL(blob);
    const a = crearElemento('a');
    a.href = url;
    a.download = nombre;
    cuerpoActivo().appendChild(a);
    a.click();
    cuerpoActivo().removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);

    toast(t('export.downloaded', { nombre }), 'ok');
  } catch (err) {
    console.error('Error exportando:', err);
    toast(t('export.error', { mensaje: err.message }), 'error');
  }
}

function actualizarBotonesExportacion() {
  // Reglas de visibilidad por norma:
  //   JSON, CSV    → siempre disponibles
  //   EAD          → ISAD(G) y DACS (ambas son normas de descripción archivística)
  //   EAC-CPF      → solo ISAAR(CPF)
  //   Turtle (RDF) → solo perfiles RIC
  const norma = estado.normaActual || '';
  const esEad = (norma === 'isad-g' || norma === 'dacs');
  const esEac = (norma === 'isaar-cpf');
  const esRic = norma.startsWith('ric-');

  const botonEad = $('boton-exportar-ead');
  const botonEac = $('boton-exportar-eac');
  const botonTurtle = $('boton-exportar-turtle');

  if (botonEad)    botonEad.style.display    = esEad ? '' : 'none';
  if (botonEac)    botonEac.style.display    = esEac ? '' : 'none';
  if (botonTurtle) botonTurtle.style.display = esRic ? '' : 'none';
}


/* =============================================================================
   8d. Modo personalizado: modal de selección de campos
   -----------------------------------------------------------------------------
   Funciona después de procesar el documento como filtro visual/exportador.
   Si el usuario pulsa Reprocesar mientras está activo, la selección se envía
   al backend para limitar también la extracción del modelo.
   ========================================================================== */

function abrirModalPersonalizar() {
  if (!estado.propuestaActual) {
    toast(t('custom.needsProcessing') || 'Procesa primero un documento para personalizar los campos.');
    return;
  }
  construirCuadriculaModal();
  $('modal-personalizar').style.display = 'flex';
}

function cerrarModalPersonalizar() {
  $('modal-personalizar').style.display = 'none';
}

function construirCuadriculaModal() {
  const cuadricula = $('modal-cuadricula');
  cuadricula.innerHTML = '';
  
  // Agrupamos los campos disponibles por área usando el orden del esquema.
  // Los campos disponibles son los que llegaron en la propuesta.
  const campos = estado.campos || [];
  if (campos.length === 0) return;
  
  // Agrupación por área enviada por el backend. Si no existe, se infiere por id.
  const porArea = {};
  for (const c of campos) {
    const prefijo = (c.id || '').split('.').slice(0, 2).join('.') || 'general';
    const area = c.area_id || prefijo;
    const nombre = c.area_nombre || ((estado.idioma === 'en' ? 'Area ' : 'Área ') + prefijo);
    if (!porArea[area]) porArea[area] = { nombre, elementos: [] };
    porArea[area].elementos.push(c);
  }
  
  // Estado actual: si hay personalización previa, usarla; si no, marcar todos
  const seleccionado = estado.camposPersonalizados || new Set(campos.map(c => c.clave));
  
  for (const [areaId, area] of Object.entries(porArea)) {
    const div = crearElemento('div');
    div.className = 'modal-area';
    div.dataset.areaId = areaId;
    
    const titulo = crearElemento('div');
    titulo.className = 'modal-area-titulo';
    
    const nombreAr = crearElemento('span');
    nombreAr.textContent = area.nombre;
    titulo.appendChild(nombreAr);
    
    const cuenta = crearElemento('span');
    cuenta.className = 'modal-area-cuenta';
    cuenta.textContent = `${area.elementos.length} ${area.elementos.length === 1 ? 'campo' : 'campos'}`;
    titulo.appendChild(cuenta);
    
    const botonAr = crearElemento('button');
    botonAr.type = 'button';
    botonAr.className = 'modal-area-checkbox';
    botonAr.textContent = t('custom.toggleArea') || 'Marcar/desmarcar área';
    botonAr.addEventListener('click', () => toggleArea(div));
    titulo.appendChild(botonAr);
    
    div.appendChild(titulo);
    
    const campos_div = crearElemento('div');
    campos_div.className = 'modal-campos';
    
    for (const campo of area.elementos) {
      const label = crearElemento('label');
      label.className = 'modal-campo';
      if (campo.obligatorio) label.classList.add('obligatorio');
      
      const cb = crearElemento('input');
      cb.type = 'checkbox';
      cb.value = campo.clave;
      cb.checked = seleccionado.has(campo.clave);
      label.appendChild(cb);
      
      const nombre = crearElemento('span');
      nombre.className = 'modal-campo-nombre';
      nombre.textContent = campo.nombre || campo.clave;
      label.appendChild(nombre);
      
      if (campo.id) {
        const codigo = crearElemento('span');
        codigo.className = 'modal-campo-codigo';
        codigo.textContent = campo.id;
        label.appendChild(codigo);
      }
      
      campos_div.appendChild(label);
    }
    
    div.appendChild(campos_div);
    cuadricula.appendChild(div);
  }
}

function toggleArea(divArea) {
  const checkboxes = divArea.querySelectorAll('input[type="checkbox"]');
  const todosMarcados = Array.from(checkboxes).every(cb => cb.checked);
  checkboxes.forEach(cb => { cb.checked = !todosMarcados; });
}

function marcarTodosCheckboxesModal(valor) {
  $('modal-cuadricula').querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.checked = valor;
  });
}

function marcarSoloEsencialesModal() {
  $('modal-cuadricula').querySelectorAll('input[type="checkbox"]').forEach(cb => {
    const label = cb.closest('.modal-campo');
    cb.checked = label && label.classList.contains('obligatorio');
  });
}

function aplicarFiltroPersonalizado() {
  const seleccionados = new Set();
  $('modal-cuadricula').querySelectorAll('input[type="checkbox"]:checked').forEach(cb => {
    seleccionados.add(cb.value);
  });
  
  if (seleccionados.size === 0) {
    toast(t('custom.atLeastOne') || 'Selecciona al menos un campo.');
    return;
  }
  
  estado.camposPersonalizados = seleccionados;
  estado.modoActual = 'personalizado';
  
  // Marcar el botón "Personalizar" como activo y desmarcar los otros
  $$('#selector-modo .modo').forEach(b => b.classList.remove('activo'));
  $('boton-personalizar').classList.add('activo');
  
  cerrarModalPersonalizar();
  
  // Re-renderizar con el filtro aplicado
  if (estado.propuestaActual) renderCampos();
}


/* =============================================================================
   8c. Apagado local desde la interfaz
   ========================================================================== */

async function apagarAplicacion() {
  const boton = $('boton-apagar');
  if (!confirm(t('shutdown.confirm'))) return;

  try {
    boton.disabled = true;
    $('estado-trabajo-texto').textContent = t('shutdown.sending');

    const r = await fetchProtegido('/api/apagar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });

    if (!r.ok) {
      let mensaje = 'Error ' + r.status;
      try {
        const err = await r.json();
        mensaje = err.detail || mensaje;
      } catch {}
      throw new Error(mensaje);
    }

    toast(t('shutdown.done'), 'ok');
    $('estado-texto').textContent = estado.idioma === 'en' ? 'shutting down' : 'apagando';
    $('estado-trabajo-texto').textContent = t('shutdown.done');
  } catch (err) {
    console.error('Error apagando la aplicación:', err);
    boton.disabled = false;
    toast(t('shutdown.error', { mensaje: err.message }), 'error');
    $('estado-trabajo-texto').textContent = t('status.error');
  }
}


/* =============================================================================
   9. Modo flotante
   ========================================================================== */

function inicializarModoFlotante() {
  const boton = $('boton-flotante');

  // Detección de capacidad
  if (!('documentPictureInPicture' in window)) {
    // Fallback: window.open con popup
    boton.addEventListener('click', () => {
      const w = Math.min(screen.width * 0.4, 520);
      const h = Math.min(screen.height * 0.8, 900);
      window.open(
        location.href,
        'asistente-flotante',
        `popup=yes,width=${w},height=${h},left=${screen.width - w - 40},top=80`
      );
    });
    return;
  }

  // API moderna: Document Picture-in-Picture (Chrome/Edge ≥ 116)
  boton.addEventListener('click', async () => {
    try {
      const pipWindow = await window.documentPictureInPicture.requestWindow({
        width: 480,
        height: 820,
      });

      // Clonar estilos al documento PiP desde el documento principal.
      [...documentoPrincipal.styleSheets].forEach(ss => {
        try {
          const reglas = [...ss.cssRules].map(r => r.cssText).join('');
          const style = pipWindow.document.createElement('style');
          style.textContent = reglas;
          pipWindow.document.head.appendChild(style);
        } catch {
          // Estilos de orígenes cruzados: copiamos el <link>.
          const link = pipWindow.document.createElement('link');
          link.rel = 'stylesheet';
          link.href = ss.href;
          pipWindow.document.head.appendChild(link);
        }
      });

      // Copiar hojas de estilo declaradas como <link>.
      documentoPrincipal.querySelectorAll('link[rel="stylesheet"]').forEach(l => {
        const copia = l.cloneNode(true);
        pipWindow.document.head.appendChild(copia);
      });

      // Mover el contenido principal a la ventana PiP y declarar ese documento
      // como documento activo para todos los selectores, overlays, toasts,
      // inputs temporales y renders posteriores.
      const main = documentoPrincipal.body;
      const marcador = documentoPrincipal.createElement('div');
      marcador.id = '__pip_marcador__';
      main.parentNode.insertBefore(marcador, main);
      pipWindow.document.body.appendChild(main);
      estado.uiDocument = pipWindow.document;

      // Al cerrar la PiP, devolver el contenido al documento original.
      pipWindow.addEventListener('pagehide', () => {
        estado.uiDocument = documentoPrincipal;
        marcador.parentNode.replaceChild(main, marcador);
      });

    } catch (err) {
      console.error('Fallo al abrir ventana flotante:', err);
      toast(t('floating.error'), 'error');
    }
  });
}

/* =============================================================================
   10. Toasts
   ========================================================================== */

function toast(mensaje, tipo = '', doc = null) {
  const contexto = doc || documentoActivo();
  const contenedor = contexto.getElementById('toasts') || documentoPrincipal.getElementById('toasts');

  if (!contenedor) {
    console.warn('No se encontró el contenedor de notificaciones:', mensaje);
    return;
  }

  const t = contexto.createElement('div');
  t.className = 'toast ' + tipo;
  t.textContent = mensaje;
  contenedor.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}


/* =============================================================================
   11. Arranque
   ========================================================================== */

function inicializarControles() {
  // Selector de idioma
  $('selector-idioma').addEventListener('change', (e) => {
    const idiomaAnterior = estado.idioma;
    aplicarIdioma(e.target.value);
    if (estado.propuestaActual && idiomaAnterior !== estado.idioma) {
      toast(t('outputLanguage.reprocessHint'));
    }
  });

  // Apagado local
  $('boton-apagar').addEventListener('click', apagarAplicacion);

  // Selector de norma
  $('selector-norma').addEventListener('change', (e) => {
    estado.normaActual = e.target.value;
    actualizarBotonesExportacion();
    if (estado.ficheroActual) {
      toast(t('norms.reprocessHint'));
    }
  });

  // Selector de modo
  $$('#selector-modo .modo').forEach(btn => {
    btn.addEventListener('click', () => {
      // El botón "Personalizar" abre un modal en vez de cambiar el modo
      if (btn.id === 'boton-personalizar') {
        abrirModalPersonalizar();
        return;
      }
      // Los modos normales (esencial / completo)
      $$('#selector-modo .modo').forEach(b => {
        if (b.id !== 'boton-personalizar') b.classList.remove('activo');
      });
      btn.classList.add('activo');
      estado.modoActual = btn.dataset.modo;
      // Salir del modo personalizado si lo estábamos
      estado.camposPersonalizados = null;
      if (estado.propuestaActual) renderCampos();
    });
  });

  // Botones de exportación
  $('boton-exportar-json').addEventListener('click', () => exportar('json'));
  $('boton-exportar-auditoria')?.addEventListener('click', descargarAuditoria);
  $('ficha-auditoria-toggle')?.addEventListener('click', () => {
    const detalle = $('ficha-auditoria-detalle');
    if (detalle) detalle.style.display = detalle.style.display === 'none' ? 'block' : 'none';
  });
  $('boton-exportar-csv').addEventListener('click', () => exportar('csv'));
  $('boton-exportar-ead').addEventListener('click', () => exportar('ead'));
  $('boton-exportar-eac').addEventListener('click', () => exportar('eac-cpf'));
  const botonTurtle = $('boton-exportar-turtle');
  if (botonTurtle) botonTurtle.addEventListener('click', () => exportar('turtle'));

  // Modal de personalización
  $('modal-cerrar')?.addEventListener('click', cerrarModalPersonalizar);
  $('modal-cancelar')?.addEventListener('click', cerrarModalPersonalizar);
  $('modal-overlay')?.addEventListener('click', (e) => {
    if (e.target.id === 'modal-personalizar') cerrarModalPersonalizar();
  });
  $('modal-aplicar')?.addEventListener('click', aplicarFiltroPersonalizado);
  $('modal-todos')?.addEventListener('click', () => marcarTodosCheckboxesModal(true));
  $('modal-ninguno')?.addEventListener('click', () => marcarTodosCheckboxesModal(false));
  $('modal-esenciales')?.addEventListener('click', marcarSoloEsencialesModal);
  // Cerrar con Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && $('modal-personalizar').style.display !== 'none') {
      cerrarModalPersonalizar();
    }
  });
}

async function main() {
  aplicarIdioma(estado.idioma);

  // Obtener token CSRF lo primero (antes de cualquier otra llamada).
  // Si falla, las peticiones mutadoras posteriores también fallarán,
  // pero fetchProtegido se encargará de reintentar pidiendo el token.
  await obtenerTokenCSRF();
  await aplicarPoliticaSeguridadUI();

  inicializarDropZone();
  inicializarControles();
  inicializarModoFlotante();
  await esperarMotorYArrancar();
}

document.addEventListener('DOMContentLoaded', main);
