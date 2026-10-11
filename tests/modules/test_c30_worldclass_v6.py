"""V6 / c30.worldclass - world-class benchmark board (supplied numbers only)."""
import copy
import json
import pytest
from app.modules.c30 import worldclass


def run(rid, benchmark, metric, hib, value, rdate='2026-10-10'):
    return {'benchmark': benchmark, 'metric': metric,
            'higher_is_better': hib, 'value': value, 'run_id': rid,
            'run_date': rdate}


def baseline(benchmark, metric, name, value, url, rdate='2026-09-01'):
    return {'benchmark': benchmark, 'metric': metric, 'name': name,
            'value': value, 'source_url': url, 'reported_date': rdate}


RUNS = [
    run('r1', 'b1', 'accuracy', True, 0.82),
    run('r2', 'b1', 'accuracy', True, 0.80),
    run('r3', 'b2', 'latency', False, 120.0),
    run('r4', 'b2', 'latency', False, 95.0),
    run('r5', 'b3', 'coverage', True, 0.9),
    run('r6', 'b4', 'f1', True, 0.7),
    run('r7', 'b1', 'accuracy', True, 0.75),
    run('r8', 'b5', 'robustness', True, 0.5),
    run('r9', 'b6', 'winrate', True, 0.55),
    run('r10', 'b7', 'cost', False, 3.0),
]

BASELINES = [
    baseline('b1', 'accuracy', 'Grok', 0.80, 'https://grok.example/b1'),
    baseline('b1', 'accuracy', 'Muse', 0.70, 'https://muse.example/b1'),
    baseline('b2', 'latency', 'Instinct', 100.0, 'https://inst.example/b2'),
    baseline('b2', 'latency', 'Grok', 90.0, ''),
    baseline('b3', 'coverage', 'Muse', 0.85, 'http://muse.example/b3'),
    baseline('b5', 'robustness', 'Grok', 0.5, 'https://grok.example/b5'),
    baseline('b6', 'winrate', 'Muse', 0.0, 'https://muse.example/b6'),
    baseline('b1', 'accuracy', 'Instinct', 0.81, 'https://inst.example/b1',
             '2026-12-01'),
    baseline('b7', 'cost', 'Grok', 4.0, 'https://grok.example/b7',
             '2026-10-11'),
    baseline('b8', 'memory', 'Muse', 0.6, 'https://muse.example/b8'),
    baseline('b1', 'accuracy', 'Claude', 0.83, 'https://claude.example'),
    baseline('b2', 'latency', 'GPT', 80.0, 'https://user:pass@gpt.example/x'),
]


def request(runs=None, baselines=None):
    return {'as_of': '2026-10-11',
            'runs': copy.deepcopy(RUNS) if runs is None else runs,
            'baselines': copy.deepcopy(BASELINES)
            if baselines is None else baselines}


def refuse(req, message):
    with pytest.raises(ValueError) as ei:
        worldclass.run(req)
    assert str(ei.value) == message


def test_happy_path_counts_exact():
    out = worldclass.run(request())
    assert out['counts'] == {'ahead': 7, 'behind': 5, 'tied': 2,
                             'no_baseline': 2, 'no_source': 3}
    assert len(out['pairs']) == 14
    assert len(out['no_baseline_rows']) == 2


def test_pair_row_exact():
    out = worldclass.run(request())
    p = out['pairs'][0]
    assert p == {'benchmark': 'b1', 'metric': 'accuracy', 'run_id': 'r1',
                 'baseline_name': 'Grok', 'value': 0.82,
                 'baseline_value': 0.80, 'margin': 0.02,
                 'relative_margin': 0.025, 'flags': [], 'verdict': 'ahead',
                 'source_url': 'https://grok.example/b1',
                 'run_date': '2026-10-10', 'reported_date': '2026-09-01'}


def test_tie_verdicts():
    out = worldclass.run(request())
    by = {(p['run_id'], p['baseline_name']): p for p in out['pairs']}
    assert by[('r2', 'Grok')]['verdict'] == 'tied'
    assert by[('r2', 'Grok')]['margin'] == 0.0
    assert by[('r8', 'Grok')]['verdict'] == 'tied'
    assert by[('r2', 'Muse')]['verdict'] == 'ahead'
    assert by[('r2', 'Claude')]['verdict'] == 'behind'


