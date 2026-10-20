import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
import yaml

spec = importlib.util.spec_from_file_location('checker', Path(__file__).parents[1] / 'scripts/memory_check.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config(2)
        self.base = dict(schema_version=2, id='report.monthly', kind='workflow', title='Monthly report', status='candidate', scope='project', tags=['report'], created='2026-10-20', updated='2026-10-20', sources=[], supersedes=[], context='Monthly totals, same definitions', verification='Not executed yet', related=[], inputs=['Source file and month'], steps=['Check definitions', 'Sum and reconcile'], acceptance=['Totals equal source'])
    def config(self, version):
        (self.root/'config.yaml').write_text(yaml.safe_dump(dict(schema_version=version, projects=dict(current='..'))), encoding='utf-8')
    def put(self, item, filename=None):
        path = self.root/'memories'/item['kind']/(filename or item['id']+'.md')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\n'+yaml.safe_dump(item)+'---\nEvidence\n',encoding='utf-8')
    def result(self): return checker.inspect(self.root)
    def test_empty_library(self): self.assertEqual(self.result()['errors'], [])
    def test_v1_compatibility(self):
        self.config(1)
        row=dict(self.base, schema_version=1, kind='fix')
        self.put(row)
        self.assertFalse(self.result()['errors'])
    def test_candidate_and_readonly_preview(self):
        self.put(self.base)
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.result()
        self.assertFalse(result['errors'])
        self.assertIn('report.monthly',checker.render_index(result['records']))
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_active_requires_evidence(self):
        self.put(dict(self.base,status='active'))
        self.assertTrue(self.result()['errors'])
    def test_active_with_passed_run(self):
        self.put(dict(self.base,status='active',related=['run.monthly']))
        run=dict(self.base,id='run.monthly',kind='run',status='active',outcome='passed',related=['report.monthly'])
        self.put(run)
        self.assertFalse(self.result()['errors'])
        self.put(dict(run,outcome='failed'))
        self.assertTrue(self.result()['errors'])
    def test_missing_related(self):
        self.put(dict(self.base,related=['missing']))
        self.assertTrue(self.result()['errors'])
    def test_invalid_source(self):
        self.put(dict(self.base,sources=[dict(project='current',path='../secret')]))
        self.assertTrue(self.result()['errors'])
    def test_duplicate(self):
        self.put(self.base)
        self.put(self.base,'copy.md')
        self.assertTrue(self.result()['errors'])
    def test_cycle(self):
        self.put(dict(self.base,supersedes=['report.monthly']))
        self.assertTrue(self.result()['errors'])
    def test_v2_requires_config_upgrade(self):
        self.config(1); self.put(self.base)
        self.assertTrue(self.result()['errors'])
    def test_invalid_steps(self):
        self.put(dict(self.base,steps=[]))
        self.assertTrue(self.result()['errors'])

if __name__=='__main__': unittest.main()
