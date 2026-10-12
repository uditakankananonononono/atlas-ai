"""Acceptance pins for the mounted engines 697, 698, 700, 702 and 703: hand-derived vectors, exact refusal text and exact caps."""
import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

BASE = '/api/v1/api/modules/20'
P697 = BASE + '/feature-flags/697/evaluate'
P698 = BASE + '/trunk-based-development/698/analyze'
P700 = BASE + '/semantic-versioning/700/analyze'
P702 = BASE + '/release-notes/702/plan'
P703 = BASE + '/documentation-generation/703/generate'


@pytest.fixture
def call(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV', 'production')
    client = TestClient(app, raise_server_exceptions=False)
    counter = {'n': 0}

    def go(path, data, expect=200):
        counter['n'] += 1  # requests are limited per tenant and actor, so every call uses its own tenant
        tenant = 'pin%s%d' % (path.rsplit('/', 2)[-2], counter['n'])
        r = client.post(path, headers=oidc_auth_headers(tenant, 'owner'), json={'data': data})
        assert r.status_code == expect, r.text
        j = r.json()
        if expect == 200:
            assert j.pop('tenant_id') == tenant and j.pop('actor_id') == 'owner'
            return j
        return j['detail']
    return go


# ------------------------------------------------------------------ 697
def cmp_(op, field, value):
    return {'op': op, 'field': field, 'value': value}


def flag(name, rules, default=False, **extra):
    return {'name': name, 'source_id': 's-' + name, 'default': default, 'rules': rules, **extra}


def rule(rid, priority, value, condition):
    return {'id': rid, 'source_id': 'r-' + rid, 'priority': priority, 'value': value, 'condition': condition}


def req697(flags, schema=None, context=None):
    return {'context_schema': {'x': 'int', 'name': 'string'} if schema is None else schema,
            'evaluation_context': {'x': 5} if context is None else context, 'flags': flags}


def test_697_vector_priority_trace_and_three_valued_logic(call):
    flags = [
        flag('b', [rule('hi', 20, True, cmp_('ge', 'x', 5)), rule('lo', 10, False, cmp_('gt', 'x', 4))], True),
        flag('a', [rule('miss', 1, True, cmp_('eq', 'name', 'z')), rule('neg', 2, True, {'op': 'not', 'arg': cmp_('eq', 'name', 'z')})]),
        flag('c', [rule('any', 1, True, {'op': 'any', 'args': [cmp_('eq', 'name', 'z'), cmp_('eq', 'x', 5)]}),
                   rule('all', 2, True, {'op': 'all', 'args': [cmp_('eq', 'name', 'z'), cmp_('eq', 'x', 6)]})]),
    ]
    j = call(P697, req697(flags))
    assert [f['name'] for f in j['flags']] == ['a', 'b', 'c']  # sorted by name
    a, b, c = j['flags']
    # a: 'name' is absent from the context, so eq is unknown (None) and not(unknown) stays unknown: no rule matches
    assert a['value'] is False and a['reason'] == 'default_no_match' and a['priority'] is None and a['matched_rule_id'] is None
    assert a['trace'] == [{'rule_id': 'miss', 'source_id': 'r-miss', 'priority': 1, 'matched': None, 'missing_fields': ['name']},
                          {'rule_id': 'neg', 'source_id': 'r-neg', 'priority': 2, 'matched': None, 'missing_fields': ['name']}]
    # b: the lowest priority number is evaluated first and wins even though a higher number also matches
    assert b['value'] is False and b['reason'] == 'matched_rule' and b['priority'] == 10 and b['matched_rule_id'] == 'lo'
    assert [t['rule_id'] for t in b['trace']] == ['lo', 'hi'] and all(t['matched'] is True for t in b['trace'])
    # c: any(unknown, true) is true; all(unknown, false) is false
    assert c['value'] is True and c['matched_rule_id'] == 'any'
    assert [t['matched'] for t in c['trace']] == [True, False] and c['trace'][1]['missing_fields'] == ['name']
    assert a['caller_diagnostic_safe'] is None and j['status'] == 'supplied_flag_rules_evaluated'
    assert j['capability_executed'] is True and j['evidence_verified'] is False
    assert j['repository_behavior_verified'] is False and j['release_authorized'] is False
    assert j['boundary'] == 'Finite caller-supplied rules only; no rollout, network, persistence or deployment.'


def test_697_bucket_is_sha256_of_seed_and_value(call):
    # score = first 8 bytes of sha256 of the compact JSON [seed, value], big-endian, mod 10000; matched iff score < percent * 100
    enc = json.dumps(['seed', 'u1'], separators=(',', ':')).encode()
    score = int.from_bytes(hashlib.sha256(enc).digest()[:8], 'big') % 10000
    pct_hit = score // 100 + 1
    pct_miss = score // 100
    cond = lambda p: {'op': 'bucket', 'field': 'name', 'seed': 'seed', 'percent': p}
    flags = [flag('hit', [rule('r', 1, True, cond(pct_hit))]), flag('miss', [rule('r', 1, True, cond(pct_miss))]),
             flag('all', [rule('r', 1, True, cond(100))]), flag('none', [rule('r', 1, True, cond(0))])]
    j = call(P697, req697(flags, context={'name': 'u1'}))
    assert {f['name']: f['value'] for f in j['flags']} == {'hit': True, 'miss': False, 'all': True, 'none': False}


def test_697_bool_is_not_int_and_ints_stop_at_2_53(call):
    top = 2 ** 53 - 1
    call(P697, req697([], context={'x': top}))
    assert call(P697, req697([], context={'x': top + 1}), 422) == 'FLAG697_TYPE: context.x'
    assert call(P697, req697([], context={'x': True}), 422) == 'FLAG697_TYPE: context.x'
    assert call(P697, req697([flag('f', [rule('r', 1, True, cmp_('eq', 'x', True))])]), 422) == 'FLAG697_TYPE: rule.r.value'


def test_697_exact_refusals(call):
    ok = rule('r', 1, True, cmp_('eq', 'x', 5))
    assert call(P697, req697([flag('f', [ok]), flag('f', [])]), 422) == 'FLAG697_DUPLICATE_FLAG: f'
    assert call(P697, req697([flag('f', [ok, rule('r', 2, True, cmp_('eq', 'x', 5))])]), 422) == 'FLAG697_DUPLICATE_RULE: r'
    assert call(P697, req697([flag('f', [ok, rule('q', 1, True, cmp_('eq', 'x', 5))])]), 422) == 'FLAG697_DUPLICATE_PRIORITY: f'
    assert call(P697, req697([flag('f', [rule('r', -1, True, cmp_('eq', 'x', 5))])]), 422) == 'FLAG697_PRIORITY: r'
    assert call(P697, req697([flag('f', [rule('r', 1000001, True, cmp_('eq', 'x', 5))])]), 422) == 'FLAG697_PRIORITY: r'
    call(P697, req697([flag('f', [rule('r', 1000000, True, cmp_('eq', 'x', 5))])]))
    assert call(P697, req697([flag('f', [rule('r', 1, True, cmp_('eq', 'nope', 5))])]), 422) == 'FLAG697_FIELD: rule.r.field'
    assert call(P697, req697([flag('f', [rule('r', 1, True, cmp_('lt', 'name', 'a'))])]), 422) == 'FLAG697_OPERATOR_TYPE: rule.r'
    assert call(P697, req697([flag('f', [rule('r', 1, True, cmp_('regex', 'x', 5))])]), 422) == 'FLAG697_OPERATOR: rule.r.op'
    assert call(P697, req697([flag('f', [rule('r', 1, True, {'op': 'bucket', 'field': 'x', 'seed': 's', 'percent': 5})])]), 422) == 'FLAG697_OPERATOR_TYPE: rule.r'
    assert call(P697, req697([flag('f', [rule('r', 1, True, {'op': 'bucket', 'field': 'name', 'seed': 's', 'percent': 101})])]), 422) == 'FLAG697_BUCKET: rule.r.percent'
    assert call(P697, req697([flag('f', [rule('r', 1, True, {'op': 'bucket', 'field': 'name', 'seed': 's', 'percent': True})])]), 422) == 'FLAG697_BUCKET: rule.r.percent'
    assert call(P697, req697([flag('f', [])], schema={'x': 'float'}), 422) == 'FLAG697_TYPE: schema.x'


def test_697_caps_exact(call):
    ok = lambda i: rule('r%d' % i, i, True, cmp_('eq', 'x', 5))
    call(P697, req697([flag('f%d' % i, []) for i in range(32)]))
    assert call(P697, req697([flag('f%d' % i, []) for i in range(33)]), 422) == 'FLAG697_BOUND: flags'
    call(P697, req697([flag('f', [ok(i) for i in range(32)])]))
    assert call(P697, req697([flag('f', [ok(i) for i in range(33)])]), 422) == 'FLAG697_BOUND: flag.rules'
    call(P697, req697([], schema={'f%d' % i: 'int' for i in range(64)}, context={}))
    assert call(P697, req697([], schema={'f%d' % i: 'int' for i in range(65)}, context={}), 422) == 'FLAG697_BOUND: context'
    call(P697, req697([flag('n' * 64, [])]))
    assert call(P697, req697([flag('n' * 65, [])]), 422) == 'FLAG697_ID: flag.name'
    deep = lambda d: (cmp_('eq', 'x', 5) if d == 1 else {'op': 'not', 'arg': deep(d - 1)})
    call(P697, req697([flag('f', [rule('r', 1, True, deep(8))])]))
    assert call(P697, req697([flag('f', [rule('r', 1, True, deep(9))])]), 422) == 'FLAG697_BOUND: rule.r.arg.arg.arg.arg.arg.arg.arg.arg'
    wide = lambda n: {'op': 'all', 'args': [cmp_('eq', 'x', 5)] * n}
    call(P697, req697([flag('f', [rule('r', 1, True, wide(127))])]))
    assert call(P697, req697([flag('f', [rule('r', 1, True, wide(128))])]), 422) == 'FLAG697_BOUND: rule.r.args'
    s256 = lambda n: req697([], schema={'name': 'string'}, context={'name': 's' * n})
    call(P697, s256(256))
    assert call(P697, s256(257), 422) == 'FLAG697_TYPE: context.name'


def test_697_unknown_stays_unknown_in_all_and_any(call):
    t, u, f_ = cmp_('eq', 'x', 5), cmp_('eq', 'name', 'z'), cmp_('eq', 'x', 6)
    flags = [flag('p', [rule('all_tu', 1, True, {'op': 'all', 'args': [t, u]}), rule('any_fu', 2, True, {'op': 'any', 'args': [f_, u]}),
                        rule('all_tt', 3, True, {'op': 'all', 'args': [t, t]}), rule('any_ff', 4, True, {'op': 'any', 'args': [f_, f_]})])]
    tr = call(P697, req697(flags))['flags'][0]['trace']
    assert [(x['rule_id'], x['matched']) for x in tr] == [('all_tu', None), ('any_fu', None), ('all_tt', True), ('any_ff', False)]


def test_697_bucket_boundary_is_strictly_below_percent(call):
    for n in range(100000):
        seed = 'b%d' % n
        score = int.from_bytes(hashlib.sha256(json.dumps([seed, 'u'], separators=(',', ':')).encode()).digest()[:8], 'big') % 10000
        if score % 100 == 0 and score:
            break
    cond = lambda p: {'op': 'bucket', 'field': 'name', 'seed': seed, 'percent': p}
    j = call(P697, req697([flag('on', [rule('r', 1, True, cond(score // 100 + 1))]), flag('edge', [rule('r', 1, True, cond(score // 100))])],
                          context={'name': 'u'}))
    assert {f['name']: f['value'] for f in j['flags']} == {'on': True, 'edge': False}


def test_697_condition_node_total_is_128_127_children_per_group_and_129_refused(call):
    leaf = cmp_('eq', 'x', 5)
    tree = lambda a, b: {'op': 'all', 'args': [{'op': 'all', 'args': [leaf] * a}, {'op': 'all', 'args': [leaf] * b}]}
    call(P697, req697([flag('f', [rule('r', 1, True, tree(63, 62))])]))  # 1 + (1 + 63) + (1 + 62) = 128 nodes
    assert call(P697, req697([flag('f', [rule('r', 1, True, tree(63, 63))])]), 422) == 'FLAG697_BOUND: rule.r.args.1.args.62'  # the 129th node


# ------------------------------------------------------------------ 698
def sha(i):
    return '%040x' % i


def c698(i, parents, at):
    return {'sha': sha(i), 'parents': [sha(p) for p in parents], 'committed_at': at}


def req698(**over):
    d = {'source_ref': 'snap', 'trunk': 'main', 'reference_time': '2026-10-11T12:00:00Z', 'max_branch_age_hours': 24,
         'required_checks': ['ci'],
         'commits': [c698(1, [], '2026-10-01T00:00:00Z'), c698(2, [1], '2026-10-10T00:00:00Z'),
                     c698(3, [1], '2026-10-10T12:00:00Z'), c698(4, [3], '2026-10-11T00:00:00Z')],
         'branches': [{'name': 'main', 'tip': sha(2)}, {'name': 'feat', 'tip': sha(4)}],
         'checks': [{'name': 'ci', 'sha': sha(2), 'conclusion': 'success'}, {'name': 'ci', 'sha': sha(4), 'conclusion': 'failure'}]}
    d.update(over)
    return d


def test_698_vector_divergence_age_and_exact_sha_checks(call):
    j = call(P698, req698())
    feat = [b for b in j['branches'] if b['name'] == 'feat'][0]
    assert (feat['state'], feat['ahead'], feat['behind']) == ('diverged', 2, 1)
    assert feat['merge_bases'] == [sha(1)] and feat['unmerged_commits'] == [sha(3), sha(4)]
    assert feat['oldest_unmerged_commit_at'] == '2026-10-10T12:00:00Z' and feat['age_seconds'] == 86400
    assert feat['stale'] is False  # exactly 24 hours old is not older than the 24 hour limit
    assert feat['required_checks'] == {'ci': {'status': 'failed', 'stale_ancestor_shas': []}} and feat['required_checks_covered'] is False
    assert j['trunk']['tip'] == sha(2) and j['trunk']['commit_count'] == 2 and j['trunk']['required_checks_covered'] is True
    assert j['stale_branches'] == [] and j['branch_protection_verified'] is False and j['main_mutated'] is False
    assert j['unreachable_commits'] == []
    j2 = call(P698, req698(max_branch_age_hours=23.999999))
    assert j2['stale_branches'] == ['feat']


def test_698_pass_on_an_ancestor_does_not_cover_a_descendant_tip(call):
    d = req698(checks=[{'name': 'ci', 'sha': sha(3), 'conclusion': 'success'}, {'name': 'ci', 'sha': sha(2), 'conclusion': 'success'}])
    feat = [b for b in call(P698, d)['branches'] if b['name'] == 'feat'][0]
    assert feat['required_checks'] == {'ci': {'status': 'missing', 'stale_ancestor_shas': [sha(3)]}}
    assert feat['required_checks_covered'] is False


def test_698_exact_refusals(call):
    assert call(P698, req698(trunk='nope'), 422) == 'trunk branch nope not in branches'
    assert call(P698, req698(reference_time='2026-10-11T12:00:00'), 422) == 'timestamp reference_time must be ISO-8601 with explicit UTC offset'
    assert call(P698, req698(max_branch_age_hours=0), 422) == 'max_branch_age_hours must be a finite number in (0, 8760]'
    call(P698, req698(max_branch_age_hours=8760))
    assert call(P698, req698(max_branch_age_hours=8761), 422) == 'max_branch_age_hours must be a finite number in (0, 8760]'
    assert call(P698, req698(required_checks=[]) | {'bogus': 1}, 422) == "unknown key 'bogus' in request"
    assert call(P698, req698(branches=[{'name': 'main', 'tip': sha(2)}, {'name': 'main', 'tip': sha(2)}]), 422) == 'duplicate branch main'
    assert call(P698, req698(branches=[{'name': 'main', 'tip': sha(9)}]), 422) == 'unknown tip %s for branch main' % sha(9)
    assert call(P698, req698(commits=[c698(1, [], '2026-10-01T00:00:00Z'), c698(2, [7], '2026-10-10T00:00:00Z')],
                             branches=[{'name': 'main', 'tip': sha(2)}], checks=[]), 422) == 'unknown parent %s of commit %s' % (sha(7), sha(2))
    assert call(P698, req698(commits=[c698(1, [], '2026-10-12T00:00:00Z'), c698(2, [1], '2026-10-12T01:00:00Z')],
                             branches=[{'name': 'main', 'tip': sha(2)}], checks=[]), 422) == 'commit %s is after reference_time' % sha(1)
    assert call(P698, req698(checks=[{'name': 'ci', 'sha': sha(2), 'conclusion': 'maybe'}]), 422) == "check ci@%s has unsupported conclusion 'maybe'" % sha(2)


def test_698_caps_exact(call):
    many = lambda n: [{'name': 'b%d' % i, 'tip': sha(1)} for i in range(n)]
    call(P698, req698(branches=[{'name': 'main', 'tip': sha(2)}] + many(63)))
    assert call(P698, req698(branches=[{'name': 'main', 'tip': sha(2)}] + many(64)), 422) == 'branches exceed 64'
    call(P698, req698(required_checks=['c%d' % i for i in range(16)]))
    assert call(P698, req698(required_checks=['c%d' % i for i in range(17)]), 422) == 'required_checks exceed 16'
    chain = lambda n: [c698(i + 1, [i] if i else [], '2026-10-01T00:00:00Z') for i in range(n)]
    call(P698, req698(commits=chain(2000), branches=[{'name': 'main', 'tip': sha(2000)}], checks=[]))
    assert call(P698, req698(commits=chain(2001), branches=[{'name': 'main', 'tip': sha(2001)}], checks=[]), 422) == 'commits exceed 2000'
    call(P698, req698(source_ref='s' * 200))
    assert call(P698, req698(source_ref='s' * 201), 422) == 'source_ref exceeds 200 characters'
    call(P698, req698(trunk='t' * 100, branches=[{'name': 't' * 100, 'tip': sha(2)}]))
    assert call(P698, req698(trunk='t' * 101), 422) == "invalid trunk name '%s'" % ('t' * 101)
    checks = lambda n: [{'name': 'ci', 'sha': sha(2), 'conclusion': 'success'}] + [{'name': 'x%d' % i, 'sha': sha(2), 'conclusion': 'success'} for i in range(n - 1)]
    call(P698, req698(checks=checks(512)))
    assert call(P698, req698(checks=checks(513)), 422) == 'checks exceed 512'


# ------------------------------------------------------------------ 700
def prm(name, kind='positional', required=True, typ='int'):
    return {'name': name, 'kind': kind, 'required': required, 'type': typ}


def fn(name, params, returns='int'):
    return {'name': name, 'kind': 'function', 'signature': {'params': params, 'returns': returns}}


def req700(base, cand, version='1.2.3', **extra):
    return {'current_version': version, 'baseline_snapshot': {'symbols': base}, 'candidate_snapshot': {'symbols': cand}, **extra}


def test_700_vector_breaking_beats_additive_and_details_are_sorted(call):
    base = [fn('f', [prm('a'), prm('b', required=False)]), fn('g', []), fn('h', [prm('a')]), fn('k', [])]
    cand = [fn('f', [prm('a', typ='str'), prm('b'), prm('c', required=False)], 'str'), fn('g', []), fn('h', [prm('a', required=False)]), fn('n', [])]
    j = call(P700, req700(base, cand))
    assert (j['diff'], j['bump'], j['next_version'], j['stable_core']) == ('breaking', 'major', '2.0.0', '1.2.3')
    assert j['symbol_changes'] == [
        {'name': 'f', 'change': 'modified-breaking',
         'details': ['param-added-optional:c', 'param-made-required:b', 'param-type-changed:a', 'return-type-changed:int->str']},
        {'name': 'g', 'change': 'identical', 'details': []},
        {'name': 'h', 'change': 'modified-additive', 'details': ['param-made-optional:a']},
        {'name': 'k', 'change': 'removed', 'details': ['symbol-removed']},
        {'name': 'n', 'change': 'added', 'details': ['symbol-added']}]
    assert j['counts'] == {'removed': 1, 'added': 1, 'modified_breaking': 1, 'modified_additive': 1, 'identical': 1}
    assert j['human_review_required'] is True and j['label_conflicts'] == []


def test_700_bump_levels_and_prerelease_is_stripped(call):
    same = [fn('f', [prm('a')])]
    assert call(P700, req700(same, same, '1.2.3'))['next_version'] == '1.2.4'
    assert call(P700, req700(same, same + [fn('g', [])], '1.2.3'))['next_version'] == '1.3.0'
    assert call(P700, req700(same, [], '1.2.3'))['next_version'] == '2.0.0'
    j = call(P700, req700(same, same, '1.2.3-rc.1+b7'))
    assert j['stable_core'] == '1.2.3' and j['next_version'] == '1.2.4' and j['bump'] == 'patch' and j['diff'] == 'no-public-change'


def test_700_positional_order_matters_keyword_order_does_not(call):
    a, b = prm('a'), prm('b')
    j = call(P700, req700([fn('f', [a, b])], [fn('f', [b, a])]))
    assert j['symbol_changes'][0]['details'] == ['positional-renamed-or-reordered:index0:a->b', 'positional-renamed-or-reordered:index1:b->a']
    ka, kb = prm('a', 'keyword'), prm('b', 'keyword')
    j = call(P700, req700([fn('f', [ka, kb])], [fn('f', [kb, ka])]))
    assert j['bump'] == 'patch' and j['symbol_changes'][0]['change'] == 'identical'


def test_700_caller_labels_never_change_the_computed_bump(call):
    same = [fn('f', [])]
    j = call(P700, req700(same, same + [fn('g', [])], caller_labels={'overall': 'none'}))
    assert j['bump'] == 'minor' and j['label_conflicts'] == ['caller-overall:none!=additive']
    assert call(P700, req700(same, same, caller_labels={'overall': 'huge'}), 422) == "E_SCHEMA: unknown overall label 'huge'"


def test_700_exact_refusals_and_bounds(call):
    same = [fn('f', [])]
    assert call(P700, req700(same, same, '1.2'), 422) == "E_VERSION_PARSE: invalid semantic version: '1.2'"
    top = 2 ** 53 - 1
    assert call(P700, req700(same, same, '%d.0.0' % (top + 1)), 422) == 'E_VERSION_PARSE: component %d exceeds exact bound %d' % (top + 1, top)
    assert call(P700, req700(same, [], '%d.0.0' % top), 422) == 'E_OVERFLOW: major bump from %d exceeds exact bound' % top
    assert call(P700, req700(same, same + [fn('g', [])], '1.%d.0' % top), 422) == 'E_OVERFLOW: minor bump from %d exceeds exact bound' % top
    assert call(P700, req700(same, same, '1.0.%d' % top), 422) == 'E_OVERFLOW: patch bump from %d exceeds exact bound' % top
    assert call(P700, req700(same + same, same), 422) == "E_SCHEMA: baseline duplicate symbol name 'f'"
    assert call(P700, req700(same, [{**same[0], 'kind': 'class'}]), 422) == "E_SCHEMA: candidate symbol 'f': only kind function is supported"
    assert call(P700, req700(same, [fn('f', [prm('a'), prm('a')])]), 422) == "E_SCHEMA: candidate symbol 'f': duplicate param name 'a'"
    assert call(P700, req700(same, [fn('f', [prm('a', 'star')])]), 422).startswith("E_SCHEMA: candidate symbol 'f': param kind must be one of")


def test_700_caps_exact(call):
    syms = lambda n: [fn('s%d' % i, []) for i in range(n)]
    call(P700, req700(syms(1024), syms(1024)))
    assert call(P700, req700(syms(1025), []), 422) == 'E_SCHEMA: baseline symbols must be a list of 0..1024 entries'
    params = lambda n: [fn('f', [prm('p%d' % i) for i in range(n)])]
    call(P700, req700(params(64), params(64)))
    assert call(P700, req700(params(65), params(64)), 422) == "E_SCHEMA: baseline symbol 'f': params must be a list of 0..64"
    call(P700, req700([fn('n' * 200, [])], [fn('n' * 200, [])]))
    assert call(P700, req700([fn('n' * 201, [])], []), 422) == 'E_SCHEMA: baseline symbol name must be a string of 1..200 chars'
    call(P700, req700([fn('f', [], 'r' * 200)], [fn('f', [], 'r' * 200)]))
    assert call(P700, req700([fn('f', [], 'r' * 201)], []), 422) == "E_SCHEMA: baseline symbol 'f': returns must be a string of 1..200 chars"


# ------------------------------------------------------------------ 702
def chg(i, description='d', user_visible=True, breaking=False):
    return {'id': i, 'description': description, 'user_visible': user_visible, 'breaking': breaking}


def req702(changes, **over):
    return {'version': '2.0', 'audience': 'ops', 'changes': changes, 'upgrade_steps': ['u1'], 'known_issues': ['k1'], **over}


def test_702_vector_highlights_breaking_order_and_digest(call):
    data = req702([chg('c1', 'first', True, False), chg('c2', 'second', False, True), chg('c3', 'third', True, True), chg('c4', 'fourth', False, False)])
    j = call(P702, data)
    assert j['highlights'] == [{'id': 'c1', 'description': 'first'}, {'id': 'c3', 'description': 'third'}]
    assert j['breaking_changes'] == [{'id': 'c2', 'description': 'second'}, {'id': 'c3', 'description': 'third'}]
    assert j['generated_from_change_ids'] == ['c1', 'c2', 'c3', 'c4']
    assert j['version'] == '2.0' and j['audience'] == 'ops' and j['upgrade_steps'] == ['u1'] and j['known_issues'] == ['k1']
    assert j['status'] == 'draft_only' and j['published'] is False and j['release_authorized'] is False
    assert j['snapshot_sha256'] == hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    reordered = {k: data[k] for k in reversed(list(data))}
    assert call(P702, reordered)['snapshot_sha256'] == j['snapshot_sha256']  # key order does not change the digest


def test_702_exact_refusals(call):
    assert call(P702, req702([chg('c1'), chg('c1')]), 422) == 'RELEAS702: duplicate change id'
    assert call(P702, req702([chg('c1', user_visible=1)]), 422) == 'RELEAS702: flag must be bool'
    assert call(P702, req702([{**chg('c1'), 'x': 1}]), 422) == 'RELEAS702: change fields invalid'
    assert call(P702, req702([{k: v for k, v in chg('c1').items() if k != 'breaking'}]), 422) == 'RELEAS702: change fields invalid'
    assert call(P702, req702([], version='   '), 422) == 'RELEAS702: text must be 1..1000 characters without controls'
    assert call(P702, req702([], audience='a\u200bb'), 422) == 'RELEAS702: text must be 1..1000 characters without controls'
    assert call(P702, req702([], upgrade_steps='x'), 422) == 'RELEAS702: list required'
    assert call(P702, req702([], known_issues=[1]), 422) == 'RELEAS702: text must be 1..1000 characters without controls'
    d = req702([]); d.pop('audience')
    assert call(P702, d, 422) == 'RELEAS702: request fields invalid'


def test_702_caps_exact(call):
    t = lambda n: 'x' * n
    j = call(P702, req702([chg('c1', t(1000))], version=t(1000)))
    assert len(j['highlights'][0]['description']) == 1000
    assert call(P702, req702([chg('c1', t(1001))]), 422) == 'RELEAS702: text must be 1..1000 characters without controls'
    call(P702, req702([], upgrade_steps=['u'] * 10000))
    assert call(P702, req702([], upgrade_steps=['u'] * 10001), 422) == 'RELEAS702: list exceeds 10000'
    call(P702, req702([], known_issues=['k'] * 10000))
    assert call(P702, req702([], known_issues=['k'] * 10001), 422) == 'RELEAS702: list exceeds 10000'


# ------------------------------------------------------------------ 703
SRC703 = ('import os\n\n'
          'def f(a: int, b="x", *args, c, **kw) -> str:\n'
          '    """Doc."""\n'
          '    return b\n\n'
          'class K(Base):\n'
          '    def m(self):\n'
          '        pass\n')


def test_703_vector_signature_ranges_and_unknowns(call):
    j = call(P703, {'source': SRC703})
    assert j['status'] == 'generated' and j['algorithm'] == 'python_ast_api_documentation_v1'
    assert j['source_sha256'] == hashlib.sha256(SRC703.encode()).hexdigest()
    assert (j['source_chars'], j['source_bytes'], j['line_count']) == (130, 130, 9)
    assert [s['qualname'] for s in j['symbols']] == ['f', 'K', 'K.m']
    f, k, m = j['symbols']
    assert f['signature_text'] == '(a: int, b="x", *args, c, **kw) -> str'
    assert [(p['name'], p['kind'], p['has_default']) for p in f['parameters']] == [
        ('a', 'positional_or_keyword', False), ('b', 'positional_or_keyword', True), ('args', 'var_positional', False),
        ('c', 'keyword_only', False), ('kw', 'var_keyword', False)]
    assert f['parameters'][1]['default'] == '"x"' and f['parameters'][0]['annotation'] == 'int' and f['returns'] == 'str'
    assert f['range'] == {'start': {'line': 3, 'col': 0}, 'end': {'line': 5, 'col': 12}}
    assert f['docstring']['raw'] == 'Doc.' and f['docstring']['range'] == {'start': {'line': 4, 'col': 4}, 'end': {'line': 4, 'col': 14}}
    assert f['missing'] == {'docstring': False, 'return_annotation': False, 'unannotated_parameters': ['b', 'args', 'c', 'kw']}
    assert f['unknown_semantics'] == ['parameter_descriptions', 'return_description', 'raises', 'side_effects', 'behavior', 'thread_safety']
    assert f['semantics_derived'] is False and f['parameters'][0]['semantics'] == 'unknown'
    assert k['bases'] == ['Base'] and k['constructor_signature'] == 'not_derived' and k['docstring'] is None
    assert k['unknown_semantics'] == ['attributes', 'behavior', 'invariants', 'thread_safety']
    assert (m['parent_id'], m['depth'], m['scope']) == ('K#1', 1, 'class')
    assert m['range'] == {'start': {'line': 8, 'col': 4}, 'end': {'line': 9, 'col': 12}}


def test_703_source_is_parsed_never_executed(call):
    j = call(P703, {'source': 'raise SystemExit(3)\nopen("/nonexistent/x", "w")\ndef f(): pass\n'})
    assert [s['name'] for s in j['symbols']] == ['f']
    assert call(P703, {'source': 'def f(:\n'}, 422)


def test_703_exact_caps(call):
    ok = ('#' * 65535) + '\n'
    assert len(ok) == 65536
    call(P703, {'source': ok})
    assert call(P703, {'source': ok + '#'}, 422) == 'source exceeds 65536 characters'
    call(P703, {'source': '\n' * 2000})
    assert call(P703, {'source': '\n' * 2001}, 422)
    assert call(P703, {'source': 'x\x00'}, 422) == 'source contains NUL'
