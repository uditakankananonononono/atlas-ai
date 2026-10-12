"""Synthetic private-store and authenticated opt-in mounting tests."""
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.modules.m20_general_cognitive_worker.launch_quiz_c2 import QuizError
from app.modules.m20_general_cognitive_worker.launch_quiz_c2_store import DurableLaunchQuiz
from app.modules.m20_general_cognitive_worker.launch_quiz_c2_routes import mount_launch_quiz

@pytest.fixture
def path(tmp_path):
    tmp_path.chmod(0o700)
    return tmp_path / 'quiz.sqlite'


def mounted(path):
    app = FastAPI()
    mount_launch_quiz(app, {'ATLAS_C2_ENABLED': '1', 'ATLAS_C2_DB': str(path)})
    return TestClient(app)


def test_mount_disabled_and_missing_storage():
    app = FastAPI()
    mount_launch_quiz(app, {})
    mount_launch_quiz(app, {'ATLAS_C2_ENABLED': 'true'})
    assert not any('launch-quiz' in r.path for r in app.routes)
    with pytest.raises(QuizError, match='STORAGE'):
        mount_launch_quiz(app, {'ATLAS_C2_ENABLED': '1'})


def test_main_calls_opt_in_mount():
    from pathlib import Path
    import ast
    source = Path('backend/app/main.py').read_text()
    tree = ast.parse(source)
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == 'mount_launch_quiz' and n.args[0].id == 'app'
               for n in ast.walk(tree))


def test_authenticated_restart_plan_revoke(path, monkeypatch, oidc_auth_headers):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    h = oidc_auth_headers(tenant='c2tenant', subject='owner')
    other = oidc_auth_headers(tenant='c2tenant', subject='other')
    c = mounted(path)
    assert c.post('/api/v1/c31/launch-quiz/run', json={'operation':'start'}).status_code == 401
    def run(client, op, sid='', payload=None, headers=h):
        return client.post('/api/v1/c31/launch-quiz/run', headers=headers,
                           json={'operation':op,'session_id':sid,'payload':payload or {}})
    assert run(c,'start',payload={'consent':'true'}).status_code == 400
    sid = run(c,'start',payload={'consent':True}).json()['session_id']
    for key, choice in [('values','accuracy'),('decision','evidence'),('dilemma','compare'),('writing','concise')]:
        assert run(c,'answer',sid,{'question_id':key,'choice':choice,'explanation':'Synthetic example'}).status_code == 200
    assert run(c,'documents',sid,{'documents':[{'id':'doc','text':'verify compare','consent':True}]}).status_code == 200
    c = mounted(path)
    profile = c.get('/api/v1/c31/launch-quiz/report',headers=h,params={'session_id':sid}).json()
    assert profile['answered_count'] == 4 and profile['documents'][0]['text'] == 'verify compare'
    assert 'durable storage' not in profile['scope']['not_implemented']
    assert run(c,'plan',sid,{'task':'Synthetic task'}).json()['status'] == 'draft'
    assert run(c,'plan',sid,{'task':'send','action':'outreach'}).json()['detail'] == 'POLICY_REFUSED_OUTREACH'
    assert run(c,'revoke',sid,headers=other).json()['detail'] == 'FLEET_REFUSED_OWNER'
    assert run(c,'edit',sid,{'key':'writing','value':'detailed'}).status_code == 200
    assert mounted(path).get('/api/v1/c31/launch-quiz/report',headers=h,params={'session_id':sid}).json()['preferences']['writing']['value']=='detailed'
    assert run(c,'revoke',sid).json()['deleted'] is True
    assert mounted(path).get('/api/v1/c31/launch-quiz/report',headers=h,params={'session_id':sid}).json()['detail']=='FLEET_REFUSED_NOTFOUND'
    assert b'verify compare' not in path.read_bytes()


def test_two_instances_transaction_sequence_and_delete(path):
    a,b = DurableLaunchQuiz(path),DurableLaunchQuiz(path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: (a if i%2 else b).start('owner',consent=True), range(20)))
    ids = {r['session_id'] for r in results}
    assert len(ids)==20
    sid = results[0]['session_id']
    assert b.delete('owner',sid)['deleted'] is True
    with pytest.raises(QuizError,match='NOTFOUND'):a.profile('owner',sid)
    assert DurableLaunchQuiz(path).start('owner',consent=True)['session_id']=='quiz-21'


