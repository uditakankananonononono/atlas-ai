import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.architecture_decision_records705 import architecture_decision_records705
from app.modules.m20_general_cognitive_worker.comment_audit706 import audit
from app.modules.m20_general_cognitive_worker.naming_checker707 import check_naming
from app.modules.m20_general_cognitive_worker.code_formatting708 import run

ADR={'title':'Pick local','context':'Supplied tradeoff','decision':'Use local','consequences':['Keep records'],'status':'accepted'}
COMMENTS={'source':'# explains intent\nx = 1\n'}
NAMING={'source':'def BadName():\n    pass\n','rules':{'rules':[{'id':'fn','kinds':['function'],'style':'snake_case'}]}}
FORMATTING={'style':{'name':'team-style-a','indent':'spaces','indent_width':4,'max_line_length':40,'line_ending':'lf','final_newline':True},'files':[{'path':'a.py','before':'x=1\n','after':'x = 1\n'}]}
CASES=[('/architecture-decisions/705/record',ADR,architecture_decision_records705),
       ('/code-comments/706/audit',COMMENTS,audit),
       ('/naming-conventions/707/check',NAMING,lambda d:check_naming(d['source'],d['rules'])),
       ('/code-formatting/708/inspect',FORMATTING,run)]

@pytest.mark.parametrize('path,data,engine',CASES)
def test_four_mounted_engines_real_parity(monkeypatch,oidc_auth_headers,path,data,engine):
    monkeypatch.setenv('ATLAS_ENV','production')
    client=TestClient(app,raise_server_exceptions=False)
    path='/api/v1/api/modules/20'+path
    assert client.post(path,json={'data':data}).status_code==401
    for tenant,actor in [('a','owner'),('b','other')]:
        result=client.post(path,headers=oidc_auth_headers(tenant,actor),json={'data':data})
        assert result.status_code==200,result.text
        assert result.json()=={**engine(data),'tenant_id':tenant,'actor_id':actor}
    headers=oidc_auth_headers('a','owner')
    for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]}]:
        assert client.post(path,headers=headers,json={'data':data,**extra}).status_code==403
    assert client.post(path,headers=headers,json={'data':{}}).status_code==422
    assert client.post(path,headers={**headers,'Content-Type':'application/json'},content=json.dumps({'data':{'source':'\ud800'}})).status_code==422

@pytest.mark.parametrize('path,data,engine',CASES)
def test_resource_refs_cap_boundary(monkeypatch,oidc_auth_headers,path,data,engine):
    monkeypatch.setenv('ATLAS_ENV','production')
    client=TestClient(app,raise_server_exceptions=False)
    path='/api/v1/api/modules/20'+path
    tenant='set-c-refs-'+hashlib.sha256(path.encode()).hexdigest()[:12]
    headers=oidc_auth_headers(tenant,'owner')
    refs=[{'tenant_id':tenant,'actor_id':'owner','id':str(i)}for i in range(64)]
    ok=client.post(path,headers=headers,json={'data':data,'resource_refs':refs})
    assert ok.status_code==200,ok.text
    assert client.post(path,headers=headers,json={'data':data,'resource_refs':refs+[{'tenant_id':tenant,'actor_id':'owner','id':'65'}]}).status_code==422

@pytest.mark.parametrize('path,data,engine',CASES)
def test_explicit_null_identity_fields_treated_as_absent(monkeypatch,oidc_auth_headers,path,data,engine):
    monkeypatch.setenv('ATLAS_ENV','production')
    client=TestClient(app,raise_server_exceptions=False)
    tenant='set-c-null-'+hashlib.sha256(path.encode()).hexdigest()[:12]
    r=client.post('/api/v1/api/modules/20'+path,headers=oidc_auth_headers(tenant,'owner'),json={'data':data,'tenant_id':None,'actor_id':None})
    assert r.status_code==200,r.text
    assert r.json()['tenant_id']==tenant and r.json()['actor_id']=='owner'

# Dedicated acceptance: closed-scoped, NOT literal breadth. Accepted only as
# the engine's own docstring states, over caller-supplied inputs. Authorizes,
# executes, merges, releases or approves nothing. It does not establish the
# row's literal capability.
import copy
import hashlib

EXACT_ADR = {'title':'Use X','context':'c','decision':'d','consequences':['k'],'alternatives':['a','b']}
EXACT_COMMENTS = {'source':'x = 1  # x\n# TODO fix\ny = 2\n'}
EXACT_NAMING = NAMING
EXACT_CASES = [('/architecture-decisions/705/record', EXACT_ADR),
               ('/code-comments/706/audit', EXACT_COMMENTS),
               ('/naming-conventions/707/check', EXACT_NAMING),
               ('/code-formatting/708/inspect', FORMATTING)]


