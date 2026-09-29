/* Droid Studio: Blockly is the editor; Python validates and executes commands. */
'use strict';
const $ = id => document.getElementById(id);
const colours = { action: '#858bdc', touch: '#8b7cc9', flow: '#d2a159', device: '#64aaa0', data: '#5899b0', variable: '#b78050' };
const definitions = [
  { type: 'backup_list', group: 'data', colour: '#3f8f7a', label: 'Liste sichern', hint: 'öffnen + screenshotten', message0: 'Sichere Liste als %1 %2 Inhalt %3 höchstens %4 Seiten je Eintrag', args0: [{ type: 'field_input', name: 'NAME', text: 'Sicherung' }, { type: 'input_dummy' }, { type: 'field_dropdown', name: 'ORDER', options: [['vom Ende zum Anfang (Chat)', 'end_to_start'], ['vom Anfang zum Ende (E-Mail)', 'start_to_end']] }, { type: 'field_number', name: 'MAX_PAGES', value: 200, min: 1, max: 2000, precision: 1 }], help: 'Öffnet jeden Eintrag der ausgewählten Liste, blättert ihn vollständig durch und speichert jede Seite als Screenshot mit Bericht und SHA-256-Hashwerten im Fallordner.' },
  { type: 'scan_list', group: 'data', colour: colours.data, label: 'Bildschirmliste aufnehmen', message0: 'Scrolle und speichere Liste %1 %2 Filter %3 %4', args0: [{ type: 'field_input', name: 'NAME', text: 'Bildschirmliste' }, { type: 'input_dummy' }, { type: 'field_dropdown', name: 'BY', options: [['Text enthält', 'textContains'], ['Element-ID', 'resourceId'], ['Elementtyp', 'className']] }, { type: 'field_input', name: 'VALUE', text: '' }], help: 'Scrollt zuerst zum Anfang, dann bis zum Ende. Speichert jeden unterschiedlichen Text einmal. Die Liste bleibt auch nach dem Lauf verfügbar.' },
  { type: 'scroll_find', group: 'action', colour: colours.touch, label: 'Text durch Scrollen suchen', message0: 'Scrolle ab Anfang bis Text %1 %2', args0: [{ type: 'field_input', name: 'VALUE', text: 'Anzeige' }, { type: 'field_dropdown', name: 'MATCH', options: [['genau übereinstimmt', 'exact'], ['enthalten ist', 'contains']] }], help: 'Beginnt ganz oben und scrollt bis zum Text. Ohne Treffer am Ende wird der Ablauf angehalten. Tippt den Treffer nicht an.' },
  { type: 'scroll_find_item', group: 'data', colour: colours.data, label: 'Eintrag durch Scrollen suchen', message0: 'Scrolle ab Anfang bis aktueller Eintrag %1', args0: [{ type: 'field_dropdown', name: 'MATCH', options: [['genau übereinstimmt', 'exact'], ['enthalten ist', 'contains']] }], help: 'In einer Für-jeden-Eintrag-Schleife: sucht den aktuellen Listenwert vom Anfang aus. Danach kann „Eintrag antippen“ folgen.' },
  { type: 'launch', group: 'action', colour: colours.action, label: 'App öffnen', hint: 'Einstellungen', message0: 'Öffne App %1', args0: [{ type: 'field_input', name: 'PACKAGE', text: 'com.android.settings' }] },
  { type: 'click', group: 'action', colour: colours.touch, label: 'Element antippen', hint: 'Text', message0: 'Tippe auf %1 %2', args0: [{ type: 'field_dropdown', name: 'BY', options: [['Text', 'text'], ['Element-ID', 'resourceId'], ['Beschreibung', 'description']] }, { type: 'field_input', name: 'VALUE', text: 'Anzeige' }] },
  { type: 'tap', group: 'action', colour: colours.touch, label: 'Position antippen', message0: 'Tippe bei x %1 %% y %2 %%', args0: [{ type: 'field_number', name: 'X', value: 50, min: 0, max: 100 }, { type: 'field_number', name: 'Y', value: 50, min: 0, max: 100 }] },
  { type: 'type', group: 'action', colour: colours.touch, label: 'Text eingeben', hint: 'Hallo', message0: 'Gib Text ein %1', args0: [{ type: 'field_input', name: 'TEXT', text: 'Hallo Welt' }] },
  { type: 'swipe', group: 'action', colour: colours.touch, label: 'Wischen', hint: 'nach oben', message0: 'Wische %1', args0: [{ type: 'field_dropdown', name: 'DIRECTION', options: [['nach oben', 'up'], ['nach unten', 'down'], ['nach links', 'left'], ['nach rechts', 'right']] }] },
  { type: 'wait', group: 'flow', colour: colours.flow, label: 'Warten', hint: '1 Sek.', message0: 'Warte %1 Sekunden', args0: [{ type: 'field_number', name: 'SECONDS', value: 1, min: 0, max: 3600 }] },
  { type: 'wait_for', group: 'flow', colour: colours.flow, label: 'Auf Element warten', message0: 'Warte auf %1 %2 bis zu %3 Sek.', args0: [{ type: 'field_dropdown', name: 'BY', options: [['Text', 'text'], ['Element-ID', 'resourceId'], ['Beschreibung', 'description']] }, { type: 'field_input', name: 'VALUE', text: 'Anzeige' }, { type: 'field_number', name: 'TIMEOUT', value: 10, min: 0, max: 120 }] },
  { type: 'repeat', group: 'flow', colour: colours.flow, label: 'Wiederholen', hint: '3 mal', message0: 'Wiederhole %1 mal %2 %3', args0: [{ type: 'field_number', name: 'TIMES', value: 3, min: 1, max: 100, precision: 1 }, { type: 'input_dummy' }, { type: 'input_statement', name: 'BODY' }] },
  { type: 'if_exists', group: 'flow', colour: colours.flow, label: 'Wenn Element da ist', message0: 'Wenn %1 %2 sichtbar ist %3 dann %4 sonst %5', args0: [{ type: 'field_dropdown', name: 'BY', options: [['Text', 'text'], ['Element-ID', 'resourceId'], ['Beschreibung', 'description']] }, { type: 'field_input', name: 'VALUE', text: 'Anzeige' }, { type: 'input_dummy' }, { type: 'input_statement', name: 'BODY' }, { type: 'input_statement', name: 'OTHERWISE' }] },
  { type: 'list_create', group: 'data', colour: colours.data, label: 'Liste erstellen', message0: 'Liste %1 mit %2', args0: [{ type: 'field_input', name: 'NAME', text: 'Werte' }, { type: 'field_input', name: 'ITEMS', text: 'Anzeige; Akku; Apps' }], help: 'Werte mit Semikolon trennen. Mit dem Stift kannst du sie zeilenweise bearbeiten. Leere Einträge werden ausgelassen.' },
  { type: 'read_list', group: 'data', colour: colours.data, label: 'Listentexte lesen', message0: 'Lese sichtbare Texte in Liste %1 %2 Filter %3 %4', args0: [{ type: 'field_input', name: 'NAME', text: 'Werte' }, { type: 'input_dummy' }, { type: 'field_dropdown', name: 'BY', options: [['Text enthält', 'textContains'], ['Element-ID', 'resourceId'], ['Elementtyp', 'className']] }, { type: 'field_input', name: 'VALUE', text: '' }], help: 'Liest Texte der aktuell sichtbaren Elemente, ohne zu scrollen. „Text enthält“ leer lassen, um alle sichtbaren Texte zu lesen. Doppelte Werte bleiben erhalten.' },
  { type: 'for_each', group: 'data', colour: colours.data, label: 'Für jeden Eintrag', message0: 'Für jeden Eintrag in Liste %1 %2 %3', args0: [{ type: 'field_input', name: 'NAME', text: 'Werte' }, { type: 'input_dummy' }, { type: 'input_statement', name: 'BODY' }], help: 'Stecke Befehle in diese Schleife. „Aktueller Eintrag“ bezieht sich auf den Wert dieses Durchlaufs. Der Listenname muss mit dem Erstellen-/Lesen-Baustein übereinstimmen.' },
  { type: 'type_item', group: 'data', colour: colours.data, label: 'Eintrag eingeben', message0: 'Gib aktuellen Eintrag als Text ein', help: 'Innerhalb einer Für-jeden-Eintrag-Schleife: schreibt den aktuellen Wert in das fokussierte Eingabefeld.' },
  { type: 'click_item', group: 'data', colour: colours.data, label: 'Eintrag antippen', message0: 'Tippe auf %1 aktueller Eintrag', args0: [{ type: 'field_dropdown', name: 'BY', options: [['Text', 'text'], ['Element-ID', 'resourceId'], ['Beschreibung', 'description']] }], help: 'Innerhalb einer Für-jeden-Eintrag-Schleife: sucht das Element mit dem aktuellen Listenwert und tippt es an.' },
  { type: 'press', group: 'device', colour: colours.device, label: 'Gerätetaste drücken', message0: 'Drücke %1', args0: [{ type: 'field_dropdown', name: 'KEY', options: [['Zurück', 'back'], ['Home', 'home'], ['Letzte Apps', 'recent'], ['Enter', 'enter'], ['Lauter', 'volume_up'], ['Leiser', 'volume_down']] }] },
  { type: 'screenshot', group: 'device', colour: colours.device, label: 'Screenshot auf PC speichern', message0: 'Speichere Screenshot auf PC', help: 'Speichert das aktuelle Gerätebild im Ordner outputs auf deinem PC. Das Protokoll zeigt den Speicherort und einen Link zum Bild.' },
];
definitions.push(
  { type: 'var_set', group: 'variable', colour: colours.variable, label: 'Variable setzen', message0: 'Setze %1 auf %2', args0: [{type:'field_input',name:'NAME',text:'Wert'}, {type:'input_value',name:'VALUE',check:['String','Number']}], help: 'Speichert Text oder eine Zahl unter diesem Namen. Der Wert gilt für den aktuellen Lauf.' },
  { type: 'var_change', group: 'variable', colour: colours.variable, label: 'Variable ändern', message0: 'Ändere %1 um %2', args0: [{type:'field_input',name:'NAME',text:'Zähler'}, {type:'input_value',name:'AMOUNT',check:'Number'}], help: 'Addiert eine Zahl zu einer zuvor gesetzten Zahlenvariable. Negative Zahlen ziehen etwas ab.' },
  { type: 'var_get', group: 'variable', colour: colours.variable, label: 'Variablenwert', output: null, message0:'Wert von %1', args0:[{type:'field_input',name:'NAME',text:'Wert'}], help:'In einen Werteingang stecken. Der Name muss zu einer zuvor gesetzten Variablen passen.' },
  { type: 'value_text', group:'variable', colour:colours.variable, label:'Textwert', output:'String', message0:'Text %1', args0:[{type:'field_input',name:'TEXT',text:'Hallo'}] },
  { type:'value_number', group:'variable', colour:colours.variable, label:'Zahlenwert', output:'Number', message0:'Zahl %1', args0:[{type:'field_number',name:'NUMBER',value:1,min:-1e12,max:1e12}] },
  { type:'value_item', group:'variable', colour:colours.data, label:'Aktueller Listeneintrag', output:'String', message0:'aktueller Listeneintrag', help:'Wert des aktuellen Durchlaufs einer Für-jeden-Eintrag-Schleife.' }
);
const valueInputs = {
  type: [['TEXT','Eingabetext','String']], click: [['VALUE','Suchwert','String']], wait_for: [['VALUE','Suchwert','String'],['TIMEOUT','Zeitlimit','Number']],
  if_exists: [['VALUE','Suchwert','String']], scroll_find: [['VALUE','Suchtext','String']], read_list: [['VALUE','Listenfilter','String']], scan_list: [['VALUE','Listenfilter','String']],
  wait: [['SECONDS','Sekunden','Number']], repeat: [['TIMES','Anzahl','Number']]
};
definitions.sort((a, b) => ['action', 'flow', 'data', 'variable', 'device'].indexOf(a.group) - ['action', 'flow', 'data', 'variable', 'device'].indexOf(b.group));
let workspace, token, state, category = 'all', picking = false, elements = [], screenUrl;
let autosaveTimer, toastTimer, lastLogs = '', screenBusy = false, changingDevice = false, screenRevision = 0;
let capturePending = null, backupPending = false;
let runControlPending = false;
let lastSelectedBlockId = null;
let capturePicker, backupPicker, captureBlock = null, backupBlock = null;
let libraryData = null, librarySelection = null, libraryTimer = null, caseEditing = null;
const STORAGE = 'droid-studio-project-v1';
const APP_VERSION = 2; // must match APP_VERSION in automator/server.py
const appChoices = [['Einstellungen', 'com.android.settings'], ['Chrome', 'com.android.chrome'], ['YouTube', 'com.google.android.youtube'], ['WhatsApp', 'com.whatsapp']];
function rememberApp(packageName, label) { if (!appChoices.some(option => option[1] === packageName)) appChoices.push([label || packageName.split('.').pop(), packageName]); }

