"""Row 700 semver diff: test-only pins (runtime unchanged).

Literal bounds (not the module constants), exact schema key sets, exact length
bounds on every text field, both directions of the required-flag comparison,
label validation, and exact summary counters. Targets ONLY
app.modules.m20_general_cognitive_worker.api_semver700."""
import pytest
from app.modules.m20_general_cognitive_worker import api_semver700 as sv

MAXC = 9007199254740991  # 2**53 - 1, written out so a changed constant cannot hide


def sym(name, params=(), returns='int'):
    return {'name': name, 'kind': 'function',
            'signature': {'params': [dict(p) for p in params], 'returns': returns}}

def pos(name, required=True, type='int'):
    return {'name': name, 'kind': 'positional', 'required': required, 'type': type}

def kw(name, required=False, type='int'):
    return {'name': name, 'kind': 'keyword', 'required': required, 'type': type}

def snap(*symbols):
    return {'symbols': list(symbols)}

def diff(cur='1.2.3', base=None, cand=None, labels=None):
    b = base if base is not None else snap(sym('f', [pos('a')]))
    c = cand if cand is not None else b
    return sv.diff_api_snapshots(cur, b, c, caller_labels=labels)

def refused(code, **kw_):
    with pytest.raises(sv.SemverError) as e:
        diff(**kw_)
    assert e.value.code == code
    return str(e.value)


# ---- literal constants ----
def test_constants_are_the_documented_literals():
    assert sv.MAX_COMPONENT == 9007199254740991 == 2**53 - 1
    assert sv.MAX_SYMBOLS == 1024
    assert sv.MAX_PARAMS == 64
    assert sv.MAX_NAME == 200


# ---- version component bound, each position, exact N and N+1 ----
@pytest.mark.parametrize('tmpl', ['{}.0.0', '0.{}.0', '0.0.{}'])
def test_version_component_exact_bound_each_position(tmpl):
    ok = tmpl.format(9007199254740991)
    assert sv.parse_version(ok)[:3] == tuple(int(x) for x in ok.split('.'))
    with pytest.raises(sv.SemverError) as e:
        sv.parse_version(tmpl.format(9007199254740992))
    assert e.value.code == 'E_VERSION_PARSE'
    with pytest.raises(sv.SemverError) as e:
        sv.parse_version(tmpl.format(99999999999999999999))
    assert e.value.code == 'E_VERSION_PARSE'

def test_version_bound_message_names_the_bound():
    with pytest.raises(sv.SemverError) as e:
        sv.parse_version('9007199254740992.0.0')
    assert '9007199254740992' in str(e.value) and '9007199254740991' in str(e.value)

def test_non_string_version_refused():
    for bad in (None, 1, 1.2, b'1.2.3', ['1.2.3']):
        with pytest.raises(sv.SemverError) as e:
            sv.parse_version(bad)
        assert e.value.code == 'E_VERSION_PARSE'

def test_bump_at_one_below_bound_is_accepted_and_reaches_bound():
    base = snap(sym('f', [pos('a')]))
    assert diff(cur=f'1.2.{MAXC - 1}')['next_version'] == f'1.2.{MAXC}'
    assert diff(cur=f'1.{MAXC - 1}.0', cand=snap(sym('f', [pos('a')]), sym('g')))['next_version'] == f'1.{MAXC}.0'
    assert diff(cur=f'{MAXC - 1}.0.0', base=base, cand=snap())['next_version'] == f'{MAXC}.0.0'

def test_bump_at_bound_refused_for_each_component():
    base = snap(sym('f', [pos('a')]))
    assert 'E_OVERFLOW' in refused('E_OVERFLOW', cur=f'0.0.{MAXC}')
    assert 'E_OVERFLOW' in refused('E_OVERFLOW', cur=f'0.{MAXC}.0', base=base, cand=snap(sym('f', [pos('a')]), sym('g')))
    assert 'E_OVERFLOW' in refused('E_OVERFLOW', cur=f'{MAXC}.0.0', base=base, cand=snap())

