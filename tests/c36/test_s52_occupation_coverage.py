import copy
import pytest
from app.modules.c36.gaps import run


def payload():
    return {'as_of':'2026-10-13','taxonomy_source':'O*NET supplied export 30.3',
            'occupations':[{'id':'a','title':'Analyst','tasks':[{'id':'a1','text':'Compare records'}, {'id':'a2','text':'Review results'}]},
                           {'id':'b','title':'Writer','tasks':[{'id':'b1','text':'Write report'}]}],
            'opportunities':[{'id':'p','occupation_id':'a','task_ids':['a1'], 'proposal':'Compare supplied rows', 'evidence_refs':['test:compare']}]}


def rejects(p, reason):
    with pytest.raises(ValueError) as exc:
        run(p)
    assert str(exc.value) == 'VENT_REFUSED_' + reason


def test_exact_coverage_and_gaps():
    r=run(payload())
    assert r['coverage']=={'occupations_supplied':2,'occupations_with_proposals':1,'occupation_percent':50.0,
                           'tasks_supplied':3,'tasks_with_proposals':1,'task_percent':100/3}
    assert r['gaps']==[{'occupation_id':'a','task_ids':['a2']},{'occupation_id':'b','task_ids':['b1']}]
    assert r['mapping'][0]['tasks'][0]['opportunity_ids']==['p']
    assert r['mapping'][1]['opportunity_ids']==[]
    assert r['proposal_evidence']=='supplied_unverified'
    assert r['execution_coverage_verified'] is False
    assert r['scope']['as_of']=='2026-10-13'
    assert 'execution' in r['scope']['not_implemented']


def test_nonmutation_determinism_and_detached_result():
    p=payload(); before=copy.deepcopy(p); a=run(p); b=run(p)
    assert a==b and p==before
    a['mapping'][0]['tasks'][0]['text']='changed'
    a['opportunities'][0]['evidence_refs'].append('changed')
    assert p==before and run(p)==b


def test_union_does_not_double_count_and_order_is_canonical():
    p=payload(); p['opportunities'].append({**copy.deepcopy(p['opportunities'][0]), 'id':'q'})
    a=run(p); p['occupations'].reverse(); p['opportunities'].reverse()
    assert run(p)==a
    assert a['coverage']['tasks_with_proposals']==1
    assert a['mapping'][0]['tasks'][0]['opportunity_ids']==['p','q']


def test_no_proposals_and_empty_taxonomy():
    p=payload(); p['opportunities']=[]; r=run(p)
    assert r['coverage']['occupation_percent']==0 and r['coverage']['task_percent']==0
    p['occupations']=[]; r=run(p)
    assert r['coverage']['occupation_percent'] is None and r['coverage']['task_percent'] is None
    assert r['mapping']==r['gaps']==[]


def test_taskless_occupation_has_no_task_denominator():
    p=payload(); p['occupations']=[{'id':'a','title':'Analyst','tasks':[]}]; p['opportunities']=[]
    r=run(p); assert r['coverage']['task_percent'] is None
    assert r['gaps']==[{'occupation_id':'a','task_ids':[]}]


@pytest.mark.parametrize('field,value,reason',[
 ('as_of','2026-02-30','BAD_DATE:as_of'),('as_of','2026-1-13','BAD_DATE:as_of'),
 ('as_of',True,'BAD_TYPE:as_of'),('taxonomy_source','','EMPTY:taxonomy_source'),
 ('taxonomy_source','x\u202e','CONTROL_CHARS:taxonomy_source'),
 ('taxonomy_source','x'*501,'TEXT_TOO_LONG:taxonomy_source'),
 ('occupations',{},'BAD_TYPE:occupations'),('opportunities',(), 'BAD_TYPE:opportunities')])
def test_top_fields(field,value,reason):
    p=payload();p[field]=value;rejects(p,reason)


def test_missing_unknown_and_nonstring_keys():
    p=payload();del p['as_of'];rejects(p,'MISSING:as_of')
    p=payload();p['surprise']=1;rejects(p,'UNKNOWN:request')
    p=payload();p[2]=1;rejects(p,'BAD_TYPE:key')


@pytest.mark.parametrize('key,rule',[('spend','SPEND'),('send','OUTREACH'),('submit','OUTREACH'),
 ('fake_accounts','FAKEACCT'),('autopost','AUTOPOST'),('scrape','SCRAPE'),('trade','TRADE')])
@pytest.mark.parametrize('value',[False,True])
def test_forbidden_flags_never_authorize(key,rule,value):
    p=payload();p[key]=value;rejects(p,rule)
    p=payload();p['opportunities'][0][key]=value;rejects(p,rule)


def test_reference_and_duplicate_integrity():
    p=payload();p['opportunities'][0]['occupation_id']='missing';rejects(p,'UNKNOWN_OCCUPATION')
    p=payload();p['opportunities'][0]['task_ids']=['b1'];rejects(p,'UNKNOWN_TASK')
    p=payload();p['opportunities'][0]['task_ids']=['a1','a1'];rejects(p,'DUPLICATE:task_ids')
    p=payload();p['occupations'].append(copy.deepcopy(p['occupations'][0]));rejects(p,'DUPLICATE:occupation_id')
    p=payload();p['occupations'][0]['tasks'].append(copy.deepcopy(p['occupations'][0]['tasks'][0]));rejects(p,'DUPLICATE:task_id')
    p=payload();p['opportunities'].append(copy.deepcopy(p['opportunities'][0]));rejects(p,'DUPLICATE:opportunity_id')
    p=payload();p['opportunities'][0]['task_ids']=[];rejects(p,'EMPTY:task_ids')
    p=payload();p['opportunities'][0]['evidence_refs']=[];rejects(p,'EMPTY:evidence_refs')