function toast(message, error = false, sticky = false) {
  $('toast').textContent = message; $('toast').classList.toggle('error', error); $('toast').hidden = false;
  clearTimeout(toastTimer); if (!sticky) toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 6500 : 3300);
}
// Startup problems must stay visible; otherwise the page just looks empty.
function fatal(message) {
  toast(message, true, true);
  $('screenError').textContent = message; $('screenError').hidden = false;
}

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Studio-Token': token }, body: JSON.stringify(body) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Die Anfrage ist fehlgeschlagen.');
  return result;
}

function isRunning() { return state && ['running', 'paused', 'stopping'].includes(state.run.status); }
function bind(id, handler) {
  $(id).addEventListener('click', async () => { try { await handler(); } catch (error) { toast(error.message, true); } });
}

function defineStudioBlocks() {
  Blockly.defineBlocksWithJsonArray([
    { type: 'start', message0: 'Wenn gestartet', nextStatement: null, colour: '#a788cc', hat: 'cap', tooltip: 'Alle verbundenen Bausteine werden nacheinander ausgeführt.' },
    ...definitions.map(({ group, label, hint, help, ...definition }) => ({ ...definition, ...(Object.hasOwn(definition, 'output') ? {} : {previousStatement: null, nextStatement: null}), inputsInline: true, tooltip: help || label }))
  ]);
  const initList = Blockly.Blocks.list_create.init;
  const initScan = Blockly.Blocks.scan_list.init;
  Blockly.Blocks.scan_list.init = function () {
    initScan.call(this);
    const icon = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="3" fill="none" stroke="white" stroke-width="2"/><path d="M6 12h12M12 6v12" stroke="white" stroke-width="2"/></svg>');
    this.appendDummyInput().appendField(new Blockly.FieldImage(icon, 20, 20, 'Listenelement auswählen', () => openCapture(this))).appendField(new Blockly.FieldLabelSerializable('Textfilter'), 'PATTERN_HINT');
    this.customContextMenu = options => options.push({ text: 'Listenelement auswählen …', enabled: !isRunning(), callback: () => openCapture(this) });
  };
  Blockly.Blocks.scan_list.saveExtraState = function () { return { pattern: this.itemPattern || null }; };
  Blockly.Blocks.scan_list.loadExtraState = function (extra) { this.itemPattern = extra.pattern || null; this.setFieldValue(this.itemPattern ? 'Eintragsmuster' : 'Textfilter', 'PATTERN_HINT'); };
  const initBackup = Blockly.Blocks.backup_list.init;
  Blockly.Blocks.backup_list.init = function () {
    initBackup.call(this);
    const icon = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="3" fill="none" stroke="white" stroke-width="2"/><path d="M6 12h12M12 6v12" stroke="white" stroke-width="2"/></svg>');
    this.appendDummyInput().appendField(new Blockly.FieldImage(icon, 20, 20, 'Listeneintrag auswählen', () => openBackup(this))).appendField(new Blockly.FieldLabelSerializable('Listeneintrag fehlt – hier auswählen'), 'PATTERN_HINT');
    this.customContextMenu = options => options.push({ text: 'Listeneintrag auswählen …', enabled: !isRunning(), callback: () => openBackup(this) });
  };
  Blockly.Blocks.backup_list.saveExtraState = function () { return { pattern: this.itemPattern || null }; };
  Blockly.Blocks.backup_list.loadExtraState = function (extra) { this.itemPattern = extra.pattern || null; this.setFieldValue(this.itemPattern ? 'Listeneintrag gewählt' : 'Listeneintrag fehlt – hier auswählen', 'PATTERN_HINT'); };
  for (const [type, inputs] of Object.entries(valueInputs)) {
    const original = Blockly.Blocks[type].init;
    Blockly.Blocks[type].init = function () {
      original.call(this);
      for (const [field, label, check] of inputs) {
        this.appendValueInput(`${field}_VALUE`).setCheck(check === 'String' ? ['String','Number'] : 'Number').appendField(`${label} stattdessen`);
        if (this.getInput('BODY')) this.moveInputBefore(`${field}_VALUE`, 'BODY');
      }
      this.setTooltip((definitions.find(d => d.type === type).help || definitions.find(d => d.type === type).label) + ' Ein eingesteckter Wert ersetzt das entsprechende feste Feld. Leere Werteingänge sind optional.');
    };
  }
  Blockly.Blocks.list_create.init = function () {
    initList.call(this);
    const pencil = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="m4 16 12-12 4 4-12 12H4zm10-10 4 4" fill="none" stroke="white" stroke-width="2"/></svg>');
    this.appendDummyInput().appendField(new Blockly.FieldImage(pencil, 20, 20, 'Listenwerte bearbeiten', () => editList(this)));
    this.customContextMenu = options => options.push({ text: 'Listenwerte bearbeiten …', enabled: !isRunning(), callback: () => editList(this) });
  };
  Blockly.Blocks.launch = {
    init() {
      this.appendDummyInput().appendField('Öffne App').appendField(new Blockly.FieldDropdown(() => appChoices.map(option => [...option])), 'PACKAGE');
      this.setPreviousStatement(true); this.setNextStatement(true); this.setColour(colours.action);
      this.setTooltip('Wähle eine App oder nutze „Geöffnete App übernehmen“ unter der Geräteansicht.');
    },
    saveExtraState() { return { package: this.getFieldValue('PACKAGE'), label: this.getField('PACKAGE').getText() }; },
    loadExtraState(extra) { if (typeof extra.package === 'string' && typeof extra.label === 'string') rememberApp(extra.package, extra.label); }
  };
}