def test_bound_component_does_not_block_other_bumps():
    # a maxed MINOR does not stop a breaking (major) or patch bump, and so on
    base = snap(sym('f', [pos('a')]))
    assert diff(cur=f'1.{MAXC}.{MAXC}', base=base, cand=snap())['next_version'] == '2.0.0'
    assert diff(cur=f'{MAXC}.{MAXC}.4')['next_version'] == f'{MAXC}.{MAXC}.5'
    assert diff(cur=f'{MAXC}.4.{MAXC}', base=base, cand=snap(sym('f', [pos('a')]), sym('g')))['next_version'] == f'{MAXC}.5.0'


# ---- literal count and length bounds ----
def test_symbols_1024_accepted_1025_refused_both_sides():
    n = 1024
    many = snap(*[sym(f's{i}') for i in range(n)])
    o = diff(base=many, cand=many)
    assert o['counts']['identical'] == 1024
    over = snap(*[sym(f's{i}') for i in range(n + 1)])
    assert 'baseline symbols must be a list of 0..1024' in refused('E_SCHEMA', base=over, cand=many)
    assert 'candidate symbols must be a list of 0..1024' in refused('E_SCHEMA', base=many, cand=over)

def test_params_64_accepted_65_refused_both_sides():
    ok = snap(sym('f', [kw(f'p{i}') for i in range(64)]))
    assert diff(base=ok, cand=ok)['diff'] == 'no-public-change'
    over = snap(sym('f', [kw(f'p{i}') for i in range(65)]))
    assert 'baseline symbol' in refused('E_SCHEMA', base=over, cand=ok) and 'params must be a list of 0..64' in refused('E_SCHEMA', base=over, cand=ok)
    assert 'candidate symbol' in refused('E_SCHEMA', base=ok, cand=over)

def _text_field_cases():
    L = 'x' * 200
    return {
        'symbol-name': lambda s: snap(sym(s)),
        'param-name': lambda s: snap(sym('f', [pos(s)])),
        'param-type': lambda s: snap(sym('f', [pos('a', type=s)])),
        'returns': lambda s: snap(sym('f', [pos('a')], returns=s)),
    }

@pytest.mark.parametrize('field', ['symbol-name', 'param-name', 'param-type', 'returns'])
def test_text_field_length_1_and_200_accepted_201_and_empty_refused(field):
    mk = _text_field_cases()[field]
    for good in ('x', 'x' * 199, 'x' * 200):
        s = mk(good)
        assert diff(base=s, cand=s)['diff'] == 'no-public-change', (field, len(good))
    for bad in ('', 'x' * 201, 'x' * 1000):
        refused('E_SCHEMA', base=mk(bad), cand=mk('x'))
        refused('E_SCHEMA', base=mk('x'), cand=mk(bad))

@pytest.mark.parametrize('field', ['symbol-name', 'param-name', 'param-type', 'returns'])
def test_text_field_non_string_refused(field):
    mk = _text_field_cases()[field]
    for bad in (None, 5, ['x'], b'x'):
        refused('E_SCHEMA', base=mk(bad), cand=mk('x'))

def test_returns_length_error_message_mentions_200():
    m = refused('E_SCHEMA', base=snap(sym('f', returns='r' * 201)), cand=snap(sym('f')))
    assert 'returns must be a string of 1..200 chars' in m


# ---- exact schema key sets ----
def _sym_dict():
    return sym('f', [pos('a')])

@pytest.mark.parametrize('key', ['name', 'kind', 'signature'])
def test_symbol_exact_keys_missing_and_extra(key):
    s = _sym_dict(); del s[key]
    assert 'exactly name/kind/signature' in refused('E_SCHEMA', base={'symbols': [s]})
    s = _sym_dict(); s['extra'] = 1
    assert 'exactly name/kind/signature' in refused('E_SCHEMA', base={'symbols': [s]})
    s = _sym_dict(); s['extra'] = 1; del s[key]  # same size, wrong set
    refused('E_SCHEMA', base={'symbols': [s]})

@pytest.mark.parametrize('key', ['params', 'returns'])
def test_signature_exact_keys_missing_and_extra(key):
    s = _sym_dict(); del s['signature'][key]
    assert 'exactly params/returns' in refused('E_SCHEMA', base={'symbols': [s]})
    s = _sym_dict(); s['signature']['extra'] = 1
    assert 'exactly params/returns' in refused('E_SCHEMA', base={'symbols': [s]})
    s = _sym_dict(); s['signature']['extra'] = 1; del s['signature'][key]
    refused('E_SCHEMA', base={'symbols': [s]})

