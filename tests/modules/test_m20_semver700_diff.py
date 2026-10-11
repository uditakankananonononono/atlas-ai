"""Row 700 Semantic Versioning: supplied API signature snapshot diff + exact
next-semver recommendation. Tests target ONLY the new module
app.modules.m20_general_cognitive_worker.api_semver700. Declared API shapes
only; caller change labels are never evidence; no publishing."""
import json
import pytest
from app.modules.m20_general_cognitive_worker import api_semver700 as sv


def sym(name, params=(), returns='int'):
    return {'name': name, 'kind': 'function',
            'signature': {'params': [dict(p) for p in params], 'returns': returns}}

def pos(name, required=True, type='int'):
    return {'name': name, 'kind': 'positional', 'required': required, 'type': type}

def kw(name, required=False, type='int'):
    return {'name': name, 'kind': 'keyword', 'required': required, 'type': type}

def snap(*symbols):
    return {'symbols': list(symbols)}

BASE = snap(sym('f', [pos('a'), kw('b')], 'int'))

def diff(cur='1.2.3', base=BASE, cand=BASE, labels=None):
    return sv.diff_api_snapshots(cur, base, cand, caller_labels=labels)


# ---- version parsing: exact, bounded, N/N+1 ----
def test_parse_valid_forms():
    assert sv.parse_version('1.2.3') == (1, 2, 3, None, None)
    assert sv.parse_version('0.0.0') == (0, 0, 0, None, None)
    assert sv.parse_version('1.2.3-rc.1') == (1, 2, 3, 'rc.1', None)
    assert sv.parse_version('1.2.3+build.5') == (1, 2, 3, None, 'build.5')
    assert sv.parse_version('10.20.30-alpha-2.x-y') == (10, 20, 30, 'alpha-2.x-y', None)

@pytest.mark.parametrize('bad', ['01.2.3', '1.02.3', '1.2', 'v1.2.3', '1.2.3.4',
                                 '1.2.3-', '1.2.3-a..b', '1.2.3+', 'a.b.c', '', '1.2.3 '])
def test_parse_refuses_invalid(bad):
    with pytest.raises(sv.SemverError) as e:
        sv.parse_version(bad)
    assert e.value.code == 'E_VERSION_PARSE'

def test_parse_component_bound_nn1():
    assert sv.parse_version(f'{sv.MAX_COMPONENT}.0.0')[0] == sv.MAX_COMPONENT  # N ok
    with pytest.raises(sv.SemverError) as e:
        sv.parse_version(f'{sv.MAX_COMPONENT + 1}.0.0')  # N+1 refused
    assert e.value.code == 'E_VERSION_PARSE'

# ---- identical -> no-public-change -> patch ----
def test_identical_is_no_public_change_patch():
    o = diff()
    assert o['diff'] == 'no-public-change' and o['next_version'] == '1.2.4' and o['bump'] == 'patch'
    assert o['symbol_changes'] == [{'name': 'f', 'change': 'identical', 'details': []}]
    assert o['counts'] == {'removed': 0, 'added': 0, 'modified_breaking': 0, 'modified_additive': 0, 'identical': 1}
    assert o['label_conflicts'] == [] and o['human_review_required'] is True
    assert o['scope'] == 'declared-api-shapes-only'

def test_empty_snapshots_no_public_change():
    o = diff(base=snap(), cand=snap())
    assert o['diff'] == 'no-public-change' and o['next_version'] == '1.2.4' and o['symbol_changes'] == []

# ---- additive -> minor ----
def test_new_symbol_additive():
    o = diff(cand=snap(sym('f', [pos('a'), kw('b')], 'int'), sym('g', [], 'str')))
    assert o['diff'] == 'additive' and o['next_version'] == '1.3.0' and o['bump'] == 'minor'

def test_optional_keyword_added_additive():
    o = diff(cand=snap(sym('f', [pos('a'), kw('b'), kw('c', required=False, type='str')], 'int')))
    assert o['diff'] == 'additive' and o['next_version'] == '1.3.0'
    ch = o['symbol_changes'][0]
    assert ch['change'] == 'modified-additive' and ch['details'] == ['param-added-optional:c']