def test_verdict_on_unrounded_margin():
    req = request([run('r1', 'b', 'm', True, 0.8000000005)],
                  [baseline('b', 'm', 'X', 0.8, 'https://x.example')])
    p = worldclass.run(req)['pairs'][0]
    assert p['margin'] == 0.0  # display rounded to 6 places
    assert p['verdict'] == 'tied'  # unrounded margin 5e-10 < 1e-9


def test_lower_is_better_direction():
    out = worldclass.run(request())
    by = {(p['run_id'], p['baseline_name']): p for p in out['pairs']}
    assert by[('r3', 'Instinct')]['verdict'] == 'behind'
    assert by[('r3', 'Instinct')]['margin'] == -20.0
    assert by[('r4', 'Instinct')]['verdict'] == 'ahead'
    assert by[('r10', 'Grok')]['verdict'] == 'ahead'
    assert by[('r10', 'Grok')]['margin'] == 1.0


def test_zero_baseline_flag_and_null_relative():
    out = worldclass.run(request())
    p = next(p for p in out['pairs'] if p['run_id'] == 'r9')
    assert p['relative_margin'] is None
    assert p['flags'] == ['baseline_zero']
    assert p['verdict'] == 'ahead'


def test_no_source_drops_blank_http_userinfo():
    out = worldclass.run(request())
    assert out['counts']['no_source'] == 3
    paired = {(p['benchmark'], p['metric'], p['baseline_name'])
              for p in out['pairs']}
    assert ('b2', 'latency', 'Grok') not in paired  # blank url
    assert ('b3', 'coverage', 'Muse') not in paired  # http
    assert ('b2', 'latency', 'GPT') not in paired  # userinfo


def test_future_date_dropped_equal_day_kept():
    out = worldclass.run(request())
    names = {p['baseline_name'] for p in out['pairs']
             if p['benchmark'] == 'b1'}
    assert 'Instinct' not in names  # 2026-12-01 > as_of
    by = {p['baseline_name']: p for p in out['pairs'] if p['run_id'] == 'r10'}
    assert 'Grok' in by  # reported_date == as_of kept


def test_no_baseline_rows_raw_value_only():
    out = worldclass.run(request())
    rows = {r['run_id']: r for r in out['no_baseline_rows']}
    assert rows['r5'] == {'benchmark': 'b3', 'metric': 'coverage',
                          'run_id': 'r5', 'value': 0.9}
    assert rows['r6'] == {'benchmark': 'b4', 'metric': 'f1',
                          'run_id': 'r6', 'value': 0.7}


def test_unmeasured_when_zero_pairs():
    req = request([run('r1', 'b', 'm', True, 0.5)],
                  [baseline('b', 'm', 'X', 0.4, '')])
    refuse(req, 'PLAN_REFUSED_UNMEASURED')


def test_forbidden_key_precedence_and_normalization():
    refuse(request(), None) if False else None
    req = request()
    req['password'] = 'x'
    req['send'] = 'y'
    refuse(req, 'PLAN_REFUSED_SEND:send')
    req = request()
    req['runs'][0]['approval-token'] = 1
    refuse(req, 'PLAN_REFUSED_SEND:approval_token')
    req = request()
    req['baselines'][0]['nested'] = {'card_number': '4'}
    refuse(req, 'PLAN_REFUSED_SPEND:card_number')
    req = request()
    req['runs'][0]['tags'] = [{'publish': True}]
    refuse(req, 'PLAN_REFUSED_EFFECT:publish')
    req = request()
    req['api_key'] = 'k'
    refuse(req, 'PLAN_REFUSED_NOCREDS:api_key')
    req = request()
    req['sender'] = 1
    req['approval_token'] = 2
    refuse(req, 'PLAN_REFUSED_SEND:approval_token')


def test_non_str_dict_key():
    refuse({1: 2}, 'PLAN_REFUSED_BAD_TYPE:key')


def test_unknown_keys_named_by_parent():
    req = request()
    req['zzz'] = 1
    refuse(req, 'PLAN_REFUSED_UNKNOWN:request')
    req = request()
    req['runs'][0]['zzz'] = 1
    refuse(req, 'PLAN_REFUSED_UNKNOWN:runs')
    req = request()
    req['baselines'][0]['zzz'] = 1
    refuse(req, 'PLAN_REFUSED_UNKNOWN:baselines')


