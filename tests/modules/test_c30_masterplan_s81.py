import copy
import json
import pytest
from app.modules.c30 import masterplan as m


def section(i='s1', **kw):
    x=dict(id=i,heading='Heading',source_ref='supplied-ref',body='original body')
    x.update(kw);return x


def volume(i='v1', sections=None, **kw):
    x=dict(id=i,title='Volume',sections=[section()] if sections is None else sections)
    x.update(kw);return x


def request(volumes=None, **kw):
    x=dict(as_of='2026-10-11',volumes=[volume()] if volumes is None else volumes)
    x.update(kw);return x


def refuses(x,code):
    with pytest.raises(ValueError) as e:m.run(x)
    assert str(e.value).startswith('PLAN_REFUSED_'+code)


def test_three_volumes_unfilled_and_repetition():
    x=request([volume('v1'),volume('v2',[section('s2',body='')]),volume('v3',[section('s3',body='a'*800)])])
    r=m.run(x)
    assert r['unfilled_count']==1 and r['excluded_count']==1
    assert '[UNFILLED: Heading]' in r['volumes'][1]['markdown']
    assert '[EXCLUDED_REPETITION: Heading]' in r['volumes'][2]['markdown']
    assert 'a'*800 not in r['volumes'][2]['markdown']
    assert r['accepted_body_chars']==len('original body')
    assert [v['id'] for v in r['volumes']]==['v1','v2','v3']
    assert [s['section_id'] for s in r['table_of_contents']]==['s1','s2','s3']


@pytest.mark.parametrize('n,expected',[(1,1),(2999,1),(3000,1),(3001,2),(6000,2)])
def test_estimate_boundaries(n,expected):
    # Unicode code points make each sampled window unique without repetition.
    body=''.join(chr(0x10000+i) for i in range(n))
    r=m.run(request([volume(sections=[section(body='  '+body+'\n')])],target_pages=4))
    assert r['estimated_text_pages']==expected and r['estimate_basis_chars']==3000
    assert r['accepted_body_chars']==n and r['estimated_shortfall']==max(0,4-expected)
    assert r['target_estimated_text_pages']==4
    assert 'target_pages' not in r and 'measured_pages' not in r


def test_internal_whitespace_raw_for_count():
    r=m.run(request([volume(sections=[section(body='  a    b  ')])]))
    assert r['accepted_body_chars']==6


@pytest.mark.parametrize('changes',[{'body':''},{'body':'  '},{'source_ref':''},{'source_ref':'  '}])
def test_unfilled_and_all_unsourced(changes):
    refuses(request([volume(sections=[section(**changes)])]),'UNSOURCED')
    r=m.run(request([volume(sections=[section(),section('s2',**changes)])]))
    assert r['unfilled_count']==1 and r['section_receipts'][1]['status']=='unfilled'


def test_missing_body_or_source_is_unfilled():
    s=section('s2');del s['body'];r=m.run(request([volume(sections=[section(),s])]))
    assert r['unfilled_count']==1
    del s['source_ref'];assert m.run(request([volume(sections=[section(),s])]))['unfilled_count']==1


@pytest.mark.parametrize('field',['body','heading','source_ref'])
@pytest.mark.parametrize('value',[None,False,3,[]])
def test_nonstring_fields(field,value):refuses(request([volume(sections=[section(**{field:value})])]),'BAD_TYPE')


def test_cross_section_repetition_four_not_three():
    b=''.join(chr(0x10000+i) for i in range(200))
    ss=[section('s'+str(i),body=b) for i in range(3)]
    assert m.run(request([volume(sections=ss)]))['excluded_count']==0
    ss.append(section('s3',body=b));ss.append(section('safe',body='distinct body'))
    r=m.run(request([volume(sections=ss)]));assert r['excluded_count']==4
    assert r['accepted_body_chars']==len('distinct body')


def test_unsourced_does_not_pollute_repetition():
    b='z'*200
    ss=[section(),section('s2',body=b)]+[section('u'+str(i),body=b,source_ref='') for i in range(4)]
    r=m.run(request([volume(sections=ss)]));assert r['excluded_count']==0 and r['unfilled_count']==4


