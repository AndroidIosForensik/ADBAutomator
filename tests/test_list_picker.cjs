const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const {JSDOM} = require('jsdom');

// Use real XML-derived candidates, including a wrapper spanning all mail rows.
const candidates = JSON.parse(execFileSync('python', ['-c', `
import json
from tests.test_list_items import mailbox
from automator.list_items import list_item_candidates
xml = mailbox()
xml = xml.replace('<node class="Header"', '<node class="Wrapper" bounds="[0,80][400,750]"><node class="Header"')
xml = xml.replace('</node></hierarchy>', '</node></node></hierarchy>')
print(json.dumps(list_item_candidates(xml, 1000, 800)))
`], {encoding: 'utf8'}));
const dom = new JSDOM(fs.readFileSync('web/index.html', 'utf8'));
const source = fs.readFileSync('web/app.js', 'utf8').replace(/main\(\)\.catch[\s\S]*$/, '');
const context = vm.createContext({document: dom.window.document, console, candidates});
const execute = code => vm.runInContext(code, context);
vm.runInContext(source, context);
execute('state = {device: {serial: "test"}};');

for (const prefix of ['backup', 'capture']) {
  context.prefix = prefix;
  execute('var picker = new ListPicker(prefix, () => {}); picker.candidates = candidates; picker.serial = "test";');
  const image = dom.window.document.getElementById(`${prefix}Image`);
  const highlight = dom.window.document.getElementById(`${prefix}Highlight`);
  const current = dom.window.document.getElementById(`${prefix}Current`);
  const select = dom.window.document.getElementById(`${prefix}Candidate`);
  image.getBoundingClientRect = () => ({left: 0, top: 0, width: 1000, height: 800});
  const move = (x, y) => image.dispatchEvent(new dom.window.MouseEvent('pointermove', {clientX: x, clientY: y}));
  const click = (x, y) => image.dispatchEvent(new dom.window.MouseEvent('click', {clientX: x, clientY: y}));
  const leave = () => image.dispatchEvent(new dom.window.Event('pointerleave'));

  move(30, 110); // Hover on sender text must select the surrounding repeated mail row.
  assert.equal(highlight.hidden, false);
  assert.match(current.textContent, /Unter der Maus: Google/);
  assert.match(current.textContent, /Betreff/);
  assert.equal(highlight.style.height, '17.5%');
  assert.equal(execute('picker.ready()'), false, 'Hover must not confirm a pattern');
  click(30, 110);
  assert.equal(execute('picker.choice.pattern.item.at(-1).resource_id'), 'mail');
  assert.equal(execute('picker.ready()'), true);

  move(30, 260);
  assert.match(current.textContent, /Unter der Maus: ChatGPT/);
  assert.equal(execute('picker.choice.label.startsWith("Google")'), true, 'Hover preserves confirmed row');
  leave();
  assert.match(current.textContent, /Ausgewählter Eintrag: Google/);
  assert.equal(highlight.style.top, '12.5%');

  select.value = execute('String(picker.matches.findIndex(c => c.pattern.item.at(-1).resource_id === "sender"))');
  select.dispatchEvent(new dom.window.Event('change'));
  assert.equal(execute('picker.choice.pattern.item.at(-1).resource_id'), 'sender');
  move(30, 260);
  leave();
  assert.equal(execute('picker.matches[Number(picker.el("Candidate").value)] === picker.choice'), true);
  assert.equal(current.textContent, 'Ausgewählter Eintrag: Google');

  move(900, 790);
  assert.equal(highlight.hidden, true);
  assert.equal(execute('picker.ready()'), true);
  leave();
  assert.equal(highlight.hidden, false);
  execute('picker.clear();');
  move(900, 790);
  assert.equal(highlight.hidden, true);
  assert.equal(execute('picker.ready()'), false);
}
console.log('List picker: XML row detection, hover preview, click confirmation and scope persistence passed.');
