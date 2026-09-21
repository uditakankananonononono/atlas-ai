import json
from collections import Counter
from pathlib import Path

AUDIT = json.loads(Path('audits/expanded-owner-spec.json').read_text())
EXPECTED = Counter({'M1': 131, 'M2': 48, 'M3': 31, 'M4': 48, 'Tools': 20, 'Claire': 51})
SOURCE = 'wamid.HBgMOTE4MTM0MDk4NTcxFQIAEhggQUNDRUZGNEMyOEM5ODc2Q0E4MTlFRUZBRThERTYxQ0UA'


def test_expanded_owner_spec_is_fully_rowized():
    rows = AUDIT['rows']
    assert len(rows) == 329
    assert [row['id'] for row in rows] == list(range(1, 330))
    assert Counter(row['module'] for row in rows) == EXPECTED
    assert AUDIT['counts'] == {'verified-pushed': 320, 'missing': 9}


def test_rows_are_complete_unique_and_source_linked():
    rows = AUDIT['rows']
    requirements = [row['requirement'].strip().casefold() for row in rows]
    assert len(requirements) == len(set(requirements))
    assert all(row['requirement'] and row['description'] and row['boundary'] for row in rows)
    assert all(row['source_message_ids'] == [SOURCE] for row in rows)
    assert {row['status'] for row in rows} <= {'verified-pushed', 'thin', 'missing'}


def test_scale_targets_remain_literal_and_unverified():
    expected = {
        'Source adapter: Exactly 200 scholarship sites',
        '10,000+ keyword registry',
        '500,000 accounts per platform target',
        '50 critique passes per LLM target',
        '500,000-field idea taxonomy target',
        '1,000,000-variable analysis target',
        '1,000+ funded-proposal corpus target',
        'Twenty-part grant workflow target',
        'Forty-page research specification target',
    }
    by_requirement = {row['requirement']: row for row in AUDIT['rows']}
    assert expected <= by_requirement.keys()
    assert all(by_requirement[name]['status'] == 'missing' for name in expected)


def test_safety_substitutions_are_explicit():
    by_requirement = {row['requirement']: row for row in AUDIT['rows']}
    assert 'self-bots' in by_requirement['Source adapter: Discord channels']['boundary']
    assert 'Never invent activities' in by_requirement['No fabricated applicant activities']['boundary']
    assert 'No piracy' in by_requirement['OceanofPDF excluded and legal replacement']['boundary']
    assert 'No "unbounded/no ethics" mode' in by_requirement['Risk classification']['boundary']
    assert 'exact-preview approval' in by_requirement['Exact-review install approval']['boundary']
    assert 'not private chain of thought' in by_requirement['No hidden chain-of-thought capture']['boundary']


def test_future_verified_rows_require_machine_evidence():
    for row in AUDIT['rows']:
        if row['status'] == 'verified-pushed':
            assert len(row['evidence']['commit']) == 40
            assert Path(row['evidence']['implementation_path']).exists()
            assert Path(row['evidence']['test_path']).exists()
