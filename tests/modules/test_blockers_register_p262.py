"""Declared-input register tests, no external verification."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('blockers',Path(__file__).resolve().parents[2]/'backend/app/modules/instinct_doc/blockers_register_p262.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def item(i='A',status='BLOCKED'):
    return dict(id=i,owner='declared-team',status=status,reason='supplied reason',source_refs=['caller-ref'])

class RegisterTests(unittest.TestCase):
    def test_sort_counts_and_truth_labels(self):
        rows=[item('z','RESOLVED'),item('a','UNVERIFIED'),item('b')]
        r=module.register_blockers(rows)
        self.assertEqual(r['counts'],{'BLOCKED':1,'UNVERIFIED':1,'RESOLVED':1})
        self.assertEqual([x['id'] for x in r['items']],['a','b','z'])
        self.assertEqual(r['open_item_ids'],['a','b'])
        self.assertEqual(r,module.register_blockers(list(reversed(rows))))
        self.assertEqual(r['status'],'declared_input_register_only')
        self.assertIs(r['evidence_verified'],False)
        self.assertIs(r['actual_blockers_exhaustively_checked'],False)
        self.assertIs(r['completion_verified'],False)
        for x in r['items']:
            self.assertIs(x['owner_is_caller_declared'],True)
            self.assertIs(x['status_is_caller_declared'],True)
    def test_empty_not_completeness(self):
        r=module.register_blockers([])
        self.assertEqual(r['items'],[]);self.assertEqual(r['open_item_ids'],[])
        self.assertIs(r['completion_verified'],False)
        self.assertEqual(r['boundary'],'Only supplied records checked. Empty register does not prove absence of actual blockers; RESOLVED and owner are caller declarations, not verified completion or assignment.')
    def test_exact_n_nplus1(self):
        module.register_blockers([item(str(i)) for i in range(256)])
        with self.assertRaises(ValueError) as e:module.register_blockers([item(str(i)) for i in range(257)])
        self.assertEqual(str(e.exception),'items: expected list of at most 256 records')
        for field,limit in [('id',128),('owner',128),('reason',2000)]:
            row=item();row[field]='x'*limit;module.register_blockers([row])
            row[field]+='x'
            with self.assertRaises(ValueError) as e:module.register_blockers([row])
            self.assertEqual(str(e.exception),f'{field}: expected nonblank string of length 1..{limit}')
    def test_refs_bounds_canonical_order(self):
        row=item();row['source_refs']=['z','a'];a=module.register_blockers([row])
        row['source_refs'].reverse();self.assertEqual(a,module.register_blockers([row]))
        self.assertEqual(a['items'][0]['source_refs'],['a','z'])
        row['source_refs']=['x'*256];module.register_blockers([row]);row['source_refs']=['x'*257]
        with self.assertRaisesRegex(ValueError,'source_ref: expected nonblank string of length 1..256'):module.register_blockers([row])
        row['source_refs']=[str(i) for i in range(16)];module.register_blockers([row]);row['source_refs'].append('17')
        with self.assertRaisesRegex(ValueError,'source_refs: expected list of at most 16 references'):module.register_blockers([row])
    def test_fresh_duplicate_exact_error(self):
        with self.assertRaises(ValueError) as e:module.register_blockers([item('fresh-999'),item('fresh-999')])
        self.assertEqual(str(e.exception),'duplicate item id: fresh-999')
        row=item();row['source_refs']=['a','a']
        with self.assertRaisesRegex(ValueError,'duplicate source_ref: a'):module.register_blockers([row])
    def test_types_and_unknown_status(self):
        for status in ['done','blocked',True,None]:
            row=item();row['status']=status
            with self.assertRaisesRegex(ValueError,'status: expected BLOCKED, UNVERIFIED or RESOLVED'):module.register_blockers([row])
        for value in [None,{},'x',True]:
            with self.assertRaisesRegex(ValueError,'items: expected list of at most 256 records'):module.register_blockers(value)
        for field in ['id','owner','reason']:
            for v in ['', ' ',None,True,1]:
                row=item();row[field]=v
                with self.assertRaises(ValueError):module.register_blockers([row])
    def test_schema_no_mutation_and_missing_refs(self):
        row=item();row['source_refs']=[]
        r=module.register_blockers([row]);self.assertEqual(r['missing_source_item_ids'],['A'])
        r['items'][0]['source_refs'].append('new');self.assertEqual(row['source_refs'],[])
        for changed in [{**row,'completion_verified':True},{k:v for k,v in row.items() if k!='owner'}]:
            with self.assertRaisesRegex(ValueError,'item: exactly id,owner,status,reason,source_refs required'):module.register_blockers([changed])
    def test_status_oracle(self):
        import itertools
        for combo in itertools.product(['BLOCKED','UNVERIFIED','RESOLVED'],repeat=3):
            r=module.register_blockers([item(str(i),s) for i,s in enumerate(combo)])
            self.assertEqual(r['counts'],{s:combo.count(s) for s in ['BLOCKED','UNVERIFIED','RESOLVED']})
            self.assertEqual(r['open_item_ids'],[str(i) for i,s in enumerate(combo) if s!='RESOLVED'])

if __name__=='__main__':unittest.main(verbosity=2)
