"""S4.1 / c35.sweep - competition sweeper dossier builder (PARKED)."""
import json
import pytest
from app.modules.c35 import sweep

PARKED_MSG = 'APPLY_REFUSED_PARKED'


def source(sid, kind, text, url=None, **extra):
    s = {'id': sid, 'kind': kind, 'text': text, 'url': url}
    s.update(extra)
    return s


STS_TEXT = ('Regeneron Science Talent Search\n'
            'Deadline: 2026-11-05 at 8pm ET\n'
            'Entry fee: free\n'
            'Open to grade 12 students in the United States\n'
            'Rules require original research reports\n'
            'Past winners include 2025 champion A. Example\n'
            'Judging criteria weigh creativity and rigor\n')

STS_TEXT_DUP = ('regeneron   science talent search\n'
                'deadline 2026-11-05\n'
                'Judging criteria also weigh clarity\n')

TEXTS = [
    ('s1', 'starred_mail', STS_TEXT, 'https://www.societyforscience.org/regeneron-sts/'),
    ('s2', 'social_save', STS_TEXT_DUP, None),
    ('s3', 'bookmark_doc', 'FIRST Robotics Competition\nKickoff January 9, 2027\n'
     'Team fee $35 per event\ngrades 9-12 may compete\n', None),
    ('s4', 'public_page', 'Local Essay Cup\nAn annual writing contest.\n', None),
    ('s5', 'public_page', 'Mystery Math Meet\nFinal round February 30, 2027\n', None),
    ('s6', 'starred_mail', 'Old Chess Open\nDeadline: 2026-01-15\nEntry fee USD 50\n'
     'Open to ages under 19\n', None),
    ('s7', 'public_page', 'Art Prize\nDeadline: 2027-03-01\nFee: USD 50\n', None),
    ('s8', 'bookmark_doc', 'Quiz League\nDeadline: 2027-05-05\nfree to enter\n', None),
    ('s9', 'social_save', 'Code Sprint\nDeadline: 2027-06-01\n', None),
    ('s10', 'starred_mail', 'Poetry Slam\nDeadline: 2026-10-11\n', None),
    ('s11', 'public_page', 'Debate Day\nDeadline: 2026-12-31\nWinners receive trophies\n', None),
    ('s12', 'bookmark_doc', 'Science Bowl\nDeadline: 2027-02-20\n'
     'Rules require teams of four\nJudging criteria include speed\n', None),
]


def request(texts=None):
    return {'as_of': '2026-10-11',
            'sources': [source(sid, kind, text, url) for sid, kind, text, url in
                        (texts or TEXTS)]}


def refuse(req, message):
    with pytest.raises(ValueError) as ei:
        sweep.build_dossiers(req)
    assert str(ei.value) == message


def test_run_always_refused_parked():
    with pytest.raises(ValueError) as ei:
        sweep.run(request())
    assert str(ei.value) == PARKED_MSG


def test_run_parked_first_even_for_garbage():
    for bad in (None, 42, [], {}, {'unparked': True}, {'sources': 'x'}):
        with pytest.raises(ValueError) as ei:
            sweep.run(bad)
        assert str(ei.value) == PARKED_MSG


def test_parked_constant_true():
    assert sweep.PARKED is True


def test_happy_path_coverage_exact():
    out = sweep.build_dossiers(request())
    assert out['coverage'] == {'sources_supplied': 12, 'with_deadline': 9,
                               'with_fee': 5, 'expired': 1}


def test_duplicate_merged_by_folded_title_and_deadline():
    out = sweep.build_dossiers(request())
    titles = [o['title'] for o in out['opportunities']]
    assert titles.count('Regeneron Science Talent Search') == 1
    sts = next(o for o in out['opportunities']
               if o['title'] == 'Regeneron Science Talent Search')
    assert sts['source_ids'] == ['s1', 's2']
    assert sts['deadline'] == '2026-11-05'
    assert sts['status'] == 'active'
    assert [l['source_id'] for l in sts['judging_criteria']] == ['s1', 's2']
    assert len(out['opportunities']) == 11