def test_failed_operation_rolls_back(path):
    e=DurableLaunchQuiz(path)
    sid=e.start('owner',consent=True)['session_id']
    with pytest.raises(QuizError):e.answer('owner',sid,'values','accuracy','')
    assert DurableLaunchQuiz(path).profile('owner',sid)['answered_count']==0


def test_private_paths_and_corruption(path):
    import sqlite3
    e=DurableLaunchQuiz(path)
    assert path.stat().st_mode & 0o077 == 0
    with sqlite3.connect(path) as db:db.execute("UPDATE state SET body='{}'")
    with pytest.raises(QuizError,match='STORAGE'):e.start('owner',consent=True)
    path.chmod(0o644)
    with pytest.raises(QuizError,match='STORAGE'):DurableLaunchQuiz(path)
    link=path.parent/'link.sqlite';link.symlink_to(path)
    with pytest.raises(QuizError,match='STORAGE'):DurableLaunchQuiz(link)
    with pytest.raises(QuizError,match='STORAGE'):DurableLaunchQuiz('relative.sqlite')
    path.parent.chmod(0o755)
    with pytest.raises(QuizError,match='STORAGE'):DurableLaunchQuiz(path)


def test_real_main_app_mount_and_default(path,monkeypatch,oidc_auth_headers):
    import importlib
    import app.main as main
    monkeypatch.delenv('ATLAS_C2_ENABLED',raising=False)
    monkeypatch.delenv('ATLAS_C2_DB',raising=False)
    main=importlib.reload(main)
    c=TestClient(main.app)
    assert c.get('/health').json()=={'status':'ok'}
    assert c.get('/api/v1/c31/launch-quiz/report',params={'session_id':'x'}).status_code==404
    monkeypatch.setenv('ATLAS_C2_ENABLED','1')
    monkeypatch.setenv('ATLAS_C2_DB',str(path))
    try:
        main=importlib.reload(main)
        c=TestClient(main.app)
        h=oidc_auth_headers(tenant='main-c2',subject='owner')
        started=c.post('/api/v1/c31/launch-quiz/run',headers=h,json={'operation':'start','payload':{'consent':True}})
        assert started.status_code==200
        sid=started.json()['session_id']
        main=importlib.reload(main)
        assert TestClient(main.app).get('/api/v1/c31/launch-quiz/report',headers=h,params={'session_id':sid}).status_code==200
    finally:
        monkeypatch.delenv('ATLAS_C2_ENABLED')
        monkeypatch.delenv('ATLAS_C2_DB')
        importlib.reload(main)


def storage_refusal(call):
    with pytest.raises(QuizError) as exc:
        call()
    assert str(exc.value) == 'FLEET_REFUSED_STORAGE'


def test_parent_symlink_and_missing(path):
    link=path.parent/'alias';link.symlink_to(path.parent,target_is_directory=True)
    storage_refusal(lambda:DurableLaunchQuiz(link/'quiz.sqlite'))
    storage_refusal(lambda:DurableLaunchQuiz(path.parent/'missing'/'quiz.sqlite'))


@pytest.mark.parametrize('change',['640','604','hardlink','parent750'])
def test_post_construction_path_recheck(path,change):
    import os
    engine=DurableLaunchQuiz(path)
    if change=='hardlink':os.link(path,path.parent/'second.sqlite')
    elif change=='parent750':path.parent.chmod(0o750)
    else:path.chmod(int(change,8))
    storage_refusal(lambda:engine.start('owner',consent=True))


@pytest.mark.parametrize('body',['','{}','{"sequence":0,"sessions":{},"extra":1}',
    '{"sequence":-1,"sessions":{}}','{"sequence":true,"sessions":{}}',
    '{"sequence":0,"sessions":[]}'])
def test_bad_persisted_shape_exact(path,body):
    import sqlite3
    engine=DurableLaunchQuiz(path)
    with sqlite3.connect(path) as db:db.execute('UPDATE state SET body=?',(body,))
    storage_refusal(lambda:engine.start('owner',consent=True))


