"""Row 872 bounded mind-map radiation over declared associations.

Hermetic, stdlib-only; loads the module by file path so the suite runs in an
isolated stdlib+pytest environment.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

P = Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/mind_mapping872.py'
s = importlib.util.spec_from_file_location('mind872', P)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


def req(**over):
    base = {
        'center': 'photosynthesis',
        'spokes': [
            {'id': 's1', 'label': 'chlorophyll', 'tier': 1, 'weight': 3},
            {'id': 's2', 'label': 'sunlight', 'tier': 1, 'weight': 1},
            {'id': 's3', 'label': 'calvin cycle', 'tier': 2, 'weight': 4},
            {'id': 's4', 'label': 'stomata', 'tier': 2, 'weight': 0},
        ],
    }
    base.update(over)
    return base


def test_exact_radiation_order_shares_and_zero_weights():
    out = m.radiate(req())
    assert [(r['tier'], r['label']) for r in out['spokes']] == [
        (1, 'chlorophyll'), (1, 'sunlight'), (2, 'calvin cycle'), (2, 'stomata')]
    assert [r['weight_share'] for r in out['spokes']] == ['3/8', '1/8', '1/2', '0/1']
    assert out['total_weight'] == 8 and out['spoke_count'] == 4
    assert out['tiers_present'] == [1, 2]
    assert out['zero_weight_spoke_ids'] == ['s4']
    assert out['associations_generated'] == 0
    assert out['interpretation'].startswith('caller-declared')
    assert len(out['limits']) == 3


def test_deterministic_under_input_permutation():
    a = m.radiate(req())
    d = req()
    d['spokes'] = list(reversed(d['spokes']))
    assert a == m.radiate(d)


def test_all_zero_weights_gives_zero_shares_not_error():
    d = req(spokes=[{'id': 'a', 'label': 'x', 'tier': 1, 'weight': 0}])
    out = m.radiate(d)
    assert out['spokes'][0]['weight_share'] == '0/1'
    assert out['total_weight'] == 0


def refuse(d):
    with pytest.raises(ValueError, match='^MIND872:'):
        m.radiate(d)


def test_schema_and_unknown_keys_refused():
    for bad in [None, [], {}, {'center': 'x'}, dict(req(), extra=1)]:
        refuse(bad)
    refuse(req(center=''))
    refuse(req(center='x' * 121))


def test_spoke_field_validation():
    refuse(req(spokes=[]))
    refuse(req(spokes=[{'id': 'a', 'label': 'x', 'tier': 1, 'weight': 0}] * 65))
    d = req(); d['spokes'][1]['id'] = 's1'; refuse(d)          # duplicate id
    d = req(); d['spokes'][0]['tier'] = 0; refuse(d)
    d = req(); d['spokes'][0]['tier'] = 5; refuse(d)
    d = req(); d['spokes'][0]['tier'] = True; refuse(d)        # bool is not a tier
    d = req(); d['spokes'][0]['weight'] = True; refuse(d)      # bool is not a weight
    d = req(); d['spokes'][0]['weight'] = -1; refuse(d)
    d = req(); d['spokes'][0]['weight'] = 10 ** 6 + 1; refuse(d)
    d = req(); d['spokes'][0]['weight'] = '3'; refuse(d)
    d = req(); d['spokes'][0]['label'] = '  '; refuse(d)
    d = req(); d['spokes'][0].pop('tier'); refuse(d)
    d = req(); d['spokes'][0]['extra'] = 1; refuse(d)


def test_boundaries_accepted():
    out = m.radiate(req(spokes=[{'id': 'a', 'label': 'x', 'tier': 4, 'weight': 10 ** 6}]))
    assert out['spokes'][0]['weight_share'] == '1/1'
    out = m.radiate(req(spokes=[{'id': str(i), 'label': 'x%d' % i, 'tier': 1, 'weight': 1} for i in range(64)]))
    assert out['spoke_count'] == 64


def test_v3_distinct_spoke_length_and_tuple_refusals():
    spokes = [{'id': str(i), 'label': 'x', 'tier': 1, 'weight': 1} for i in range(65)]
    with pytest.raises(ValueError, match=r'^MIND872:spokes must be a list of 1[.][.]64 records$'):
        m.radiate(req(spokes=spokes))
    with pytest.raises(ValueError, match=r'^MIND872:spokes must be a list of 1[.][.]64 records$'):
        m.radiate(req(spokes=tuple(req()['spokes'])))


def test_v3_label_order_beats_anticorrelated_id_order():
    out = m.radiate(req(spokes=[{'id': 'a', 'label': 'z', 'tier': 1, 'weight': 1},
                               {'id': 'z', 'label': 'a', 'tier': 1, 'weight': 1}]))
    assert [r['id'] for r in out['spokes']] == ['z', 'a']


def test_v3_center_schema_and_limits_are_owned():
    out = m.radiate(req(center='  declared center  '))
    assert out['center'] == 'declared center'
    before = list(m.LIMITS)
    out['limits'].append('caller edit')
    try:
        assert m.LIMITS == before
        assert m.radiate(req())['limits'] == before
    finally:
        m.LIMITS[:] = before
    for bad in [dict(req(), extra=1), {'center': 'x'}, {'spokes': req()['spokes']}]:
        with pytest.raises(ValueError, match='^MIND872:request must have exactly center and spokes$'):
            m.radiate(bad)


def test_v3_full_duplicate_and_field_messages():
    d=req(); d['spokes'][1]['id']='s1'
    with pytest.raises(ValueError, match='^MIND872:duplicate spoke id$'):m.radiate(d)
    for field, message in [('center','center'),('id','spoke id'),('label','spoke label')]:
        d=req()
        if field=='center':d[field]=' '
        else:d['spokes'][0][field]=' '
        with pytest.raises(ValueError, match='^MIND872:'+message+' must be nonblank text up to 120 characters$'):
            m.radiate(d)


def test_v4_request_mapping_full_message():
    for value in (None, [], 'center'):
        with pytest.raises(ValueError, match='^MIND872:request must be a mapping$'):
            m.radiate(value)


def test_v4_spoke_schema_full_message_formatted_indices():
    for index in (0, 2):
        d = req()
        d['spokes'][index].pop('weight')
        with pytest.raises(ValueError, match='^MIND872:spoke %d must have exactly id, label, tier, weight$' % index):
            m.radiate(d)


def test_v4_weight_and_tier_full_messages():
    for value in (True, -1, 10 ** 6 + 1, '3'):
        d = req(); d['spokes'][0]['weight'] = value
        with pytest.raises(ValueError, match=r'^MIND872:spoke weight must be an integer 0[.][.]10\^6$'):
            m.radiate(d)
    for value in (True, 0, 5, 1.0):
        d = req(); d['spokes'][0]['tier'] = value
        with pytest.raises(ValueError, match=r'^MIND872:spoke tier must be an integer 1[.][.]4$'):
            m.radiate(d)


def test_v5_center_exact_label_limit_is_accepted():
    center = 'x' * 120
    assert m.radiate(req(center=center))['center'] == center


def test_v5_nonstring_center_has_full_value_error():
    with pytest.raises(ValueError, match='^MIND872:center must be nonblank text up to 120 characters$'):
        m.radiate(req(center=5))


def test_v5_nondict_spoke_has_full_value_error():
    with pytest.raises(ValueError, match='^MIND872:spoke 0 must have exactly id, label, tier, weight$'):
        m.radiate(req(spokes=[5]))


def test_v6_exact_api_output_declarations():
    out = m.radiate(req())
    assert out['interpretation'] == 'caller-declared associations only; exact arrangement arithmetic, nothing generated'
    assert out['limits'] == ['Every spoke is caller-supplied; the mechanism radiates nothing by itself and discovers no unstated association.', 'Weight shares are exact ratios of declared integer weights; no salience, relevance or truth is computed or implied.', 'A mind map is an arrangement of declarations, not evidence of understanding; no learning, memory or creativity is claimed.']


def test_v6_exact_module_corpus_hash():
    import hashlib
    assert hashlib.sha256(m.__doc__.encode()).hexdigest() == '0f33d49e140aea1ebcd66164da5a0258f433328292ae8ae61ba770ef420e8611'
