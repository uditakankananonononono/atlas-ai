import pytest
from app.modules.c31 import tool_scan

def request():
    return {'sources':[{'id':'repo','name':'Lamp','url':'https://example.org/repo','text':'License: MIT\nPricing: Free\nCapabilities: search, draft\nRandom marketing claims ignored.'},
                       {'id':'page','name':'Garden','url':'https://example.org/garden','text':'License: proprietary\nPrice tier: paid\nCapability: search'}],
            'atlas_modules':['draft']}

def test_extract_explicit_source_fields_and_gap_oracle():
    assert hasattr(tool_scan,'scan_sources'),'saved-text extraction absent'
    r=tool_scan.scan_sources(request())
    assert r['tool_count']==2 and r['gap_list']==['search']
    assert r['matrix']==[{'name':'Garden','license':'proprietary','price_tier':'paid','capabilities':['search']},
                         {'name':'Lamp','license':'mit','price_tier':'free','capabilities':['draft','search']}]
    for source in r['source_records']:
        raw=next(s['text'] for s in request()['sources'] if s['id']==source['source_id'])
        assert all(raw[e['start']:e['end']]==e['quote'] for e in source['evidence'])
    assert r['sources_verified'] is False

def test_no_heuristic_license_upgrade_and_ambiguous_refusal():
    assert hasattr(tool_scan,'scan_sources'),'saved-text extraction absent'
    r=request();r['sources'][0]['text']='A free marketing slogan. MIT appears in a story.\nCapability: draft'
    matrix=tool_scan.scan_sources(r)['matrix']
    lamp=next(t for t in matrix if t['name']=='Lamp')
    assert lamp['license']==lamp['price_tier']=='unknown'
    r=request();r['sources'][0]['text']+='\nLicense: proprietary'
    with pytest.raises(ValueError,match='AMBIGUOUS'):tool_scan.scan_sources(r)

def test_authenticated_source_route(oidc_auth_headers,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0');monkeypatch.setenv('ATLAS_ENV','production')
    with TestClient(app) as c:
        assert c.post('/api/v1/c31/tool-scan',json=request()).status_code==401
        r=c.post('/api/v1/c31/tool-scan',json=request(),headers=oidc_auth_headers())
        assert r.status_code==200,r.text
        assert r.json()['gap_list']==['search']


@pytest.mark.parametrize('line', ['LİCENSE: MIT', 'Licenſe: MIT', 'PRICİNG: free'])
def test_unicode_confusable_labels_are_not_fields(line):
    r=request()
    r['sources']=[dict(r['sources'][0],text=line)]
    out=tool_scan.scan_sources(r)
    assert out['matrix']==[{'name':'Lamp','license':'unknown','price_tier':'unknown','capabilities':[]}]
    assert out['source_records'][0]['evidence']==[]
    assert out['source_records'][0]['missing_fields']==['license','price_tier','capabilities']


def test_authenticated_route_ignores_unicode_confusable_labels(oidc_auth_headers,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('ATLAS_DEV_NO_AUTH','0')
    monkeypatch.setenv('ATLAS_ENV','production')
    with TestClient(app) as c:
        for line in ['LİCENSE: MIT','Licenſe: MIT','PRICİNG: free']:
            r=request()
            r['sources']=[dict(r['sources'][0],text=line)]
            response=c.post('/api/v1/c31/tool-scan',json=r,headers=oidc_auth_headers())
            assert response.status_code==200,response.text
            result=response.json()
            assert result['matrix']==[{'name':'Lamp','license':'unknown','price_tier':'unknown','capabilities':[]}]
            assert result['gap_list']==[]
            assert result['source_records'][0]['evidence']==[]
            assert result['sources_verified'] is False