@pytest.fixture
def mounted_owner(monkeypatch, oidc_auth_headers):
    monkeypatch.setenv('ATLAS_ENV','production')
    return TestClient(app,raise_server_exceptions=False), oidc_auth_headers('a','owner')


def post(mounted_owner, path, data):
    client, headers = mounted_owner
    return client.post('/api/v1/api/modules/20'+path,headers=headers,json={'data':data})


def output(mounted_owner, path, data):
    response = post(mounted_owner,path,data)
    assert response.status_code == 200, response.text
    return response.json()


def test_705_exact_declared_record_and_non_authority(mounted_owner):
    out=output(mounted_owner,EXACT_CASES[0][0],EXACT_ADR)
    assert out == {'record':{**EXACT_ADR,'status':'proposed','supersedes':None},
                   'counts':{'alternatives':2,'consequences':1},
                   'scope':'caller_supplied_adr_bookkeeping_only',
                   'immutable_history_required':True,'history_immutability_enforced':False,
                   'architecture_validated':False,'repository_behavior_verified':False,
                   'release_authorized':False,'evidence_verified':False,'human_review_required':True,
                   'tenant_id':'a','actor_id':'owner'}
    accepted=output(mounted_owner,EXACT_CASES[0][0],{**EXACT_ADR,'status':'accepted'})
    assert accepted['record']['status']=='accepted' and accepted['release_authorized'] is False


def test_706_exact_comment_positions_flags_counts_and_hash(mounted_owner):
    out=output(mounted_owner,EXACT_CASES[1][0],EXACT_COMMENTS)
    assert out['algorithm']=='python_comment_audit_v1' and out['status']=='audited'
    assert out['source_sha256']=='c84aa1b4dbe4cb70a1b63a2a76ba47bba3f57d761508425d84a3b3899c3673c9'
    assert (out['source_chars'],out['source_bytes'],out['line_count'],out['code_line_count'],out['comment_count'])==(28,28,3,2,2)
    assert out['options']=={'max_line_length':100,'min_lines_for_comment':15}
    assert out['comments']==[
        {'id':'C0001','line':1,'col':7,'end_col':10,'kind':'inline','text':' x','category':'prose','flags':['restates_code_candidate'],'has_rationale_keyword':False,'block_id':None,'associated_line':1},
        {'id':'C0002','line':2,'col':0,'end_col':10,'kind':'standalone','text':' TODO fix','category':'marker','flags':['marker_without_owner_or_ref'],'has_rationale_keyword':False,'block_id':'B0001','associated_line':3}]
    assert out['blocks']==[{'id':'B0001','first_line':2,'last_line':2,'col':0,'comment_ids':['C0002'],'associated_line':3}]
    assert out['symbols']==[]
    assert out['counts']=={'by_category':{'directive':0,'empty':0,'marker':1,'prose':1},'by_kind':{'inline':1,'standalone':1},'by_flag':{'marker_without_owner_or_ref':1,'restates_code_candidate':1}}
    assert out['code_executed'] is False and out['semantics_judged'] is False


def test_707_exact_identifier_position_rule_and_noninference(mounted_owner):
    out=output(mounted_owner,EXACT_CASES[2][0],EXACT_NAMING)
    assert out['schema']=='naming707/1'
    assert out['source_sha256']=='c98c52c8ff2532141a5731470e9004bf2d030fc5827071a2d4b56c24f9434812'
    assert out['rules_applied']==['fn'] and out['style_inferred'] is False and out['compliant'] is False
    assert (out['checked_count'],out['exempt_count'],out['position_unverified_count'])==(1,0,0)
    position={'name':'BadName','kind':'function','line':1,'col':5,'end_line':1,'end_col':12}
    assert out['checked']==[{**position,'rule_ids':['fn']}]
    assert out['findings']==[{**position,'rule_id':'fn','reason':'style_mismatch','expected':'snake_case','detail':None}]
    assert out['not_inspected']==['attribute_targets','del_targets','match_patterns','names_in_strings_and_comments','subscript_targets','unrenamed_imports']
    assert out['limits']=={'max_source_bytes':262144,'max_nodes':20000,'max_rules':32,'max_acronyms':64}