def test_optional_positional_appended_additive():
    o = diff(cand=snap(sym('f', [pos('a'), pos('z', required=False), kw('b')], 'int')))
    assert o['diff'] == 'additive' and o['symbol_changes'][0]['details'] == ['param-added-optional:z']

def test_param_made_optional_additive():
    o = diff(cand=snap(sym('f', [pos('a', required=False), kw('b')], 'int')))
    assert o['diff'] == 'additive' and o['symbol_changes'][0]['details'] == ['param-made-optional:a']

def test_baseline_empty_all_added():
    o = diff(base=snap(), cand=snap(sym('g', [], 'str')))
    assert o['diff'] == 'additive' and o['symbol_changes'] == [{'name': 'g', 'change': 'added', 'details': ['symbol-added']}]

# ---- breaking -> major, never patch ----
BREAKING_CASES = {
    'symbol-removed': (BASE, snap()),
    'param-removed': (BASE, snap(sym('f', [kw('b')], 'int'))),
    'required-keyword-added': (BASE, snap(sym('f', [pos('a'), kw('b'), kw('c', required=True)], 'int'))),
    'required-positional-appended': (BASE, snap(sym('f', [pos('a'), pos('z', required=True), kw('b')], 'int'))),
    'param-type-changed': (BASE, snap(sym('f', [pos('a', type='str'), kw('b')], 'int'))),
    'param-made-required': (BASE, snap(sym('f', [pos('a'), kw('b', required=True)], 'int'))),
    'return-type-changed': (BASE, snap(sym('f', [pos('a'), kw('b')], 'str'))),
    'positional-reordered': (snap(sym('f', [pos('a'), pos('c')], 'int')), snap(sym('f', [pos('c'), pos('a')], 'int'))),
    'positional-renamed': (BASE, snap(sym('f', [pos('zzz'), kw('b')], 'int'))),
    'kind-changed-pos-to-kw': (snap(sym('f', [pos('a')], 'int')), snap(sym('f', [kw('a', required=True)], 'int'))),
    'positional-inserted-middle': (snap(sym('f', [pos('a'), pos('c')], 'int')), snap(sym('f', [pos('a'), pos('x', required=False), pos('c')], 'int'))),
}

@pytest.mark.parametrize('case', sorted(BREAKING_CASES))
def test_breaking_is_major_never_patch(case):
    base, cand = BREAKING_CASES[case]
    o = diff(base=base, cand=cand)
    assert o['diff'] == 'breaking' and o['bump'] == 'major' and o['next_version'] == '2.0.0'
    assert o['next_version'] != '1.2.4'  # NO patch recommendation for a breaking diff

def test_breaking_detail_strings():
    base, cand = BREAKING_CASES['param-type-changed']
    o = diff(base=base, cand=cand)
    assert o['symbol_changes'][0]['change'] == 'modified-breaking'
    assert o['symbol_changes'][0]['details'] == ['param-type-changed:a']
    base, cand = BREAKING_CASES['symbol-removed']
    o = diff(base=base, cand=cand)
    assert o['symbol_changes'] == [{'name': 'f', 'change': 'removed', 'details': ['symbol-removed']}]

def test_breaking_plus_additive_is_breaking():
    o = diff(base=snap(sym('f', [pos('a')], 'int'), sym('g', [], 'int')),
             cand=snap(sym('f', [pos('a'), kw('n', required=False)], 'int')))
    assert o['diff'] == 'breaking' and o['next_version'] == '2.0.0'  # g removed dominates f's additive change

# ---- prerelease / development treatment, declared ----
def test_prerelease_development_line_core_bump():
    o = diff(cur='2.0.0-rc.1', cand=snap(sym('f', [pos('a'), kw('b'), kw('c')], 'int')))
    assert o['stable_core'] == '2.0.0' and o['prerelease_treatment'] == 'development-line-core-bump'
    assert o['diff'] == 'additive' and o['next_version'] == '2.1.0'  # stable core bump, no prerelease managed

def test_prerelease_breaking_bumps_from_core():
    o = diff(cur='1.2.3-alpha', base=BASE, cand=snap())
    assert o['diff'] == 'breaking' and o['next_version'] == '2.0.0'

