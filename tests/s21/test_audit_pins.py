"""Nine independent-audit pin groups; no runtime changes."""
import hashlib
import json
from test_social_scan import m, record, payload, run, refuse, scanner, AS_OF
import pytest


def plugin_run(rows, **kw):
    class Fixture:
        def read(self, data):
            return iter(rows)
    return scanner(connectors={'fixture':Fixture()}, **kw).run(tenant_id='a',connector='fixture',payload=b'x',as_of=AS_OF)


def test_default_records_5000_and_5001():
    assert run(data=payload([record()]*5000))['counts']=={'supplied':5000,'unique':1,'duplicates':4999,'liked_post':1,'comment':0,'followed_account':0,'feed_post':0}
    refuse('SOCIAL_REFUSED_OVERSIZE',lambda:run(data=payload([record()]*5001)))


def test_default_reports_100_and_config_1000():
    s=scanner()
    reports=[run(s,data=payload([record(id=str(i))])) for i in range(101)]
    refuse('SOCIAL_REFUSED_NOTFOUND',lambda:s.report('a',reports[0]['report_id']))
    assert s.report('a',reports[1]['report_id'])==reports[1]
    assert len(s._reports)==100
    assert scanner(max_reports=1000).max_reports==1000
    refuse('SOCIAL_REFUSED_LIMIT',lambda:scanner(max_reports=1001))


def test_exact_byte_limit_accepted():
    data=payload()
    assert run(scanner(max_bytes=len(data)),data)['counts']['unique']==1
    refuse('SOCIAL_REFUSED_OVERSIZE',lambda:run(scanner(max_bytes=len(data)-1),data))


@pytest.mark.parametrize('field',['id','author','platform','source_ref'])
def test_other_field_2000_2001(field):
    prefix='export:' if field=='source_ref' else ''
    assert run(data=payload([record(**{field:prefix+'x'*(2000-len(prefix))})]))['counts']['unique']==1
    refuse('SOCIAL_REFUSED_OVERSIZE',lambda:run(data=payload([record(**{field:prefix+'x'*(2001-len(prefix))})])))


def test_tenant_120_121():
    s=scanner()
    assert s.run(tenant_id='t'*120,connector='normalized_json',payload=payload(),as_of=AS_OF)['counts']['unique']==1
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:s.run(tenant_id='t'*121,connector='normalized_json',payload=payload(),as_of=AS_OF))


@pytest.mark.parametrize('char',['\ud800','\udfff'])
def test_both_lone_surrogate_endpoints(char):
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=payload([record(text=char)])))


def test_exact_mixed_counts_clusters_and_dedupes():
    a=record(id='a',text='robot',author='maker',source_ref='export:same')
    b=record(id='b',text='sensor',author='maker',source_ref='export:same')
    c=record(id='c',kind='comment',text='design',author='artist',source_ref='export:c')
    d=record(id='d',kind='followed_account',text='robot',author='second',source_ref='export:d')
    out=run(data=payload([d,c,b,a,a]))
    assert out['counts']=={'supplied':5,'unique':4,'duplicates':1,'liked_post':2,'comment':1,'followed_account':1,'feed_post':0}
    assert out['clusters']==[
        {'theme':'design','record_count':1,'source_refs':['export:c'],'authors':['artist']},
        {'theme':'engineering','record_count':3,'source_refs':['export:d','export:same'],'authors':['second','maker']},
    ]


def test_equal_theme_score_alphabetical():
    assert run(data=payload([record(text='robot design')]))['clusters'][0]['theme']=='design'


def test_fixed_report_id_canonical_json():
    out=run()
    report_id=out.pop('report_id')
    assert report_id==hashlib.sha256(json.dumps(out,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert report_id=='d32958e2431081fa4524f9e04ea339e78014f7a4edf5516b8eb03ec7333f3624'


@pytest.mark.parametrize('row',[None,[],17,'text'])
def test_non_dict_row_schema_code(row):
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:plugin_run([row]))


@pytest.mark.parametrize('data',[None,[],1,'text'])
def test_non_dict_json_schema_code(data):
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=json.dumps(data).encode()))


@pytest.mark.parametrize('version',[0,2,-1,'1',1.0,None])
def test_version_refusal_exact_code(version):
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=json.dumps({'schema_version':version,'records':[]}).encode()))


@pytest.mark.parametrize('tenant',[None,[],{},1,True])
def test_non_string_tenant_refusal(tenant):
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:scanner().run(tenant_id=tenant,connector='normalized_json',payload=payload(),as_of=AS_OF))


@pytest.mark.parametrize('data',[None,'text',[],bytearray(b'x')])
def test_non_bytes_payload_refusal(data):
    # Runtime's actual contract is NOEXPORT for absent/non-bytes input.
    refuse('SOCIAL_REFUSED_NOEXPORT',lambda:scanner().run(tenant_id='a',connector='normalized_json',payload=data,as_of=AS_OF))


@pytest.mark.parametrize('connector',[[],{},None,1])
def test_unhashable_and_nonstring_connector_refusal(connector):
    refuse('SOCIAL_REFUSED_CONNECTOR',lambda:scanner().run(tenant_id='a',connector=connector,payload=payload(),as_of=AS_OF))


def test_csv_malformed_quoted_row_and_bom_only():
    header=b'id,kind,platform,author,text,visibility,source_ref\n'
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=header+b'p1,liked_post,sandbox,maker,"unterminated,public,export:p1\n',connector_override='pasted_csv'))
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=b'\xef\xbb\xbf',connector_override='pasted_csv'))
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=b'id,id,kind,platform,author,text,visibility,source_ref\n',connector_override='pasted_csv'))


def test_report_write_recency_not_insertion_order():
    s=scanner(max_reports=2)
    a=run(s,data=payload([record(id='a')]))
    b=run(s,data=payload([record(id='b')]))
    assert run(s,data=payload([record(id='a')]))==a
    c=run(s,data=payload([record(id='c')]))
    assert s.report('a',a['report_id'])==a
    assert s.report('a',c['report_id'])==c
    refuse('SOCIAL_REFUSED_NOTFOUND',lambda:s.report('a',b['report_id']))


def test_exact_dict_and_exact_string_guards():
    class DictSubclass(dict): pass
    class StrSubclass(str): pass
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:plugin_run([DictSubclass(record())]))
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:plugin_run([record(text=StrSubclass('robot'))]))
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:plugin_run([record(text=1)]))


def test_csv_strict_rejects_quote_trailing_characters():
    header=b'id,kind,platform,author,text,visibility,source_ref\n'
    row=b'p1,liked_post,sandbox,maker,"x"y,public,export:p1\n'
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=header+row,connector_override='pasted_csv'))


def test_csv_seven_columns_wrong_set_without_rows():
    header=b'id,id,platform,author,text,visibility,source_ref\n'
    refuse('SOCIAL_REFUSED_SCHEMA',lambda:run(data=header,connector_override='pasted_csv'))
