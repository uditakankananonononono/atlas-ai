import copy
import pytest
from app.modules.c37.company_monitor import CompanyMonitor


def snap(records=None,complete=True):
    return {'company_id':'acme','as_of':'2026-10-13','snapshot_complete':complete,
            'records':records if records is not None else [{'id':'r','kind':'press','url':'https://example.com/press','title':'Product update','text':'Version one'}]}


def create(tmp_path):
    return CompanyMonitor(tmp_path/'watch.sqlite',tenant_id='t')


def test_actual_restart_diff_and_deletion(tmp_path):
    m=create(tmp_path);a=m.record(snap());assert [r['id'] for r in a['added']]==['r']
    m.close();m=create(tmp_path);b=m.record(snap());assert b['unchanged_ids']==['r'] and b['added']==[]
    p=snap();p['records'][0]['text']='Version two';c=m.record(p)
    assert c['changed'][0]['before']['text']=='Version one' and c['changed'][0]['after']['text']=='Version two'
    empty=snap([]);empty['allow_empty_complete']=True;d=m.record(empty);assert d['removed'][0]['text']=='Version two'
    assert m.history('acme')['revisions']==4
    assert d['coverage']=={'supplied_records':0,'added':0,'changed':0,'removed':1,'unchanged':0}
    assert d['scope']['as_of']=='2026-10-13' and d['source_authentication']=='unverified_supplied'


def test_partial_snapshot_preserves_unseen_records(tmp_path):
    m=create(tmp_path);m.record(snap());r=m.record(snap([],False))
    assert r['removed']==[] and r['not_observed_ids']==['r']
    assert m.current('acme')['records'][0]['id']=='r'
    assert m.record(snap())['unchanged_ids']==['r']


def test_tenant_isolation_and_company_isolation(tmp_path):
    path=tmp_path/'watch.sqlite';a=CompanyMonitor(path,tenant_id='a');b=CompanyMonitor(path,tenant_id='b')
    a.record(snap());assert b.current('acme') is None
    p=snap();p['company_id']='other';a.record(p)
    assert a.current('acme')['records']==a.current('other')['records']
    assert a.history('acme')['revisions']==1 and a.history('other')['revisions']==1


def test_failed_batch_no_partial_commit(tmp_path):
    m=create(tmp_path);m.record(snap());p=snap();p['records'].append({'id':'bad'})
    with pytest.raises(ValueError):m.record(p)
    assert m.history('acme')['revisions']==1


def test_same_date_allows_separate_revisions_older_date_refuses(tmp_path):
    m=create(tmp_path);m.record(snap());m.record(snap())
    p=snap();p['as_of']='2026-10-12'
    with pytest.raises(ValueError,match='STALE_SNAPSHOT'):m.record(p)
    assert m.history('acme')['revisions']==2


def test_date_url_types_and_duplicate_guard(tmp_path):
    m=create(tmp_path)
    p=snap();p['as_of']='2026-02-30'
    with pytest.raises(ValueError,match='BAD_DATE'):m.record(p)
    for url in ['http://example.com','https://user:pass@example.com','https://example.com:99','https://127.0.0.1','file:///private']:
        p=snap();p['records'][0]['url']=url
        with pytest.raises(ValueError,match='URL'):m.record(p)
    p=snap();p['records']*=2
    with pytest.raises(ValueError,match='DUPLICATE'):m.record(p)
    p=snap();p['snapshot_complete']=1
    with pytest.raises(ValueError,match='BAD_TYPE'):m.record(p)
    assert m.current('acme') is None


def test_effect_fields_refuse_even_false(tmp_path):
    m=create(tmp_path)
    for key,code in [('send','OUTREACH'),('spend','SPEND'),('scrape','SCRAPE'),('trade','TRADE'),('autopost','AUTOPOST'),('fake_accounts','FAKEACCT')]:
        p=snap();p[key]=False
        with pytest.raises(ValueError,match='^INTEL_REFUSED_'+code+'$'):m.record(p)
    assert m.current('acme') is None