@pytest.mark.parametrize('file,chars,hashes,idempotence,findings',[
    ({'path':'a.py','before':'x=1\n','after':'x = 1\n'},(4,6),
     ('98752ee28d5484bdc2814fb70adb6a0b2fb31f6a9b8ee7ae81fd2fc9cf300b3b','9e26bf369911c45c243c684147b23fc9e1dcfcf257d299a1c632016a6fcd33f4'),'second_pass_not_supplied',False),
    ({'path':'b.py','before':'if x:\n\ty = 1\n','after':'if x:\n\ty = 1  \n','second_pass':'zz'},(13,15),
     ('a40a77d9558da769ed331c83b24bbf82b1d898049d85892ee2a09925f538a66a','f14b7cc90b8cc5b197de0916368098e70a1ff55818f9c956de98fcc0b5f1d1ab'),'second_pass_differs',True)])
def test_708_exact_supplied_text_facts(mounted_owner,file,chars,hashes,idempotence,findings):
    out=output(mounted_owner,EXACT_CASES[3][0],{'style':FORMATTING['style'],'files':[file]})
    assert out['style']==FORMATTING['style']
    row=out['files'][0]
    assert len(out['files'])==1 and row['path']==file['path']
    assert row['changed'] is True and row['whitespace_only_change'] is True
    assert (row['before_chars'],row['after_chars'])==chars
    assert (row['before_sha256'],row['after_sha256'])==hashes
    assert row['idempotence']==idempotence and row['has_style_findings'] is findings
    assert row['style_findings']=={'long_lines':[],'long_line_count':0,'trailing_whitespace_lines':[2] if findings else [],'trailing_whitespace_count':int(findings),'indent_mismatch_lines':[2] if findings else [],'indent_mismatch_count':int(findings),'indent_width_lines':[],'indent_width_count':0,'wrong_line_ending_lines':[],'wrong_line_ending_count':0,'final_newline_ok':True}
    assert out['changed_paths']==[file['path']]
    assert out['counts']=={'files':1,'changed':1,'unchanged':0,'whitespace_only':1,'with_style_findings':int(findings)}
    assert out['idempotence_counts']=={'second_pass_equal':0,'second_pass_differs':int(findings),'second_pass_not_supplied':int(not findings)}
    for flag in ('formatter_executed','semantics_verified','style_authority','idempotence_proven'):assert out[flag] is False


REFUSALS=[
 (0,{'title':'t','context':'c','decision':'d'},'ARCHIT705: missing consequences'),
 (0,{**EXACT_ADR,'consequences':[]},'ARCHIT705: consequences must not be empty'),
 (0,{**EXACT_ADR,'status':'approved'},'ARCHIT705: status must be a declared ADR status'),
 (0,{**EXACT_ADR,'extra':1},'ARCHIT705: unknown fields'),
 (0,{**EXACT_ADR,'title':' '},'ARCHIT705: title must be nonblank safe text'),
 (1,{},"input keys invalid: missing ['source'] unknown []"),
 (1,{'source':'x=1\r'},'source must use LF or CRLF line breaks'),
 (1,{'source':'x=1','max_line_length':10},'max_line_length must be an integer 40..200'),
 (2,{'source':'pass','rules':{'rules':[]}},'rules must be a non-empty list'),
 (2,{'rules':NAMING['rules']},"'source'"),
 (2,{'source':'pass'},"'rules'"),
 (3,{**FORMATTING,'run':True},'CODEFO708:EXEC_REQUEST:run'),
 (3,{'files':FORMATTING['files']},'CODEFO708:MISSING:style'),
 (3,{'style':FORMATTING['style'],'files':[{'path':'/a','before':'','after':''}]},'CODEFO708:BAD_PATH'),
 (3,{'style':FORMATTING['style'],'files':FORMATTING['files']*2},'CODEFO708:DUPLICATE:path')]


@pytest.mark.parametrize('index,data,detail',REFUSALS)
def test_exact_engine_refusal_is_mounted_422(mounted_owner,index,data,detail):
    response=post(mounted_owner,EXACT_CASES[index][0],data)
    assert response.status_code==422,response.text
    assert response.json()=={'detail':detail}


@pytest.mark.parametrize('index,prefix',[(1,'syntax_error: line 1'),(2,'source is not valid Python syntax at line 1')])
def test_parser_version_scoped_refusal_prefix(mounted_owner,index,prefix):
    data={'source':'def ('}
    if index==2:data['rules']=NAMING['rules']
    response=post(mounted_owner,EXACT_CASES[index][0],data)
    assert response.status_code==422 and response.json()['detail'].startswith(prefix)


