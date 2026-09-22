import json
from pathlib import Path


def test_second_design_mapping_is_complete_and_makes_no_unearned_claims():
    audit=json.loads(Path('audits/second-design-line-by-line.json').read_text())
    assert audit['source_document_id']=='1ReYOhOZNH0JvaZfmifEW12t9mG5N_63aSntqbVSgH2g'
    assert audit['counts']=={'source_lines':239,'headings':22,'substantive_paragraphs':217,
                             'verified':0,'thin':0,'missing':0,'unverified':217}
    assert [r['row'] for r in audit['rows']]==list(range(1,218))
    assert len({r['source_paragraph'] for r in audit['rows']})==217
    assert all(r['source_text'].strip() and r['status']=='unverified' for r in audit['rows'])
    assert all(r['implementation_path'] is None and r['test_evidence'] is None for r in audit['rows'])
