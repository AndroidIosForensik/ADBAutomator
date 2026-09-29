const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Blockly = require('blockly');
const {JSDOM} = require('jsdom');
const dom = new JSDOM(fs.readFileSync('web/index.html','utf8'));
const source = fs.readFileSync('web/app.js','utf8').replace(/main\(\)\.catch[\s\S]*$/, '');
const context = vm.createContext({Blockly, document:dom.window.document, window:dom.window, console, setTimeout, clearTimeout});
vm.runInContext(source, context);
vm.runInContext('defineStudioBlocks(); workspace = new Blockly.Workspace();', context);
const execute = code => vm.runInContext(code,context);
const load = project => { context.fixture=project; execute('Blockly.serialization.workspaces.load(fixture.workspace, workspace);'); };
const program = () => JSON.parse(JSON.stringify(execute('programFromWorkspace()')));

// All existing projects must still compile with their original literal fields.
for (const name of fs.readdirSync('examples').filter(n=>n.endsWith('.json'))) {
  load(JSON.parse(fs.readFileSync(`examples/${name}`,'utf8')));
  assert.ok(program().length, name);
}
load(JSON.parse(fs.readFileSync('examples/variablen.json','utf8')));
const expected = program();
assert.equal(expected[0].value,0);
assert.deepEqual(expected[3].value,{source:'variable',name:'Suchtext'});
assert.deepEqual(expected[4].times,{source:'variable',name:'Durchläufe'});
assert.equal(expected[4].body[0].amount,1);
context.serialized=JSON.parse(JSON.stringify(execute('Blockly.serialization.workspaces.save(workspace)')));
execute('workspace.clear(); Blockly.serialization.workspaces.load(serialized, workspace);');
assert.deepEqual(program(),expected,'Save/load preserves connected value blocks');

// A variable overrides the literal; disconnecting restores the original field.
execute(`workspace.clear();
  var start = workspace.newBlock('start');
  var wait = workspace.newBlock('wait'); wait.setFieldValue(7,'SECONDS');
  start.nextConnection.connect(wait.previousConnection);
  var getter = workspace.newBlock('var_get'); getter.setFieldValue('Pause','NAME');
  wait.getInput('SECONDS_VALUE').connection.connect(getter.outputConnection);`);
assert.deepEqual(program()[0].seconds,{source:'variable',name:'Pause'});
execute('getter.dispose();');
assert.equal(program()[0].seconds,7);
execute(`var stringValue = workspace.newBlock('value_text');`);
assert.equal(execute(`workspace.connectionChecker.canConnect(stringValue.outputConnection, wait.getInput('SECONDS_VALUE').connection, false)`),false,'Text cannot connect to numeric socket');
assert.throws(program,/lose Bausteine/,'Unconnected value blocks must not silently disappear');
console.log('Blockly: existing projects, variable compilation, persistence, overrides and connection types passed.');
execute('workspace.dispose();');
