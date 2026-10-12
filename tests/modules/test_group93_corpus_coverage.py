import pytest
from app.modules.c33.corpus_coverage import coverage

def post(i,cat,url='https://example.org/public-posts'):
    return {'id':i,'category':cat,'source_url':url,'text':'AI software field notes','likes':0,'shares':0}

def test_coverage_keeps_missing_categories_and_exact_provenance():
    out=coverage([post('a','tech'),post('b','tech')],['tech','beauty'])
    assert out['categories']['beauty']['status']=='no_supplied_posts'
    assert out['categories']['tech']['count']==2
    assert out['categories']['tech']['source_count']==1
    assert out['posts'][0]['source_url']=='https://example.org/public-posts'
    assert out['posts'][0]['id']=='a'
    assert len(out['posts'][0]['text_sha256'])==64
    assert out['complete_category_coverage'] is False

def test_duplicate_ids_and_unlisted_category_refuse():
    with pytest.raises(ValueError,match='duplicate'):
        coverage([post('a','tech'),post('a','tech')],['tech'])
    with pytest.raises(ValueError,match='unlisted'):
        coverage([post('a','tech')],['beauty'])

def test_coverage_does_not_call_supplied_positive_labels_broad_collection():
    out=coverage([post('a','tech'),post('b','beauty')],['tech','beauty'])
    assert out['complete_category_coverage'] is False
    assert out['represented_supplied_categories']==2
    assert out['scope']=='Supplied records only; no platform collection, accounts or publishing.'

def test_exact_text_hash_and_invalid_source_url_refusal():
    import hashlib
    out=coverage([post('a','tech')],['tech'])
    assert out['posts'][0]['text_sha256']==hashlib.sha256(b'AI software field notes').hexdigest()
    for url in ('https://user:secret@example.org/posts','file:///tmp/posts','https:///missing'):
        with pytest.raises(ValueError,match='public source URL'):coverage([post('a','tech',url)],['tech'])