function initBlockly() {
  defineStudioBlocks();
  document.querySelector('.count-badge').textContent = definitions.length;
  const theme = Blockly.Theme.defineTheme('droid', { base: Blockly.Themes.Classic, componentStyles: { workspaceBackgroundColour: '#fcfcfe', scrollbarColour: '#d9dce7', insertionMarkerColour: '#c5b2f0', insertionMarkerOpacity: 0.5 }, fontStyle: { family: 'Segoe UI, sans-serif', weight: '500', size: 12 }, startHats: true });
  workspace = Blockly.inject('blockly', { renderer: 'zelos', theme, media: '/vendor/media/', sounds: false, trashcan: true, maxBlocks: 501, grid: { spacing: 20, length: 1.5, colour: '#dfe1eb', snap: true }, zoom: { controls: true, wheel: true, startScale: 0.88, maxScale: 1.4, minScale: 0.35, scaleSpeed: 1.1 }, move: { scrollbars: true, drag: true, wheel: true } });
  new ResizeObserver(() => Blockly.svgResize(workspace)).observe($('blockly'));
  workspace.addChangeListener(event => {
    if (event.type === Blockly.Events.SELECTED && event.newElementId && workspace.getBlockById(event.newElementId)) lastSelectedBlockId = event.newElementId;
    if (event.isUiEvent) return;
    $('blockCount').textContent = `${workspace.getAllBlocks(false).filter(b => b.type !== 'start').length} Bausteine`;
    clearTimeout(autosaveTimer); autosaveTimer = setTimeout(saveDraft, 350);
  });
  $('blockly').addEventListener('dragover', event => { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; });
  $('blockly').addEventListener('drop', event => {
    event.preventDefault(); if (isRunning()) return;
    const type = event.dataTransfer.getData('application/x-droid-block');
    if (!definitions.some(definition => definition.type === type)) return;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(workspace.getCanvas().getScreenCTM().inverse());
    const block = addBlock(type, {}, point);
    if (type === 'backup_list') openBackup(block);
  });
}

// A block dropped from the palette docks like a dragged Blockly block when it lands near a connection.
function snapToNeighbour(block) {
  const connection = block.previousConnection || block.outputConnection;
  const found = connection?.closest(Blockly.config.snapRadius * 2, new Blockly.utils.Coordinate(0, 0));
  if (found?.connection) found.connection.connect(connection);
  return Boolean(found?.connection);
}

function selectBlock(block) {
  // Blockly 12 selects through focus; block.select() alone leaves stale highlights behind.
  if (Blockly.getFocusManager) Blockly.getFocusManager().focusNode(block); else block.select();
  lastSelectedBlockId = block.id;
}

function showStart() {
  const start = workspace.getTopBlocks(true).find(block => block.type === 'start');
  if (!start) { workspace.scrollCenter(); return; }
  const xy = start.getRelativeToSurfaceXY();
  workspace.scroll(32 - xy.x * workspace.scale, 32 - xy.y * workspace.scale);
}

function renderPalette() {
  const query = $('blockSearch').value.toLowerCase();
  $('paletteItems').replaceChildren();
  $('listHelp').hidden = category !== 'data';
  $('variableHelp').hidden = category !== 'variable';
  let lastGroup = '';
  for (const def of definitions) {
    if (category !== 'all' && (category === 'action' ? !['action', 'device'].includes(def.group) : def.group !== category)) continue;
    if (!`${def.label} ${def.hint || ''}`.toLowerCase().includes(query)) continue;
    if (def.group !== lastGroup) {
      const label = document.createElement('div'); label.className = 'palette-group';
      label.textContent = { action: 'APPS & INTERAKTION', flow: 'ABLAUF & LOGIK', data: 'LISTEN & EINTRÄGE', variable: 'VARIABLEN & WERTE', device: 'GERÄT' }[def.group];
      $('paletteItems').append(label); lastGroup = def.group;
    }
    const button = document.createElement('button'); button.className = 'block-card'; button.draggable = true; button.dataset.type = def.type;
    button.style.setProperty('--block-colour', def.colour); button.append(document.createTextNode(def.label));
    button.title = `${def.label}: klicken zum Anhängen oder auf die Fläche ziehen`;
    if (def.hint) { const hint = document.createElement('span'); hint.className = 'mini'; hint.textContent = def.hint; button.append(hint); }
    button.addEventListener('click', () => { if (isRunning()) return; const block = addBlock(def.type); if (def.type === 'backup_list') openBackup(block); });
    button.addEventListener('dragstart', event => { event.dataTransfer.setData('application/x-droid-block', def.type); event.dataTransfer.effectAllowed = 'copy'; });
    $('paletteItems').append(button);
  }
  if (!$('paletteItems').children.length) { const empty = document.createElement('p'); empty.className = 'no-results'; empty.textContent = 'Kein passender Baustein gefunden.'; $('paletteItems').append(empty); }
}

function addBlock(type, fields = {}, position) {
  Blockly.Events.setGroup(true);
  try {
    const selected = Blockly.getSelected() || workspace.getBlockById(lastSelectedBlockId || '');
    const block = workspace.newBlock(type);
    for (const [key, value] of Object.entries(fields)) block.setFieldValue(String(value), key);
    block.initSvg(); block.render();
    if (type === 'var_set') block.getInput('VALUE').connection.setShadowState({type:'value_text',fields:{TEXT:'Hallo'}});
    if (type === 'var_change') block.getInput('AMOUNT').connection.setShadowState({type:'value_number',fields:{NUMBER:1}});
    if (position) { block.moveBy(position.x, position.y); snapToNeighbour(block); }
    else if (block.outputConnection) {
      const input = selected?.inputList?.find(input => input.connection && input.type === Blockly.inputs.inputTypes.VALUE && (!input.connection.targetBlock() || input.connection.targetBlock().isShadow()) && workspace.connectionChecker.canConnect(block.outputConnection, input.connection, false));
      if (input) input.connection.connect(block.outputConnection);
      else { block.moveBy(70, 110); toast('Ziehe den Wertbaustein in einen passenden Werteingang.'); }
    }
    else {
      let tail = workspace.getTopBlocks(true).find(b => b.type === 'start');
      if (!tail) { tail = workspace.newBlock('start'); tail.initSvg(); tail.render(); tail.moveBy(45, 70); tail.setDeletable(false); }
      while (tail.getNextBlock()) tail = tail.getNextBlock();
      if (tail.nextConnection && block.previousConnection) tail.nextConnection.connect(block.previousConnection);
      else block.moveBy(60, 100);
    }
    selectBlock(block);
    return block;
  } finally { Blockly.Events.setGroup(false); }
}

function initialProject(example = true) {
  workspace.clear();
  const start = workspace.newBlock('start'); start.initSvg(); start.render(); start.moveBy(47, 76); start.setDeletable(false);
  if (example) { addBlock('launch'); addBlock('wait'); addBlock('click'); addBlock('screenshot'); }
  showStart();
  $('projectName').value = example ? 'Mein erster Ablauf' : 'Neuer Ablauf';
  saveDraft();
}

function programFromWorkspace() {
  const top = workspace.getTopBlocks(true).filter(b => b.isEnabled());
  const starts = top.filter(b => b.type === 'start');
  if (starts.length !== 1) throw new Error('Der Ablauf braucht genau einen Startblock.');
  if (top.some(b => b.type !== 'start')) throw new Error('Es gibt lose Bausteine. Verbinde sie mit dem Startblock oder entferne sie.');
  function valueOf(block) {
    if (!block || !block.isEnabled()) throw new Error('Bitte einen Wert in den Variablen-Baustein einsetzen.');
    if (block.type === 'var_get') return {source:'variable',name:block.getFieldValue('NAME')};
    if (block.type === 'value_item') return {source:'item'};
    if (block.type === 'value_text') return block.getFieldValue('TEXT');
    if (block.type === 'value_number') return Number(block.getFieldValue('NUMBER'));
    throw new Error('Dieser Baustein liefert keinen verwendbaren Wert.');
  }
  function chain(block) {
    const result = [];
    for (; block; block = block.getNextBlock()) {
      if (!block.isEnabled()) continue;
      const node = { op: block.type, id: block.id };
      const field = key => block.getInputTargetBlock(`${key}_VALUE`) ? valueOf(block.getInputTargetBlock(`${key}_VALUE`)) : block.getFieldValue(key);
      const numeric = key => { const value = field(key); return typeof value === 'object' ? value : Number(value); };
      const textual = key => { const value = field(key); return typeof value === 'number' ? String(value) : value; };
      if (['click', 'wait_for', 'if_exists'].includes(block.type)) Object.assign(node, { by: field('BY'), value: textual('VALUE') });
      switch (block.type) {
        case 'launch': node.package = field('PACKAGE'); break;
        case 'tap': node.x = Number(field('X')) / 100; node.y = Number(field('Y')) / 100; break;
        case 'type': node.text = textual('TEXT'); break;
        case 'var_set': node.name = field('NAME'); node.value = valueOf(block.getInputTargetBlock('VALUE')); break;
        case 'var_change': node.name = field('NAME'); node.amount = valueOf(block.getInputTargetBlock('AMOUNT')); break;
        case 'type_item': node.op = 'type'; node.text = { source: 'item' }; break;
        case 'click_item': node.op = 'click'; node.by = field('BY'); node.value = { source: 'item' }; node.timeout = 10; break;
        case 'list_create': node.name = field('NAME'); node.items = listItems(field('ITEMS')); break;
        case 'backup_list': node.name = field('NAME'); node.order = field('ORDER'); node.max_pages = Number(field('MAX_PAGES')); if (block.itemPattern) node.pattern = block.itemPattern; break;
        case 'scan_list': node.name = field('NAME'); node.by = block.itemPattern ? 'textContains' : field('BY'); node.value = block.itemPattern ? '' : textual('VALUE'); if (block.itemPattern) node.pattern = block.itemPattern; break;
        case 'read_list': node.name = field('NAME'); node.by = field('BY'); node.value = textual('VALUE'); break;
        case 'scroll_find': node.value = textual('VALUE'); node.match = field('MATCH'); break;
        case 'scroll_find_item': node.op = 'scroll_find'; node.value = { source: 'item' }; node.match = field('MATCH'); break;
        case 'for_each': node.name = field('NAME'); node.body = chain(block.getInputTargetBlock('BODY')); break;
        case 'wait': node.seconds = numeric('SECONDS'); break;
        case 'click': node.timeout = 10; break;
        case 'wait_for': node.timeout = numeric('TIMEOUT'); break;
        case 'swipe': node.direction = field('DIRECTION'); break;
        case 'press': node.key = field('KEY'); break;
        case 'repeat': node.times = numeric('TIMES'); node.body = chain(block.getInputTargetBlock('BODY')); break;
        case 'if_exists': node.body = chain(block.getInputTargetBlock('BODY')); node.otherwise = chain(block.getInputTargetBlock('OTHERWISE')); break;
      }
      result.push(node);
    }
    return result;
  }
  return chain(starts[0].getNextBlock());
}

