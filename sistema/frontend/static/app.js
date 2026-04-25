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

const estado = {
  motorListo: false,
  normas: [],
  normaActual: null,
  modoActual: 'esencial',
  ficheroActual: null,
  propuestaActual: null,
  tipoDetectado: null,
  campos: [],       // todos los campos (extraibles + no extraibles)
  camposOcultos: [],
  csrfToken: null,  // token anti-CSRF, se pide al backend al arrancar
  idioma: localStorage.getItem('idioma-ui') || 'es',
};

function $(id) { return document.getElementById(id); }

function mostrarPantalla(nombre) {
  document.querySelectorAll('.pantalla').forEach(p => p.classList.remove('activa'));
  $('pantalla-' + nombre).classList.add('activa');
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
    'brand.subtitle': 'Descripción asistida · v0.3.0-alpha',
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
  },
  en: {
    'brand.title': 'PlumA',
    'brand.subtitle': 'Assisted description · v0.3.0-alpha',
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
  document.documentElement.lang = estado.idioma;
  document.title = estado.idioma === 'en' ? 'PlumA' : 'PlumA';

  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });
  document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
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
  for (const n of estado.normas) {
    const op = document.createElement('option');
    op.value = n.clave;
    op.textContent = textoOpcionNorma(n);
    selector.appendChild(op);
  }
  estado.normaActual = valorPrevio || (estado.normas[0] && estado.normas[0].clave);
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

  dz.addEventListener('click', () => input.click());
  dz.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      input.click();
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

  input.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      procesarFichero(e.target.files[0]);
    }
  });

  $('boton-otro-documento').addEventListener('click', irABienvenida);
  $('boton-reprocesar').addEventListener('click', () => {
    if (estado.ficheroActual) procesarFichero(estado.ficheroActual);
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

  // Advertencias
  renderAdvertencias(data.propuesta.advertencias || []);

  // Visibilidad de botones de exportación según norma
  actualizarBotonesExportacion();
}

function renderCampos() {
  const contenedor = $('lista-campos');
  contenedor.innerHTML = '';

  const campos = estado.campos;

  // En modo esencial/personalizado, ocultamos los campos que la IA no
  // procesó (valor nulo + extraible != "no"). Los dejamos en un buffer
  // por si el usuario pide mostrarlos.
  const campoActivo = c =>
    c.extraible === 'no' ||             // siempre mostrar los manuales
    c.valor !== null ||                 // con propuesta
    estado.modoActual === 'completo';   // modo completo: mostrar todo

  const activos = campos.filter(campoActivo);
  const ocultos = campos.filter(c => !campoActivo(c));
  estado.camposOcultos = ocultos;

  // Agrupar por área (inferida del id del campo, ej. 3.1.1 → área 3.1)
  const grupos = agruparPorArea(activos);
  let extraidos = 0;

  for (const [etiqueta, items] of grupos) {
    const h = document.createElement('div');
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
      document.querySelectorAll('.modo').forEach(b => {
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
  // El id de los campos tiene formato "X.Y.Z"; agrupamos por "X.Y".
  // Los nombres de área los infiero genéricamente; si el backend los
  // expusiese directamente sería más elegante, pero esto vale para v0.2.
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
    const clave = c.id.split('.').slice(0, 2).join('.');
    const etiqueta = nombres[clave] || ((estado.idioma === 'en' ? 'Area ' : 'Área ') + clave);
    if (!mapa.has(etiqueta)) mapa.set(etiqueta, []);
    mapa.get(etiqueta).push(c);
  }
  return mapa;
}

function crearElementoCampo(c) {
  const tpl = $('plantilla-campo');
  const nodo = tpl.content.cloneNode(true).firstElementChild;

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

  // Evidencia
  if (c.evidencia) {
    const ev = nodo.querySelector('.campo-evidencia');
    ev.style.display = 'block';
    ev.textContent = '«' + c.evidencia + '»';
  }

  // Copiar
  const btn = nodo.querySelector('.boton-copiar');
  btn.title = t('copy.title');
  btn.addEventListener('click', () => copiarTexto(btn, valorEl.value));

  return nodo;
}

function ajustarAlturasCamposVisibles() {
  document.querySelectorAll('.campo-valor').forEach(ajustarAlturaTextarea);
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

  const div = document.createElement('div');
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


/* =============================================================================
   8. Copia al portapapeles
   ========================================================================== */

async function copiarTexto(boton, texto) {
  if (!texto) {
    toast(t('copy.empty'));
    return;
  }
  try {
    await navigator.clipboard.writeText(texto);
    boton.classList.add('copiado');
    boton.querySelector('.icono-copiar').style.display = 'none';
    boton.querySelector('.icono-ok').style.display = 'block';
    setTimeout(() => {
      boton.classList.remove('copiado');
      boton.querySelector('.icono-copiar').style.display = 'block';
      boton.querySelector('.icono-ok').style.display = 'none';
    }, 1500);
  } catch (err) {
    // Fallback para contextos sin permisos de clipboard (ej. HTTP sin TLS)
    try {
      const ta = document.createElement('textarea');
      ta.value = texto;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      boton.classList.add('copiado');
      setTimeout(() => boton.classList.remove('copiado'), 1500);
    } catch {
      toast(t('copy.error'), 'error');
    }
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

  // Sincronizar los valores editados en la UI con la estructura en memoria
  // (los cambios en los textarea ya están en estado.campos por el listener
  // de 'change'; aquí forzamos por si algún navegador no lo disparó).
  document.querySelectorAll('.campo').forEach((elCampo, i) => {
    const ta = elCampo.querySelector('.campo-valor');
    if (ta && estado.campos[i]) {
      const valorActual = ta.value;
      if (valorActual !== (estado.campos[i].valor || '')) {
        estado.campos[i].valor = valorActual;
      }
    }
  });

  // Actualizar los campos en la propuesta
  estado.propuestaActual.propuesta.campos = estado.campos;

  try {
    const r = await fetchProtegido('/api/exportar/' + formato, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(estado.propuestaActual),
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
    const a = document.createElement('a');
    a.href = url;
    a.download = nombre;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);

    toast(t('export.downloaded', { nombre }), 'ok');
  } catch (err) {
    console.error('Error exportando:', err);
    toast(t('export.error', { mensaje: err.message }), 'error');
  }
}

function actualizarBotonesExportacion() {
  // Mostrar EAD solo para ISAD(G), EAC-CPF solo para ISAAR(CPF).
  // JSON y CSV están siempre disponibles.
  const esIsad = estado.normaActual === 'isad-g';
  const esIsaar = estado.normaActual === 'isaar-cpf';

  const botonEad = $('boton-exportar-ead');
  const botonEac = $('boton-exportar-eac');

  botonEad.style.display = esIsad ? '' : 'none';
  botonEac.style.display = esIsaar ? '' : 'none';
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

      // Clonar estilos al documento PiP
      [...document.styleSheets].forEach(ss => {
        try {
          const reglas = [...ss.cssRules].map(r => r.cssText).join('');
          const style = document.createElement('style');
          style.textContent = reglas;
          pipWindow.document.head.appendChild(style);
        } catch {
          // Estilos de orígenes cruzados: copiamos el <link>
          const link = document.createElement('link');
          link.rel = 'stylesheet';
          link.href = ss.href;
          pipWindow.document.head.appendChild(link);
        }
      });

      // Copiar las fuentes externas
      document.querySelectorAll('link[rel="stylesheet"]').forEach(l => {
        const copia = l.cloneNode(true);
        pipWindow.document.head.appendChild(copia);
      });

      // Mover el contenido principal a la ventana PiP
      const main = document.body;
      const marcador = document.createElement('div');
      marcador.id = '__pip_marcador__';
      main.parentNode.insertBefore(marcador, main);
      pipWindow.document.body.appendChild(main);

      // Al cerrar la PiP, devolver el contenido al documento original
      pipWindow.addEventListener('pagehide', () => {
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

function toast(mensaje, tipo = '') {
  const t = document.createElement('div');
  t.className = 'toast ' + tipo;
  t.textContent = mensaje;
  $('toasts').appendChild(t);
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
  document.querySelectorAll('.modo').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modo').forEach(b => b.classList.remove('activo'));
      btn.classList.add('activo');
      estado.modoActual = btn.dataset.modo;
      if (estado.propuestaActual) renderCampos();
    });
  });

  // Botones de exportación
  $('boton-exportar-json').addEventListener('click', () => exportar('json'));
  $('boton-exportar-csv').addEventListener('click', () => exportar('csv'));
  $('boton-exportar-ead').addEventListener('click', () => exportar('ead'));
  $('boton-exportar-eac').addEventListener('click', () => exportar('eac-cpf'));
}

async function main() {
  aplicarIdioma(estado.idioma);

  // Obtener token CSRF lo primero (antes de cualquier otra llamada).
  // Si falla, las peticiones mutadoras posteriores también fallarán,
  // pero fetchProtegido se encargará de reintentar pidiendo el token.
  await obtenerTokenCSRF();

  inicializarDropZone();
  inicializarControles();
  inicializarModoFlotante();
  await esperarMotorYArrancar();
}

document.addEventListener('DOMContentLoaded', main);
