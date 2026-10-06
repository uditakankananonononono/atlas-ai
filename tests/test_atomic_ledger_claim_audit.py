import json
from pathlib import Path

import pytest

AUDIT = json.loads(Path('audits/additional-atomic-concepts.json').read_text())
ROWS_BY_ID = {row['atomic_row_id']: row for row in AUDIT['rows']}
PURE_WRAPPER_IDS = ['7.5', '7.6', '7.7', '8.1', '8.2', '8.3', '8.4', '8.5', '8.6', '9.1', '9.2', '9.3', '9.4', '9.5', '9.6',
                    '10.1', '10.2', '10.3', '11.1', '11.2', '13.1', '13.2', '17.1']


def test_exact_23_pure_wrapper_ids_stay_missing_independent_of_selection():
    # Looks the ids up directly, so relabelling one (which would drop it from any "missing" selection) fails here.
    assert len(PURE_WRAPPER_IDS) == 23
    for atomic_id in PURE_WRAPPER_IDS:
        assert ROWS_BY_ID[atomic_id]['status'] == 'missing', atomic_id
    assert AUDIT['counts'] == {'verified-pushed': 137, 'missing': 23}
    assert sum(1 for row in AUDIT['rows'] if row['status'] == 'missing') == 23


def test_each_row_has_its_own_unfulfilled_limit():
    texts = []
    for atomic_id in PURE_WRAPPER_IDS:
        audit = ROWS_BY_ID[atomic_id]['claim_audit']
        assert audit['implementation_kind'] == 'pure-analysis-wrapper'
        assert audit['effects_performed'] == []
        assert Path(audit['implementation_path']).exists() and Path(audit['test_evidence']).exists()
        assert audit['unfulfilled'].startswith('NOT DELIVERED: ')
        texts.append(audit['unfulfilled'])
    assert len(set(texts[:7] + texts[9:])) >= 17  # rows share wording only within 8.1-8.3


@pytest.mark.parametrize('atomic_id', PURE_WRAPPER_IDS)
def test_every_wrapper_row_reports_no_effects_performed(atomic_id):
    from tests.modules.test_m21_atomic_concepts_47_69 import d
    from app.modules.m21_claire.atomic_concepts_47_69 import run
    out = run(atomic_id, d(atomic_id))
    assert out['atomic_row_id'] == atomic_id
    assert out['effects_performed'] == []
    assert 'Analysis/proposal only' in out['boundary']