def test_no_deadline_flag():
    out = sweep.build_dossiers(request())
    cup = next(o for o in out['opportunities'] if o['title'] == 'Local Essay Cup')
    assert cup['deadline'] is None
    assert cup['flags'] == ['no_deadline']
    assert cup['status'] == 'undated'


def test_deadline_unparsed_flag():
    out = sweep.build_dossiers(request())
    meet = next(o for o in out['opportunities'] if o['title'] == 'Mystery Math Meet')
    assert meet['deadline'] is None
    assert meet['flags'] == ['deadline_unparsed']
    assert meet['status'] == 'undated'


def test_expired_status_and_equal_day_not_expired():
    out = sweep.build_dossiers(request())
    by_title = {o['title']: o for o in out['opportunities']}
    assert by_title['Old Chess Open']['status'] == 'expired'
    assert by_title['Poetry Slam']['deadline'] == '2026-10-11'
    assert by_title['Poetry Slam']['status'] == 'active'


def test_fee_formats_free_dollar_usd():
    out = sweep.build_dossiers(request())
    by_title = {o['title']: o for o in out['opportunities']}
    assert by_title['Regeneron Science Talent Search']['fee'] == 'free'
    assert by_title['FIRST Robotics Competition']['fee'] == '$35'
    assert by_title['Art Prize']['fee'] == 'USD 50'
    assert by_title['Quiz League']['fee'] == 'free'
    assert by_title['Old Chess Open']['fee'] == 'USD 50'
    assert by_title['Code Sprint']['fee'] is None


def test_verbatim_sections_and_offsets():
    out = sweep.build_dossiers(request())
    sts = next(o for o in out['opportunities']
               if o['title'] == 'Regeneron Science Talent Search')
    assert sts['rules'] == [
        {'source_id': 's1', 'offset': STS_TEXT.index('Rules require'),
         'text': 'Rules require original research reports'}]
    assert sts['past_winners'] == [
        {'source_id': 's1', 'offset': STS_TEXT.index('Past winners'),
         'text': 'Past winners include 2025 champion A. Example'}]
    assert sts['eligibility'] == [
        {'source_id': 's1', 'offset': STS_TEXT.index('Open to grade 12'),
         'text': 'Open to grade 12 students in the United States'}]
    bowl = next(o for o in out['opportunities'] if o['title'] == 'Science Bowl')
    assert bowl['past_winners'] == 'not_in_sources'


def test_submit_like_keys_refused():
    for key in ('submit', 'apply', 'password', 'token'):
        req = request([('s1', 'public_page', 'X\nDeadline: 2027-01-01\n', None)])
        req['sources'][0][key] = 'y'
        refuse(req, 'APPLY_REFUSED_SUBMIT')
    req = request([('s1', 'public_page', 'X\n', None)])
    req['sources'][0]['submission_url'] = 'https://x'
    refuse(req, 'APPLY_REFUSED_SUBMIT')


def test_private_kind_refused():
    req = request([('s1', 'private_third_party', 'X\n', None)])
    refuse(req, 'APPLY_REFUSED_PRIVATE')


def test_unknown_top_key_refused():
    req = request([('s1', 'public_page', 'X\n', None)])
    req['unparked'] = True
    refuse(req, 'APPLY_REFUSED_UNKNOWN:unparked')


def test_unknown_source_key_refused():
    req = request([('s1', 'public_page', 'X\n', None)])
    req['sources'][0]['note'] = 'hi'
    refuse(req, 'APPLY_REFUSED_UNKNOWN:note')


def test_bad_kind_refused():
    req = request([('s1', 'carrier_pigeon', 'X\n', None)])
    refuse(req, 'APPLY_REFUSED_BAD_TYPE:kind')


