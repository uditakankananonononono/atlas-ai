"""Row687 bounded supplied TDD receipt consistency, never test execution."""
from __future__ import annotations
import unicodedata


def _fail(code):
    raise ValueError('TESTDR687:'+code)


def _fields(value,keys,name):
    if type(value) is not dict:_fail('type:'+name)
    if len(value)>64:_fail('fields:'+name)
    for key in value:
        if type(key) is not str:_fail('fields:'+name)
        if key not in keys:_fail('fields:'+name)
    if len(value)!=len(keys):_fail('fields:'+name)


def _text(value,name):
    if type(value) is not str:_fail('type:'+name)
    if len(value)>256:_fail('text_length:'+name)
    if any(unicodedata.category(c) in ('Cc','Cf','Zl','Zp') for c in value):
        _fail('text_control:'+name)
    if not value.strip():_fail('empty:'+name)
    return value


def _list(value,name,cap):
    if type(value) is not list:_fail('type:'+name)
    if len(value)>cap:_fail('limit:'+name)
    if not value:_fail('empty:'+name)
    return value


def run(request):
    _fields(request,('as_of','cycles'),'request')
    label=_text(request['as_of'],'as_of')
    cycles=_list(request['cycles'],'cycles',64)
    seen=set();reports=[]
    for cycle in cycles:
        _fields(cycle,('id','behavior','receipts'),'cycle')
        cid=_text(cycle['id'],'cycle_id');behavior=_text(cycle['behavior'],'behavior')
        if cid in seen:_fail('duplicate:cycle_id')
        seen.add(cid)
        receipts=_list(cycle['receipts'],'receipts',3)
        if len(receipts)!=3:_fail('count:receipts')
        counts={};test_sets=[];ordinals=[];suites=[];revisions=[];refs=[]
        for stage,receipt in zip(('red','green','refactor'),receipts):
            _fields(receipt,('stage','ordinal','revision_ref','suite_ref','evidence_ref','results'),'receipt')
            if type(receipt['stage']) is not str:_fail('stage:receipts')
            if len(receipt['stage'])>256:_fail('stage:receipts')
            if receipt['stage']!=stage:_fail('stage:receipts')
            ordinal=receipt['ordinal']
            if type(ordinal) is not int or not 1<=ordinal<=10**9:_fail('integer:ordinal')
            ordinals.append(ordinal)
            suites.append(_text(receipt['suite_ref'],'suite_ref'))
            revisions.append(_text(receipt['revision_ref'],'revision_ref'))
            refs.append(_text(receipt['evidence_ref'],'evidence_ref'))
            results=_list(receipt['results'],'results',100)
            ids=set();stage_counts={'PASS':0,'FAIL':0}
            for result in results:
                _fields(result,('id','outcome'),'result')
                tid=_text(result['id'],'test_id')
                if tid in ids:_fail('duplicate:test_id')
                ids.add(tid)
                outcome=result['outcome']
                if type(outcome) is not str:_fail('outcome:result')
                if len(outcome)>256:_fail('outcome:result')
                if outcome not in stage_counts:_fail('outcome:result')
                stage_counts[outcome]+=1
            counts[stage]=stage_counts;test_sets.append(ids)
        reasons=[]
        if not ordinals[0]<ordinals[1]<ordinals[2]:reasons.append('stage_order_not_increasing')
        if counts['red']['FAIL']==0:reasons.append('red_has_no_failure')
        if counts['green']['FAIL']>0:reasons.append('green_has_failure')
        if counts['refactor']['FAIL']>0:reasons.append('refactor_has_failure')
        if not suites[0]==suites[1]==suites[2]:reasons.append('suite_ref_changed')
        if not test_sets[0]==test_sets[1]==test_sets[2]:reasons.append('test_ids_changed')
        if revisions[0]==revisions[1]:reasons.append('red_green_revision_unchanged')
        reports.append(dict(id=cid,behavior=behavior,declaration_consistent=not reasons,reasons=reasons,
                            result_counts=counts,evidence_refs=refs))
    return dict(as_of=label,status='supplied_receipt_consistency_only',cycles=reports,
                consistent_cycles=sum(r['declaration_consistent'] for r in reports),
                tests_executed=False,evidence_verified=False,repository_behavior_verified=False,
                release_authority=False)
