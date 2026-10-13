"""Row1284 Jury Selection: app-level production-auth mounted review. Bounded supplied-reference bookkeeping only; no juror profiling, scoring or legal conclusion."""
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
PATH = '/m20/legal/1284/review'
VOCAB = ['case_neutral_topics', 'cause_grounds', 'equal_protection_review']
PREFIX = 'JURYSE1284:'

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('ATLAS_DEV_NO_AUTH', raising=False)
    with TestClient(app) as c:
        yield c

def request(**changes):
    return dict({'row': 1284, 'as_of': '2026-10-12', 'entries': [
        {'element': VOCAB[0], 'status': 'supplied', 'source_ref': 'PRIVATE_REFERENCE', 'entry_date': '2026-10-10'},
        {'element': VOCAB[0], 'status': 'missing'},
        {'element': VOCAB[0], 'status': 'disputed', 'source_ref': 'OTHER_REFERENCE', 'entry_date': '2026-10-11'}]}, **changes)

def test_row1284_mounted_partition_dates_and_boundary(client, oidc_auth_headers):
    r=client.post(PATH,headers=oidc_auth_headers(),json=request())
    assert r.status_code==200,r.text
    out=r.json()
    assert out['row']==1284
    assert [x['element'] for x in out['elements']]==VOCAB
    assert out['elements'][0]=={'element':VOCAB[0],'status':'disputed','also_declared_missing':True,'latest_entry_date':'2026-10-11','days_since_latest':1}
    assert out['coverage']=={'elements_total':len(VOCAB),'referenced':0,'disputed':1,'declared_missing':0,'unaddressed':len(VOCAB)-1}
    assert all(x['status']=='unaddressed' and x['latest_entry_date'] is None for x in out['elements'][1:])
    assert out['counsel_review_required'] is True and out['legal_conclusion'] is False and out['references_verified'] is False
    assert out['boundary'].startswith('Legal work product for review, not legal advice.')
    assert out['scope']['jurisdiction']=='jurisdiction not supplied or validated'
    assert out['scope']['as_of']=='2026-10-12'
    assert 'PRIVATE_REFERENCE' not in r.text and 'OTHER_REFERENCE' not in r.text

def test_row1284_mounted_vocab_and_missing(client, oidc_auth_headers):
    headers=oidc_auth_headers()
    r=client.post(PATH,headers=headers,json=request(entries=[{'element':v,'status':'supplied','source_ref':'secret'} for v in VOCAB]))
    assert r.status_code==200,r.text
    assert r.json()['coverage']['referenced']==len(VOCAB)
    assert 'secret' not in r.text
    r=client.post(PATH,headers=headers,json=request(entries=[{'element':VOCAB[1],'status':'missing'}]))
    assert r.status_code==200,r.text
    assert r.json()['elements'][1]['status']=='declared_missing'
    assert r.json()['coverage']['declared_missing']==1

@pytest.mark.parametrize('changes,reason',[
    ({'row':True},'BAD_TYPE:row'),({'row':1284+10},'UNKNOWN:row'),
    ({'entries':[]},'EMPTY:entries'),({'as_of':'20260230'},'BAD_TYPE:as_of'),
    ({'entries':[{'element':VOCAB[0],'status':'supplied','source_ref':'PRIVATE_REFERENCE','entry_date':'2026-10-13'}]},'BAD_TYPE:entry_date'),
    ({'entries':[{'element':'OTHER_1284_ONLY','status':'missing'}]},'UNKNOWN:element'),
])
def test_row1284_mounted_strict_refusals(client,oidc_auth_headers,changes,reason):
    r=client.post(PATH,headers=oidc_auth_headers(),json=request(**changes))
    assert r.status_code==422,r.text
    assert r.json()=={'detail':PREFIX+' '+reason}
    assert 'PRIVATE_REFERENCE' not in r.text and 'OTHER_1284_ONLY' not in r.text

def test_row1284_mounted_forbidden_precedence(client,oidc_auth_headers):
    headers=oidc_auth_headers()
    for changes,reason in [({'send':False,'pay':False},'SEND:send'),({'password':None},'NOCREDS:password'),({'file':False},'EFFECT:file')]:
        r=client.post(PATH,headers=headers,json=request(**changes))
        assert r.status_code==422,r.text
        assert r.json()=={'detail':PREFIX+' '+reason}
    r=client.post(PATH,headers=headers,json=request(entries=[{'token':1}]*201))
    assert r.status_code==422,r.text
    assert r.json()=={'detail':PREFIX+' OVERSIZE:entries'}

def test_row1284_mounted_decoder_and_media(client,oidc_auth_headers):
    headers=oidc_auth_headers()
    for raw in [b'\xff',b'{broken',b'null',b'[]',(json.dumps(request())[:-1]+',"row":'+str(1284)+'}').encode(),b'{"row":NaN}']:
        r=client.post(PATH,headers={**headers,'Content-Type':'application/json'},content=raw)
        assert r.status_code==422,r.text
        assert r.json()['detail'].startswith(PREFIX+' ')
    r=client.post(PATH,headers={**headers,'Content-Type':'text/plain'},content='PRIVATE_REFERENCE')
    assert r.status_code==415,r.text
    assert 'PRIVATE_REFERENCE' not in r.text

def test_row1284_mounted_body_cap_exact_boundary(client,oidc_auth_headers):
    headers={**oidc_auth_headers(),'Content-Type':'application/json'}
    raw=json.dumps(request()).encode();raw+=b' '*(8192-len(raw))
    r=client.post(PATH,headers=headers,content=raw)
    assert r.status_code==200,r.text
    r=client.post(PATH,headers=headers,content=raw+b' ')
    assert r.status_code==413,r.text

def test_row1284_mounted_auth_before_engine(client,monkeypatch):
    from app.modules.m20_general_cognitive_worker import jury_selection1284
    def forbidden(_):raise AssertionError('unauthenticated engine call')
    monkeypatch.setattr(jury_selection1284,'run',forbidden)
    r=client.post(PATH,json=request())
    assert r.status_code==401,r.text

def test_row1284_mounted_repeat_tenant_isolation(client,oidc_auth_headers):
    data=request()
    a=client.post(PATH,headers=oidc_auth_headers('tenant-a'),json=data)
    b=client.post(PATH,headers=oidc_auth_headers('tenant-b'),json=data)
    assert a.status_code==b.status_code==200,(a.text,b.text)
    assert a.json()==b.json()


def test_row1284_mounted_empty_probe(client, oidc_auth_headers):
    assert client.post(PATH, headers=oidc_auth_headers(), json={}).status_code == 422
    assert client.post(PATH, json={}).status_code == 401