def test_sources_missing_empty_or_wrong_type():
    refuse({'as_of': '2026-10-11', 'sources': []}, 'APPLY_REFUSED_NOSOURCE')
    refuse({'as_of': '2026-10-11'}, 'APPLY_REFUSED_NOSOURCE')
    refuse({'as_of': '2026-10-11', 'sources': 'x'}, 'APPLY_REFUSED_NOSOURCE')


def test_request_not_dict():
    refuse(None, 'APPLY_REFUSED_BAD_TYPE:request')
    refuse([], 'APPLY_REFUSED_BAD_TYPE:request')


def test_oversize_source_count():
    texts = [(f's{i}', 'public_page', 'X\nDeadline: 2027-01-01\n', None)
             for i in range(201)]
    refuse(request(texts), 'APPLY_REFUSED_OVERSIZE')


def test_oversize_total_chars():
    texts = [('s1', 'public_page', 'x' * 190_000 + '\nDeadline: 2027-01-01\n', None)] * 11
    refuse(request(texts), 'APPLY_REFUSED_OVERSIZE')


def test_single_text_too_long_is_clean_text_refusal():
    req = request([('s1', 'public_page', 'x' * 200_001, None)])
    refuse(req, 'APPLY_REFUSED_TEXT_TOO_LONG:text')


def test_as_of_must_be_iso():
    req = request([('s1', 'public_page', 'X\n', None)])
    for bad in ('10/11/2026', '2026-1-1', '20261110', '2026-13-01', 7):
        req['as_of'] = bad
        refuse(req, 'APPLY_REFUSED_BAD_TYPE:as_of')


def test_non_dict_source_refused():
    refuse({'as_of': '2026-10-11', 'sources': ['x']},
           'APPLY_REFUSED_BAD_TYPE:source')


def test_determinism_byte_identical():
    a = sweep.build_dossiers(request())
    b = sweep.build_dossiers(request())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    titles = [o['title'] for o in a['opportunities']]
    assert titles == sorted(titles, key=lambda t: t.casefold())


def test_scope_block_and_no_effect_surface():
    out = sweep.build_dossiers(request())
    scope = out['scope']
    assert scope['data_source'] == 'supplied-text-only'
    assert scope['as_of'] == '2026-10-11'
    assert scope['implemented'] and scope['not_implemented']
    public = {n for n in dir(sweep) if not n.startswith('_')
              and callable(getattr(sweep, n))
              and getattr(getattr(sweep, n), '__module__', '') == sweep.__name__}
    assert public == {'run', 'build_dossiers'}
    with pytest.raises(ValueError):
        sweep.run(request())


# ---- repair pins (two runtime repair pins)

class _DictSub(dict):
    pass


class _ListSub(list):
    pass


def _req_with(sources_list):
    return {'as_of': '2026-10-11', 'sources': sources_list}


def test_request_dict_subclass_refused_exact_builtin():
    refuse(_DictSub(request()), 'APPLY_REFUSED_BAD_TYPE:request')


def test_sources_list_subclass_refused_exact_builtin():
    r = request()
    r['sources'] = _ListSub(r['sources'])
    refuse(r, 'APPLY_REFUSED_NOSOURCE')


def test_source_dict_subclass_refused_exact_builtin():
    r = request()
    r['sources'][0] = _DictSub(r['sources'][0])
    refuse(r, 'APPLY_REFUSED_BAD_TYPE:source')


def test_non_str_request_key_refused_cleanly():
    r = request()
    r[5] = 'x'
    refuse(r, 'APPLY_REFUSED_BAD_TYPE:key')


def test_non_str_source_key_refused_cleanly():
    r = request()
    r['sources'][0][5] = 'x'
    refuse(r, 'APPLY_REFUSED_BAD_TYPE:key')


# ---- boundary pins (boundary cases; doc LIMITS table values)

def test_max_sources_200_ok_201_refused():
    mk = lambda n: [source(f's{i}', 'public_page', f'Unique Title {i}\n') for i in range(n)]
    out = sweep.build_dossiers(_req_with(mk(200)))
    assert out['coverage']['sources_supplied'] == 200
    refuse(_req_with(mk(201)), 'APPLY_REFUSED_OVERSIZE')