@pytest.mark.parametrize('key', ['name', 'kind', 'required', 'type'])
def test_param_exact_keys_missing_and_extra(key):
    s = _sym_dict(); del s['signature']['params'][0][key]
    assert 'exactly name/kind/required/type' in refused('E_SCHEMA', base={'symbols': [s]})
    s = _sym_dict(); s['signature']['params'][0]['extra'] = 1
    assert 'exactly name/kind/required/type' in refused('E_SCHEMA', base={'symbols': [s]})
    s = _sym_dict(); p = s['signature']['params'][0]; p['extra'] = 1; del p[key]
    refused('E_SCHEMA', base={'symbols': [s]})

def test_snapshot_exact_keys_and_types():
    assert 'exactly a symbols list' in refused('E_SCHEMA', base={})
    assert 'exactly a symbols list' in refused('E_SCHEMA', base={'symbols': [], 'extra': 1})
    assert 'exactly a symbols list' in refused('E_SCHEMA', base={'other': []})
    assert 'exactly a symbols list' in refused('E_SCHEMA', base=['symbols'])
    with pytest.raises(sv.SemverError) as e:
        sv.diff_api_snapshots('1.2.3', None, snap())
    assert e.value.code == 'E_SCHEMA' and 'exactly a symbols list' in str(e.value)
    refused('E_SCHEMA', base={'symbols': ()})
    refused('E_SCHEMA', cand={'symbols': 'x'})

def test_symbol_and_param_must_be_objects():
    refused('E_SCHEMA', base={'symbols': ['f']})
    refused('E_SCHEMA', base={'symbols': [['name', 'kind', 'signature']]})
    s = _sym_dict(); s['signature']['params'] = ['a']
    refused('E_SCHEMA', base={'symbols': [s]})
    s = _sym_dict(); s['signature']['params'] = ('x',)
    refused('E_SCHEMA', base={'symbols': [s]})

def test_required_must_be_real_bool_not_int():
    for bad in (1, 0, None, 'true'):
        s = _sym_dict(); s['signature']['params'][0]['required'] = bad
        refused('E_SCHEMA', base={'symbols': [s]})


# ---- required-flag comparison, both directions, positional and keyword ----
@pytest.mark.parametrize('maker', [pos, kw])
def test_made_optional_is_additive_minor(maker):
    o = diff(base=snap(sym('f', [maker('x', required=True)])), cand=snap(sym('f', [maker('x', required=False)])))
    assert o['diff'] == 'additive' and o['bump'] == 'minor' and o['next_version'] == '1.3.0'
    assert o['symbol_changes'] == [{'name': 'f', 'change': 'modified-additive', 'details': ['param-made-optional:x']}]

@pytest.mark.parametrize('maker', [pos, kw])
def test_made_required_is_breaking_major(maker):
    o = diff(base=snap(sym('f', [maker('x', required=False)])), cand=snap(sym('f', [maker('x', required=True)])))
    assert o['diff'] == 'breaking' and o['bump'] == 'major' and o['next_version'] == '2.0.0'
    assert o['symbol_changes'] == [{'name': 'f', 'change': 'modified-breaking', 'details': ['param-made-required:x']}]

@pytest.mark.parametrize('maker', [pos, kw])
@pytest.mark.parametrize('flag', [True, False])
def test_unchanged_required_flag_is_identical(maker, flag):
    s = snap(sym('f', [maker('x', required=flag)]))
    o = diff(base=s, cand=s)
    assert o['diff'] == 'no-public-change' and o['symbol_changes'][0]['details'] == []

def test_made_optional_and_required_on_different_params_is_breaking_with_both_details():
    o = diff(base=snap(sym('f', [pos('a', True), pos('b', False)])), cand=snap(sym('f', [pos('a', False), pos('b', True)])))
    assert o['diff'] == 'breaking'
    assert o['symbol_changes'][0]['details'] == ['param-made-optional:a', 'param-made-required:b']

def test_type_change_alone_each_kind_names_the_param():
    assert diff(base=snap(sym('f', [pos('a')])), cand=snap(sym('f', [pos('a', type='str')])))['symbol_changes'][0]['details'] == ['param-type-changed:a']
    assert diff(base=snap(sym('f', [kw('k')])), cand=snap(sym('f', [kw('k', type='str')])))['symbol_changes'][0]['details'] == ['param-type-changed:k']