function project() { return { format: 'droid-studio', version: 1, name: $('projectName').value || 'Mein Ablauf', workspace: Blockly.serialization.workspaces.save(workspace) }; }
function saveDraft() {
  try { localStorage.setItem(STORAGE, JSON.stringify(project())); $('saveState').textContent = 'Entwurf im Browser gespeichert'; }
  catch { $('saveState').textContent = 'Bitte als Datei speichern'; }
}
function loadProject(data) {
  if (data.format !== 'droid-studio' || data.version !== 1 || !data.workspace || typeof data.name !== 'string') throw new Error('Diese Datei ist kein gültiges Droid-Studio-Projekt.');
  // Load into a temporary workspace first, so malformed files cannot destroy the current draft.
  const temporary = new Blockly.Workspace();
  try {
    Blockly.serialization.workspaces.load(data.workspace, temporary);
    if (temporary.getAllBlocks(false).length > 501 || temporary.getTopBlocks(false).filter(b => b.type === 'start').length !== 1 || temporary.getAllBlocks(false).some(b => b.type !== 'start' && !definitions.some(d => d.type === b.type))) throw new Error('Projekt enthält zu viele oder ungültige Bausteine.');
  } finally { temporary.dispose(); }
  Blockly.serialization.workspaces.load(data.workspace, workspace);
  for (const block of workspace.getAllBlocks(false)) if (block.type === 'start') block.setDeletable(false);
  $('projectName').value = data.name.slice(0, 80); showStart(); saveDraft();
}
function download(text, filename, mime) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function filename(extension) { return ($('projectName').value.replace(/[^\p{L}\p{N}_-]+/gu, '-').slice(0, 70) || 'ablauf') + extension; }
function listItems(text) { return text.split(/[;\r\n]+/).map(value => value.trim()).filter(Boolean); }
function editList(block) {
  if (isRunning()) return;
  $('listValues').value = listItems(block.getFieldValue('ITEMS')).join('\n');
  $('listEditorTitle').textContent = `Liste „${block.getFieldValue('NAME')}“`;
  $('listApply').onclick = () => {
    if (isRunning()) { toast('Bitte zuerst den Ablauf stoppen.', true); return; }
    const values = listItems($('listValues').value);
    if (values.length > 500 || values.some(value => value.length > 2000)) { toast('Maximal 500 Einträge mit jeweils 2000 Zeichen sind erlaubt.', true); return; }
    if (!workspace.getBlockById(block.id)) { $('listDialog').close(); return; }
    block.setFieldValue(values.join('; '), 'ITEMS');
    $('listDialog').close(); saveDraft();
  };
  $('listDialog').showModal(); $('listValues').focus();
}
function confirmReplace() {
  return new Promise(resolve => {
    const dialog = $('replaceDialog');
    const finish = answer => { dialog.close(); resolve(answer); };
    $('replaceCancel').onclick = () => finish(false);
    $('replaceAccept').onclick = () => finish(true);
    dialog.oncancel = event => { event.preventDefault(); finish(false); };
    dialog.showModal();
  });
}

function renderState(next) {
  state = next;
  const variableRows = Object.entries(next.run.variables || {});
  const variableKey = JSON.stringify(variableRows);
  if ($('variableValues').dataset.values !== variableKey) {
    $('variableValues').dataset.values = variableKey; $('variableValues').replaceChildren();
    if (!variableRows.length) $('variableValues').textContent = 'Noch keine Variablen gesetzt.';
    for (const [name, value] of variableRows) {
      const row = document.createElement('span'); row.className = 'variable-value'; row.textContent = `${name} = ${typeof value === 'string' ? `„${value}“` : value}`; $('variableValues').append(row);
    }
  }
  const running = isRunning();
  const paused = next.run.status === 'paused';
  document.body.classList.toggle('running', running);
  for (const id of ['runButton', 'connectButton', 'newButton', 'openButton', 'exampleButton', 'listExampleButton', 'variableExampleButton', 'pickButton', 'undoButton', 'inspectorButton', 'currentAppButton', 'backupButton', 'caseButton']) $(id).disabled = running;
  updateCaptureReady(); updateBackupReady();
  $('caseTitle').textContent = next.case.title; $('caseExaminer').textContent = next.case.examiner || '';
  const backup = running ? next.run.backup : null;
  if (capturePending && !running) {
    const name = capturePending; capturePending = null;
    if (next.run.status === 'completed') openLibrary({ kind: 'list', id: name }).catch(error => toast(error.message, true));
  }
  if (backupPending && !running) {
    backupPending = false;
    if (next.run.backup) openLibrary({ kind: 'backup', id: next.run.backup.id }).catch(error => toast(error.message, true));
  }
  if (running && $('libraryDialog').open && !libraryTimer) scheduleLibraryRefresh();
  $('stopButton').disabled = !running || next.run.status === 'stopping';
  for (const button of document.querySelectorAll('.android-nav button')) button.disabled = running;
  $('runButton').lastChild.textContent = paused ? 'Fortsetzen' : running ? 'Läuft …' : 'Starten';
  $('runButton').disabled = runControlPending || (running && !paused);
  $('stepButton').textContent = running ? (backup ? 'Nächster Eintrag' : 'Nächster Schritt') : 'Schrittweise';
  $('stepButton').disabled = runControlPending || (running && !paused);
  $('pauseButton').hidden = !running || paused;
  $('pauseButton').disabled = runControlPending || next.run.status !== 'running' || next.run.step_mode;
  $('pauseButton').textContent = next.run.step_mode ? (backup ? 'Hält nach diesem Eintrag …' : 'Hält vor nächstem Befehl …') : 'Pause';
  $('stepInfo').hidden = !running;
  $('stepInfo').textContent = backup
    ? `Sicherung „${backup.name}“ · Eintrag ${backup.entry || '–'}${backup.text ? `: „${backup.text}“` : ''} · Seite ${backup.page} · ${backup.saved} gesichert${backup.problems ? ` · ${backup.problems} mit Hinweis` : ''}${paused ? ' · Angehalten. „Fortsetzen“ sichert weiter, „Nächster Eintrag“ nur einen.' : ''}`
    : `${paused ? 'Nächster Befehl' : 'Aktueller Befehl'}: ${next.run.active_label || 'Vorbereitung'}${next.run.current_item != null ? ` · Listeneintrag: „${next.run.current_item}“` : ''}${paused ? ' · Mit „Nächster Schritt“ ausführen.' : ''}`;
  $('deviceName').textContent = next.device.name;
  $('deviceDetail').textContent = next.device.demo ? 'Ohne Smartphone ausprobieren' : next.device.serial;
  $('liveBadge').classList.toggle('real', !next.device.demo);
  $('liveBadge').lastChild.textContent = next.device.demo ? ' DEMO' : ' LIVE';
  $('viewLabel').textContent = next.device.demo ? 'Vorschau' : 'Bildschirm · 1 Bild/s';
  $('footerConnection').textContent = next.device.demo ? 'Demo-Modus · Kein Gerät verbunden' : `Verbunden · ${next.device.serial}`;
  const status = { idle: 'Bereit', running: 'Läuft', paused: backup ? 'Angehalten' : 'Schritt bereit', stopping: 'Wird gestoppt', completed: 'Abgeschlossen', stopped: 'Gestoppt', error: 'Fehler' }[next.run.status];
  $('runStatus').textContent = status; $('runStatus').className = `status-badge ${next.run.status}`;
  $('elapsed').textContent = next.run.status === 'idle' ? 'Noch kein Lauf' : `${next.run.steps} Schritte · ${next.run.elapsed.toFixed(1)} s`;
  workspace.highlightBlock(next.run.active_id);
  const logs = JSON.stringify(next.run.logs);
  if (logs !== lastLogs && next.run.logs.length) {
    lastLogs = logs; $('logs').replaceChildren();
    for (const item of next.run.logs) {
      const line = document.createElement('div'); line.className = `log-line ${item.level}`;
      const time = document.createElement('span'); time.className = 'log-time'; time.textContent = item.time;
      const text = document.createElement('span'); text.textContent = item.text;
      line.append(time, text);
      if (item.artifact) { const link = document.createElement('a'); link.href = item.artifact; link.textContent = 'Öffnen ↗'; link.target = '_blank'; link.rel = 'noopener'; line.append(link); }
      $('logs').append(line);
    }
    $('logs').scrollTop = $('logs').scrollHeight;
  }
}

