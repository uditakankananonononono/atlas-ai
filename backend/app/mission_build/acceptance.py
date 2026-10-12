"""Source-bound acceptance manifests for counted capability requirements.

Review reports preserve missing entries and measured gaps. Names, aliases,
file existence and self-attested pass booleans do not count as acceptance.
Receipts must be supplied by the host's test runner, not web content.
"""
import hashlib
import json
import re


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def inspect_manifest(entries,receipts,*,expected_modules=None,per_module=None,required_concepts=None):
    if type(entries) is not list or len(entries)>10000 or type(receipts) is not list or len(receipts)>10000:
        raise ValueError('bounded entry and receipt arrays required')
    if (per_module is None)!=(expected_modules is None):raise ValueError('module list and per-module count required together')
    if per_module is not None and (type(per_module) is not int or not 1<=per_module<=10000):raise ValueError('positive module count required')
    if required_concepts is not None and (type(required_concepts) is not int or not 1<=required_concepts<=10000):raise ValueError('positive concept count required')
    if expected_modules is not None:
        if not expected_modules or any(type(x) is not str or not x.strip() for x in expected_modules) or len(set(expected_modules))!=len(expected_modules):raise ValueError('distinct expected modules required')
    reports=[];ids=set();implementation_ids=set();evidence={}
    for receipt in receipts:
        node=receipt.get('node_id')
        if type(node) is not str or not node or node in evidence:raise ValueError('unique receipt node_id required')
        if receipt.get('result') not in {'passed','failed','skipped','error'}:raise ValueError('test-runner result required')
        for key in ('source_sha256','test_sha256'):
            if type(receipt.get(key)) is not str or not re.fullmatch('[a-f0-9]{64}',receipt[key]):raise ValueError('source/test digest required')
        evidence[node]=receipt
    for entry in entries:
        ident=entry.get('id');module=entry.get('module');implementation=entry.get('implementation_id')
        if type(ident) is not str or not ident or ident in ids:raise ValueError('distinct entry ids required')
        ids.add(ident)
        if type(module) is not str or not module:raise ValueError('module required')
        if type(implementation) is not str or not implementation:raise ValueError('implementation identity required')
        gaps=[]
        if implementation in implementation_ids:gaps.append('duplicate implementation alias')
        implementation_ids.add(implementation)
        if not entry.get('source_ref'):gaps.append('missing source requirement')
        if entry.get('new_after_baseline') is not True:gaps.append('not demonstrated new')
        tests=entry.get('test_nodes')
        if type(tests) is not list or not tests:gaps.append('missing functional tests');tests=[]
        for node in tests:
            receipt=evidence.get(node)
            if not receipt:gaps.append('missing test receipt:'+str(node))
            elif receipt['result']!='passed':gaps.append('test not passed:'+node)
            elif receipt['source_sha256']!=entry.get('source_sha256') or receipt['test_sha256']!=entry.get('test_sha256'):
                gaps.append('stale source/test receipt:'+node)
        reports.append({'id':ident,'module':module,'accepted_on_supplied_receipts':not gaps,'gaps':gaps})
    counts={}
    for row in reports:
        if row['accepted_on_supplied_receipts']:counts[row['module']]=counts.get(row['module'],0)+1
    deficits={m:max(0,per_module-counts.get(m,0)) for m in expected_modules or []}
    accepted=sum(r['accepted_on_supplied_receipts'] for r in reports)
    return {'entries':reports,'accepted_count':accepted,'by_module':counts,'module_deficits':deficits,
            'concept_deficit':max(0,required_concepts-accepted) if required_concepts is not None else None,
            'manifest_sha256':_digest(entries),'receipts_sha256':_digest(receipts),
            'independent_execution_verified':False,'literal_requirement_closed':False,
            'scope':'Validation of supplied host-runner receipt bindings, not execution or independent review.'}