def test_max_total_chars_boundary_across_sources():
    big = 't\n' + 'x' * 199_998          # exactly 200,000 chars per source
    ten = [source(f's{i}', 'public_page', big) for i in range(10)]
    out = sweep.build_dossiers(_req_with(ten))          # 2,000,000 total: ok
    assert out['coverage']['sources_supplied'] == 10
    refuse(_req_with(ten + [source('s10', 'public_page', 'x')]),
           'APPLY_REFUSED_OVERSIZE')                    # 2,000,001: refused


def test_max_text_chars_200000_ok_200001_refused():
    ok = 't\n' + 'x' * 199_998
    out = sweep.build_dossiers(_req_with([source('s1', 'public_page', ok)]))
    assert out['coverage']['sources_supplied'] == 1
    refuse(_req_with([source('s1', 'public_page', 't\n' + 'x' * 199_999)]),
           'APPLY_REFUSED_TEXT_TOO_LONG:text')


def test_id_128_ok_129_refused():
    out = sweep.build_dossiers(_req_with([source('i' * 128, 'public_page', 'T\n')]))
    assert out['coverage']['sources_supplied'] == 1
    refuse(_req_with([source('i' * 129, 'public_page', 'T\n')]),
           'APPLY_REFUSED_TEXT_TOO_LONG:id')


def test_url_512_ok_513_refused():
    out = sweep.build_dossiers(_req_with([source('s1', 'public_page', 'T\n', 'u' * 512)]))
    assert out['coverage']['sources_supplied'] == 1
    refuse(_req_with([source('s1', 'public_page', 'T\n', 'u' * 513)]),
           'APPLY_REFUSED_TEXT_TOO_LONG:url')


def test_title_200_ok_201_refused():
    out = sweep.build_dossiers(_req_with([source('s1', 'public_page', 't' * 200 + '\n')]))
    assert out['opportunities'][0]['title'] == 't' * 200
    refuse(_req_with([source('s1', 'public_page', 't' * 201 + '\n')]),
           'APPLY_REFUSED_TEXT_TOO_LONG:title')


# ---- behavior pins (merge / fee / sort survivors)

def test_same_title_different_deadlines_do_not_merge():
    a = 'Alpha Prize\nDeadline: 2027-01-01\n'
    b = 'alpha   prize\nDeadline: 2027-02-01\n'
    out = sweep.build_dossiers(_req_with([source('s1', 'public_page', a),
                                          source('s2', 'bookmark_doc', b)]))
    assert len(out['opportunities']) == 2
    assert [o['deadline'] for o in out['opportunities']] == ['2027-01-01', '2027-02-01']


def test_fee_first_wins_across_merged_sources():
    a = 'Beta Cup\nDeadline: 2027-01-01\nFee: USD 50\n'
    b = 'beta cup\nDeadline: 2027-01-01\nFee: USD 99\n'
    out = sweep.build_dossiers(_req_with([source('s1', 'public_page', a),
                                          source('s2', 'bookmark_doc', b)]))
    assert len(out['opportunities']) == 1
    assert out['opportunities'][0]['fee'] == 'USD 50'
    assert out['opportunities'][0]['source_ids'] == ['s1', 's2']


def test_final_sort_ties_break_by_deadline():
    a = 'Gamma Open\nDeadline: 2027-03-01\n'
    b = 'gamma   open\nDeadline: 2027-01-01\n'
    c = 'GAMMA OPEN\nDeadline: 2027-02-01\n'
    out = sweep.build_dossiers(_req_with([source('s1', 'public_page', a),
                                          source('s2', 'bookmark_doc', b),
                                          source('s3', 'social_save', c)]))
    assert [o['deadline'] for o in out['opportunities']] == ['2027-01-01', '2027-02-01', '2027-03-01']