function el(tag, className = '', text = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}
function formatTime(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'medium' });
}
function caseLabel(item) { return item ? `${item.title}${item.examiner ? ` · ${item.examiner}` : ''}` : ''; }
function encodePath(path) { return path.split('/').map(encodeURIComponent).join('/'); }
function statusClass(status) { return { abgeschlossen: 'ok', gesichert: 'ok', 'läuft': 'running' }[status] || 'problem'; }
function confirmAction({ title, text, accept = 'OK', danger = false, input = null }) {
  return new Promise(resolve => {
    const dialog = $('confirmDialog');
    $('confirmTitle').textContent = title; $('confirmText').textContent = text;
    $('confirmAccept').textContent = accept; $('confirmAccept').classList.toggle('danger', danger);
    $('confirmLabel').hidden = $('confirmInput').hidden = !input;
    if (input) { $('confirmLabel').textContent = input.label; $('confirmInput').value = input.value || ''; }
    const finish = answer => { dialog.close(); resolve(answer); };
    $('confirmCancel').onclick = () => finish(null);
    $('confirmAccept').onclick = () => finish(input ? $('confirmInput').value : true);
    dialog.oncancel = event => { event.preventDefault(); finish(null); };
    dialog.showModal();
    if (input) { $('confirmInput').focus(); $('confirmInput').select(); }
  });
}

/* Device picture in which the user clicks one complete list entry (Liste sichern, Listentexte aufnehmen). */
class ListPicker {
  constructor(prefix, changed) {
    this.prefix = prefix; this.loading = false;
    this.clear(); this.changed = changed;
    this.el('Image').addEventListener('click', event => this.pick(event));
    this.el('Candidate').addEventListener('change', () => this.show());
  }
  el(name) { return $(this.prefix + name); }
  ready() { return Boolean(this.choice) && this.serial === state?.device.serial; }
  clear() {
    this.choice = null; this.candidates = []; this.matches = []; this.serial = null;
    this.el('Selection').hidden = true; this.el('Highlight').hidden = true;
    this.el('Candidate').replaceChildren(); this.el('Candidate').disabled = true; this.el('Preview').replaceChildren();
    this.el('MatchCount').textContent = 'Klicke links im Bild auf einen Eintrag.';
    this.changed?.();
  }
  async load() {
    if (this.loading || isRunning()) return;
    this.loading = true; this.clear();
    const hint = this.el('PickHint'); hint.hidden = false; hint.textContent = 'Lade Gerätebild und Listeneinträge …';
    try {
      const preview = await api('/api/list-preview');
      if (preview.serial !== state.device.serial) throw new Error('Das Gerät wurde gewechselt. Bitte das Bild neu laden.');
      this.candidates = preview.candidates; this.serial = preview.serial;
      this.el('Image').src = preview.image; this.el('Selection').hidden = false;
      hint.textContent = this.candidates.length ? 'Klicke im Bild auf einen Eintrag. Prüfe danach den Rahmen und die Vorschau.' : 'Keine lesbaren Einträge gefunden. Öffne eine Liste auf dem Gerät und lade das Bild erneut.';
      this.el('Pick').textContent = 'Gerätebild neu laden';
    } catch (error) { hint.textContent = error.message; throw error; }
    finally { this.loading = false; this.changed?.(); }
  }
  pick(event) {
    const rect = event.target.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width, y = (event.clientY - rect.top) / rect.height;
    const area = ({ bounds: [x1, y1, x2, y2] }) => (x2 - x1) * (y2 - y1);
    this.matches = this.candidates.filter(({ bounds: [x1, y1, x2, y2] }) => x >= x1 && x <= x2 && y >= y1 && y <= y2);
    this.matches.sort((a, b) => a.depth - b.depth || area(b) - area(a));
    this.el('Candidate').replaceChildren(...this.matches.map((candidate, index) => {
      const option = el('option', '', `${index + 1}. ${candidate.count} passende Einträge · ${candidate.label.replace(/\s+/g, ' ').slice(0, 90)}`); option.value = index; return option;
    }));
    const preferred = this.matches.findIndex(candidate => candidate.count > 1);
    if (this.matches.length) this.el('Candidate').value = String(Math.max(0, preferred));
    this.el('Candidate').disabled = !this.matches.length; this.show();
  }
  show() {
    this.choice = this.matches[Number(this.el('Candidate').value)] || null;
    this.el('Highlight').hidden = !this.choice; this.el('Preview').replaceChildren();
    if (this.choice) {
      const [x1, y1, x2, y2] = this.choice.bounds;
      Object.assign(this.el('Highlight').style, { left: `${x1 * 100}%`, top: `${y1 * 100}%`, width: `${(x2 - x1) * 100}%`, height: `${(y2 - y1) * 100}%` });
      this.el('MatchCount').textContent = `${this.choice.count} passende Einträge im sichtbaren Bereich · Vorschau der ersten ${this.choice.preview.length}`;
      this.el('Preview').append(...this.choice.preview.map(value => el('li', '', value)));
    } else this.el('MatchCount').textContent = 'Hier wurde kein lesbarer Listeneintrag erkannt. Wähle einen anderen Bereich.';
    this.changed?.();
  }
}

function updateCaptureReady() {
  if (!capturePicker) return;
  $('captureStart').disabled = isRunning() || capturePicker.loading || ($('captureMode').value === 'items' && !capturePicker.ready());
  $('capturePick').disabled = isRunning() || capturePicker.loading;
}

function openCapture(block = null) {
  if (isRunning()) return;
  captureBlock = block;
  stopPicking(); capturePicker.clear(); $('captureMode').value = 'items';
  $('captureItemTools').hidden = false; $('captureTextTools').hidden = true;
  $('capturePick').textContent = 'Listenelement auswählen';
  $('capturePickHint').textContent = 'Öffne die gewünschte Liste auf dem Gerät. Klicke dann auf „Listenelement auswählen“.';
  let name = 'Bildschirmliste', index = 2;
  while ((state.list_names || []).includes(name)) name = `Bildschirmliste ${index++}`;
  $('captureName').value = block ? block.getFieldValue('NAME') : name;
  $('captureStart').textContent = block ? 'Muster im Baustein übernehmen' : 'Aufnahme starten';
  $('captureOverwrite').hidden = true; $('captureDialog').showModal(); updateCaptureReady();
}

/* „Liste sichern“: assistant that starts a backup or configures a backup block. */
function updateBackupReady() {
  if (!backupPicker) return;
  const blocked = isRunning() || backupPicker.loading;
  $('backupStart').disabled = $('backupAsBlock').disabled = blocked || !backupPicker.ready();
  $('backupPick').disabled = $('backupDemo').disabled = blocked;
}

function openBackup(block = null) {
  if (isRunning()) return;
  backupBlock = block;
  stopPicking(); backupPicker.clear();
  $('backupPick').textContent = 'Gerätebild laden'; $('backupPickHint').hidden = true;
  $('backupCase').textContent = caseLabel(state.case);
  $('backupDemo').hidden = !state.device.demo;
  $('backupName').value = block ? block.getFieldValue('NAME') : '';
  if (block) { $('backupOrder').value = block.getFieldValue('ORDER'); $('backupMaxPages').value = block.getFieldValue('MAX_PAGES'); }
  $('backupStart').textContent = block ? 'Im Baustein übernehmen' : 'Sicherung starten';
  $('backupAsBlock').hidden = Boolean(block);
  $('backupDialog').showModal(); updateBackupReady();
}

function backupSettings() {
  const name = $('backupName').value.trim();
  if (!name) throw new Error('Bitte eine Bezeichnung für die Sicherung eingeben, z. B. „WhatsApp Chats“.');
  const maxPages = Number($('backupMaxPages').value);
  if (!Number.isInteger(maxPages) || maxPages < 1 || maxPages > 2000) throw new Error('Höchstens Seiten je Eintrag: bitte eine ganze Zahl von 1 bis 2000.');
  if (!backupPicker.ready()) throw new Error('Bitte zuerst einen Listeneintrag im aktuellen Gerätebild auswählen.');
  return { name, order: $('backupOrder').value, max_pages: maxPages, pattern: backupPicker.choice.pattern };
}

function applyBackupBlock(block, settings) {
  block.itemPattern = settings.pattern;
  block.setFieldValue(settings.name, 'NAME'); block.setFieldValue(settings.order, 'ORDER'); block.setFieldValue(settings.max_pages, 'MAX_PAGES');
  block.setFieldValue('Listeneintrag gewählt', 'PATTERN_HINT');
  saveDraft();
}

async function startBackup() {
  const settings = backupSettings();
  if (backupBlock) {
    if (!workspace.getBlockById(backupBlock.id)) throw new Error('Der Baustein wurde entfernt.');
    applyBackupBlock(backupBlock, settings); $('backupDialog').close(); toast('Listeneintrag und Einstellungen im Baustein gespeichert.'); return;
  }
  stopPicking(); $('backupStart').disabled = true;
  try {
    const next = await api('/api/backup', { ...settings, serial: backupPicker.serial });
    backupPending = true; $('backupDialog').close(); renderState(next);
    toast('Sicherung läuft. „Pause“ hält zwischen zwei Einträgen an, „Stopp“ beendet sie.');
  } finally { updateBackupReady(); }
}

