"""Direct-call hand acceptance, independent of pytest runner/fixtures."""
import importlib.util
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[2]
path=root/'backend/app/modules/m20_general_cognitive_worker/c33_self_feed'
spec=importlib.util.spec_from_file_location('hand_s21',path/'__init__.py',submodule_search_locations=[str(path)])
m=importlib.util.module_from_spec(spec);sys.modules['hand_s21']=m;spec.loader.exec_module(m)
s=m.Scanner()
snapshot='2026-10-11T15:10:00+05:30'
fixture=(root/'tests/fixtures/s21/pasted.csv').read_bytes()
out=s.run(tenant_id='owner',connector='pasted_csv',payload=fixture,as_of=snapshot)
assert out['counts']['unique']==2
assert [g['theme'] for g in out['clusters']]==['design','engineering']
assert all(b['status']=='draft' and b['source_refs'] for b in out['briefs'])
assert out['action']=='none'
assert s.report('owner',out['report_id'])==out
checks=['supplied fixture two records','two measured themes','draft-only provenance','no effects','owner report roundtrip']
for code,call in [
 ('SOCIAL_REFUSED_NOTFOUND',lambda:s.report('stranger',out['report_id'])),
 ('POLICY_REFUSED_ACTION',lambda:s.run(tenant_id='owner',connector='pasted_csv',payload=fixture,as_of=snapshot,action='post')),
 ('SOCIAL_REFUSED_CONNECTOR',lambda:s.run(tenant_id='owner',connector='instagram_live',payload=fixture,as_of=snapshot)),
]:
    try:call()
    except m.Refusal as exc:assert exc.code==code;checks.append(code)
    else:raise AssertionError('expected refusal')
print(json.dumps({'checks_passed':len(checks),'checks':checks,'report':out},indent=2))