def memory_state(engine,monkeypatch):
    """Use actual SQLite transactions in RAM for 25MB guard tests on tight disk."""
    import sqlite3
    db=sqlite3.connect(':memory:',isolation_level=None)
    db.execute('CREATE TABLE state(id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
    class Connection:
        def execute(self,*args):return db.execute(*args)
        def close(self):
            if db.in_transaction:db.execute('ROLLBACK')
    monkeypatch.setattr(engine,'_connect',lambda:Connection())
    return db


def test_read_byte_cap_exact_and_plus_one(path,monkeypatch):
    import json
    engine=DurableLaunchQuiz(path)
    db=memory_state(engine,monkeypatch)
    try:
        body=json.dumps({'sequence':0,'sessions':{}})
        db.execute('INSERT INTO state VALUES(1,?)',(body+' '*(25_000_000-len(body)),))
        assert engine.start('owner',consent=True)['session_id']=='quiz-1'
        db.execute('UPDATE state SET body=?',(body+' '*(25_000_001-len(body)),))
        storage_refusal(lambda:engine.start('owner',consent=True))
    finally:db.close()


@pytest.mark.parametrize('count',[100,101])
def test_session_load_cap(path,count):
    import json,sqlite3
    engine=DurableLaunchQuiz(path)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE state SET body=?',(json.dumps({'sequence':count,'sessions':{str(i):{} for i in range(count)}}),))
    # An inert engine entry proves the loader boundary independent of max-start refusal.
    from unittest.mock import patch
    with patch('app.modules.m20_general_cognitive_worker.launch_quiz_c2_store.LaunchQuiz.profile',return_value={'loaded':True}):
        if count==100:assert engine.profile('owner','unused')=={'loaded':True}
        else:storage_refusal(lambda:engine.profile('owner','unused'))


def test_unicode_disk_and_scope(path):
    engine=DurableLaunchQuiz(path)
    sid=engine.start('owner',consent=True)['session_id']
    for key,choice in [('values','accuracy'),('decision','evidence'),('dilemma','compare'),('writing','concise')]:
        engine.answer('owner',sid,key,choice,'Synthetic')
    engine.documents('owner',sid,[{'id':'u','text':'café ☃','consent':True}])
    assert b'caf\\u00e9 \\u2603' in path.read_bytes()
    for result in [DurableLaunchQuiz(path).profile('owner',sid),engine.plan('owner',sid,'Task')]:
        assert 'private local SQLite persistence' in result['scope']['implemented']
    assert DurableLaunchQuiz(path).profile('owner',sid)['documents'][0]['text']=='café ☃'


def test_write_cap_refuses_and_rolls_back(path,monkeypatch):
    import json
    from app.modules.m20_general_cognitive_worker.launch_quiz_c2 import LaunchQuiz
    core=LaunchQuiz()
    for i in range(21):core.start('owner',consent=True)
    docs=[{'id':str(i),'text':'雪'*20_000,'consent':True} for i in range(10)]
    for i in range(1,21):core.documents('owner','quiz-'+str(i),docs)
    body=json.dumps({'sequence':core._sequence,'sessions':core._sessions},ensure_ascii=True)
    assert len(body.encode())<25_000_000
    import sqlite3
    engine=DurableLaunchQuiz(path)
    # Journal OFF only in this synthetic guard test. No UPDATE is reached;
    # production always uses its untouched secure/FULL configuration.
    db=sqlite3.connect(path,isolation_level=None)
    db.execute('PRAGMA journal_mode=OFF')
    class Connection:
        def execute(self,*args):return db.execute(*args)
        def close(self):
            if db.in_transaction:db.execute('ROLLBACK')
    monkeypatch.setattr(engine,'_connect',lambda:Connection())
    try:
        db.execute('UPDATE state SET body=?',(body,))
        storage_refusal(lambda:engine.documents('owner','quiz-21',docs))
        assert db.execute('SELECT body FROM state').fetchone()[0]==body
    finally:db.close()


def test_attribute_allowlist(path):
    engine=DurableLaunchQuiz(path)
    for name in ['start','answer','documents','edit','plan','delete','revoke','profile']:
        assert callable(getattr(engine,name))
    with pytest.raises(AttributeError):getattr(engine,'unknown')

def test_relative_path_refused_from_restrictive_cwd(tmp_path, monkeypatch):
    # From a 0700 cwd the parent-mode checks pass, so only the absolute-path
    # boundary refuses a relative store path; pin that refusal and no creation.
    monkeypatch.chdir(tmp_path)
    tmp_path.chmod(0o700)
    with pytest.raises(QuizError, match='STORAGE'):
        DurableLaunchQuiz('rel.sqlite')
    assert not (tmp_path / 'rel.sqlite').exists()