def test_zero_major_treated_identically():
    o = diff(cur='0.2.3', base=BASE, cand=snap())
    assert o['next_version'] == '1.0.0'  # no special 0.x semantics, exact arithmetic only
    o = diff(cur='0.2.3')
    assert o['next_version'] == '0.2.4'

# ---- caller labels are claims, never evidence ----
def test_label_breaking_on_identical_is_ignored_and_flagged():
    o = diff(labels={'overall': 'breaking'})
    assert o['diff'] == 'no-public-change' and o['next_version'] == '1.2.4'
    assert o['label_conflicts'] == ['caller-overall:breaking!=no-public-change']

def test_label_none_on_breaking_is_flagged():
    o = diff(base=BASE, cand=snap(), labels={'overall': 'none'})
    assert o['diff'] == 'breaking' and o['label_conflicts'] == ['caller-overall:none!=breaking']

def test_per_symbol_labels_checked_not_used():
    o = diff(base=snap(sym('f', [pos('a')], 'int'), sym('g', [], 'int')),
             cand=snap(sym('f', [pos('a'), kw('n')], 'int'), sym('g', [], 'int')),
             labels={'symbols': {'f': 'identical', 'g': 'additive'}})
    assert o['diff'] == 'additive'
    assert o['label_conflicts'] == ['symbol:f:label-identical!=modified-additive', 'symbol:g:label-additive!=identical']

def test_label_unknown_symbol_refused():
    with pytest.raises(sv.SemverError) as e:
        diff(labels={'symbols': {'nope': 'breaking'}})
    assert e.value.code == 'E_SCHEMA'

def test_label_bad_value_refused():
    with pytest.raises(sv.SemverError) as e:
        diff(labels={'overall': 'huge'})
    assert e.value.code == 'E_SCHEMA'

# ---- determinism, idempotence, order-independence ----
def test_idempotent_byte_identical():
    a, b = diff(), diff()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

def test_order_independence():
    base = snap(sym('a1', [pos('x')], 'int'), sym('b2', [], 'str'), sym('c3', [kw('k')], 'int'))
    cand = snap(sym('c3', [kw('k'), kw('k2')], 'int'), sym('a1', [pos('x')], 'int'), sym('d4', [], 'bool'))
    o1 = diff(base=base, cand=cand)
    o2 = diff(base=snap(*reversed(base['symbols'])), cand=snap(*reversed(cand['symbols'])))
    assert json.dumps(o1, sort_keys=True) == json.dumps(o2, sort_keys=True)
    names = [c['name'] for c in o1['symbol_changes']]
    assert names == sorted(names)

# ---- bounds N/N+1 on snapshots ----
def test_symbol_count_bound_nn1():
    many = snap(*[sym(f's{i}') for i in range(sv.MAX_SYMBOLS)])
    assert diff(base=many, cand=many)['diff'] == 'no-public-change'  # N ok
    too_many = snap(*[sym(f's{i}') for i in range(sv.MAX_SYMBOLS + 1)])
    with pytest.raises(sv.SemverError) as e:
        diff(base=too_many)  # N+1 refused
    assert e.value.code == 'E_SCHEMA'

def test_param_count_bound_nn1():
    ok = snap(sym('f', [kw(f'p{i}') for i in range(sv.MAX_PARAMS)], 'int'))
    assert diff(base=ok, cand=ok)['diff'] == 'no-public-change'  # N ok
    too = snap(sym('f', [kw(f'p{i}') for i in range(sv.MAX_PARAMS + 1)], 'int'))
    with pytest.raises(sv.SemverError) as e:
        diff(base=too)  # N+1 refused
    assert e.value.code == 'E_SCHEMA'

def test_name_length_bound_nn1():
    ok = snap(sym('n' * sv.MAX_NAME))
    assert diff(base=ok, cand=ok)['diff'] == 'no-public-change'  # N ok
    with pytest.raises(sv.SemverError) as e:
        diff(base=snap(sym('n' * (sv.MAX_NAME + 1))))  # N+1 refused
    assert e.value.code == 'E_SCHEMA'

