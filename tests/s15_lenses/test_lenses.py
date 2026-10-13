import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"backend/app/modules/m20_general_cognitive_worker/c31_s15"))
from app.modules.m20_general_cognitive_worker.c31_s15.lenses import run, Refused, DEFINITIONS

class Tests(unittest.TestCase):
    def test_lenses_distinct_deterministic(self):
        a=run({'idea':'Reduce water wasted in a small garden','lenses':['pattern-first','systemizing','reflective-depth']},as_of='2026-10-11')
        self.assertEqual(a,run({'idea':'Reduce water wasted in a small garden','lenses':['pattern-first','systemizing','reflective-depth']},as_of='2026-10-11'))
        self.assertEqual(a['count'],3)
        self.assertEqual(len({x['questions'][0] for x in a['angles']}),3)
        self.assertTrue(all('Reduce water wasted in a small garden' in x['questions'][0] for x in a['angles']))
        self.assertIn('not a diagnosis',a['disclaimer'])
        self.assertIn('not_implemented',a['scope'])

    def test_each_definition_executed(self):
        for key in DEFINITIONS:
            a=run(dict(idea='Design a quiet library',lenses=[key]),as_of='2026-10-11')
            self.assertEqual(a['angles'][0]['lens'],key)
            self.assertEqual(len(a['angles'][0]['questions']),3)
            self.assertTrue(a['angles'][0]['next_step'])

    def test_invalid_lens(self):
        for lenses in ([],['unknown'],['systemizing','systemizing'],['autism'],list(DEFINITIONS)+['unknown']):
            with self.assertRaises(Refused):run(dict(idea='Design a garden',lenses=lenses),as_of='2026-10-11')

    def test_idea_limits(self):
        for idea in ('','   ','x'*2001,None,17):
            with self.assertRaises(Refused):run(dict(idea=idea,lenses=['systemizing']),as_of='2026-10-11')
        self.assertEqual(run(dict(idea='x'*2000,lenses=['systemizing']),as_of='2026-10-11')['count'],1)

    def test_clinical_refusal(self):
        for idea in ('Diagnose my depression','Imitate autism as a medical condition','Mimic savant syndrome','Do I have autism?'):
            with self.assertRaisesRegex(Refused,'FLEET_REFUSED_CLINICAL'):
                run(dict(idea=idea,lenses=['pattern-first']),as_of='2026-10-11')
        with self.assertRaisesRegex(Refused,'FLEET_REFUSED_CLINICAL'):
            run(dict(idea='Design a garden',lenses=['systemizing'],clinical_claim=True),as_of='2026-10-11')

    def test_nonclinical_not_medical_claim(self):
        result=run(dict(idea='Design accessible support for autistic students',lenses=['systemizing']),as_of='2026-10-11')
        self.assertIn('no clinical validity',result['disclaimer'])

    def test_schema(self):
        for request in ({},dict(idea='Build a garden',lenses='systemizing'),dict(idea='Build a garden',lenses=['systemizing'],extra=1),None):
            with self.assertRaises(Refused):run(request,as_of='2026-10-11')

    def test_policy_called(self):
        calls=[]
        def guard(action):calls.append(action);return None
        run(dict(idea='Build a garden',lenses=['systemizing']),as_of='2026-10-11',guard=guard)
        self.assertEqual(len(calls),1)

    def test_policy_failure_prevents_run(self):
        def guard(action):raise PermissionError('POLICY_REFUSED_OUTREACH')
        with self.assertRaises(PermissionError):run(dict(idea='Build a garden',lenses=['systemizing']),as_of='2026-10-11',guard=guard)

    def test_as_of_required(self):
        for as_of in ('','not-date',None):
            with self.assertRaises(Refused):run(dict(idea='Build a garden',lenses=['systemizing']),as_of=as_of)

if __name__=='__main__':unittest.main()

class GuardEdges(unittest.TestCase):
    def test_types_and_limits(self):
        for request in (dict(idea='x',lenses=['systemizing'],clinical_claim='false'),dict(idea='x',lenses=[1]),dict(idea='x',lenses=list(DEFINITIONS)+['systemizing'])):
            with self.assertRaises(Refused):run(request,as_of='2026-10-11')
        self.assertEqual(run(dict(idea='x',lenses=list(DEFINITIONS)),as_of='2026-10-11')['count'],len(DEFINITIONS))
    def test_each_prompt_uses_idea_and_disclaimer_exact(self):
        from lenses import DISCLAIMER
        a=run(dict(idea='test sentinel',lenses=list(DEFINITIONS)),as_of='2026-10-11')
        self.assertEqual(a['disclaimer'],DISCLAIMER)
        self.assertTrue(all('test sentinel' in q for angle in a['angles'] for q in angle['questions']))
    def test_policy_action_is_read(self):
        calls=[]
        run(dict(idea='x',lenses=['systemizing']),as_of='2026-10-11',guard=calls.append)
        self.assertEqual(calls,['read'])

class MutationRepair(unittest.TestCase):
    def test_falsey_nonbool_clinical_flag(self):
        for value in (0,'',[],None):
            with self.assertRaisesRegex(Refused,'FLEET_REFUSED_SCHEMA'):
                run(dict(idea='garden',lenses=['systemizing'],clinical_claim=value),as_of='2026-10-11')
    def test_selected_lens_has_its_own_strategy(self):
        self.assertIn('inputs, outputs',run(dict(idea='garden',lenses=['systemizing']),as_of='2026-10-11')['angles'][0]['questions'][0])
        self.assertIn('human cost',run(dict(idea='garden',lenses=['reflective-depth']),as_of='2026-10-11')['angles'][0]['questions'][0])

class RoutesTests(unittest.TestCase):
    def test_route_tenant_and_guard(self):
        from app.modules.m20_general_cognitive_worker.c31_s15.route_adapter import Routes
        r=Routes({},lambda action:None)
        with self.assertRaises(Refused):r.dispatch('POST','/api/v1/c31/lenses/run','',dict(idea='garden',lenses=['systemizing']),as_of='2026-10-11')
        a=r.dispatch('POST','/api/v1/c31/lenses/run','a',dict(idea='garden',lenses=['systemizing']),as_of='2026-10-11')
        self.assertEqual(r.dispatch('GET','/api/v1/c31/lenses/report','a',as_of='2026-10-11'),a)
        with self.assertRaises(Refused):r.dispatch('GET','/api/v1/c31/lenses/report','b',as_of='2026-10-11')
        with self.assertRaises(Refused):r.dispatch('GET','/wrong','a',as_of='2026-10-11')
        def deny(action):raise PermissionError('blocked')
        r.guard=deny
        with self.assertRaises(PermissionError):r.dispatch('GET','/api/v1/c31/lenses/report','a',as_of='2026-10-11')


class PackageTests(unittest.TestCase):
    def test_package_import_guard(self):
        import subprocess
        code=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker'
        if not code.exists():return
        p=subprocess.run([sys.executable,'-c',"from c31_s15.lenses import run; from c31_s15.route_adapter import Routes; r=run({'idea':'garden','lenses':['systemizing']},as_of='2026-10-11'); assert r['count']==1"],cwd=code,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
