"""Finite declared-rule evaluator. Never executes code or certifies a repository."""
from __future__ import annotations

import math
from typing import Any

LIMITS = {'fields':32, 'rules':64, 'examples':128, 'questions':64,
          'depth':8, 'nodes':64, 'text':2000, 'id':128, 'sources':16}
_TYPES = {'integer','number','string','boolean'}
_COMPARATORS = {'eq','ne','lt','le','gt','ge'}


def _object(value: Any, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ValueError('unknown or missing schema fields')
    return value


def _text(value: Any, limit: int) -> str:
    if type(value) is not str or not value.strip() or len(value)>limit:
        raise ValueError('nonempty bounded text required')
    return value


def _sources(value: Any) -> list[str]:
    if type(value) is not list or not 1<=len(value)<=LIMITS['sources']:
        raise ValueError('bounded source IDs required')
    ids=[_text(s,LIMITS['id']) for s in value]
    if len(set(ids))!=len(ids):
        raise ValueError('duplicate source ID')
    return sorted(ids)


def _scalar(value: Any, kind: str) -> Any:
    valid = ((kind=='integer' and type(value) is int and abs(value)<=2**53)
             or (kind=='number' and type(value) in (int,float)
                 and abs(value)<=2**53 and math.isfinite(value))
             or (kind=='boolean' and type(value) is bool)
             or (kind=='string' and type(value) is str and len(value)<=LIMITS['text']))
    if not valid:
        raise ValueError('scalar type or bound mismatch')
    return value


def _rows(value: Any, key: str, keys: set[str], nonempty: bool=False) -> list[dict]:
    if type(value) is not list or len(value)>LIMITS[key] or (nonempty and not value):
        raise ValueError('collection bound: '+key)
    seen=set(); out=[]
    for row in value:
        _object(row,keys); identity=_text(row['id'],LIMITS['id'])
        if identity in seen:
            raise ValueError('duplicate '+key+' ID')
        seen.add(identity);out.append(row)
    return sorted(out,key=lambda r:r['id'])


def _predicate(value: Any, fields: dict[str,str], depth: int, count: list[int]) -> dict:
    count[0]+=1
    if depth>LIMITS['depth'] or count[0]>LIMITS['nodes']:
        raise ValueError('predicate depth or node bound')
    if type(value) is not dict or type(value.get('op')) is not str:
        raise ValueError('predicate object required')
    op=value['op']
    if op in _COMPARATORS:
        _object(value,{'op','field','value'})
        field=_text(value['field'],LIMITS['id'])
        if field not in fields:
            raise ValueError('unknown field reference')
        kind=fields[field]
        if op in {'lt','le','gt','ge'} and kind not in {'integer','number'}:
            raise ValueError('ordering requires numeric field')
        return {'op':op,'field':field,'value':_scalar(value['value'],kind)}
    if op=='not':
        _object(value,{'op','arg'})
        return {'op':op,'arg':_predicate(value['arg'],fields,depth+1,count)}
    if op in {'and','or'}:
        _object(value,{'op','args'})
        if type(value['args']) is not list or not value['args'] or len(value['args'])>LIMITS['nodes']:
            raise ValueError('bounded nonempty boolean operands required')
        return {'op':op,'args':[_predicate(x,fields,depth+1,count) for x in value['args']]}
    raise ValueError('unknown predicate operator')


def _run(p: dict, inputs: dict) -> bool:
    op=p['op']
    if op=='not':return not _run(p['arg'],inputs)
    if op in {'and','or'}:
        outcomes=[_run(x,inputs) for x in p['args']]
        return all(outcomes) if op=='and' else any(outcomes)
    a=inputs[p['field']];b=p['value']
    if op=='eq':return a==b
    if op=='ne':return a!=b
    if op=='lt':return a<b
    if op=='le':return a<=b
    if op=='gt':return a>b
    return a>=b


def evaluate_example_mapping(data: dict[str,Any]) -> dict[str,Any]:
    """Validate the complete packet before computing any rule outcomes."""
    _object(data,{'story','fields','rules','examples','questions'})
    story=_text(data['story'],LIMITS['text'])
    field_rows=_rows(data['fields'],'fields',{'id','type'},True)
    fields={}
    for row in field_rows:
        if type(row['type']) is not str or row['type'] not in _TYPES:
            raise ValueError('unknown field type')
        fields[row['id']]=row['type']
    rules=[]
    for row in _rows(data['rules'],'rules',{'id','predicate','source_ids'},True):
        rules.append({'id':row['id'],'predicate':_predicate(row['predicate'],fields,1,[0]),'source_ids':_sources(row['source_ids'])})
    rule_ids={r['id'] for r in rules}
    examples=[]
    for row in _rows(data['examples'],'examples',{'id','inputs','expected','source_ids'}):
        inputs=_object(row['inputs'],set(fields))
        values={f:_scalar(inputs[f],fields[f]) for f in sorted(fields)}
        expected=row['expected']
        if type(expected) is not dict or not expected:
            raise ValueError('nonempty expected rule outcomes required')
        for ref,outcome in expected.items():
            if type(ref) is not str or ref not in rule_ids:
                raise ValueError('unknown rule reference')
            if type(outcome) is not bool:
                raise ValueError('expected outcome must be boolean')
        examples.append({'id':row['id'],'inputs':values,'expected':dict(sorted(expected.items())),'source_ids':_sources(row['source_ids'])})
    questions=[]
    for row in _rows(data['questions'],'questions',{'id','text','source_ids'}):
        questions.append({'id':row['id'],'text':_text(row['text'],LIMITS['text']),'source_ids':_sources(row['source_ids'])})
    mismatches=[];covered=set()
    for example in examples:
        actual={r['id']:_run(r['predicate'],example['inputs']) for r in rules}
        example['actual']=actual
        for rule in rules:
            rid=rule['id']
            if rid not in example['expected']:continue
            covered.add(rid)
            if actual[rid]!=example['expected'][rid]:
                mismatches.append({'example_id':example['id'],'rule_id':rid,'expected':example['expected'][rid],
                                   'actual':actual[rid],'source_ids':sorted(set(example['source_ids']+rule['source_ids']))})
    uncovered=sorted(rule_ids-covered)
    satisfied=bool(examples) and not (mismatches or uncovered or questions)
    return {'story':story,'fields':[dict(r) for r in field_rows],'rules':rules,'examples':examples,
            'mismatches':mismatches,'uncovered_rule_ids':uncovered,'unresolved_questions':questions,
            'mapping_satisfied':satisfied,'status':'satisfied' if satisfied else 'needs_resolution',
            'evaluation_scope':'finite_declared_rule_examples_only',
            'repository_behavior_verified':False,'release_authorized':False}