class HostileDict(dict):
    def __iter__(self):raise AssertionError('must not iterate subclass')
    def items(self):raise AssertionError('must not iterate subclass')
class HostileList(list):
    def __iter__(self):raise AssertionError('must not iterate subclass')


def test_exact_shapes_and_no_recursive_inputs():
    rejects(HostileDict(payload()),'BAD_TYPE:request')
    p=payload();p['occupations']=HostileList(p['occupations']);rejects(p,'BAD_TYPE:occupations')
    p=payload();p['occupations'][0]=HostileDict(p['occupations'][0]);rejects(p,'BAD_TYPE:occupation')
    p=payload();p['occupations'][0]['tasks'][0]['text']=p;rejects(p,'BAD_TYPE:task_text')


def test_caps_and_no_content_in_error():
    p=payload();p['occupations']=[{}]*2001;rejects(p,'OVERSIZE:occupations')
    p=payload();p['opportunities']=[{}]*10001;rejects(p,'OVERSIZE:opportunities')
    p=payload();p['occupations'][0]['tasks']=[{}]*201;rejects(p,'OVERSIZE:tasks')
    p=payload();p['occupations'][0]['id']='secret\n';rejects(p,'CONTROL_CHARS:occupation_id')
    p=payload();p['opportunities'][0]['task_ids']=['a1']*201;rejects(p,'OVERSIZE:task_ids')
    p=payload();p['opportunities'][0]['evidence_refs']=['x']*21;rejects(p,'OVERSIZE:evidence_refs')


def test_full_coverage_is_only_supplied_proposals():
    p=payload();p['occupations']=[p['occupations'][0]]
    p['opportunities'][0]['task_ids']=['a1','a2']
    r=run(p);assert r['coverage']['occupation_percent']==100
    assert r['coverage']['task_percent']==100 and r['gaps']==[]
    assert not r['execution_coverage_verified']


@pytest.mark.parametrize('field,cap', [('occupation_id',128),('occupation_title',500),('task_id',128),('task_text',2000),('opportunity_id',128),('proposal',4000)])
def test_scalar_cap_exact_and_one_over(field,cap):
    p=payload()
    def set_value(v):
        if field=='occupation_id':
            p['occupations'][0]['id']=v;p['opportunities'][0]['occupation_id']=v
        elif field=='occupation_title':p['occupations'][0]['title']=v
        elif field=='task_id':
            p['occupations'][0]['tasks'][0]['id']=v;p['opportunities'][0]['task_ids']=[v]
        elif field=='task_text':p['occupations'][0]['tasks'][0]['text']=v
        elif field=='opportunity_id':p['opportunities'][0]['id']=v
        else:p['opportunities'][0]['proposal']=v
    set_value('x'*cap);run(p)
    set_value('x'*(cap+1));rejects(p,'TEXT_TOO_LONG:'+field)


def test_resource_caps_exact():
    p=payload();p['occupations']=[{'id':str(i),'title':'T','tasks':[]} for i in range(2000)];p['opportunities']=[]
    assert run(p)['coverage']['occupations_supplied']==2000
    p=payload();p['occupations'][0]['tasks']=[{'id':str(i),'text':'T'} for i in range(200)]
    p['opportunities'][0]['task_ids']=[str(i) for i in range(200)]
    p['opportunities'][0]['evidence_refs']=[str(i) for i in range(20)]
    assert run(p)['coverage']['tasks_with_proposals']==200
    p=payload();p['opportunities']=[{**copy.deepcopy(p['opportunities'][0]),'id':str(i)} for i in range(10000)]
    assert len(run(p)['opportunities'])==10000


def test_date_formats_and_key_shapes():
    for value in ['20261013','2026-W42-2','2026-10-1','2026-00-13']:
        p=payload();p['as_of']=value;rejects(p,'BAD_DATE:as_of')
    p=payload();p['as_of']='2024-02-29';assert run(p)['scope']['as_of']=='2024-02-29'
    p=payload();p['occupations'][0][3]='secret';rejects(p,'BAD_TYPE:key')
    p=payload();p['occupations'][0]['bad\u202e']='secret';rejects(p,'CONTROL_CHARS:key')
    p=payload();p['occupations'][0].update({str(i):0 for i in range(30)});rejects(p,'OVERSIZE:occupation')
    p=payload();p['opportunities'][0]['evidence_refs']=['x','x'];rejects(p,'DUPLICATE:evidence_refs')


def test_text_source_reference_and_key_caps():
    p=payload();p['taxonomy_source']='x'*500;run(p)
    p['taxonomy_source']='x'*501;rejects(p,'TEXT_TOO_LONG:taxonomy_source')
    p=payload();p['opportunities'][0]['evidence_refs']=['x'*500];run(p)
    p['opportunities'][0]['evidence_refs']=['x'*501];rejects(p,'TEXT_TOO_LONG:evidence_refs')
    p=payload();p['x'*128]=0;rejects(p,'UNKNOWN:request')
    p=payload();p['x'*129]=0;rejects(p,'TEXT_TOO_LONG:key')
    p=payload();p['occupations'][0].update({str(i):0 for i in range(29)});rejects(p,'UNKNOWN:occupation')


def test_independent_id_length_guards_and_date_raw_cap():
    p=payload();p['occupations'][0]['id']='x'*129;rejects(p,'TEXT_TOO_LONG:occupation_id')
    p=payload();p['opportunities'][0]['occupation_id']='x'*129;rejects(p,'TEXT_TOO_LONG:occupation_id')
    p=payload();p['as_of']='2026-10-130';rejects(p,'TEXT_TOO_LONG:as_of')