def test_caps_oversize_before_clean_text():
    req = request([run(f'r{i}', 'b', 'm', True, 0.1) for i in range(501)],
                  [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_OVERSIZE:runs')
    req = request([run('r1', 'x' * 201, 'm', True, 0.1)],
                  [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_OVERSIZE:benchmark')
    req = request([run('r1', 'b', 'm', True, 0.1)],
                  [baseline('b', 'm', 'X', 0.1, 'https://' + 'x' * 2001)])
    refuse(req, 'PLAN_REFUSED_OVERSIZE:source_url')
    req = request([], [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_EMPTY:runs')


def test_value_type_rules():
    for bad in (True, '0.8', None, float('nan'), float('inf')):
        refuse(request([run('r1', 'b', 'm', True, bad)],
                       [baseline('b', 'm', 'X', 0.1, 'https://x.example')]),
               'PLAN_REFUSED_BAD_TYPE:runs')
    refuse(request([run('r1', 'b', 'm', True, 0.5)],
                   [baseline('b', 'm', 'X', 'x', 'https://x.example')]),
           'PLAN_REFUSED_BAD_TYPE:baselines')


def test_higher_is_better_must_be_bool():
    refuse(request([run('r1', 'b', 'm', 1, 0.5)],
                   [baseline('b', 'm', 'X', 0.1, 'https://x.example')]),
           'PLAN_REFUSED_BAD_TYPE:runs')


def test_duplicate_ids_refused():
    refuse(request([run('r1', 'b', 'm', True, 0.5),
                    run('r1', 'c', 'm', True, 0.6)],
                   [baseline('b', 'm', 'X', 0.1, 'https://x.example')]),
           'PLAN_REFUSED_BAD_TYPE:runs')
    refuse(request([run('r1', 'b', 'm', True, 0.5)],
                   [baseline('b', 'm', 'X', 0.1, 'https://x.example'),
                    baseline('b', 'm', 'X', 0.2, 'https://y.example')]),
           'PLAN_REFUSED_BAD_TYPE:baselines')


def test_dates_strict_real_calendar():
    for field in ('as_of', 'run_date', 'reported_date'):
        req = request([run('r1', 'b', 'm', True, 0.5)],
                      [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
        if field == 'as_of':
            req['as_of'] = '2026-02-30'
        elif field == 'run_date':
            req['runs'][0]['run_date'] = '2026-02-30'
        else:
            req['baselines'][0]['reported_date'] = '2026-02-30'
        refuse(req, 'PLAN_REFUSED_BAD_TYPE:%s' % field)
    req = request([run('r1', 'b', 'm', True, 0.5, '2026-12-01')],
                  [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:run_date')


def test_source_url_non_str_refused_blank_is_drop():
    req = request([run('r1', 'b', 'm', True, 0.5)],
                  [baseline('b', 'm', 'X', 0.1, 42)])
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:baselines')
    for blank in (None, '', '   '):
        out = worldclass.run(request(
            [run('r1', 'b', 'm', True, 0.5)],
            [baseline('b', 'm', 'X', 0.1, blank),
             baseline('b', 'm', 'Y', 0.2, 'https://y.example')]))
        assert out['counts']['no_source'] == 1
        assert len(out['pairs']) == 1


def test_url_gate_https_host_required():
    for bad in ('http://x.example', 'ftp://x.example', '//x.example',
                'https://', 'https://user@x.example', 'not a url'):
        out = worldclass.run(request(
            [run('r1', 'b', 'm', True, 0.5)],
            [baseline('b', 'm', 'X', 0.1, bad),
             baseline('b', 'm', 'Y', 0.2, 'https://y.example')]))
        assert out['counts']['no_source'] == 1
        assert len(out['pairs']) == 1
    out = worldclass.run(request(
        [run('r1', 'b', 'm', True, 0.5)],
        [baseline('b', 'm', 'X', 0.1, 'HTTPS://X.EXAMPLE:8443/p?q=1#f')]))
    assert out['counts']['no_source'] == 0
    assert out['pairs'][0]['source_url'] == 'HTTPS://X.EXAMPLE:8443/p?q=1#f'


def test_top_level_types():
    refuse(None, 'PLAN_REFUSED_BAD_TYPE:request')
    refuse([], 'PLAN_REFUSED_BAD_TYPE:request')
    req = request()
    req['as_of'] = '10/11/2026'
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:as_of')
    req = request()
    req['runs'] = 'x'
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:runs')
    req = request()
    req['baselines'] = None
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:baselines')


def test_determinism_byte_identical():
    a = worldclass.run(request())
    b = worldclass.run(request())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_scope_and_no_effect_surface():
    out = worldclass.run(request())
    assert out['scope']['data_source'] == 'supplied-unverified'
    assert out['scope']['as_of'] == '2026-10-11'
    public = {n for n in dir(worldclass) if not n.startswith('_')
              and callable(getattr(worldclass, n))
              and getattr(getattr(worldclass, n), '__module__', '')
              == worldclass.__name__}
    assert public == {'run'}


def test_margin_above_epsilon_verdict_ahead():
    # Kills epsilon-widening and rounded-verdict mutants: unrounded margin
    # 5e-8 is > 1e-9 (ahead) but rounds to 0.0 for display.
    req = request([run('r1', 'b', 'm', True, 0.80000005)],
                  [baseline('b', 'm', 'X', 0.8, 'https://x.example')])
    p = worldclass.run(req)['pairs'][0]
    assert p['verdict'] == 'ahead'
    assert p['margin'] == 0.0


def test_pairing_exact_case_sensitive():
    req = request([run('r1', 'B1', 'M', True, 0.5)],
                  [baseline('b1', 'm', 'X', 0.4, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_UNMEASURED')


def test_pairing_requires_metric_match():
    req = request([run('r1', 'b', 'accuracy', True, 0.5)],
                  [baseline('b', 'latency', 'X', 0.4, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_UNMEASURED')


def test_relative_margin_uses_abs_for_negative_baseline():
    req = request([run('r1', 'b', 'm', True, 0.4)],
                  [baseline('b', 'm', 'X', -0.5, 'https://x.example')])
    p = worldclass.run(req)['pairs'][0]
    assert p['margin'] == 0.9
    assert p['relative_margin'] == 1.8


def test_margin_rounded_six_places():
    req = request([run('r1', 'b', 'm', True, 0.923456789)],
                  [baseline('b', 'm', 'X', 0.8, 'https://x.example')])
    p = worldclass.run(req)['pairs'][0]
    assert p['margin'] == 0.123457


def test_forbidden_key_casefolded():
    req = request()
    req['SEND'] = 1
    refuse(req, 'PLAN_REFUSED_SEND:send')


# ---- Runtime 1: baseline coverage ----

def test_baseline_coverage_exact_and_invariant():
    out = worldclass.run(request())
    cov = out['baseline_coverage']
    assert cov == {'baselines_supplied': 12, 'baselines_matched': 7,
                   'baselines_unmatched': 1,
                   'baselines_dropped_by_reason': {'no_source': 3,
                                                   'future_date': 1}}
    assert cov['baselines_supplied'] == (
        cov['baselines_matched'] + cov['baselines_unmatched']
        + sum(cov['baselines_dropped_by_reason'].values()))
    assert out['counts'] == {'ahead': 7, 'behind': 5, 'tied': 2,
                             'no_baseline': 2, 'no_source': 3}


def test_baseline_coverage_future_drop_no_refusal():
    req = request([run('r1', 'b', 'm', True, 0.5)],
                  [baseline('b', 'm', 'X', 0.4, 'https://x.example'),
                   baseline('b', 'n', 'Y', 0.4, 'https://y.example',
                            '2026-12-01')])
    out = worldclass.run(req)  # must not raise for the future baseline
    cov = out['baseline_coverage']
    assert cov['baselines_dropped_by_reason'] == {'no_source': 0,
                                                  'future_date': 1}
    assert cov['baselines_matched'] == 1 and cov['baselines_unmatched'] == 0
    # an all-future input still takes the existing UNMEASURED path
    refuse(request([run('r1', 'b', 'm', True, 0.5)],
                   [baseline('b', 'm', 'X', 0.4, 'https://x.example',
                             '2026-12-01')]), 'PLAN_REFUSED_UNMEASURED')


def test_baseline_coverage_all_matched():
    out = worldclass.run(request([run('r1', 'b', 'm', True, 0.5)],
                                 [baseline('b', 'm', 'X', 0.4,
                                           'https://x.example')]))
    assert out['baseline_coverage'] == {
        'baselines_supplied': 1, 'baselines_matched': 1,
        'baselines_unmatched': 0,
        'baselines_dropped_by_reason': {'no_source': 0, 'future_date': 0}}


# ---- Runtime 2: URL char gate and field Unicode refusal ----

def _with_baseline_url(url):
    return request([run('r1', 'b', 'm', True, 0.5)],
                   [baseline('b', 'm', 'X', 0.1, url),
                    baseline('b', 'm', 'Y', 0.2, 'https://y.example')])


def test_url_whitespace_control_format_chars_drop():
    for bad in ('https://a.org/a b', 'https://a.org/a\tb',
                'https://a.org/a\nb', 'https://a.org/a b',
                'https://a.org/a​b', 'https://a.org/a\x7fb'):
        out = worldclass.run(_with_baseline_url(bad))
        assert out['counts']['no_source'] == 1, repr(bad)


def test_url_percent_encoded_space_passes():
    out = worldclass.run(_with_baseline_url('https://a.org/a%20b'))
    assert out['counts']['no_source'] == 0


def test_field_unicode_refusal_field_only_code():
    for field in ('benchmark', 'metric', 'run_id'):
        req = request([run('r1', 'b', 'm', True, 0.5)],
                      [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
        req['runs'][0][field] = 'bad value​'
        refuse(req, 'PLAN_REFUSED_BAD_TYPE:%s' % field)
    req = request([run('r1', 'b', 'm', True, 0.5)],
                  [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    req['baselines'][0]['name'] = 'Gro​k'
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:name')
    req = request([run('r1', 'b', 'm', True, 0.5)],
                  [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    req['runs'][0]['benchmark'] = 'b\x7f'
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:benchmark')
    # cap first: oversize value with a bad char -> OVERSIZE, not BAD_TYPE
    req = request([run('r1', 'b', 'm', True, 0.5)],
                  [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    req['runs'][0]['benchmark'] = 'x' * 200 + ' '
    refuse(req, 'PLAN_REFUSED_OVERSIZE:benchmark')


# ---- Peer-pinned test groups ----

def test_caps_500_pass_501_oversize_runs_and_baselines():
    runs500 = [run(f'r{i}', 'b', 'm', True, 0.1) for i in range(500)]
    bl = [baseline('b', 'm', 'X', 0.1, 'https://x.example')]
    out = worldclass.run(request(runs500, bl))
    assert out['baseline_coverage']['baselines_matched'] == 1
    refuse(request(runs500 + [run('r500', 'b', 'm', True, 0.1)], bl),
           'PLAN_REFUSED_OVERSIZE:runs')
    bl500 = [baseline(f'b{i}', 'm', 'X', 0.1, 'https://x.example')
             for i in range(499)] + bl
    out = worldclass.run(request([run('r1', 'b', 'm', True, 0.1)], bl500))
    assert out['baseline_coverage']['baselines_supplied'] == 500
    bl501 = [baseline(f'b{i}', 'm', 'X', 0.1, 'https://x.example')
             for i in range(501)]
    refuse(request([run('r1', 'b', 'm', True, 0.1)], bl501),
           'PLAN_REFUSED_OVERSIZE:baselines')


def test_field_caps_200_pass_201_oversize():
    ok = 'x' * 200
    req = request([run(ok, ok, ok, True, 0.1)],
                  [baseline(ok, ok, ok, 0.1, 'https://x.example')])
    out = worldclass.run(req)
    assert out['pairs'][0]['benchmark'] == ok
    for field in ('benchmark', 'metric', 'run_id'):
        req = request([run('r1', 'b', 'm', True, 0.1)],
                      [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
        req['runs'][0][field] = 'x' * 201
        refuse(req, 'PLAN_REFUSED_OVERSIZE:%s' % field)
    req = request([run('r1', 'b', 'm', True, 0.1)],
                  [baseline('b', 'm', 'X' * 201, 0.1, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_OVERSIZE:name')


def test_url_cap_2000_pass_2001_oversize():
    ok = 'https://' + 'a' * 1992
    assert len(ok) == 2000
    out = worldclass.run(_with_baseline_url(ok))
    assert out['counts']['no_source'] == 0
    refuse(_with_baseline_url('https://' + 'a' * 1993),
           'PLAN_REFUSED_OVERSIZE:source_url')


def test_blank_fields_empty():
    for field in ('benchmark', 'metric', 'run_id'):
        req = request([run('r1', 'b', 'm', True, 0.1)],
                      [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
        req['runs'][0][field] = '   '
        refuse(req, 'PLAN_REFUSED_EMPTY:%s' % field)
    req = request([run('r1', 'b', 'm', True, 0.1)],
                  [baseline('b', 'm', ' ', 0.1, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_EMPTY:name')


def test_dates_non_str_and_basic_iso_refused():
    req = request([run('r1', 'b', 'm', True, 0.1, 20261010)],
                  [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:run_date')
    for field in ('as_of', 'run_date', 'reported_date'):
        req = request([run('r1', 'b', 'm', True, 0.1)],
                      [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
        if field == 'as_of':
            req['as_of'] = '20260301'
        elif field == 'run_date':
            req['runs'][0]['run_date'] = '20260301'
        else:
            req['baselines'][0]['reported_date'] = '20260301'
        refuse(req, 'PLAN_REFUSED_BAD_TYPE:%s' % field)


def test_non_str_benchmark_and_non_dict_entries():
    req = request([run('r1', 42, 'm', True, 0.1)],
                  [baseline('b', 'm', 'X', 0.1, 'https://x.example')])
    refuse(req, 'PLAN_REFUSED_BAD_TYPE:benchmark')
    refuse({'as_of': '2026-10-11', 'runs': [42],
            'baselines': [baseline('b', 'm', 'X', 0.1, 'https://x.example')]},
           'PLAN_REFUSED_BAD_TYPE:runs')
    refuse({'as_of': '2026-10-11', 'runs': [run('r1', 'b', 'm', True, 0.1)],
            'baselines': ['x']}, 'PLAN_REFUSED_BAD_TYPE:baselines')


def test_run_date_equal_as_of_accepted():
    out = worldclass.run(request([run('r1', 'b', 'm', True, 0.5, '2026-10-11')],
                                 [baseline('b', 'm', 'X', 0.4,
                                           'https://x.example')]))
    assert out['pairs'][0]['run_date'] == '2026-10-11'


def test_epsilon_boundary_tied_both_directions():
    for value in (1e-9, -1e-9):
        out = worldclass.run(request([run('r1', 'b', 'm', True, value)],
                                     [baseline('b', 'm', 'X', 0.0,
                                               'https://x.example')]))
        assert out['pairs'][0]['verdict'] == 'tied', value


def test_relative_margin_two_thirds():
    out = worldclass.run(request([run('r1', 'b', 'm', True, 1.0)],
                                 [baseline('b', 'm', 'X', 3.0,
                                           'https://x.example')]))
    p = out['pairs'][0]
    assert p['margin'] == -2.0
    assert p['relative_margin'] == -0.666667
    assert p['verdict'] == 'behind'


def test_unparseable_ipv6_url_drops_no_source():
    out = worldclass.run(_with_baseline_url('https://[::1/x'))
    assert out['counts']['no_source'] == 1


def test_url_password_only_userinfo_drops():
    out = worldclass.run(_with_baseline_url('https://:pw@a.org/x'))
    assert out['counts']['no_source'] == 1
    out = worldclass.run(_with_baseline_url('https://user:pw@a.org/x'))
    assert out['counts']['no_source'] == 1


def test_empty_baselines_list_refused():
    refuse({'as_of': '2026-10-11', 'runs': [run('r1', 'b', 'm', True, 0.5)],
            'baselines': []}, 'PLAN_REFUSED_EMPTY:baselines')


def test_benchmark_mismatch_metric_match_is_no_pair():
    out = worldclass.run(request([run('r1', 'b', 'm', True, 0.5),
                                  run('r2', 'other', 'm', True, 0.6)],
                                 [baseline('other', 'm', 'X', 0.1,
                                           'https://x.example')]))
    assert len(out['pairs']) == 1
    assert out['pairs'][0]['benchmark'] == 'other'
    assert [row['benchmark'] for row in out['no_baseline_rows']] == ['b']
    assert out['baseline_coverage']['baselines_unmatched'] == 0
    assert out['baseline_coverage']['baselines_matched'] == 1


def test_ord33_exclamation_is_ordinary_char():
    out = worldclass.run(request([run('r1', 'b!', 'm', True, 0.5)],
                                 [baseline('b!', 'm', 'X', 0.1,
                                           'https://a.org/a!b')]))
    assert out['counts']['no_source'] == 0
    assert len(out['pairs']) == 1


def test_cap_first_beats_blank_for_over_cap_blank():
    refuse(request([run('r1', ' ' * 250, 'm', True, 0.5)],
                   [baseline('b', 'm', 'X', 0.1, 'https://x.example')]),
           'PLAN_REFUSED_OVERSIZE:benchmark')


def test_zs_accepted_in_every_non_url_field():
    out = worldclass.run(request(
        [run('run 1', 'MMLU Pro', 'acc norm', True, 0.5)],
        [baseline('MMLU Pro', 'acc norm', 'Model X', 0.4,
                  'https://x.example')]))
    assert len(out['pairs']) == 1
    assert out['pairs'][0]['benchmark'] == 'MMLU Pro'
    assert out['pairs'][0]['run_id'] == 'run 1'
    # name='Model X' accepted: validation passed without refusal


def test_nbsp_accepted_in_every_non_url_field():
    out = worldclass.run(request(
        [run('run 1', 'MMLU Pro', 'acc norm', True, 0.5)],
        [baseline('MMLU Pro', 'acc norm', 'Model X', 0.4,
                  'https://x.example')]))
    assert len(out['pairs']) == 1
    assert out['pairs'][0]['benchmark'] == 'MMLU Pro'


def test_cc_cf_zl_zp_refused_in_non_url_fields():
    for bad in ('a\tb', 'a\nb', 'a b', 'a​b', 'a\x7fb'):
        refuse(request([run('r1', bad, 'm', True, 0.5)],
                       [baseline('b', 'm', 'X', 0.1, 'https://x.example')]),
               'PLAN_REFUSED_BAD_TYPE:benchmark')
        refuse(request([run('r1', 'b', bad, True, 0.5)],
                       [baseline('b', 'm', 'X', 0.1, 'https://x.example')]),
               'PLAN_REFUSED_BAD_TYPE:metric')
        refuse(request([run(bad, 'b', 'm', True, 0.5)],
                       [baseline('b', 'm', 'X', 0.1, 'https://x.example')]),
               'PLAN_REFUSED_BAD_TYPE:run_id')
        refuse(request([run('r1', 'b', 'm', True, 0.5)],
                       [baseline('b', 'm', bad, 0.1, 'https://x.example')]),
               'PLAN_REFUSED_BAD_TYPE:name')
    # refused value is never echoed
    try:
        worldclass.run(request([run('r1', 'a​b', 'm', True, 0.5)],
                               [baseline('b', 'm', 'X', 0.1,
                                         'https://x.example')]))
        raise AssertionError('should refuse')
    except ValueError as e:
        assert 'a​b' not in str(e)


def test_pairing_exact_no_space_collapse():
    out = worldclass.run(request(
        [run('r1', 'MMLU Pro', 'm', True, 0.5),
         run('r2', 'MMLU  Pro', 'm', True, 0.6)],
        [baseline('MMLU Pro', 'm', 'X', 0.4, 'https://x.example')]))
    assert len(out['pairs']) == 1
    assert out['pairs'][0]['run_id'] == 'r1'
    assert [row['run_id'] for row in out['no_baseline_rows']] == ['r2']


def test_url_tilde_accepted_and_pairs():
    out = worldclass.run(request([run('r1', 'b', 'm', True, 0.5)],
                                 [baseline('b', 'm', 'X', 0.4,
                                           'https://x.example/~u')]))
    assert out['counts']['no_source'] == 0
    assert len(out['pairs']) == 1
    assert out['pairs'][0]['source_url'] == 'https://x.example/~u'
    assert out['baseline_coverage']['baselines_matched'] == 1


def test_url_exclamation_accepted_and_pairs():
    out = worldclass.run(request([run('r1', 'b', 'm', True, 0.5)],
                                 [baseline('b', 'm', 'X', 0.4,
                                           'https://x.example/a!b')]))
    assert out['counts']['no_source'] == 0
    assert len(out['pairs']) == 1