def test_detached_and_input_nonmutating(tmp_path):
    m=create(tmp_path);p=snap();before=copy.deepcopy(p);a=m.record(p)
    a['added'][0]['text']='wrong';r=m.current('acme');r['records'][0]['text']='wrong'
    assert p==before and m.current('acme')['records'][0]['text']=='Version one'


def test_history_cap_and_counts(tmp_path):
    m=create(tmp_path)
    for i in range(3):m.record(snap())
    h=m.history('acme',limit=2);assert h['revisions']==3 and len(h['items'])==2 and h['truncated']
    assert [r['revision'] for r in h['items']]==[3,2]
    with pytest.raises(ValueError):m.history('acme',limit=True)


def test_separate_writer_transaction_revisions(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path=tmp_path/'watch.sqlite';m=CompanyMonitor(path,tenant_id='t');m.close()
    def write(i):
        worker=CompanyMonitor(path,tenant_id='t')
        try:return worker.record(snap())['revision']
        finally:worker.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        revisions=list(pool.map(write,range(12)))
    assert sorted(revisions)==list(range(1,13))
    m=CompanyMonitor(path,tenant_id='t');assert m.history('acme')['revisions']==12


def test_write_failure_rolls_back_state_and_history(tmp_path):
    import sqlite3
    m=create(tmp_path);m.record(snap())
    m._db.execute("CREATE TRIGGER test_failure BEFORE INSERT ON company_monitor_history BEGIN SELECT RAISE(ABORT,'blocked'); END;")
    m._db.commit();p=snap();p['records'][0]['text']='changed'
    with pytest.raises(sqlite3.IntegrityError):m.record(p)
    assert m.current('acme')['records'][0]['text']=='Version one'
    assert m.history('acme')['revisions']==1


def test_scalar_exact_caps_and_over(tmp_path):
    m=create(tmp_path)
    for field,cap in [('id',128),('title',500),('text',10000)]:
        p=snap();p['records'][0][field]='x'*cap;m.record(p)
        p['records'][0][field]='x'*(cap+1)
        with pytest.raises(ValueError,match='TEXT_TOO_LONG'):m.record(p)
    p=snap();p['records']=[{'id':str(i),'kind':'press','url':'https://example.com','title':'t','text':'x'} for i in range(1000)]
    assert m.record(p)['coverage']['supplied_records']==1000
    p['records'].append(p['records'][0])
    with pytest.raises(ValueError,match='OVERSIZE:records'):m.record(p)


def test_total_content_cap_and_history_limit_boundary(tmp_path):
    m=create(tmp_path);p=snap();p['records']=[{'id':str(i),'kind':'press','url':'https://example.com','title':'t','text':'x'*10000} for i in range(100)]
    m.record(p);p['records'].append({**p['records'][0],'id':'extra'})
    with pytest.raises(ValueError,match='OVERSIZE:total_text'):m.record(p)
    assert len(m.history('acme',limit=1000)['items'])==1
    with pytest.raises(ValueError):m.history('acme',limit=1001)
    assert m.history('missing')['revisions']==0


class Hostile(dict):
    def __iter__(self):raise AssertionError('foreign iteration')


def test_shapes_unicode_and_unknown_kind(tmp_path):
    m=create(tmp_path)
    for mutate in [lambda p:p.update(records=()),lambda p:p['records'][0].update(title='x\u202e'),lambda p:p['records'][0].update(kind='private'),lambda p:p['records'][0].update(extra=True)]:
        p=snap();mutate(p)
        with pytest.raises(ValueError):m.record(p)
    with pytest.raises(ValueError):m.record(Hostile(snap()))
    p=snap();p['records'][0]['text']=p
    with pytest.raises(ValueError):m.record(p)
    p=snap();p['records'][0][3]='secret'
    with pytest.raises(ValueError,match='BAD_TYPE:key'):m.record(p)
    p=snap();p.update({str(i):0 for i in range(28)})
    with pytest.raises(ValueError,match='BAD_SHAPE'):m.record(p)
    p.update(extra=0)
    with pytest.raises(ValueError,match='OVERSIZE'):m.record(p)


def test_key_identity_kind_date_and_url_caps(tmp_path):
    m=create(tmp_path)
    p=snap();p['x'*129]=0
    with pytest.raises(ValueError,match='TEXT_TOO_LONG:key'):m.record(p)
    with pytest.raises(ValueError,match='TEXT_TOO_LONG:tenant_id'):CompanyMonitor(tmp_path/'other',tenant_id='x'*129)
    p=snap();p['company_id']='x'*129
    with pytest.raises(ValueError,match='TEXT_TOO_LONG:company_id'):m.record(p)
    for fn in (m.current,m.history):
        with pytest.raises(ValueError,match='TEXT_TOO_LONG:company_id'):fn('x'*129)
    p=snap();p['as_of']='2026-10-130'
    with pytest.raises(ValueError,match='TEXT_TOO_LONG:as_of'):m.record(p)
    p=snap();p['records'][0]['kind']='x'*33
    with pytest.raises(ValueError,match='TEXT_TOO_LONG:kind'):m.record(p)
    p=snap();p['records'][0]['url']='https://example.com/'+'x'*1980
    assert len(p['records'][0]['url'])==2000;m.record(p)
    p['records'][0]['url']+='x'
    with pytest.raises(ValueError,match='TEXT_TOO_LONG:url'):m.record(p)


def test_newlines_and_tls_port(tmp_path):
    m=create(tmp_path);p=snap();p['records'][0]['text']='first\nsecond\tthird';p['records'][0]['url']='https://example.com:443/path'
    assert m.record(p)['added'][0]['text']==p['records'][0]['text']
    p['records'][0]['url']='https://example.com:444/path'
    with pytest.raises(ValueError,match='BAD_URL'):m.record(p)


def test_history_exact_counts_and_low_limit(tmp_path):
    m=create(tmp_path);m.record(snap())
    assert m.history('acme',limit=1)['truncated'] is False
    for _ in range(51):m.record(snap())
    assert len(m.history('acme')['items'])==50
    assert m.history('acme',limit=1)['revisions']==52
    assert m.current('acme')['revision']==52
    with pytest.raises(ValueError):m.history('acme',limit=0)


def test_total_one_over_without_individual_overflow(tmp_path):
    m=create(tmp_path);p=snap();p['records']=[{'id':str(i),'kind':'press','url':'https://example.com','title':'t','text':'x'*10000} for i in range(100)]
    p['records'].append({**p['records'][0],'id':'extra','text':'x'})
    with pytest.raises(ValueError,match='OVERSIZE:total_text'):m.record(p)
    assert m.current('acme') is None


def test_empty_complete_explicit_acknowledgment_required(tmp_path):
    m=create(tmp_path);m.record(snap())
    with pytest.raises(ValueError,match='^INTEL_REFUSED_EMPTY_COMPLETE$'):m.record(snap([]))
    p=snap([]);p['allow_empty_complete']=False
    with pytest.raises(ValueError,match='^INTEL_REFUSED_EMPTY_COMPLETE$'):m.record(p)
    p['allow_empty_complete']=1
    with pytest.raises(ValueError,match='^INTEL_REFUSED_BAD_TYPE:allow_empty_complete$'):m.record(p)
    assert m.current('acme')['records'][0]['id']=='r' and m.history('acme')['revisions']==1
    p['allow_empty_complete']=True
    out=m.record(p)
    assert out['removed'][0]['id']=='r' and m.current('acme')['records']==[]
    assert out['empty_complete_acknowledged'] is True


def test_partial_empty_needs_no_ack_and_flag_does_not_authorize_effect(tmp_path):
    m=create(tmp_path);m.record(snap());out=m.record(snap([],False))
    assert out['empty_complete_acknowledged'] is False and out['removed']==[]
    p=snap([]);p['allow_empty_complete']=True;p['send']=False
    with pytest.raises(ValueError,match='^INTEL_REFUSED_OUTREACH$'):m.record(p)