# ---- schema refusals, exact core errors ----
@pytest.mark.parametrize('bad_snap', [
    {'symbols': [{'name': 'f', 'kind': 'function', 'signature': {'params': [pos('a'), pos('a')], 'returns': 'int'}}]},  # dup param name
    {'symbols': [sym('f'), sym('f')]},  # dup symbol name
    {'symbols': [{'name': 'f', 'kind': 'class', 'signature': {'params': [], 'returns': 'int'}}]},  # unknown kind
    {'symbols': [{'name': 'f', 'kind': 'function', 'signature': {'params': [{'name': 'a', 'kind': 'weird', 'required': True, 'type': 'int'}], 'returns': 'int'}}]},  # unknown param kind
    {'symbols': [{'name': 'f', 'kind': 'function', 'signature': {'params': [{'name': 'a', 'kind': 'positional', 'required': 'yes', 'type': 'int'}], 'returns': 'int'}}]},  # required not bool
    {'symbols': [{'name': 'f', 'kind': 'function', 'signature': {'params': [], 'returns': ''}}]},  # empty returns
    {'symbols': [{'name': '', 'kind': 'function', 'signature': {'params': [], 'returns': 'int'}}]},  # empty name
    {'symbols': 'notalist'},
    {'symbols': [], 'extra': 1},  # unknown top-level key
    [],
])
def test_schema_refusals(bad_snap):
    with pytest.raises(sv.SemverError) as e:
        diff(base=bad_snap)
    assert e.value.code == 'E_SCHEMA'

def test_bump_overflow_refused():
    with pytest.raises(sv.SemverError) as e:
        diff(cur=f'1.2.{sv.MAX_COMPONENT}')  # patch bump would exceed bound
    assert e.value.code == 'E_OVERFLOW'
    with pytest.raises(sv.SemverError) as e:
        diff(cur=f'1.{sv.MAX_COMPONENT}.0', cand=snap(sym('f', [pos('a'), kw('b'), kw('c')], 'int')))
    assert e.value.code == 'E_OVERFLOW'
    with pytest.raises(sv.SemverError) as e:
        diff(cur=f'{sv.MAX_COMPONENT}.0.0', base=BASE, cand=snap())
    assert e.value.code == 'E_OVERFLOW'

# ---- exhaustive small-signature table ----
def test_exhaustive_small_signatures():
    b = snap(sym('f', [pos('a'), kw('b')], 'int'))
    table = [
        (snap(sym('f', [pos('a'), kw('b')], 'int')), 'no-public-change'),
        (snap(sym('f', [pos('a'), kw('b'), kw('c')], 'int')), 'additive'),
        (snap(sym('f', [pos('a'), kw('b'), kw('c', required=True)], 'int')), 'breaking'),
        (snap(sym('f', [pos('a'), pos('z', required=False), kw('b')], 'int')), 'additive'),
        (snap(sym('f', [pos('a'), pos('z', required=True), kw('b')], 'int')), 'breaking'),
        (snap(sym('f', [pos('a', required=False), kw('b')], 'int')), 'additive'),
        (snap(sym('f', [pos('a'), kw('b', required=True)], 'int')), 'breaking'),
        (snap(sym('f', [pos('a', type='float'), kw('b')], 'int')), 'breaking'),
        (snap(sym('f', [pos('a'), kw('b', type='float')], 'int')), 'breaking'),
        (snap(sym('f', [pos('a'), kw('b')], 'float')), 'breaking'),
        (snap(sym('f', [kw('b')], 'int')), 'breaking'),
        (snap(sym('f', [pos('a')], 'int')), 'breaking'),
        (snap(sym('f', [pos('a'), kw('b')], 'int'), sym('g', [], 'int')), 'additive'),
        (snap(), 'breaking'),
    ]
    for cand, expected in table:
        got = diff(base=b, cand=cand)['diff']
        assert got == expected, f'{cand} -> {got}, want {expected}'

# ---- wiring adapter shape (for the integrator's separate patch) ----
def test_analyze_adapter_shape():
    o = sv.analyze({'current_version': '1.2.3', 'baseline_snapshot': BASE, 'candidate_snapshot': snap()})
    assert o['bump'] == 'major' and o['next_version'] == '2.0.0' and o['current_version'] == '1.2.3'
    assert o['diff'] == 'breaking' and o['human_review_required'] is True
