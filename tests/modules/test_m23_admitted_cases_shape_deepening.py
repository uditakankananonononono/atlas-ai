"""Row 56 shape deepening for admitted_cases.json and its loader. Offline: no fetch is made; the catalog is read from
disk or from a temp file."""
import json

import pytest

from app.modules.m23_study_abroad import admitted_cases as ac

IDS = ['olin', 'hamilton']


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    """Point the loader at a copy of the real catalog; cases() is cache-cleared before and after."""
    rows = json.loads(ac.CATALOG.read_text(encoding='utf-8'))

    def install(mutated):
        p = tmp_path / 'c.json'
        p.write_text(json.dumps(mutated), encoding='utf-8')
        monkeypatch.setattr(ac, 'CATALOG', p)
        ac.cases.cache_clear()
    yield rows, install
    monkeypatch.undo()
    ac.cases.cache_clear()


def test_catalog_has_the_exact_twenty_ids_and_hosts_and_https_only():
    rows = ac.cases()
    assert len(rows) == 20 and len({r['id'] for r in rows}) == 20
    hosts = sorted({r['url'].split('/')[2] for r in rows})
    assert hosts == ['admission.princeton.edu', 'admissions.dartmouth.edu', 'admissions.tufts.edu', 'admitraven.com',
                     'apply.jhu.edu', 'blog.collegevine.com', 'blog.emoryadmission.com', 'blog.prepscholar.com',
                     'borderless.so', 'business.cornell.edu', 'business.thecrimson.com', 'mitadmissions.org',
                     'sagehenstories.pomona.edu', 'www.admitsee.com', 'www.collegeessayguy.com', 'www.collegeraptor.com',
                     'www.collegetransitions.com', 'www.conncoll.edu', 'www.hamilton.edu', 'www.olin.edu']
    assert all(r['url'].startswith('https://') for r in rows)


def test_every_entry_has_exactly_the_provenance_fields_and_no_essay_text():
    keys = {'id', 'publisher', 'url', 'evidence_type', 'title', 'checked_on', 'access', 'example_school',
            'outcome_basis', 'scope_note', 'reading_mode'}
    for r in ac.cases():
        assert set(r) == keys
        assert r['scope_note'].startswith('Source index; no essay text stored.')
        assert 'not independently verified' in r['scope_note'] or 'not independently' in r['scope_note']


def test_olin_entry_is_pinned():
    r = ac.reading_route('olin')
    assert r['evidence_type'] == 'institution_published_essay'
    assert r['title'] == 'Incoming Class of 2028 essay snippets'
    assert r['url'] == 'https://www.olin.edu/blogs/voices-olins-class-2028-college-essay-snippets'
    assert r['live_status'] == 'source_only' and 'does not rehost' in r['reason']


def test_loader_refuses_duplicate_ids_duplicate_hosts_and_http(catalog):
    rows, install = catalog
    dup_id = [dict(r) for r in rows]; dup_id[1]['id'] = dup_id[0]['id']
    install(dup_id)
    with pytest.raises(AssertionError):
        ac.cases()
    dup_host = [dict(r) for r in rows]; dup_host[1]['url'] = dup_host[0]['url'] + 'x'
    install(dup_host)
    with pytest.raises(AssertionError):
        ac.cases()
    http = [dict(r) for r in rows]; http[0]['url'] = http[0]['url'].replace('https://', 'http://')
    install(http)
    with pytest.raises(AssertionError):
        ac.cases()


def test_search_is_casefolded_filtered_and_capped():
    assert ac.search_cases('  OLIN college ')[0]['id'] == 'olin'
    assert all(r['evidence_type'] == 'third_party_accepted_essay' for r in ac.search_cases(evidence_type='third_party_accepted_essay'))
    assert len(ac.search_cases(evidence_type='third_party_accepted_essay')) == 4
    assert len(ac.search_cases(limit=1000)) == 20 and len(ac.search_cases(limit=0)) == 1 and len(ac.search_cases(limit=3)) == 3
    assert [r['id'] for r in ac.search_cases('student_reported')] == [r['id'] for r in ac.cases() if r['evidence_type'] == 'student_reported_admission']
    assert ac.search_cases('zzzz-no-match') == []


def test_unknown_case_id_raises_key_error():
    with pytest.raises(KeyError):
        ac.reading_route('nope')
