"""Hermetic S2.1 canaries; load additive package without M20's global bootstrap."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('s21', ROOT / 'backend/app/modules/m20_general_cognitive_worker/c33_self_feed/__init__.py', submodule_search_locations=[str(ROOT / 'backend/app/modules/m20_general_cognitive_worker/c33_self_feed')])
m = importlib.util.module_from_spec(spec)
sys.modules['s21'] = m
spec.loader.exec_module(m)

AS_OF = '2026-10-11T15:10:00+05:30'

def record(**changes):
    return dict(id='p1', kind='liked_post', platform='sandbox', author='maker', text='Built open source robot sensor', visibility='public', source_ref='export:fixture/p1', **changes) if not changes else {**record(), **changes}

def payload(records=None):
    return json.dumps({'schema_version': 1, 'records': records if records is not None else [record()]}).encode()

def scanner(**kw):
    return m.Scanner(**kw)

def run(s=None, data=None, **kw):
    connector = kw.pop('connector_override', 'normalized_json')
    return (s or scanner()).run(tenant_id='a', connector=connector, payload=data if data is not None else payload(), as_of=AS_OF, **kw)

def refuse(code, f):
    with pytest.raises(m.Refusal) as e:
        f()
    assert e.value.code == code


def test_normalization_cluster_and_idea_provenance():
    out = run()
    assert out['counts'] == {'supplied': 1, 'unique': 1, 'duplicates': 0, 'liked_post': 1, 'comment': 0, 'followed_account': 0, 'feed_post': 0}
    assert out['clusters'][0]['theme'] == 'engineering'
    assert out['briefs'][0]['status'] == 'draft'
    assert out['briefs'][0]['source_refs'] == ['export:fixture/p1']
    assert out['scope']['as_of'] == AS_OF
    assert out['scope']['data_source'] == 'supplied:normalized_json'
    assert out['action'] == 'none'
    assert len(out['input_sha256']) == 64


def test_csv_paste_fixture():
    out = run(data=(ROOT / 'tests/fixtures/s21/pasted.csv').read_bytes(), connector_override='pasted_csv')
    assert out['counts']['unique'] == 2
    assert {c['theme'] for c in out['clusters']} == {'engineering', 'design'}


def test_duplicates_and_conflicting_ids():
    out = run(data=payload([record(), record()]))
    assert out['counts']['duplicates'] == 1
    refuse('SOCIAL_REFUSED_CONFLICT', lambda: run(data=payload([record(), record(text='different')])) )


def test_same_id_different_platform_is_distinct():
    assert run(data=payload([record(), record(platform='other')]))['counts']['unique'] == 2


@pytest.mark.parametrize('kind', ['liked_post', 'comment', 'followed_account', 'feed_post'])
def test_kinds(kind):
    assert run(data=payload([record(kind=kind)]))['counts'][kind] == 1


def test_owner_data_not_third_party_private():
    assert run(data=payload([record(visibility='owner')]))['counts']['unique'] == 1
    refuse('SOCIAL_REFUSED_THIRDPARTYPRIVATE', lambda: run(data=payload([record(visibility='private')])))
    refuse('SOCIAL_REFUSED_THIRDPARTYPRIVATE', lambda: run(data=payload([record(kind='followed_account', visibility='owner')])))


@pytest.mark.parametrize('field,value', [('id',''), ('platform',''), ('author',''), ('source_ref',''), ('kind','dm'), ('text',123), ('source_ref','javascript:alert(1)'), ('extra','secret')])
def test_invalid_records(field, value):
    refuse('SOCIAL_REFUSED_SCHEMA', lambda: run(data=payload([record(**{field:value})])))


@pytest.mark.parametrize('data', [b'bad', b'[]', b'{"schema_version":true,"records":[]}', b'{"schema_version":1,"records":{}}', b'{"schema_version":1,"records":[],"token":"secret"}', b'{"schema_version":1,"schema_version":1,"records":[]}'])
def test_bad_envelope(data):
    refuse('SOCIAL_REFUSED_SCHEMA', lambda: run(data=data))


def test_missing_unknown_connector():
    refuse('SOCIAL_REFUSED_NOEXPORT', lambda: run(data=b''))
    refuse('SOCIAL_REFUSED_CONNECTOR', lambda: scanner().run(tenant_id='a', connector='live_instagram', payload=payload(), as_of=AS_OF))


def test_limits_at_and_over_boundary():
    s = scanner(max_records=1, max_bytes=1000, max_text=40)
    assert run(s, payload([record(text='x'*40)]))['counts']['unique'] == 1
    refuse('SOCIAL_REFUSED_OVERSIZE', lambda: run(s, payload([record(text='x'*41)])))
    refuse('SOCIAL_REFUSED_OVERSIZE', lambda: run(s, payload([record(),record()])))
    refuse('SOCIAL_REFUSED_OVERSIZE', lambda: run(s, b'x'*1001))


@pytest.mark.parametrize('kw', [{'max_records':True}, {'max_records':0}, {'max_records':5001}, {'max_bytes':0}, {'max_text':False}])
def test_config_limits(kw):
    refuse('SOCIAL_REFUSED_LIMIT', lambda: scanner(**kw))


@pytest.mark.parametrize('action', ['post', 'outreach', 'scrape', 'spend', 'signup', 'trade'])
def test_policy_precedes_connector(action):
    class Spy:
        called = False
        def read(self, data):
            self.called = True
            return [record()]
    spy = Spy()
    s = scanner(connectors={'spy': spy})
    refuse('POLICY_REFUSED_ACTION', lambda: s.run(tenant_id='a', connector='spy', payload=b'x', as_of=AS_OF, action=action))
    assert not spy.called


@pytest.mark.parametrize('answer', [False, None, 1, 'yes'])
def test_injected_policy_fail_closed(answer):
    refuse('POLICY_REFUSED_ACTION', lambda: run(scanner(policy=lambda action: answer)))


def test_pluggable_sandbox_connector_and_revalidation():
    class Plugin:
        def read(self, data): return iter([record()])
    assert scanner(connectors={'mock':Plugin()}).run(tenant_id='a', connector='mock', payload=b'x', as_of=AS_OF)['counts']['unique'] == 1
    class Bad:
        def read(self, data): return [record(visibility='private')]
    refuse('SOCIAL_REFUSED_THIRDPARTYPRIVATE', lambda: scanner(connectors={'bad':Bad()}).run(tenant_id='a', connector='bad', payload=b'x', as_of=AS_OF))


def test_plugin_record_limit_stops_generator():
    class Many:
        def read(self, data):
            while True: yield record()
    refuse('SOCIAL_REFUSED_OVERSIZE', lambda: scanner(connectors={'many':Many()}, max_records=2).run(tenant_id='a',connector='many',payload=b'x',as_of=AS_OF))


def test_reports_are_detached_and_tenant_isolated():
    s = scanner()
    out = run(s)
    out['counts']['unique'] = 999
    found = s.report('a',out['report_id'])
    assert found['counts']['unique'] == 1
    found['scope']['implemented'].clear()
    assert s.report('a',out['report_id'])['scope']['implemented']
    refuse('SOCIAL_REFUSED_NOTFOUND', lambda: s.report('b',out['report_id']))


def test_empty_and_unmatched_no_invented_conclusions():
    out = run(data=payload([]))
    assert out['clusters'] == out['briefs'] == []
    out = run(data=payload([record(text='Hello world')]))
    assert out['clusters'][0]['theme'] == 'unclassified'
    assert 'human psychology' in out['scope']['not_implemented']


@pytest.mark.parametrize('as_of', ['', '2026-10-11', '2026-10-11T12:00:00', 'yesterday'])
def test_as_of_needs_timezone(as_of):
    refuse('SOCIAL_REFUSED_SCHEMA', lambda: scanner().run(tenant_id='a',connector='normalized_json',payload=payload(),as_of=as_of))


def test_tenant_required():
    refuse('SOCIAL_REFUSED_SCHEMA', lambda: scanner().run(tenant_id='',connector='normalized_json',payload=payload(),as_of=AS_OF))


def test_reports_bounded():
    s=scanner(max_reports=1)
    first=run(s)
    second=run(s,data=payload([record(id='p2')]))
    refuse('SOCIAL_REFUSED_NOTFOUND',lambda:s.report('a',first['report_id']))
    assert s.report('a',second['report_id'])['counts']['unique']==1


def test_csv_rejects_bad_headers_and_duplicate_columns():
    for data in [b'id,text\np1,hello\n', b'id,id,kind,platform,author,text,visibility,source_ref\np1,p1,liked_post,sandbox,x,hi,public,export:p1\n']:
        refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=data,connector_override='pasted_csv'))


def test_surrogate_refusal():
    refuse('SOCIAL_REFUSED_SCHEMA', lambda: run(data=payload([record(text='\ud800')])))


def test_determinism_and_word_not_substring():
    records=[record(text='robotics'),record(id='p2',text='robot')]
    a=run(data=payload(records));b=run(data=payload(list(reversed(records))))
    assert a['clusters']==b['clusters']
    assert {c['theme'] for c in a['clusters']}=={'engineering','unclassified'}


def test_failure_creates_no_partial_report():
    s=scanner()
    refuse('SOCIAL_REFUSED_THIRDPARTYPRIVATE',lambda:run(s,data=payload([record(),record(id='p2',visibility='private')])))
    assert not s._reports


def test_even_permissive_injected_guard_cannot_authorize_effect():
    refuse('POLICY_REFUSED_ACTION', lambda: run(scanner(policy=lambda action:True),action='post'))


def test_unclassified_never_generates_idea():
    assert run(data=payload([record(text='Hello world')]))['briefs']==[]


def test_policy_callable_required():
    refuse('POLICY_REFUSED_ACTION',lambda:scanner(policy=None))