# ---- exact summary counters ----
def test_summary_counters_exact_with_distinct_numbers():
    base = snap(
        sym('rm1'), sym('rm2'),
        sym('mb1', [pos('a')]),
        sym('ma1', [pos('a', True)]), sym('ma2', [pos('a', True)]), sym('ma3', [pos('a', True)]), sym('ma4', [pos('a', True)]),
        *[sym(f'id{i}') for i in range(5)])
    cand = snap(
        sym('add1'), sym('add2'), sym('add3'),
        sym('mb1', [pos('a', type='str')]),
        sym('ma1', [pos('a', False)]), sym('ma2', [pos('a', False)]), sym('ma3', [pos('a', False)]), sym('ma4', [pos('a', False)]),
        *[sym(f'id{i}') for i in range(5)])
    o = diff(base=base, cand=cand)
    assert o['counts'] == {'removed': 2, 'added': 3, 'modified_breaking': 1, 'modified_additive': 4, 'identical': 5}
    assert sum(o['counts'].values()) == len(o['symbol_changes']) == 15
    by = {}
    for c in o['symbol_changes']:
        by.setdefault(c['change'], []).append(c['name'])
    assert by == {'removed': ['rm1', 'rm2'], 'added': ['add1', 'add2', 'add3'], 'modified-breaking': ['mb1'],
                  'modified-additive': ['ma1', 'ma2', 'ma3', 'ma4'], 'identical': [f'id{i}' for i in range(5)]}
    assert o['diff'] == 'breaking' and o['next_version'] == '2.0.0'

def test_counter_keys_are_exactly_these_five():
    assert sorted(diff()['counts']) == ['added', 'identical', 'modified_additive', 'modified_breaking', 'removed']

def test_each_single_class_moves_only_its_own_counter():
    z = {'removed': 0, 'added': 0, 'modified_breaking': 0, 'modified_additive': 0, 'identical': 0}
    a = snap(sym('f', [pos('a')]))
    cases = [
        ('removed', a, snap()),
        ('added', snap(), a),
        ('modified_breaking', a, snap(sym('f', [pos('a', type='str')]))),
        ('modified_additive', a, snap(sym('f', [pos('a'), kw('o')]))),
        ('identical', a, a)]
    for key, b, c in cases:
        assert diff(base=b, cand=c)['counts'] == dict(z, **{key: 1}), key


# ---- caller labels: validation and conflicts ----
@pytest.mark.parametrize('bad', [['overall'], ['overall', 'symbols'], ('overall',), 'overall', 5, True])
def test_labels_wrong_type_refused(bad):
    assert 'only carry overall/symbols' in refused('E_SCHEMA', labels=bad)

@pytest.mark.parametrize('bad', [{'extra': 1}, {'overall': 'none', 'extra': 1}, {'symbols': {}, 'extra': 1}, {'overall': 'none', 'symbols': {}, 'x': 1}])
def test_labels_extra_key_refused(bad):
    assert 'only carry overall/symbols' in refused('E_SCHEMA', labels=bad)

@pytest.mark.parametrize('ok', [None, {}, {'overall': 'none'}, {'symbols': {}}, {'overall': None}, {'symbols': None}, {'overall': 'none', 'symbols': {}}])
def test_labels_missing_keys_or_none_accepted(ok):
    assert diff(labels=ok)['label_conflicts'] == []
    assert diff(labels=ok)['diff'] == 'no-public-change'

def test_labels_empty_dict_has_no_conflicts_and_none_overall_matches_no_change():
    assert diff(labels={})['label_conflicts'] == []
    assert diff(labels={'overall': 'none'})['label_conflicts'] == []

def test_labels_symbols_must_be_object_and_overall_known():
    assert 'symbols must be an object' in refused('E_SCHEMA', labels={'symbols': ['f']})
    refused('E_SCHEMA', labels={'symbols': 'f'})
    assert 'unknown overall label' in refused('E_SCHEMA', labels={'overall': 'major'})
    assert 'unknown overall label' in refused('E_SCHEMA', labels={'overall': 'no-public-change'})
    assert 'unknown symbol label' in refused('E_SCHEMA', labels={'symbols': {'f': 'major'}})
    assert 'unknown symbol label' in refused('E_SCHEMA', labels={'symbols': {'f': 'none'}})
    assert 'unknown symbol' in refused('E_SCHEMA', labels={'symbols': {'zzz': 'identical'}})

