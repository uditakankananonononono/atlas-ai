import copy
import json
import pytest
from app.mission_build.admissions_training import fit, predict


def fixture():
    sources = [{'id':f's{i}','url':f'https://source{i}.example/advice','training_allowed':True,'rights_receipt':'synthetic test data owned by test author'} for i in range(10)]
    rows = []
    for i in range(10):
        rows.append({'id':f't{i}','source_id':f's{i}','text':('deadline scholarship calendar funding' if i%2 else 'essay reflection identity narrative')+f' unique{i}','label':'funding' if i%2 else 'essay','split':'train'})
    rows += [{'id':'h1','source_id':'s0','text':'reflection identity meaningful narrative','label':'essay','split':'heldout'}, {'id':'h2','source_id':'s1','text':'scholarship funding application deadline','label':'funding','split':'heldout'}]
    return rows,sources


def test_actual_fitted_classifier_reload_and_heldout():
    rows,sources = fixture();r = fit(rows,sources)
    assert r['training_examples'] == 10 and len(r['training_source_domains']) == 10
    assert r['evaluation']['accuracy'] == 1 and not r['rights_verified']
    loaded = json.loads(json.dumps(r))
    assert predict(loaded,'reflection essay')['label'] == 'essay'
    assert predict(loaded,'funding deadline')['label'] == 'funding'
    assert predict(loaded,'quuxxy')['status'] == 'out_of_vocabulary'
    loaded['token_counts']['essay']['reflection'] += 1
    with pytest.raises(ValueError):predict(loaded,'reflection')


def test_unlicensed_duplicate_contamination_and_site_padding_fail():
    rows,sources = fixture();sources[0]['training_allowed']=False
    with pytest.raises(PermissionError):fit(rows,sources)
    rows,sources=fixture();rows[-1]['text']=rows[0]['text']
    with pytest.raises(ValueError):fit(rows,sources)
    rows,sources=fixture()
    for s in sources:s['url']='https://one.example/'+s['id']
    with pytest.raises(ValueError):fit(rows,sources)


def test_heldout_not_used_as_training_domain_and_class_coverage_required():
    rows,sources=fixture();rows[0]['split']='heldout'
    with pytest.raises(ValueError):fit(rows,sources)
    rows,sources=fixture();rows[-1]['label']='essay'
    with pytest.raises(ValueError):fit(rows,sources)


def test_training_is_deterministic_and_does_not_modify_inputs():
    rows,sources=fixture();before=copy.deepcopy((rows,sources))
    assert fit(rows,sources)==fit(rows,sources)
    assert (rows,sources)==before
