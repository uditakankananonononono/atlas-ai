import pytest
from app.mission_build.patent_preparation import prepare


def test_source_mapping_and_description_support_not_filing_ready():
    p={'title':'sensor enclosure','features':['adaptive valve','humidity sensor'],
       'prior_art':[{'id':'p1','url':'https://patents.example/p1','text':'A HUMIDITY sensor, controls air.'}],
       'sections':{'detailed_description':'A humidity sensor measures moisture. An adaptive valve regulates flow.'},
       'claim_basis':{'adaptive valve':'adaptive valve regulates flow','humidity sensor':'humidity sensor measures moisture'},
       'abstract':'A housing includes a humidity sensor and adaptive valve.'}
    r=prepare(p)
    assert r['prior_art_comparison'][0]['matched_features']==['humidity sensor']
    assert all(x['quote_found_in_supplied_description'] for x in r['claim_basis'])
    assert 'field' in r['missing_or_review'] and not r['filing_ready'] and not r['novelty_determined']
    assert 'DRAFT NOT FOR FILING' in r['packet_markdown']
    p['claim_basis']['adaptive valve']='fabricated reference'
    assert 'unsupported_claim_features' in prepare(p)['missing_or_review']


def test_empty_prior_art_and_overlong_abstract_not_silently_complete():
    r=prepare({'title':'widget','features':['housing'],'prior_art':[],'abstract':'word '*151})
    assert 'prior_art_corpus' in r['missing_or_review'] and 'abstract_over_150_words_review' in r['missing_or_review']


@pytest.mark.parametrize('url',['https://u:p@host.example/p','http://host.example','file:///etc/passwd'])
def test_rejects_bad_source(url):
    with pytest.raises(ValueError):prepare({'title':'widget','features':['housing'],'prior_art':[{'id':'p','url':url,'text':'housing'}]})