function insertBackupBlock() {
  const settings = backupSettings();
  applyBackupBlock(addBlock('backup_list'), settings);
  $('backupDialog').close(); toast('Baustein „Liste sichern“ eingefügt. „Starten“ führt ihn als Teil des Ablaufs aus.');
}

/* Cases */
async function openCases() {
  renderCases(await api('/api/cases')); resetCaseForm();
  if (!$('caseDialog').open) $('caseDialog').showModal();
}
function renderCases(data) {
  $('caseList').replaceChildren(...data.cases.map(item => {
    const row = el('div', `case-row${item.id === data.active ? ' active' : ''}`);
    const info = el('div', 'case-info');
    info.append(el('strong', '', item.title), el('small', '', [item.examiner, item.note, `angelegt ${formatTime(item.created)}`].filter(Boolean).join(' · ')));
    const actions = el('div', 'case-actions');
    if (item.id === data.active) actions.append(el('span', 'badge ok', 'aktiv'));
    else { const select = el('button', 'button', 'Aktivieren'); select.disabled = isRunning(); select.onclick = () => selectCase(item.id).catch(error => toast(error.message, true)); actions.append(select); }
    const edit = el('button', 'text-button link', 'Bearbeiten'); edit.onclick = () => editCase(item); actions.append(edit);
    row.append(info, actions);
    return row;
  }));
}
function resetCaseForm() {
  caseEditing = null;
  $('caseFormTitle').textContent = 'Neuen Fall anlegen'; $('caseSave').textContent = 'Fall anlegen und aktivieren'; $('caseFormCancel').hidden = true;
  $('caseNumber').value = ''; $('caseExaminerInput').value = state?.case?.examiner || ''; $('caseNote').value = '';
}
function editCase(item) {
  caseEditing = item.id;
  $('caseFormTitle').textContent = `Fall „${item.title}“ bearbeiten`; $('caseSave').textContent = 'Änderungen speichern'; $('caseFormCancel').hidden = false;
  $('caseNumber').value = item.number; $('caseExaminerInput').value = item.examiner; $('caseNote').value = item.note;
  $('caseNumber').focus();
}
async function saveCase() {
  const body = { number: $('caseNumber').value, examiner: $('caseExaminerInput').value, note: $('caseNote').value };
  if (!body.number.trim()) throw new Error('Bitte ein Aktenzeichen oder eine Fallbezeichnung eingeben.');
  const editing = caseEditing;
  const result = await api(editing ? '/api/cases/update' : '/api/cases/create', editing ? { ...body, id: editing } : body);
  renderState(result); renderCases(result.cases); resetCaseForm(); caseChanged();
  toast(editing ? 'Fall gespeichert.' : `Fall „${result.case.title}“ angelegt und aktiviert.`);
}
async function selectCase(id) {
  const result = await api('/api/cases/select', { id });
  renderState(result); renderCases(result.cases); caseChanged();
  toast(`Aktiver Fall: ${result.case.title}`);
}
function caseChanged() {
  $('backupCase').textContent = caseLabel(state.case);
  if ($('libraryDialog').open) { librarySelection = null; openLibrary().catch(error => toast(error.message, true)); }
}

/* Ablage: backups and lists of the active case */
async function openLibrary(select = null) {
  libraryData = await api('/api/library');
  if (select) librarySelection = select;
  const known = item => item && (item.kind === 'backup' ? libraryData.backups.some(b => b.id === item.id) : libraryData.lists.some(l => l.name === item.id));
  if (!known(librarySelection)) {
    librarySelection = libraryData.backups[0] ? { kind: 'backup', id: libraryData.backups[0].id } : libraryData.lists[0] ? { kind: 'list', id: libraryData.lists[0].name } : null;
  }
  $('librarySubtitle').textContent = `Fall: ${caseLabel(libraryData.case)} · Ordner: ${libraryData.evidence_path}`;
  renderLibraryItems();
  await renderLibraryDetail();
  if (!$('libraryDialog').open) $('libraryDialog').showModal();
  scheduleLibraryRefresh();
}

function scheduleLibraryRefresh() {
  clearTimeout(libraryTimer); libraryTimer = null;
  if ($('libraryDialog').open && isRunning()) libraryTimer = setTimeout(() => { libraryTimer = null; openLibrary().catch(() => {}); }, 2500);
}

function renderLibraryItems() {
  const box = $('libraryItems'); box.replaceChildren();
  const running = isRunning() ? state.run.backup?.id : null;
  const item = (kind, id, title, lines, status) => {
    const button = el('button', `library-item${librarySelection?.kind === kind && librarySelection?.id === id ? ' selected' : ''}`);
    const head = el('span', 'library-item-title', title);
    if (status) head.append(el('span', `badge ${statusClass(status)}`, status));
    button.append(head, ...lines.filter(Boolean).map(line => el('small', '', line)));
    button.onclick = () => { librarySelection = { kind, id }; renderLibraryItems(); renderLibraryDetail().catch(error => toast(error.message, true)); };
    return button;
  };
  box.append(el('h3', '', `Sicherungen (${libraryData.backups.length})`));
  if (!libraryData.backups.length) box.append(el('p', 'library-empty', 'Noch keine Sicherung in diesem Fall. Starte eine mit „Liste sichern“.'));
  for (const backup of libraryData.backups) {
    box.append(item('backup', backup.id, backup.name, [formatTime(backup.started), `${backup.saved} von ${backup.entries} Einträgen · ${backup.pages} Screenshots`], backup.id === running ? 'läuft' : backup.status));
  }
  box.append(el('h3', '', `Listen (${libraryData.lists.length})`));
  if (!libraryData.lists.length) box.append(el('p', 'library-empty', 'Noch keine Listen in diesem Fall.'));
  for (const list of libraryData.lists) box.append(item('list', list.name, list.name, [`${list.count} Einträge`, list.meta.source]));
}

async function renderLibraryDetail() {
  const detail = $('libraryDetail'), scroll = detail.scrollTop, selection = librarySelection;
  if (!selection) { detail.replaceChildren(el('p', 'library-empty', 'Hier erscheinen Sicherungen und Listen des aktiven Falls.')); return; }
  const content = selection.kind === 'list' ? listDetail(libraryData.lists.find(list => list.name === selection.id))
    : backupDetail(await api(`/api/backup?id=${encodeURIComponent(selection.id)}`));
  if (selection !== librarySelection) return;
  detail.replaceChildren(...content); detail.scrollTop = scroll;
}

function facts(rows) {
  const list = el('dl', 'facts');
  for (const [label, value] of rows) if (value) list.append(el('dt', '', label), el('dd', '', value));
  return list;
}
function linkButton(text, href, download = null) {
  const link = el('a', 'button', text); link.href = href;
  if (download) link.download = download; else { link.target = '_blank'; link.rel = 'noopener'; }
  return link;
}
function actionButton(text, handler, className = 'button') {
  const button = el('button', className, text);
  button.onclick = () => handler().catch(error => toast(error.message, true));
  return button;
}

function backupDetail(record) {
  const running = isRunning() && state.run.backup?.id === record.id;
  const saved = record.entries.filter(entry => entry.status === 'gesichert').length;
  const pages = record.entries.reduce((sum, entry) => sum + entry.pages.length, 0);
  const head = el('div', 'detail-head');
  head.append(el('h3', '', record.name), el('span', `badge ${statusClass(running ? 'läuft' : record.status)}`, running ? 'läuft' : record.status));
  const summary = facts([
    ['Ergebnis', `${saved} von ${record.entries.length} Einträgen vollständig · ${pages} Screenshots`],
    ['Zeitraum', `${formatTime(record.started)} – ${record.finished ? formatTime(record.finished) : 'läuft noch'}`],
    ['Gerät', [record.device.label, record.device.android && `Android ${record.device.android}`, record.device.serial].filter(Boolean).join(' · ')],
    ['App', record.app], ['Reihenfolge', record.options.order_label], ['Meldung', record.message], ['Ordner', record.path],
    ['SHA-256 der Hashliste', record.hash_list_sha256 || (running ? 'entsteht am Ende der Sicherung' : 'nicht vorhanden')],
  ]);
  const actions = el('div', 'detail-actions');
  if (record.finished) actions.append(linkButton('Bericht öffnen ↗', record.base + 'bericht.html'), linkButton('CSV herunterladen', record.base + 'eintraege.csv', `${record.name}.csv`));
  actions.append(actionButton('Ordner öffnen', () => api('/api/open-folder', { id: record.id })));
  const remove = actionButton('Löschen …', () => deleteBackup(record), 'button danger-text'); remove.disabled = isRunning(); actions.append(remove);
  const parts = [head, summary, actions];
  if (record.warnings.length) {
    const warnings = el('ul', 'detail-warnings');
    warnings.append(...record.warnings.map(warning => el('li', '', `${formatTime(warning.time)} · ${warning.text}`)));
    parts.push(warnings);
  }
  const table = el('table', 'entries-table'), header = el('tr');
  for (const title of ['Nr', 'Erste Seite', 'Eintrag in der Liste', 'Status', 'Seiten']) header.append(el('th', '', title));
  table.append(header);
  for (const entry of record.entries) {
    const thumb = el('td'), status = el('td'), pagesCell = el('td', 'pages', String(entry.pages.length)), links = el('div');
    if (entry.pages[0]) {
      const link = linkButton('', record.base + encodePath(entry.pages[0].file)); link.className = 'thumb';
      const image = el('img'); image.src = link.href; image.loading = 'lazy'; image.alt = `Erste Seite von Eintrag ${entry.index}`;
      link.append(image); thumb.append(link);
    }
    entry.pages.forEach((page, index) => { const link = linkButton(`S${index + 1}`, record.base + encodePath(page.file)); link.className = ''; link.title = `SHA-256 ${page.sha256}`; links.append(link, ' '); });
    pagesCell.append(links);
    status.append(el('span', `badge ${statusClass(entry.status)}`, entry.status));
    if (entry.note) status.append(el('div', 'note', entry.note));
    const row = el('tr');
    row.append(el('td', '', String(entry.index)), thumb, el('td', 'entry-text', entry.text), status, pagesCell);
    table.append(row);
  }
  if (!record.entries.length) { const row = el('tr'), cell = el('td', '', 'Noch keine Einträge.'); cell.colSpan = 5; row.append(cell); table.append(row); }
  parts.push(table);
  return parts;
}