def test_whitespace_collapse_for_repetition_only():
    b=' '.join(str(i) for i in range(100))
    ss=[section(str(i),body=b.replace(' ', '  ' if i%2 else '\n')) for i in range(4)]+[section('safe')]
    assert m.run(request([volume(sections=ss)]))['excluded_count']==4


def test_repetition_full_windows_only():
    r=m.run(request([volume(sections=[section(body='a'*199)])]))
    assert r['excluded_count']==0


def test_all_excluded_refuses():refuses(request([volume(sections=[section(body='a'*800)])]),'UNSOURCED')


def test_unique_ids_global():
    refuses(request([volume('v1'),volume('v2')]),'BAD_TYPE:section_id')
    refuses(request([volume('v1'),volume('v1',[section('s2')])]),'BAD_TYPE:volume_id')


@pytest.mark.parametrize('volumes',[[],[volume(sections=[])]])
def test_no_sections(volumes):refuses(request(volumes),'NOSECTIONS')


@pytest.mark.parametrize('target',[False,0,-1,100001,'5000',1.1])
def test_target_type(target):refuses(request(target_pages=target),'BAD_TYPE')


def test_target_exceeds_cap_and_no_fulfillment():
    r=m.run(request(target_pages=5001))
    assert r['target_exceeds_cap'] is True
    assert r['target_estimated_text_pages']==5001
    assert m.run(request(target_pages=5000))['target_exceeds_cap'] is False
    assert '5,000' in r['estimate_limit'] and 'rendered' in r['estimate_limit']


def test_oversize():refuses(request([volume(sections=[section(body='x'*15000001)])]),'BAD_TYPE:oversize')


def test_copy_order_refs_scope_determinism():
    x=request([volume('z',[section('b',source_ref='verbatim ref'),section('a')])]);before=copy.deepcopy(x)
    r=m.run(x);assert x==before
    assert r==m.run(x) and json.dumps(r,sort_keys=True)==json.dumps(m.run(x),sort_keys=True)
    assert r['section_receipts'][0]['source_ref']=='verbatim ref'
    assert all(s['evidence_verified'] is False for s in r['section_receipts'])
    assert [s['section_id'] for s in r['table_of_contents']]==['b','a']
    assert set(r['scope'])=={'implemented','not_implemented','data_source','as_of'}


@pytest.mark.parametrize('extra',[{'network':False},{'target_estimated_text_pages':5000}])
def test_unknown_request_keys(extra):refuses(request(**extra),'BAD_TYPE')


def test_heading_line_break_refused():refuses(request([volume(sections=[section(heading='forged\nheading')])]),'CONTROL_CHARS')


def test_public_surface():
    import ast
    from pathlib import Path
    tree=ast.parse(Path(m.__file__).read_text())
    assert [n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and not n.name.startswith('_')]==['run']


def test_exact_markdown_order():
    r=m.run(request([volume(sections=[section('b',heading='First',body='body one'),section('a',heading='Second',body='body two')])]))
    assert r['volumes'][0]['markdown']=='# Volume\n\n## First\n\nbody one\n\n## Second\n\nbody two\n'


def test_shortfall_never_negative():
    body=''.join(chr(0x10000+i) for i in range(3001))
    r=m.run(request([volume(sections=[section(body=body)])],target_pages=1))
    assert r['estimated_text_pages']==2 and r['estimated_shortfall']==0


def test_repetition_at_offset50_not100():
    shared=''.join(chr(0x10000+i) for i in range(200))
    ss=[section(str(i),body=chr(0x11000+i)*50+shared) for i in range(4)]+[section('safe')]
    r=m.run(request([volume(sections=ss)]));assert r['excluded_count']==4


# ---- test-only pins for the peer's S8.1 mutation survivors (core masterplan.py unchanged) ----
def uni(n, base=0x10000):
    return ''.join(chr(base + i) for i in range(n))


def refusal(x):
    with pytest.raises(ValueError) as e:m.run(x)
    return str(e.value)


