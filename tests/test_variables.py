import ast
import tempfile
import time
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from automator.devices import DemoDevice
from automator.program import validate, ProgramError, export_python
from automator.runner import Runner


def var(name):
    return {'source': 'variable', 'name': name}


def setting(name, value):
    return {'op': 'var_set', 'name': name, 'value': value}


class VariableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runner = Runner(self.temp.name)
        self.device = DemoDevice()
        self.device.demo = False
        original = self.runner.checkpoint
        self.runner.checkpoint = lambda seconds=0: original(0)

    def run_program(self, program):
        self.runner.start(program, self.device)
        self.runner.thread.join(2)
        self.assertFalse(self.runner.thread.is_alive())
        return self.runner.snapshot()

    def test_set_change_and_repeated_variable_values(self):
        self.device.perform = Mock(wraps=self.device.perform)
        result = self.run_program([setting('N', 3), setting('Zähler', 0), {'op':'repeat','times':var('N'),'body':[
            {'op':'var_change','name':'Zähler','amount':1}, {'op':'type','text':var('Zähler')}]}])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['variables'], {'N':3,'Zähler':3})
        self.assertEqual([c.args[0]['text'] for c in self.device.perform.call_args_list], ['1','2','3'])

    def test_search_filter_conditions_and_waits_accept_variables(self):
        result = self.run_program([setting('Text','Anzeige'), setting('Zeit',0),
            {'op':'wait','seconds':var('Zeit')}, {'op':'wait_for','by':'text','value':var('Text'),'timeout':var('Zeit')},
            {'op':'read_list','name':'Ergebnis','by':'textContains','value':var('Text')},
            {'op':'if_exists','by':'text','value':var('Text'),'body':[{'op':'click','by':'text','value':var('Text'),'timeout':var('Zeit')}]}])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.device.page, 'Anzeige')

    def test_list_item_can_be_assigned_and_survives_loop(self):
        result = self.run_program([{'op':'list_create','name':'Werte','items':['A','B']},
            {'op':'for_each','name':'Werte','body':[setting('Aktuell',{'source':'item'})]},
            {'op':'type','text':var('Aktuell')}])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.device.typed, 'B')

    def test_missing_variable_stops_at_responsible_block_and_resets_next_run(self):
        self.run_program([setting('Alt',1)])
        result = self.run_program([{'op':'type','id':'missing','text':var('Alt')},setting('Never',1)])
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['active_id'],'missing')
        self.assertEqual(result['variables'],{})
        self.assertIn('noch nicht gesetzt',result['logs'][-1]['text'])

    def test_invalid_runtime_types_ranges_and_empty_search_fail(self):
        cases = [([setting('V','3')],{'op':'repeat','times':var('V'),'body':[]}),
                 ([setting('V',101)],{'op':'repeat','times':var('V'),'body':[]}),
                 ([setting('V',2.5)],{'op':'repeat','times':var('V'),'body':[]}),
                 ([setting('V',-1)],{'op':'wait','seconds':var('V')}),
                 ([setting('V','')],{'op':'click','by':'text','value':var('V')}),
                 ([setting('V','x')],{'op':'var_change','name':'V','amount':1}),
                 ([setting('V',1e12)],{'op':'var_change','name':'V','amount':1})]
        for prefix, command in cases:
            with self.subTest(command=command):
                result=self.run_program(prefix+[command, setting('Never',1)])
                self.assertEqual(result['status'],'error')
                self.assertNotIn('Never',result['variables'])

    def test_invalid_values_and_references_are_rejected_before_run(self):
        for program in [[setting('',1)], [setting('x',True)], [setting('x',float('inf'))], [setting('x','x'*2001)],
                        [setting('x',{'source':'variable','name':'x','extra':1})], [setting('x',{'source':'item'})]]:
            with self.subTest(program=program), self.assertRaises(ProgramError): validate(program)
        with self.assertRaises(ProgramError):
            validate([{'op':'repeat','times':var('N'),'body':[{'op':'repeat','times':100,'body':[{'op':'wait','seconds':0}]}]}])

    def test_export_matches_execution_without_evaluating_names_or_values_as_code(self):
        name='x\"]; __import__("bad") #'
        literal='__import__("bad")\n{item}'
        program=[setting(name,literal),{'op':'type','text':var(name)},setting('N',2), setting('Z',0),
                 {'op':'repeat','times':var('N'),'body':[{'op':'var_change','name':'Z','amount':1}, {'op':'type','text':var('Z')}]},
                 setting('Pause',0),{'op':'wait','seconds':var('Pause')}]
        code=export_python(program)
        ast.parse(code)
        device=Mock(); namespace={}
        with patch.dict(sys.modules,{'uiautomator2':SimpleNamespace(connect=lambda:device)}),patch.object(Path,'mkdir'),patch('time.sleep'):
            exec(compile(code,'export.py','exec'),namespace)
        result=self.run_program(program)
        self.assertEqual(result['variables'],namespace['variables'])
        self.assertEqual([c.args[0] for c in device.send_keys.call_args_list],[literal,'1','2'])

    def test_step_mode_exposes_updated_value_before_next_step(self):
        self.runner.start([setting('Z',1),{'op':'var_change','name':'Z','amount':1}],self.device,True)
        try:
            for steps in range(2):
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    snapshot=self.runner.snapshot()
                    if snapshot['status']=='paused' and snapshot['steps']==steps:break
                    time.sleep(.005)
                self.assertEqual(snapshot['variables'],{} if steps==0 else {'Z':1})
                self.runner.advance()
            self.runner.thread.join(2)
            self.assertEqual(self.runner.snapshot()['variables'],{'Z':2})
        finally:
            self.runner.stop();self.runner.thread.join(2)


if __name__=='__main__':unittest.main()
