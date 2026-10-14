import pytest
from app.modules.c33 import content

def request():
    return {'theme':'repairable lamps','notes':['Use replaceable screws','Keep wiring accessible'],
            'sources':[{'id':'s','text':'A separate discussion of paint colours'}],
            'angle':'repair before replacement','audience':'makers'}

def test_composition_notes_provenance_no_invented_experience():
    assert hasattr(content,'compose'),'supplied-notes composition absent'
    out=content.compose(request())
    assert 'Use replaceable screws' in out['draft'] and 'Keep wiring accessible' in out['draft']
    assert 'repair before replacement' in out['draft']
    assert 'first-hand' not in out['draft']
    assert out['posted'] is False and out['originality_verified'] is False
    assert out['source_comparisons']==[{'source_id':'s','jaccard':0.032258}]
    assert out['note_provenance']==[{'index':0,'text':'Use replaceable screws'},{'index':1,'text':'Keep wiring accessible'}]

def test_verbatim_source_note_refuses_and_effect_keys_refuse():
    assert hasattr(content,'compose'),'supplied-notes composition absent'
    r=request();r['sources']=[{'id':'s','text':'Use replaceable screws'}]
    with pytest.raises(ValueError,match='SOCIAL_REFUSED_COPY'):content.compose(r)
    for key in ['post','create_accounts','extra']:
        with pytest.raises(ValueError):content.compose(dict(request(),**{key:True}))

def test_mounted_auth(oidc_auth_headers,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with TestClient(app) as c:
        assert c.post('/api/v1/c33/content',json=request()).status_code==401
        out=c.post('/api/v1/c33/content',json=request(),headers=oidc_auth_headers())
        assert out.status_code==200,out.text
        assert out.json()['posted'] is False