async function deleteBackup(record) {
  const confirmed = await confirmAction({ title: 'Sicherung löschen?', text: `„${record.name}“ wird mit allen Screenshots, Bericht und Hashwerten endgültig von diesem Computer gelöscht. Das lässt sich nicht rückgängig machen.`, accept: 'Endgültig löschen', danger: true });
  if (!confirmed) return;
  await api('/api/backups/delete', { id: record.id });
  librarySelection = null; toast('Sicherung gelöscht.'); await openLibrary();
}

function listDetail(list) {
  if (!list) return [el('p', 'library-empty', 'Diese Liste gibt es nicht mehr.')];
  const head = el('div', 'detail-head');
  head.append(el('h3', '', list.name), el('span', 'badge', `${list.count} Einträge`));
  const summary = facts([['Quelle', list.meta.source || 'ältere Liste ohne Angaben'], ['Gerät', list.meta.device], ['Aktualisiert', formatTime(list.meta.updated)]]);
  const actions = el('div', 'detail-actions');
  const use = actionButton('Als Schleife verwenden', async () => {
    if (isRunning()) return;
    addBlock('for_each', { NAME: list.name }); $('libraryDialog').close();
    toast('Schleife eingefügt. Stecke die gewünschten Befehle hinein.');
  }, 'button primary');
  const rename = actionButton('Umbenennen …', async () => {
    const name = await confirmAction({ title: 'Liste umbenennen', text: 'Bausteine, die den alten Namen verwenden, müssen danach angepasst werden.', accept: 'Umbenennen', input: { label: 'Neuer Name', value: list.name } });
    if (name == null || name.trim() === list.name) return;
    await api('/api/lists/rename', { name: list.name, new_name: name });
    await openLibrary({ kind: 'list', id: name.trim() });
  });
  const csv = actionButton('CSV exportieren', async () => {
    const quote = value => `"${String(value).replace(/"/g, '""')}"`;
    download('﻿' + ['Nr;Eintrag', ...list.values.map((value, index) => `${index + 1};${quote(value)}`)].join('\r\n') + '\r\n', `${list.name}.csv`, 'text/csv');
  });
  const remove = actionButton('Löschen …', async () => {
    if (!await confirmAction({ title: 'Liste löschen?', text: `Die Liste „${list.name}“ mit ${list.count} Einträgen wird aus diesem Fall entfernt.`, accept: 'Löschen', danger: true })) return;
    await api('/api/lists/delete', { name: list.name });
    librarySelection = null; toast('Liste gelöscht.'); await openLibrary();
  }, 'button danger-text');
  for (const button of [use, rename, remove]) button.disabled = isRunning();
  actions.append(use, rename, csv, remove);
  const values = el('ol', 'list-values');
  values.append(...list.values.map(value => el('li', '', value)));
  return [head, summary, actions, values];
}

async function refreshScreen() {
  if (screenBusy || changingDevice || picking) return;
  screenBusy = true;
  const revision = screenRevision;
  try {
    const response = await fetch('/api/screen');
    if (!response.ok) { const error = await response.json(); throw new Error(error.error); }
    const blob = await response.blob();
    if (revision !== screenRevision) return;
    const nextUrl = URL.createObjectURL(blob); const oldUrl = screenUrl;
    screenUrl = nextUrl; $('screen').src = nextUrl;
    if (oldUrl) URL.revokeObjectURL(oldUrl);
    $('screenError').hidden = true;
  } catch (error) {
    $('screenError').textContent = `Bild nicht verfügbar. ${error.message} Prüfe die USB-Verbindung.`; $('screenError').hidden = false;
  } finally { screenBusy = false; }
}

function stopPicking() {
  picking = false; $('phoneScreen').classList.remove('picking'); $('pickButton').classList.remove('active');
  $('pickButton').lastChild.textContent = 'Element auswählen'; $('elementHighlight').hidden = true;
  $('pickHint').hidden = true;
}
function hitAt(event) {
  const rect = $('screen').getBoundingClientRect();
  const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
  const matches = elements.filter(({ bounds: [x1, y1, x2, y2] }) => x >= x1 && x <= x2 && y >= y1 && y <= y2);
  matches.sort((a, b) => (a.bounds[2] - a.bounds[0]) * (a.bounds[3] - a.bounds[1]) - (b.bounds[2] - b.bounds[0]) * (b.bounds[3] - b.bounds[1]));
  return { x, y, element: matches[0] };
}

async function scanDevices() {
  $('deviceMessage').textContent = 'Suche nach Android-Geräten …'; $('deviceList').replaceChildren(); $('scanButton').disabled = true;
  try {
    const result = await api('/api/devices');
    $('deviceMessage').textContent = result.error || (result.devices.length ? 'Wähle dein Gerät aus.' : 'Noch kein Gerät gefunden. USB-Kabel und USB-Debugging prüfen, dann erneut suchen.');
    for (const device of result.devices) {
      const button = document.createElement('button'); button.textContent = `${device.serial} · ${device.state === 'device' ? 'Verbinden' : device.state === 'unauthorized' ? 'Bitte auf dem Gerät bestätigen' : device.state}`;
      button.disabled = device.state !== 'device';
      button.addEventListener('click', async () => { button.disabled = true; button.textContent = 'Verbindung wird hergestellt …'; try { await connect(device.serial); } catch (error) { $('deviceMessage').textContent = error.message; button.disabled = false; button.textContent = `${device.serial} · Erneut verbinden`; } });
      $('deviceList').append(button);
    }
  } finally { $('scanButton').disabled = false; }
}
async function connect(serial) {
  changingDevice = true; screenRevision++; stopPicking();
  try { renderState(await api('/api/connect', { serial })); $('connectDialog').close(); toast(serial === 'demo' ? 'Demo-Gerät ist bereit.' : 'Android-Gerät verbunden.'); }
  finally { changingDevice = false; }
  await refreshScreen();
}

async function showCode() {
  $('blocksTab').classList.remove('active'); $('codeTab').classList.add('active'); $('codePane').hidden = false;
  try { $('pythonCode').textContent = (await api('/api/export', { program: programFromWorkspace() })).code; }
  catch (error) { $('pythonCode').textContent = error.message; }
}