# 1. blank / whitespace-only metadata is an exact EMPTY refusal; body and source_ref may be blank
@pytest.mark.parametrize('blank',['','   ','\u00a0'])
def test_blank_metadata_exact_empty_refusal(blank):
    assert refusal(request(as_of=blank))=='PLAN_REFUSED_EMPTY:as_of'
    assert refusal(request([volume(i=blank)]))=='PLAN_REFUSED_EMPTY:volume_id'
    assert refusal(request([volume(title=blank)]))=='PLAN_REFUSED_EMPTY:title'
    assert refusal(request([volume(sections=[section(i=blank)])]))=='PLAN_REFUSED_EMPTY:section_id'
    assert refusal(request([volume(sections=[section(heading=blank)])]))=='PLAN_REFUSED_EMPTY:heading'


def test_blank_body_and_source_ref_are_not_refused():
    r=m.run(request([volume(sections=[section(),section('s2',body='',source_ref='')])]))
    assert r['unfilled_count']==1


# 2. non-body text: 1000 accepted, 1001 refused (body has its own 15,000,000 cap)
def _long(field,n):
    r=request()
    if field=='as_of':r['as_of']='a'*n
    elif field=='volume_id':r['volumes'][0]['id']='a'*n
    elif field=='title':r['volumes'][0]['title']='a'*n
    elif field=='section_id':r['volumes'][0]['sections'][0]['id']='a'*n
    elif field=='heading':r['volumes'][0]['sections'][0]['heading']='a'*n
    elif field=='source_ref':r['volumes'][0]['sections'][0]['source_ref']='a'*n
    return r


@pytest.mark.parametrize('field',['as_of','volume_id','title','section_id','heading','source_ref'])
def test_non_body_text_1000_ok_1001_refused(field):
    assert m.run(_long(field,1000))['section_receipts'][0]['status']=='accepted'
    assert refusal(_long(field,1001))=='PLAN_REFUSED_TEXT_TOO_LONG:'+field
    assert refusal(_long(field,999+2))=='PLAN_REFUSED_TEXT_TOO_LONG:'+field
    assert m.run(_long(field,999))['accepted_body_chars']==len('original body')


# 3. repetition window: exactly 200 code points, aligned at stride 50, last full window counts
def _four_plus_safe(bodies):
    return [section('r%d'%i,body=b) for i,b in enumerate(bodies)]+[section('safe',body='distinct body')]


def test_repetition_window_is_exactly_200_not_199_or_201():
    sh=uni(200)
    # share exactly 200 then a different 201st character: window 0 is shared -> excluded
    excl=m.run(request([volume(sections=_four_plus_safe([sh+chr(0x12000+i) for i in range(4)]))]))
    assert excl['excluded_count']==4
    # share only 199 then a different 200th character: no full 200 window is shared -> kept
    sh199=uni(199)
    kept=m.run(request([volume(sections=_four_plus_safe([sh199+chr(0x12000+i) for i in range(4)]))]))
    assert kept['excluded_count']==0 and kept['accepted_body_chars']==4*200+len('distinct body')


def test_repetition_body_of_199_or_exactly_200_code_points():
    b199=uni(199)
    r=m.run(request([volume(sections=_four_plus_safe([b199]*4))]))
    assert r['excluded_count']==0                      # no full window exists, four identical 199-char bodies stay
    b200=uni(200)
    r=m.run(request([volume(sections=_four_plus_safe([b200]*4))]))
    assert r['excluded_count']==4


def test_repetition_stride_includes_last_start_at_len_minus_200():
    sh=uni(200)
    for pre in (50,100,150):                       # shared run starts at the last stride start (len-200)
        bodies=[uni(pre,0x13000+i*0x400)+sh for i in range(4)]
        r=m.run(request([volume(sections=_four_plus_safe(bodies))]))
        assert r['excluded_count']==4,pre
    for pre in (49,51,99):                         # not stride aligned: never hashed together
        bodies=[uni(pre,0x13000+i*0x400)+sh for i in range(4)]
        r=m.run(request([volume(sections=_four_plus_safe(bodies))]))
        assert r['excluded_count']==0,pre