@pytest.mark.parametrize('path,data',EXACT_CASES)
def test_each_mounted_contract_boundaries(mounted_owner,path,data):
    client,headers=mounted_owner;full='/api/v1/api/modules/20'+path
    assert client.post(full,json={'data':data}).status_code==401
    for extra in [{'tenant_id':'b'},{'actor_id':'other'},{'resource_refs':[{'tenant_id':'b'}]},{'resource_refs':[{'tenant_id':'a','actor_id':'other'}]}]:
        assert client.post(full,headers=headers,json={'data':data,**extra}).status_code==403
    assert client.post(full,headers=headers,json={}).status_code==422
    assert client.post(full,headers={**headers,'Content-Type':'application/json'},content=json.dumps({'data':{'x':'\ud800'}})).status_code==422
    for refs,count in [([{'tenant_id':'a','actor_id':'owner'}]*64,200),([{'tenant_id':'a','actor_id':'owner'}]*65,422)]:
        response=client.post(full,headers=headers,json={'data':data,'resource_refs':refs})
        assert response.status_code==count,response.text
    nested='x'
    for _ in range(58):nested=[nested]
    response=client.post(full,headers=headers,json={'data':data,'resource_refs':[{'tenant_id':'a','metadata':nested}]})
    assert response.status_code==422
    assert response.json()['detail']=='computation input exceeds size/depth boundary'
    response=client.post(full,headers={**headers,'Content-Type':'application/json'},content=json.dumps({'data':data,'resource_refs':[{'tenant_id':'a','x':float('inf')}]}))
    assert response.status_code==422 and response.json()['detail']=='nonfinite numerical input rejected'


@pytest.mark.parametrize('field,cap',[('title',200),('context',4000),('decision',4000)])
def test_705_raw_text_caps(mounted_owner,field,cap):
    assert post(mounted_owner,EXACT_CASES[0][0],{**EXACT_ADR,field:'x'*cap}).status_code==200
    response=post(mounted_owner,EXACT_CASES[0][0],{**EXACT_ADR,field:'x'*(cap+1)})
    assert response.status_code==422
    assert response.json()['detail']==f'ARCHIT705: {field} raw length exceeds {cap}'


@pytest.mark.parametrize('field',['alternatives','consequences'])
def test_705_list_and_item_caps(mounted_owner,field):
    path=EXACT_CASES[0][0]
    assert post(mounted_owner,path,{**EXACT_ADR,field:['x'*1000]*32}).status_code==200
    response=post(mounted_owner,path,{**EXACT_ADR,field:['x']*33})
    assert response.status_code==422 and response.json()['detail']==f'ARCHIT705: {field} count exceeds 32'
    response=post(mounted_owner,path,{**EXACT_ADR,field:['x'*1001]})
    assert response.status_code==422 and response.json()['detail']==f'ARCHIT705: {field}[0] raw length exceeds 1000'


def test_706_raw_source_and_line_caps(mounted_owner):
    path=EXACT_CASES[1][0]
    assert post(mounted_owner,path,{'source':'#'+'x'*65535}).status_code==200
    response=post(mounted_owner,path,{'source':'#'+'x'*65536})
    assert response.status_code==422 and response.json()['detail']=='source exceeds 65536 characters'
    assert post(mounted_owner,path,{'source':'\n'*2000}).status_code==200
    response=post(mounted_owner,path,{'source':'\n'*2001})
    assert response.status_code==422 and response.json()['detail']=='source exceeds 2000 lines'


def test_707_utf8_byte_boundary(mounted_owner):
    path=EXACT_CASES[2][0]
    assert post(mounted_owner,path,{'source':'#'+'x'*262143,'rules':NAMING['rules']}).status_code==200
    response=post(mounted_owner,path,{'source':'#'+'x'*262144,'rules':NAMING['rules']})
    assert response.status_code==422 and response.json()['detail']=='source is 262145 bytes, limit is 262144'


def test_708_raw_content_and_file_caps(mounted_owner):
    path=EXACT_CASES[3][0];style=FORMATTING['style']
    assert post(mounted_owner,path,{'style':style,'files':[{'path':'a','before':'x'*100000,'after':''}]}).status_code==200
    response=post(mounted_owner,path,{'style':style,'files':[{'path':'a','before':'x'*100001,'after':''}]})
    assert response.status_code==422 and response.json()['detail']=='CODEFO708:OVERSIZE:content'
    files=[{'path':f'f{i}','before':'','after':''}for i in range(64)]
    assert post(mounted_owner,path,{'style':style,'files':files}).status_code==200
    response=post(mounted_owner,path,{'style':style,'files':files+[{'path':'extra','before':'','after':''}]})
    assert response.status_code==422 and response.json()['detail']=='CODEFO708:OVERSIZE:files'
