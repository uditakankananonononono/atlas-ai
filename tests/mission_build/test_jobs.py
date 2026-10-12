from concurrent.futures import ThreadPoolExecutor
import pytest
from app.mission_build.durable_jobs import DurableJobs


def test_restart_and_actor_isolation_and_stale_worker(tmp_path):
    path=str(tmp_path/'jobs.db');now=[1.0]
    a=DurableJobs(path,'t','a',lambda:now[0]);b=DurableJobs(path,'t','b',lambda:now[0])
    ident=a.enqueue('polynomial',{'coefficients':[1,2]})
    assert b.claim('w') is None
    with pytest.raises(KeyError):b.get(ident)
    claimed=a.claim('w',10)
    restarted=DurableJobs(path,'t','a',lambda:now[0]);assert restarted.get(ident)['status']=='running'
    with pytest.raises(ValueError):restarted.finish(ident,'other',claimed['version'],{})
    restarted.finish(ident,'w',claimed['version'],{'value':3})
    assert restarted.get(ident)['result']=={'value':3}
    with pytest.raises(ValueError):a.finish(ident,'w',claimed['version'],{})


def test_expired_lease_unknown_never_retried(tmp_path):
    now=[1.0];path=str(tmp_path/'jobs.db');a=DurableJobs(path,'t','a',lambda:now[0])
    ident=a.enqueue('strategy',{});row=a.claim('first',1);now[0]=3
    assert a.claim('second') is None and a.get(ident)['status']=='unknown'
    with pytest.raises(ValueError):a.finish(ident,'first',row['version'],{})
    assert [e['kind'] for e in a.get(ident)['events']]==['queued','running','unknown']


def test_separate_instances_claim_once(tmp_path):
    path=str(tmp_path/'jobs.db');a=DurableJobs(path,'t','a');b=DurableJobs(path,'t','a')
    a.enqueue('enclosure',{})
    with ThreadPoolExecutor(2) as pool:
        rows=list(pool.map(lambda x:x.claim('w'),[a,b]))
    assert sum(row is not None for row in rows)==1


def test_no_effect_task_and_limits(tmp_path):
    a=DurableJobs(str(tmp_path/'jobs.db'),'t','a')
    for task in ('send_message','purchase','install','exec'):
        with pytest.raises(ValueError):a.enqueue(task,{})
    with pytest.raises(ValueError):a.enqueue('strategy',{'x':float('nan')})
    with pytest.raises(ValueError):a.claim('w',True)


def test_real_worker_computes_and_durable_result_reloads(tmp_path):
    from app.mission_build.worker import execute_one
    path=str(tmp_path/'jobs.db');a=DurableJobs(path,'t','a')
    ident=a.enqueue('polynomial',{'coefficients':[1,2],'at':3})
    r=execute_one(a,'worker')
    assert r['id']==ident and r['result']['result']['value']=='7'
    assert DurableJobs(path,'t','a').get(ident)['result']==r['result']
    a.enqueue('polynomial',{'coefficients':[True]})
    assert execute_one(a,'worker')['result']['status']=='computation_failed'
    assert execute_one(a,'worker') is None


def test_worker_records_any_exception_type_as_failed_result(tmp_path,monkeypatch):
    from app.mission_build import worker
    a=DurableJobs(str(tmp_path/'jobs.db'),'t','a')
    ident=a.enqueue('polynomial',{'coefficients':[1]})
    def boom(payload):raise RuntimeError('unexpected runtime fault')
    monkeypatch.setattr(worker,'analyze',boom)
    r=worker.execute_one(a,'w')
    assert r['status']=='done' and r['result']['status']=='computation_failed'
    assert r['result']['error_type']=='RuntimeError' and 'unexpected runtime fault' in r['result']['error']
    assert worker.execute_one(a,'w') is None   # not left running for a later claim


def test_worker_keeps_computed_result_when_lease_expires_before_finish(tmp_path,monkeypatch):
    from app.mission_build import worker
    now=[1000.0]
    a=DurableJobs(str(tmp_path/'jobs.db'),'t','a',lambda:now[0])
    ident=a.enqueue('polynomial',{'coefficients':[1]})
    def slow(payload):
        now[0]+=10_000   # lease (60s) expires while computing
        return {'value':'computed'}
    monkeypatch.setattr(worker,'analyze',slow)
    r=worker.execute_one(a,'w')
    assert r['id']==ident and r['status']=='result_not_persisted'
    assert r['outcome']['status']=='computed' and r['outcome']['result']=={'value':'computed'}
    assert 'expired' in r['persist_error']


def test_worker_unserializable_result_is_stored_as_failure(tmp_path,monkeypatch):
    from app.mission_build import worker
    a=DurableJobs(str(tmp_path/'jobs.db'),'t','a')
    a.enqueue('polynomial',{'coefficients':[1]})
    monkeypatch.setattr(worker,'analyze',lambda p:{'value':float('nan')})
    r=worker.execute_one(a,'w')
    assert r['status']=='done' and r['result']['status']=='computation_failed'
    assert r['result']['error'].startswith('result could not be stored: ')