# 4. target_pages: default 5000 echoed, bounds 1..100000
def test_target_default_5000_echo_and_bounds():
    r=m.run(request())
    assert r['target_estimated_text_pages']==5000 and r['estimated_shortfall']==5000-r['estimated_text_pages']
    assert r['target_exceeds_cap'] is False
    assert m.run(request(target_pages=5000))['target_estimated_text_pages']==5000
    big=m.run(request(target_pages=100000))
    assert big['target_estimated_text_pages']==100000 and big['target_exceeds_cap'] is True
    assert big['estimated_shortfall']==100000-big['estimated_text_pages']
    assert m.run(request(target_pages=1))['target_estimated_text_pages']==1
    refuses(request(target_pages=100001),'BAD_TYPE:target_pages')
    refuses(request(target_pages=0),'BAD_TYPE:target_pages')


# 5. total body cap 15,000,000 across all sections and volumes, counted from 0
CAP=15000000


def test_total_body_cap_exact_accept_and_plus_one_refuse():
    r=m.run(request([volume(sections=[section('big',body='x'*(CAP-8)),section('s2',body='distinct')])]))
    assert r['excluded_count']==1 and r['accepted_body_chars']==8
    assert refusal(request([volume(sections=[section('big',body='x'*(CAP-8)),section('s2',body='distinct!')])]))=='PLAN_REFUSED_BAD_TYPE:oversize'
    one=m.run(request([volume(sections=[section('big',body='x'*(CAP-1)),section('s2',body='d')])]))
    assert one['accepted_body_chars']==1


def test_total_body_cap_counts_across_volumes():
    ok=request([volume('v1',[section('a',body='x'*(CAP//2))]),volume('v2',[section('b',body='y'*(CAP-CAP//2-8)),section('c',body='distinct')])])
    assert m.run(ok)['accepted_body_chars']==8
    bad=request([volume('v1',[section('a',body='x'*(CAP//2))]),volume('v2',[section('b',body='y'*(CAP-CAP//2+1))])])
    assert refusal(bad)=='PLAN_REFUSED_BAD_TYPE:oversize'


# 6. wrong container types are BAD_TYPE refusals, never TypeError/AttributeError
def test_list_volume_and_list_section_are_bad_type():
    assert refusal(request([['id','title','sections']]))=='PLAN_REFUSED_BAD_TYPE:volume'
    assert refusal(request([('id','title','sections')]))=='PLAN_REFUSED_BAD_TYPE:volume'
    assert refusal(request(['id']))=='PLAN_REFUSED_BAD_TYPE:volume'
    assert refusal(request([volume(sections=[['id','heading']])]))=='PLAN_REFUSED_BAD_TYPE:section'
    assert refusal(request([volume(sections=[['id']])]))=='PLAN_REFUSED_BAD_TYPE:section'
    assert refusal(request([volume(sections=[[]])]))=='PLAN_REFUSED_BAD_TYPE:section'
    assert refusal(request([volume(sections=['s1'])]))=='PLAN_REFUSED_BAD_TYPE:section'
    assert refusal(request([{'id':'v','title':'t'}]))=='PLAN_REFUSED_BAD_TYPE:volume'
    assert refusal(request([{'id':'v','title':'t','sections':[],'extra':1}]))=='PLAN_REFUSED_BAD_TYPE:volume'
    assert refusal(request([volume(sections=[dict(section(),extra=1)])]))=='PLAN_REFUSED_BAD_TYPE:section'


# 7. per-receipt accepted_body_chars: exact for accepted, 0 for unfilled and excluded
def test_receipt_accepted_chars_exact_per_status():
    rep=uni(200)
    ss=[section('ok',body='  '+'abc def'+'\n'),section('un',body=''),section('noref',body='nonblank',source_ref=' ')]
    ss+=[section('rep%d'%i,body=rep) for i in range(4)]
    r=m.run(request([volume(sections=ss)]))
    by={x['section_id']:x for x in r['section_receipts']}
    assert by['ok']['status']=='accepted' and by['ok']['accepted_body_chars']==len('abc def')
    assert by['un']['status']=='unfilled' and by['un']['accepted_body_chars']==0
    assert by['noref']['status']=='unfilled' and by['noref']['accepted_body_chars']==0
    for i in range(4):
        assert by['rep%d'%i]['status']=='excluded_repetition' and by['rep%d'%i]['accepted_body_chars']==0
    assert sum(x['accepted_body_chars'] for x in r['section_receipts'])==r['accepted_body_chars']==len('abc def')
