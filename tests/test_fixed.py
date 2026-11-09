"""Explicit runtime verification for generated app_fixed.py; run after defense."""
import importlib.util
from pathlib import Path
import unittest

class FixedAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[1]/'target_app/app_fixed.py'
        if not path.exists():
            raise unittest.SkipTest('Run defense_agent.py first; no generated fixed app yet')
        spec=importlib.util.spec_from_file_location('fixed_practice',path)
        module=importlib.util.module_from_spec(spec)
        # Execute only your reviewed, locally generated fix, never downloaded PR code with secrets.
        spec.loader.exec_module(module)
        module.seed_database()
        cls.client=module.app.test_client()
        cls.module=module

    def test_diagnostics_and_configuration_no_longer_public(self):
        for route in ['/debug/config','/public-config/settings.json']:
            response=self.client.get(route)
            self.assertIn(response.status_code,{401,403,404})
            self.assertNotIn(b'DEMO_NOT_A_REAL_SECRET',response.data)
            response.close()

    def test_errors_are_generic(self):
        for method,path,data in [('GET','/search',{'q':"'"}),('POST','/login',{'username':"'",'password':'invalid'})]:
            response=self.client.get(path,query_string=data) if method=='GET' else self.client.post(path,json=data)
            self.assertLess(response.status_code,500)
            text=response.get_data(as_text=True).lower()
            for leak in ['select ', 'sqlite', 'traceback', 'syntax error', 'unrecognized token']:
                self.assertNotIn(leak,text)
            if response.is_json:
                self.assertNotIn('query',response.json)

    def test_normal_routes_still_work(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertTrue(self.client.post('/login',json={'username':'alice','password':'password123'}).json['ok'])
        self.assertTrue(self.client.get('/search?q=Mug').json['results'])
        self.assertFalse(self.module.app.debug)

if __name__=='__main__':
    unittest.main()
