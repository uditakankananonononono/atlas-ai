"""Supplied Docs parsing fixtures; no external reads."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/c35/docs_ingest.py'
spec=importlib.util.spec_from_file_location('c35_docs_ingest_test',P)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
BOOKMARK='https://docs.google.com/document/d/SYNTHETIC_BOOKMARK_FIXTURE/edit?tab=t.0'
WAIVER='https://docs.google.com/document/d/SYNTHETIC_WAIVER_FIXTURE/edit?usp=sharing'

@pytest.fixture(autouse=True)
def configured_owner_pins(monkeypatch):
    monkeypatch.setenv(m.PINNED_DOC_URLS_ENV,json.dumps([BOOKMARK,WAIVER]))

def req(text,doc_url=BOOKMARK):return {'as_of':'2026-10-11','docs':[{'doc_url':doc_url,'text':text}]}
def refuse(code,f):
    with pytest.raises(ValueError)as e:f()
    assert str(e.value)==code

def fixture():
    rows=['Opportunity %d https://sciencefair.example/program/%d'%(i,i) for i in range(20)]
    rows +=['duplicate https://SCIENCEFAIR.example/program/0/#old','duplicate https://sciencefair.example/program/1?utm_source=chat','duplicate https://sciencefair.example/program/2/?utm_campaign=x','unknown https://mystery.example/one','grant https://grants.example/call?year=2026&utm_medium=share']
    return '\n'.join(rows)+'\n\nFee waiver request\nDear {school}, I am {name}. Please waive fees for {opportunity}.\n\nwaiver request\nAsk {school} for {name}.\n\n'


def test_25_links_two_templates_and_duplicates():
    out=m.run(req(fixture()))
    assert out['coverage']=={'links_found':25,'duplicates_dropped':3,'unknown_kind':1}
    assert len(out['index'])==22
    assert out['index'][0]['url']=='https://sciencefair.example/program/0'
    assert out['index'][0]['label']=='Opportunity 0 https://sciencefair.example/program/0'
    assert out['index'][0]['kind']=='competition'
    assert out['index'][-1]['kind']=='grant'
    assert out['index'][-1]['url']=='https://grants.example/call?year=2026'
    assert len(out['waiver_templates'])==2
    assert out['waiver_templates'][0]['text']=='Fee waiver request\nDear {school}, I am {name}. Please waive fees for {opportunity}.'
    assert out['waiver_templates'][0]['placeholders']==['name','opportunity','school']
    assert out['scope']['as_of']=='2026-10-11'


@pytest.mark.parametrize('doc_url',[BOOKMARK,WAIVER])
def test_both_owner_pins(doc_url):assert m.run(req('https://unknown.example',doc_url))['index']


@pytest.mark.parametrize('doc_url',[BOOKMARK+'&evil=1',BOOKMARK.split('?')[0],WAIVER+')','https://docs.google.com/document/d/random/edit'])
def test_pin_exact_equality(doc_url):refuse('APPLY_REFUSED_URL_NOT_PINNED',lambda:m.run(req('https://x.example',doc_url)))


def test_cross_doc_dedupe_and_provenance():
    r={'as_of':'d','docs':[{'doc_url':BOOKMARK,'text':'One https://X.example/path/'},{'doc_url':WAIVER,'text':'Two https://x.example/path#part'}]}
    out=m.run(r)
    assert out['coverage']['duplicates_dropped']==1
    assert out['index']==[{'url':'https://x.example/path','label':'One https://X.example/path/','kind':'unknown','doc_urls':[BOOKMARK,WAIVER]}]


def test_normalization_preserves_query_and_path_case():
    out=m.run(req('https://EXAMPLE.org/Path/?b=2&utm_source=x&a=1#x\nhttps://example.org/path/?b=2&a=1'))
    assert [r['url']for r in out['index']]==['https://example.org/Path?b=2&a=1','https://example.org/path?b=2&a=1']
    assert out['coverage']['duplicates_dropped']==0


def test_link_punctuation_markdown_and_multiple_per_line():
    out=m.run(req('Read (https://abc.example/x), [link](https://def.example/y).'))
    assert [r['url']for r in out['index']]==['https://abc.example/x','https://def.example/y']
    assert out['coverage']['links_found']==2


def test_template_casefold_blank_delimiter_and_exact_whitespace():
    text='prefix\nFEE WAIVER details\r\n  Dear {name},  \r\n\tApply {other} and {school}\r\n\r\nnot a template\n'
    out=m.run(req(text))
    assert out['waiver_templates'][0]['text']=='FEE WAIVER details\r\n  Dear {name},  \r\n\tApply {other} and {school}'
    assert out['waiver_templates'][0]['placeholders']==['name','school']
    assert len(out['waiver_templates'])==1


def test_no_template_trigger_means_none():assert m.run(req('normal text'))['waiver_templates']==[]
def test_template_final_eof():assert m.run(req('Waiver request\nHello {opportunity}'))['waiver_templates'][0]['text']=='Waiver request\nHello {opportunity}'


def test_unknown_kind_is_not_guessed():
    out=m.run(req('Scholarship contest label https://unknown.example'))
    assert out['index'][0]['kind']=='unknown'
    assert out['coverage']['unknown_kind']==1


@pytest.mark.parametrize('host,kind',[('scholarships.example','scholarship'),('competitions.example','competition'),('grants.example','grant'),('admissions.example','admissions'),('jobs.example','job')])
def test_host_keyword_table(host,kind):assert m.run(req('https://'+host))['index'][0]['kind']==kind


def test_scope_determinism_and_offline_surface():
    out=m.run(req('https://x.example'))
    assert out==m.run(req('https://x.example'))
    assert 'live verification' in out['scope']['not_implemented']
    assert not any(hasattr(m,k)for k in ('fetch','send','post','spend','trade','create_account'))
    from app.modules.c30 import policy
    assert m.policy is policy


@pytest.mark.parametrize('data,code',[
(None,'APPLY_REFUSED_BAD_TYPE:request'),
({},'APPLY_REFUSED_NOSOURCE'),
({'as_of':'d','docs':[]},'APPLY_REFUSED_NOSOURCE'),
({'as_of':'d','docs':True},'APPLY_REFUSED_BAD_TYPE:docs'),
({'as_of':'d','docs':[None]},'APPLY_REFUSED_BAD_TYPE:doc'),
({'as_of':'d','docs':[{'doc_url':BOOKMARK,'text':''}]},'APPLY_REFUSED_EMPTY:text'),
({'as_of':'','docs':[{'doc_url':BOOKMARK,'text':'x'}]},'APPLY_REFUSED_EMPTY:as_of'),
({'as_of':'d','docs':[{'doc_url':BOOKMARK,'text':False}]},'APPLY_REFUSED_BAD_TYPE:text'),
({'as_of':'d','docs':[{'doc_url':BOOKMARK,'text':'x'}],'action':'send'},'APPLY_REFUSED_BAD_TYPE:request'),
])
def test_refusals(data,code):refuse(code,lambda:m.run(data))


def test_blank_query_kept_and_utm_casefold_dropped():
    out=m.run(req('https://a.example/x?blank=&UTM_source=a&b=2#gone'))
    assert out['index'][0]['url']=='https://a.example/x?blank=&b=2'


def test_first_kind_priority_when_two_host_keywords():
    assert m.run(req('https://scholarship-contest.example'))['index'][0]['kind']=='scholarship'


def test_label_byte_preservation():
    line='  title\t https://a.example/p  '
    assert m.run(req(line))['index'][0]['label']==line


def test_no_links_clean_empty_coverage():
    assert m.run(req('no URLs here'))['coverage']=={'links_found':0,'duplicates_dropped':0,'unknown_kind':0}


def test_credentials_and_invalid_ports_refuse():
    for url in ('https://user:pass@a.example','https://a.example:bad/x','https:///broken'):
        refuse('APPLY_REFUSED_BAD_TYPE:url',lambda:m.run(req(url)))


def test_controls_and_cap_use_real_policy():
    refuse('APPLY_REFUSED_CONTROL_CHARS:text',lambda:m.run(req('bad\x00text')))
    refuse('APPLY_REFUSED_TEXT_TOO_LONG:text',lambda:m.run(req('x'*2_000_001)))


def test_template_boundary_spaces_are_preserved():
    text='  Fee waiver request  \nDear {name}, keep these spaces.  '
    assert m.run(req(text))['waiver_templates'][0]['text']==text


def test_valid_port_preserved():
    assert m.run(req('https://Example.org:8443/Path/?utm_source=x#f'))['index'][0]['url']=='https://example.org:8443/Path'


def test_ipv6_bracket_authority():
    assert m.run(req('https://[2001:DB8::1]/Path/'))['index'][0]['url']=='https://[2001:db8::1]/Path'


def test_ipv6_brackets_and_port_preserved():
    assert m.run(req('https://[2001:DB8::1]:8443/Path/'))['index'][0]['url']=='https://[2001:db8::1]:8443/Path'


def test_configuration_missing_refuses_without_default(monkeypatch):
    monkeypatch.delenv(m.PINNED_DOC_URLS_ENV)
    refuse('APPLY_REFUSED_DOC_CONFIG_MISSING',lambda:m.run(req('https://x.example')))


@pytest.mark.parametrize('raw',['', 'not json', '{}', '[]', '[null]', '[1]', '["https://evil.example/doc"]',
    '["http://docs.google.com/document/d/FIXTURE/edit"]',
    '["https://docs.google.com.evil.example/document/d/FIXTURE/edit"]',
    '["https://docs.google.com/document/d/FIXTURE/edit#fragment"]',
    '["https://user@docs.google.com/document/d/FIXTURE/edit"]'])
def test_bad_configuration_refuses(monkeypatch,raw):
    monkeypatch.setenv(m.PINNED_DOC_URLS_ENV,raw)
    code='APPLY_REFUSED_DOC_CONFIG_MISSING' if not raw else 'APPLY_REFUSED_DOC_CONFIG_INVALID'
    refuse(code,lambda:m.run(req('https://x.example')))


def test_config_refreshes_without_reload(monkeypatch):
    custom='https://docs.google.com/document/d/SYNTHETIC_CUSTOM_FIXTURE/edit?tab=t.0'
    monkeypatch.setenv(m.PINNED_DOC_URLS_ENV,json.dumps([custom]))
    assert m.run(req('https://x.example',custom))['index']
    refuse('APPLY_REFUSED_URL_NOT_PINNED',lambda:m.run(req('https://x.example')))


def test_request_cannot_override_configuration():
    r=req('https://x.example')
    r['pinned_doc_urls']=[BOOKMARK]
    refuse('APPLY_REFUSED_BAD_TYPE:request',lambda:m.run(r))


def test_duplicate_configuration_refuses(monkeypatch):
    monkeypatch.setenv(m.PINNED_DOC_URLS_ENV,json.dumps([BOOKMARK,BOOKMARK]))
    refuse('APPLY_REFUSED_DOC_CONFIG_INVALID',lambda:m.run(req('https://x.example')))
