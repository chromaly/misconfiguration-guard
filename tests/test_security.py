"""Meaningful tool boundaries, dispatch and actual local fixture behavior."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'agent'))
import tools
import agent_loop
import ci_scan
import attack_agent
import defense_agent

class ToolTests(unittest.TestCase):
    def test_prompts_match_tools_and_misconfiguration_task(self):
        self.assertIn('send_request', attack_agent.SYSTEM_PROMPT)
        self.assertIn('UNTRUSTED DATA', attack_agent.SYSTEM_PROMPT)
        self.assertIn('misconfigurations', attack_agent.SYSTEM_PROMPT)
        self.assertIn('write_file', defense_agent.SYSTEM_PROMPT)
        self.assertIn('runtime verification is pending', defense_agent.SYSTEM_PROMPT)

    def test_dispatch_lists_files(self):
        with patch.object(agent_loop.tools, 'list_files', return_value=['app.py']):
            self.assertEqual(agent_loop.run_tool({'tool':'list_files','args':{}}, 'target_app'), 'Files found:\napp.py')

    def test_file_boundaries_and_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'scan').mkdir()
            (root/'outside.txt').write_text('private')
            (root/'scan'/'escape.txt').symlink_to(root/'outside.txt')
            (root/'scan'/'settings.json').write_text('{}')
            (root/'scan'/'.env.example').write_text('FAKE=true')
            with patch.object(tools, 'BASE', tmp):
                self.assertIn('settings.json', tools.list_files('scan'))
                self.assertIn('.env.example', tools.list_files('scan'))
                self.assertTrue(tools.read_file('scan','../outside.txt').startswith('ERROR'))
                self.assertTrue(tools.read_file('scan','escape.txt').startswith('ERROR'))
                self.assertTrue(tools.write_file('scan','app.py','x=1').startswith('ERROR'))
                self.assertTrue(tools.write_file('scan','app_fixed.py','invalid python!').startswith('ERROR'))
                self.assertIn('Wrote',tools.write_file('scan','app_fixed.py','x=1'))

    def test_http_rejects_external_routes_and_disables_redirects(self):
        with patch.object(tools.requests, 'request') as request:
            self.assertIn('error', tools.send_request('GET','//example.com'))
            self.assertIn('error', tools.send_request('GET','https://example.com'))
            request.assert_not_called()
            response=request.return_value.__enter__.return_value
            response.status_code=302
            response.raw.read.return_value=b'redirect'
            self.assertEqual(tools.send_request('GET','/redirect')['status'],302)
            self.assertFalse(request.call_args.kwargs['allow_redirects'])

    def test_ci_blocks_http_and_recovers_from_bad_json(self):
        replies=iter(['[]', '{"action":"send_request","path":"/"}', '{"action":"finish","answer":"Source-only report"}'])
        with patch.object(tools,'send_request') as request:
            self.assertEqual(ci_scan.scan(lambda _:next(replies)), 'Source-only report')
            request.assert_not_called()

    def test_ci_step_limit_is_not_clean_result(self):
        with self.assertRaises(RuntimeError):
            ci_scan.scan(lambda _:'{}')

class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('practice', ROOT/'target_app/app.py')
        cls.module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.seed_database()
        cls.client=cls.module.app.test_client()

    def test_known_exposures_and_normal_behavior(self):
        self.assertEqual(self.client.get('/').status_code,200)
        normal=self.client.post('/login',json={'username':'alice','password':'password123'})
        self.assertTrue(normal.json['ok'])
        diagnostic=self.client.get('/debug/config')
        self.assertEqual(diagnostic.status_code,200)
        self.assertEqual(diagnostic.json['api_key'],'DEMO_NOT_A_REAL_SECRET')
        config=self.client.get('/public-config/settings.json')
        self.assertEqual(config.status_code,200)
        self.assertIn(b'DEMO_NOT_A_REAL_SECRET',config.data)
        config.close()
        error=self.client.get('/search',query_string={'q':"'"})
        self.assertEqual(error.status_code,400)
        self.assertIn('query',error.json)
        self.assertFalse(self.module.app.debug)

if __name__=='__main__':
    unittest.main()