async function main() {
  if (!window.Blockly) { toast('Blockly fehlt. Bitte setup.bat ausführen und die Seite neu laden.', true); return; }
  initBlockly(); renderPalette();
  let restored = false;
  try { const saved = localStorage.getItem(STORAGE); if (saved) { loadProject(JSON.parse(saved)); restored = true; } } catch { toast('Der gespeicherte Entwurf konnte nicht geladen werden.', true); }
  if (!restored) initialProject();
  capturePicker = new ListPicker('capture', updateCaptureReady);
  backupPicker = new ListPicker('backup', updateBackupReady);
  const session = await api('/api/session');
  if (session.version !== APP_VERSION) {
    fatal('Im Hintergrund läuft noch eine ältere Droid-Studio-Version. Bitte deren Konsolenfenster schließen, start.bat erneut starten und diese Seite neu laden.');
    return;
  }
  token = session.token; renderState(session);
  bind('backupButton', () => openBackup());
  bind('backupPick', () => backupPicker.load());
  bind('backupStart', startBackup);
  bind('backupAsBlock', insertBackupBlock);
  bind('backupCaseChange', openCases);
  bind('backupDemo', async () => {
    await api('/api/action', { action: { op: 'launch', package: 'de.droidstudio.demo.chats' } }); await refreshScreen();
    if (!$('backupName').value) $('backupName').value = 'Demo-Chats';
    await backupPicker.load();
  });
  bind('libraryButton', () => openLibrary());
  bind('libraryCapture', async () => { $('libraryDialog').close(); openCapture(); });
  bind('libraryFolder', () => api('/api/open-folder', {}));
  $('libraryDialog').addEventListener('close', () => { clearTimeout(libraryTimer); libraryTimer = null; });
  bind('caseButton', openCases);
  bind('caseSave', saveCase);
  bind('caseFormCancel', resetCaseForm);
  bind('capturePick', () => capturePicker.load());
  $('captureMode').addEventListener('change', () => {
    const items = $('captureMode').value === 'items';
    $('captureItemTools').hidden = !items; $('captureTextTools').hidden = items; updateCaptureReady();
  });
  $('captureName').addEventListener('input', () => { $('captureOverwrite').hidden = !(state.list_names || []).includes($('captureName').value.trim()); });
  bind('captureStart', async () => {
    const name = $('captureName').value.trim();
    if (!name) throw new Error('Bitte einen Listennamen eingeben.');
    const itemMode = $('captureMode').value === 'items';
    if (itemMode && !capturePicker.ready()) throw new Error('Bitte zuerst ein Listenelement im aktuellen Gerätebild auswählen.');
    if (captureBlock) {
      if (isRunning()) throw new Error('Bitte zuerst den Ablauf stoppen.');
      if (!workspace.getBlockById(captureBlock.id)) throw new Error('Der Baustein wurde entfernt.');
      captureBlock.itemPattern = itemMode ? capturePicker.choice.pattern : null;
      captureBlock.setFieldValue(name, 'NAME'); captureBlock.setFieldValue(itemMode ? 'Eintragsmuster' : 'Textfilter', 'PATTERN_HINT');
      captureBlock.setFieldValue(itemMode ? 'textContains' : $('captureBy').value, 'BY'); captureBlock.setFieldValue(itemMode ? '' : $('captureFilter').value, 'VALUE');
      saveDraft(); $('captureDialog').close(); toast('Aufnahmemuster im Baustein gespeichert.'); return;
    }
    stopPicking(); $('captureStart').disabled = true;
    try {
      const next = await api('/api/capture', { name, by: itemMode ? 'textContains' : $('captureBy').value, value: itemMode ? '' : $('captureFilter').value, ...(itemMode ? { pattern: capturePicker.choice.pattern, serial: capturePicker.serial } : {}) });
      capturePending = name; $('captureDialog').close(); renderState(next);
      toast('Aufnahme läuft. Mit „Stopp“ kannst du sie abbrechen.');
    } finally { updateCaptureReady(); }
  });
  $('projectMenu').addEventListener('click', event => {
    if (event.target.closest('button')) $('projectMenu').open = false;
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('#projectMenu')) $('projectMenu').open = false;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && $('projectMenu').open) { $('projectMenu').open = false; $('projectMenu').querySelector('summary').focus(); }
  });
  new ResizeObserver(() => Blockly.svgResize(workspace)).observe(document.querySelector('.canvas-wrap'));
  bind('helpButton', () => $('helpDialog').showModal());
  bind('newButton', async () => { if (await confirmReplace()) initialProject(false); });
  bind('exampleButton', async () => { if (await confirmReplace()) initialProject(true); });
  bind('listExampleButton', async () => {
    if (await confirmReplace()) { loadProject(await api('/examples/liste-durchlaufen.json')); $('codePane').hidden = true; $('blocksTab').click(); workspace.zoomToFit(); }
  });
  bind('variableExampleButton', async () => {
    if (await confirmReplace()) { loadProject(await api('/examples/variablen.json')); $('blocksTab').click(); workspace.zoomToFit(); $('variableMonitor').open = true; }
  });
  bind('saveButton', () => { saveDraft(); download(JSON.stringify(project(), null, 2), filename('.json'), 'application/json'); toast('Projektdatei gespeichert.'); });
  bind('openButton', () => $('fileInput').click());
  $('fileInput').addEventListener('change', async event => {
    try { const file = event.target.files[0]; if (!file) return; if (file.size > 2_000_000) throw new Error('Diese Projektdatei ist zu groß.'); if (isRunning()) throw new Error('Bitte zuerst den Ablauf stoppen.'); loadProject(JSON.parse(await file.text())); toast('Projekt geladen.'); }
    catch (error) { toast(`Projekt konnte nicht geöffnet werden: ${error.message}`, true); } finally { event.target.value = ''; }
  });
  $('projectName').addEventListener('input', saveDraft);
  $('blockSearch').addEventListener('input', renderPalette);
  for (const button of document.querySelectorAll('[data-category]')) button.addEventListener('click', () => { category = button.dataset.category; document.querySelectorAll('[data-category]').forEach(b => b.classList.toggle('selected', b === button)); renderPalette(); });
  async function controlRun(action) {
    if (runControlPending) return;
    runControlPending = true;
    stopPicking(); renderState(state);
    try {
      const paused = state.run.status === 'paused';
      const route = action === 'pause' ? '/api/pause' : paused ? (action === 'step' ? '/api/step' : '/api/resume') : '/api/run';
      const body = route === '/api/run' ? { program: programFromWorkspace(), step_mode: action === 'step' } : {};
      renderState(await api(route, body));
    } finally { runControlPending = false; renderState(state); }
  }
  bind('runButton', () => controlRun('run'));
  bind('stepButton', () => controlRun('step'));
  bind('pauseButton', () => controlRun('pause'));
  bind('stopButton', async () => renderState(await api('/api/stop', {})));
  bind('undoButton', () => workspace.undo(false));
  bind('fitButton', () => workspace.zoomToFit());
  bind('codeTab', showCode);
  bind('blocksTab', () => { $('codePane').hidden = true; $('blocksTab').classList.add('active'); $('codeTab').classList.remove('active'); Blockly.svgResize(workspace); });
  bind('exportButton', async () => { const result = await api('/api/export', { program: programFromWorkspace() }); download(result.code, filename('.py'), 'text/x-python'); });
  bind('connectButton', async () => { $('connectDialog').showModal(); await scanDevices(); });
  bind('currentAppButton', async () => {
    const result = await api('/api/current-app');
    if (isRunning()) return;
    rememberApp(result.package); addBlock('launch', { PACKAGE: result.package });
    toast('Die geöffnete App wurde als Baustein übernommen.');
  });
  bind('scanButton', scanDevices); bind('demoButton', () => connect('demo')); bind('refreshScreen', async () => { stopPicking(); await refreshScreen(); });
  bind('pickButton', async () => {
    if (picking) return stopPicking();
    $('pickButton').disabled = true;
    try {
      await refreshScreen(); const result = await api('/api/elements'); elements = result.elements;
      if (isRunning()) return;
      picking = true; $('phoneScreen').classList.add('picking'); $('pickButton').classList.add('active');
      $('pickButton').lastChild.textContent = 'Auswahl abbrechen'; $('pickHint').hidden = false; $('pickHint').textContent = 'Im Bild auf das gewünschte Element klicken.';
    } finally { $('pickButton').disabled = isRunning(); }
  });
  $('phoneScreen').addEventListener('mousemove', event => {
    if (!picking) return;
    const { element } = hitAt(event); $('elementHighlight').hidden = !element;
    if (element) { const [x1, y1, x2, y2] = element.bounds; Object.assign($('elementHighlight').style, { left: `${x1 * 100}%`, top: `${y1 * 100}%`, width: `${(x2 - x1) * 100}%`, height: `${(y2 - y1) * 100}%` }); }
  });
  $('phoneScreen').addEventListener('mouseleave', () => { $('elementHighlight').hidden = true; });
  $('phoneScreen').addEventListener('click', async event => {
    if (isRunning() || changingDevice || !$('screenError').hidden) return;
    const { x, y, element } = hitAt(event);
    try {
      if (picking) {
        if (element) addBlock('click', { BY: element.selector.by, VALUE: element.selector.value });
        else addBlock('tap', { X: (x * 100).toFixed(1), Y: (y * 100).toFixed(1) });
        stopPicking(); toast(element ? `„${element.label}“ als Baustein eingefügt.` : 'Bildschirmposition als Baustein eingefügt.');
      } else { await api('/api/action', { action: { op: 'tap', x, y } }); await refreshScreen(); }
    } catch (error) { toast(error.message, true); }
  });
  $('screen').addEventListener('load', () => { document.querySelector('.phone-frame').classList.toggle('landscape', $('screen').naturalWidth > $('screen').naturalHeight); });
  for (const button of document.querySelectorAll('[data-key]')) button.addEventListener('click', async () => { try { stopPicking(); await api('/api/action', { action: { op: 'press', key: button.dataset.key } }); await refreshScreen(); } catch (error) { toast(error.message, true); } });
  bind('inspectorButton', async () => {
    $('inspectorButton').disabled = true;
    toast('uiautodev wird gestartet …');
    try { const result = await api('/api/inspector', {}); $('inspectorLink').href = result.url; $('inspectorLink').hidden = false; window.open(result.url, '_blank', 'noopener'); toast('uiautodev ist bereit. Falls kein Fenster erscheint, nutze „uiautodev öffnen“.'); }
    finally { $('inspectorButton').disabled = isRunning(); }
  });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); $('saveButton').click(); }
    if (event.key === 'Escape') stopPicking();
    if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) { event.preventDefault(); $('blockSearch').focus(); }
  });
  await refreshScreen();
  async function pollState() { try { const next = await api('/api/state'); if (!runControlPending) renderState(next); } catch { $('footerConnection').textContent = 'Verbindung zur lokalen App unterbrochen'; for (const id of ['runButton', 'stepButton', 'pauseButton']) $(id).disabled = true; } setTimeout(pollState, 450); }
  async function pollScreen() { if (!document.hidden) await refreshScreen(); setTimeout(pollScreen, 1000); }
  pollState(); pollScreen();
}
main().catch(error => fatal(`Die Oberfläche konnte nicht starten: ${error.message}`));