def test_overall_label_conflict_text_for_each_level():
    a = snap(sym('f', [pos('a')]))
    levels = {
        'breaking': (a, snap()),
        'additive': (a, snap(sym('f', [pos('a')]), sym('g'))),
        'no-public-change': (a, a)}
    want = {'breaking': 'breaking', 'additive': 'additive', 'no-public-change': 'none'}
    for level, (b, c) in levels.items():
        for lab in ('breaking', 'additive', 'none'):
            o = diff(base=b, cand=c, labels={'overall': lab})
            assert o['diff'] == level
            exp = [] if lab == want[level] else [f'caller-overall:{lab}!={level}']
            assert o['label_conflicts'] == exp, (level, lab)

def test_symbol_label_conflicts_for_each_class_and_label():
    a = sym('a', [pos('p')])
    base = snap(a, sym('rm'), sym('mb', [pos('p')]), sym('ma', [pos('p', True)]), sym('same'))
    cand = snap(a, sym('add'), sym('mb', [pos('p', type='str')]), sym('ma', [pos('p', False)]), sym('same'))
    cls = {'a': 'identical', 'rm': 'removed', 'add': 'added', 'mb': 'modified-breaking', 'ma': 'modified-additive', 'same': 'identical'}
    lab_of = {'removed': 'breaking', 'modified-breaking': 'breaking', 'added': 'additive', 'modified-additive': 'additive', 'identical': 'identical'}
    for name, c in cls.items():
        for lab in ('breaking', 'additive', 'identical'):
            o = diff(base=base, cand=cand, labels={'symbols': {name: lab}})
            exp = [] if lab_of[c] == lab else [f'symbol:{name}:label-{lab}!={c}']
            assert o['label_conflicts'] == exp, (name, lab)

def test_conflicts_are_sorted_and_labels_never_change_classification():
    base = snap(sym('b'), sym('a'))
    cand = snap(sym('b'))
    plain = diff(base=base, cand=cand)
    o = diff(base=base, cand=cand, labels={'overall': 'none', 'symbols': {'b': 'breaking', 'a': 'additive'}})
    assert o['label_conflicts'] == sorted(o['label_conflicts'])
    assert o['label_conflicts'] == ['caller-overall:none!=breaking', 'symbol:a:label-additive!=removed', 'symbol:b:label-breaking!=identical']
    for k in ('diff', 'bump', 'next_version', 'symbol_changes', 'counts'):
        assert o[k] == plain[k]


# ---- analyze() adapter ----
def _payload():
    a = snap(sym('f', [pos('a')]))
    return {'current_version': '1.2.3', 'baseline_snapshot': a, 'candidate_snapshot': snap(sym('f', [pos('a')]), sym('g'))}

@pytest.mark.parametrize('bad', [None, [], 'x', 5, (1,), [('current_version', '1.2.3')]])
def test_analyze_non_object_refused_with_schema_code(bad):
    with pytest.raises(sv.SemverError) as e:
        sv.analyze(bad)
    assert e.value.code == 'E_SCHEMA' and 'payload must be an object' in str(e.value)

@pytest.mark.parametrize('key', ['current_version', 'baseline_snapshot', 'candidate_snapshot'])
def test_analyze_each_missing_field_refused_by_name(key):
    d = _payload(); del d[key]
    with pytest.raises(sv.SemverError) as e:
        sv.analyze(d)
    assert e.value.code == 'E_SCHEMA' and f'missing field {key}' in str(e.value)

def test_analyze_equals_diff_and_passes_labels_through():
    d = _payload()
    assert sv.analyze(d) == sv.diff_api_snapshots(d['current_version'], d['baseline_snapshot'], d['candidate_snapshot'])
    d['caller_labels'] = {'overall': 'breaking'}
    o = sv.analyze(d)
    assert o['label_conflicts'] == ['caller-overall:breaking!=additive']
    assert o['next_version'] == '1.3.0'

def test_analyze_does_not_accept_extra_payload_keys_as_labels():
    d = _payload(); d['labels'] = {'overall': 'breaking'}
    assert sv.analyze(d)['label_conflicts'] == []
