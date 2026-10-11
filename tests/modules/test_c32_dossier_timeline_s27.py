"""S2.7 delta tests first, isolated import of the additive module."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

P=Path(__file__).resolve().parents[2]/'backend/app/modules/c32/dossier_timeline.py'
spec=importlib.util.spec_from_file_location('app.modules.c32.dossier_timeline',P)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)


def src(text,url='https://source.example/1',**kw):return {'url':url,'text':text,**kw}
def req(sources=None,**kw):return {'subject':'Jane Doe','sources':sources or [src('Jane Doe founded Acme Labs in 2020.')],**kw}
def refuse(code,f):
    with pytest.raises(ValueError) as e:f()
    assert str(e.value)==code


def test_full_name_alias_and_partial_ambiguity():
    out=m.run(req([src('Jane Other founded Other Labs in 2019. Jane Doe founded Acme in 2020. J. Doe joined Acme in 2021.')],aliases=['J. Doe']))
    assert len(out['ambiguous_mentions'])==1
    assert out['ambiguous_mentions'][0]['sentence']=='Jane Other founded Other Labs in 2019.'
    assert [e['date'] for e in out['timeline']]==['2020','2021']
    assert 'Other Labs' not in str(out['dimensions'])


def test_name_word_boundaries_and_normalized_case():
    out=m.run(req([src('NotJane Doe founded Acme in 2001. JANE   DOE founded Beta in 2002.')]))
    assert len(out['timeline'])==1 and out['timeline'][0]['date']=='2002'


def test_alias_does_not_allow_bare_first_name_by_default():
    out=m.run(req([src('Jane founded Acme in 2000.')]))
    assert out['dimensions']=={} and out['timeline']==[]
    assert len(out['ambiguous_mentions'])==1


def test_three_sources_dedupe_and_corroboration():
    out=m.run(req([src('Jane Doe founded Acme in 2020.','https://s/1'),src('JANE DOE FOUNDED ACME IN 2020!','https://s/2'),src('Jane Doe   founded Acme in 2020?','https://s/3')]))
    fact=out['dimensions']['career'][0]
    assert len(out['dimensions']['career'])==1
    assert fact['corroborating_sources']=={'count':3,'urls':['https://s/1','https://s/2','https://s/3']}
    assert out['evidence_depth']['career']=={'fact_count':1,'corroborating_source_counts':[3],'distinct_source_count':3}


def test_same_url_is_not_independent_corroboration():
    out=m.run(req([src('Jane Doe founded Acme in 2020.')]*3))
    assert out['dimensions']['career'][0]['corroborating_sources']['count']==1


def test_conflict_no_winner_and_both_citations():
    out=m.run(req([src('Jane Doe founded Acme in 2020.','https://s/1'),src('Jane Doe founded Acme in 2021.','https://s/2')]))
    c=out['conflicts'][0]
    assert c['trigger']=='founded' and c['years']==[2020,2021]
    assert {url for f in c['facts'] for url in f['corroborating_sources']['urls']}=={'https://s/1','https://s/2'}
    assert c['status']=='unresolved' and 'winner' not in c


def test_timeline_order_iso_month_year_year_and_undated():
    out=m.run(req([src('Jane Doe joined Acme in 2022. Jane Doe was born on 2001-02-03. Jane Doe launched Acme in March 2020. Jane Doe received an award.')]))
    assert [e['date'] for e in out['timeline']]==['2001-02-03','2020-03','2022']
    assert [e['precision'] for e in out['timeline']]==['day','month','year']
    assert len(out['undated_sentences'])==1
    assert 'award' in out['undated_sentences'][0]['sentence']


def test_published_does_not_invent_event_date():
    out=m.run(req([src('Jane Doe founded Acme.',published='2026-09-01')]))
    assert out['timeline']==[] and len(out['undated_sentences'])==1


def test_invalid_calendar_date_not_recast_as_year():
    out=m.run(req([src('Jane Doe joined Acme on 2020-02-30.')]))
    assert out['timeline']==[]


def test_entity_links_full_names_not_partial():
    out=m.run(req(known_entities=[{'name':'Acme Labs','kind':'venture'},{'name':'Labs','kind':'event'},{'name':'Unknown','kind':'person'}]))
    assert {e['name'] for e in out['entity_links']}=={'Acme Labs','Labs'}
    assert all(e['fact_ids'] for e in out['entity_links'])


def test_cap_after_dedupe_ranks_corroboration_then_source_order():
    sources=[src(' '.join('Jane Doe founded Company%d in 2000.'%i for i in range(10)),'https://s/1')]
    sources +=[src('Jane Doe founded Company9 in 2000.','https://s/2'),src('JANE DOE FOUNDED COMPANY9 IN 2000!','https://s/3')]
    out=m.run(req(sources))
    facts=out['dimensions']['career']
    assert len(facts)==8 and 'Company9' in facts[0]['fact']
    assert ['Company%d'%i in f['fact'] for i,f in enumerate(facts[1:])]==[True]*7
    assert out['truncated_fact_count']>0


def test_scope_and_determinism_no_effect_functions():
    r=req(as_of='2026-10-11')
    out=m.run(r)
    assert out['completeness']==0.2 and out['source_count']==1
    assert out['scope']['as_of']=='2026-10-11'
    assert 'every-single-thing coverage' in out['scope']['not_implemented']
    assert json.dumps(out,sort_keys=True)==json.dumps(m.dossier_v2(r),sort_keys=True)
    assert not any(hasattr(m,n) for n in ('send','post','spend','trade','create_account','fetch'))
    assert 'every single thing' not in json.dumps(out).lower()


@pytest.mark.parametrize('aliases',[['x']*17,['J.\nDoe'],['']])
def test_alias_refusal(aliases):refuse('TREND_REFUSED_ALIAS',lambda:m.run(req(aliases=aliases)))


def test_private_and_unknown_effect_field():
    refuse('TREND_REFUSED_PRIVATE',lambda:m.run(req(include_private=True)))
    refuse('TREND_REFUSED_BAD_TYPE:request',lambda:m.run(req(action='scrape')))


@pytest.mark.parametrize('bad',[None,True,[],5])
def test_bad_request(bad):refuse('TREND_REFUSED_BAD_TYPE:request',lambda:m.run(bad))


def test_source_limit_and_controls():
    refuse('TREND_REFUSED_OVERSIZE',lambda:m.run(req([src('Jane Doe founded Acme.')]*129)))
    refuse('TREND_REFUSED_CONTROL_CHARS:text',lambda:m.run(req([src('Jane Doe\nwas born in 2000.')])) )
    refuse('TREND_REFUSED_BAD_TYPE:include_private',lambda:m.run(req(include_private='false')))


@pytest.mark.parametrize('kind',['venture','person','event'])
def test_entity_kinds(kind):assert m.run(req(known_entities=[{'name':'Acme Labs','kind':kind}]))['entity_links'][0]['kind']==kind


def test_guard_is_real_landed_policy(monkeypatch):
    from app.modules.c30 import policy
    assert m.policy is policy
    calls=[]
    original=policy.clean_text
    def tracking(*args,**kw):calls.append(args[2]);return original(*args,**kw)
    monkeypatch.setattr(policy,'clean_text',tracking)
    m.run(req(aliases=['J. Doe'],known_entities=[{'name':'Acme Labs','kind':'venture'}]))
    assert set(calls)=={'subject','alias','entity','as_of','url','text'}


def test_multiline_controls_remain_legacy_consistent():
    refuse('TREND_REFUSED_CONTROL_CHARS:subject',lambda:m.run(req(subject='Jane\nDoe')))


def test_source_url_metadata_not_authority():
    out=m.run(req([src('Jane Doe founded a company in 2020.',url='supplied-reference')]))
    assert out['dimensions']['career'][0]['source']=='supplied-reference'
    assert 'verified source truth' in out['scope']['not_implemented']


@pytest.mark.parametrize('data,code',[
    ({'subject':'Jane Doe','sources':[]},'TREND_REFUSED_EMPTY:sources'),
    ({'subject':'Jane Doe','sources':'x'},'TREND_REFUSED_BAD_TYPE:sources'),
    ({'subject':'Jane Doe','sources':[None]},'TREND_REFUSED_BAD_TYPE:source'),
    ({'subject':'Jane Doe','sources':[{'url':'u','text':'x','token':'secret'}]},'TREND_REFUSED_BAD_TYPE:source'),
    ({'subject':False,'sources':[src('x')]},'TREND_REFUSED_BAD_TYPE:subject'),
    ({'subject':'Jane Doe','sources':[src('x')],'known_entities':[{'name':'Acme','kind':'wrong'}]},'TREND_REFUSED_BAD_TYPE:known_entity'),
])
def test_extra_hygiene(data,code):refuse(code,lambda:m.run(data))


# ---- closing pins (repair): cap boundaries N / N+1
def _too_long(field,f):refuse('TREND_REFUSED_TEXT_TOO_LONG:'+field,f)


def test_subject_cap_128_accepted_129_refused():
    name='J'*128
    assert m.run({'subject':name,'sources':[src(name+' founded Acme in 2020.')]})['subject']==name
    _too_long('subject',lambda:m.run({'subject':'J'*129,'sources':[src('x')]}))


def test_alias_text_cap_128_accepted_129_refused():
    assert m.run(req(aliases=['A'*128]))['source_count']==1
    refuse('TREND_REFUSED_ALIAS',lambda:m.run(req(aliases=['A'*129])))


def test_alias_count_16_accepted_17_refused():
    assert m.run(req(aliases=['alias%d'%i for i in range(16)]))['source_count']==1
    refuse('TREND_REFUSED_ALIAS',lambda:m.run(req(aliases=['alias%d'%i for i in range(17)])))


def test_known_entities_count_128_accepted_129_refused():
    ents=lambda n:[{'name':'Entity%d'%i,'kind':'venture'} for i in range(n)]
    assert m.run(req(known_entities=ents(128)))['source_count']==1
    refuse('TREND_REFUSED_BAD_TYPE:known_entities',lambda:m.run(req(known_entities=ents(129))))
    refuse('TREND_REFUSED_BAD_TYPE:known_entities',lambda:m.run(req(known_entities='x')))
    refuse('TREND_REFUSED_BAD_TYPE:known_entities',lambda:m.run(req(known_entities=({'name':'A','kind':'person'},))))


def test_entity_name_cap_128_accepted_129_refused():
    assert m.run(req(known_entities=[{'name':'E'*128,'kind':'event'}]))['source_count']==1
    _too_long('entity',lambda:m.run(req(known_entities=[{'name':'E'*129,'kind':'event'}])))


def test_as_of_cap_128_accepted_129_refused():
    assert m.run(req(as_of='a'*128))['scope']['as_of']=='a'*128
    _too_long('as_of',lambda:m.run(req(as_of='a'*129)))


def test_source_count_128_accepted_129_refused():
    one=src('Jane Doe founded Acme in 2020.')
    assert m.run(req([dict(one) for _ in range(128)]))['source_count']==128
    refuse('TREND_REFUSED_OVERSIZE',lambda:m.run(req([dict(one) for _ in range(129)])))


def test_url_cap_512_accepted_513_refused():
    assert m.run(req([src('Jane Doe founded Acme in 2020.',url='u'*512)]))['source_count']==1
    _too_long('url',lambda:m.run(req([src('Jane Doe founded Acme in 2020.',url='u'*513)])))


def test_text_cap_200000_accepted_200001_refused():
    base='Jane Doe founded Acme in 2020.'
    ok=base+' '*(200000-len(base))
    assert len(ok)==200000 and m.run(req([src(ok)]))['source_count']==1
    _too_long('text',lambda:m.run(req([src(ok+' ')])))


def test_published_cap_64_accepted_65_refused():
    assert m.run(req([src('Jane Doe founded Acme in 2020.',published='p'*64)]))['source_count']==1
    _too_long('published',lambda:m.run(req([src('Jane Doe founded Acme in 2020.',published='p'*65)])))
    refuse('TREND_REFUSED_BAD_TYPE:published',lambda:m.run(req([src('x',published=5)])))


def test_tuple_sources_accepted_by_ruling_and_other_types_refused():
    out=m.run(req(tuple([src('Jane Doe founded Acme in 2020.')])))
    assert out['source_count']==1 and out['timeline'][0]['date']=='2020'
    refuse('TREND_REFUSED_BAD_TYPE:sources',lambda:m.run(req({'a':src('x')})))
    refuse('TREND_REFUSED_EMPTY:sources',lambda:m.run(req(())) if False else m.run({'subject':'Jane Doe','sources':()}))


# ---- entity record shape
@pytest.mark.parametrize('entity',[{'name':'Acme','kind':'venture','extra':1},{'name':'Acme'},{'kind':'venture'},
                                   {'name':'Acme','kind':'company'},{'name':'Acme','kind':None},'Acme',['Acme','venture'],None])
def test_entity_record_shape_refused(entity):
    refuse('TREND_REFUSED_BAD_TYPE:known_entity',lambda:m.run(req(known_entities=[entity])))


def test_entity_duplicates_collapse_to_one_link():
    out=m.run(req(known_entities=[{'name':'Acme','kind':'venture'},{'name':'Acme','kind':'venture'}]))
    assert len(out['entity_links'])==1


# ---- dates
@pytest.mark.parametrize('text,date_,prec',[
    ('Jane Doe founded Acme in March 2020.','2020-03','month'),
    ('Jane Doe founded Acme in Mar 2020.','2020-03','month'),
    ('Jane Doe founded Acme in May 2020.','2020-05','month'),
    ('Jane Doe founded Acme in Sep 2020.','2020-09','month'),
    ('Jane Doe founded Acme in December 2020.','2020-12','month'),
    ('Jane Doe founded Acme in JANUARY 2020.','2020-01','month'),
    ('Jane Doe founded Acme in 2020.','2020','year'),
    ('Jane Doe founded Acme on 2020-12-31.','2020-12-31','day'),
    ('Jane Doe founded Acme in 9999.','9999','year'),
    ('Jane Doe founded Acme in Dec 9999.','9999-12','month'),
])
def test_date_forms_values_and_precision(text,date_,prec):
    e=m.run(req([src(text)]))['timeline']
    assert [(x['date'],x['precision']) for x in e]==[(date_,prec)]


@pytest.mark.parametrize('text',['Jane Doe founded Acme in 0000.','Jane Doe founded Acme in Jan 0000.','Jane Doe founded Acme in 2020-13-01.',
                                 'Jane Doe founded Acme in 12020.'])
def test_invalid_or_boundary_dates_not_extracted(text):
    assert m.run(req([src(text)]))['timeline']==[]


def test_month_year_year_field_and_dedupe_of_same_stamp():
    out=m.run(req([src('Jane Doe founded Acme in March 2020 and March 2020.')]))
    assert [e['date'] for e in out['timeline']]==['2020-03']
    out=m.run(req([src('Jane Doe founded Acme in 2020, again 2020-01-01 and 2020.')]))
    assert [(e['date'],e['precision']) for e in out['timeline']]==[('2020','year'),('2020-01-01','day')]


# ---- truncation count exact
def test_truncated_fact_count_exact():
    src_text=' '.join('Jane Doe founded Company%d in 2000.'%i for i in range(10))
    out=m.run(req([src(src_text)]))
    # each sentence matches career ("founded") and ventures ("company"); each dimension keeps 8 of 10
    assert len(out['dimensions']['career'])==8 and len(out['dimensions']['ventures'])==8
    assert out['truncated_fact_count']==4
    assert out['unique_matched_sentence_count']==10
    assert m.run(req([src(' '.join('Jane Doe founded Company%d in 2000.'%i for i in range(8)))]))['truncated_fact_count']==0


# ---- conflict gate boundaries
def test_conflict_ignores_undated_candidates_exactly():
    out=m.run(req([src('Jane Doe founded Acme in 2020.','https://s/1'),src('Jane Doe founded Beta in 2021.','https://s/2'),
                   src('Jane Doe founded Gamma.','https://s/3')]))
    assert len(out['conflicts'])==1
    assert [f['fact'] for f in out['conflicts'][0]['facts']]==['Jane Doe founded Acme in 2020.','Jane Doe founded Beta in 2021.']
    assert out['conflicts'][0]['years']==[2020,2021]


def test_conflict_needs_two_facts_and_two_years():
    assert m.run(req([src('Jane Doe founded Acme in 2020 and Beta in 2021.')]))['conflicts']==[]  # one fact, two years
    assert m.run(req([src('Jane Doe founded Acme in 2020.','https://s/1'),src('Jane Doe founded Beta in 2020.','https://s/2')]))['conflicts']==[]  # two facts, one year
    assert m.run(req([src('Jane Doe founded Acme in 2020.')]))['conflicts']==[]
    assert m.run(req([src('Jane Doe founded Acme.','https://s/1'),src('Jane Doe founded Beta.','https://s/2')]))['conflicts']==[]
    two=m.run(req([src('Jane Doe founded Acme in 2020.','https://s/1'),src('Jane Doe founded Beta in 2021.','https://s/2')]))
    assert len(two['conflicts'])==1


def test_conflict_per_trigger_independent_and_word_boundary():
    out=m.run(req([src('Jane Doe founded Acme in 2020. Jane Doe joined Beta in 2021.')]))
    assert out['conflicts']==[]  # different triggers never pair
    out=m.run(req([src('Jane Doe was born in 1980.','https://s/1'),src('Jane Doe was born in 1981.','https://s/2')]))
    assert [c['trigger'] for c in out['conflicts']]==['born']
    out=m.run(req([src('Jane Doe unfounded Acme in 2020.','https://s/1'),src('Jane Doe unfounded Beta in 2021.','https://s/2')]))
    assert out['conflicts']==[]


# ---- completeness digits and values
@pytest.mark.parametrize('text,expect',[
    ('Jane Doe was born in 1980.',0.2),
    ('Jane Doe was born in 1980. Jane Doe founded Acme.',0.4),
    ('Jane Doe was born in 1980. Jane Doe founded Acme. Jane Doe won an award.',0.6),
    ('Jane Doe was born in 1980. Jane Doe founded Acme. Jane Doe won an award. Jane Doe recently spoke.',0.8),
    ('Jane Doe was born in 1980. Jane Doe founded Acme. Jane Doe won an award. Jane Doe recently spoke. Jane Doe launched a startup.',1.0),
])
def test_completeness_exact_values(text,expect):
    out=m.run(req([src(text)]))
    assert out['completeness']==expect and out['dimension_count']==5
    assert out['dimensions_covered']==round(expect*5)


def test_completeness_zero_when_no_dimension_keyword():
    out=m.run(req([src('Jane Doe waved.')]))
    assert out['completeness']==0.0 and out['dimensions_covered']==0 and out['citation_count']==0


def test_unknown_or_embedded_month_word_falls_back_to_bare_year_only():
    for word in ('Smarch','Sept','Marchx'):
        out=m.run(req([src('Jane Doe founded Acme in %s 2020.'%word)]))
        assert [(e['date'],e['precision']) for e in out['timeline']]==[('2020','year')]


def test_conflict_years_sorted_ascending_not_set_order():
    # {2008, 1985} iterates 2008 first in a CPython int set; the report must still sort ascending
    out=m.run(req([src('Jane Doe was born in 2008.','https://s/1'),src('Jane Doe was born in 1985.','https://s/2')]))
    assert out['conflicts'][0]['years']==[1985,2008]
