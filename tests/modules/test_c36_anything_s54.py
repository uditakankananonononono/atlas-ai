import copy
import pytest
from app.modules.c36 import anything as a


def item(text='tool', **kw):
    x=dict(id='r1',text=text,kind_hint=None);x.update(kw);return x


def req(items=None, **kw):
    x=dict(as_of='2026-10-11',requests=[item()] if items is None else items);x.update(kw);return x


def refusal(x,code):
    with pytest.raises(ValueError) as e:a.run(x)
    assert str(e.value)== 'VENT_REFUSED_'+code


@pytest.mark.parametrize('word', ['tool','app','script','api','website','bot','program','plugin','dashboard','scraper'])
def test_software(word):assert a.run(req([item(word)]))['routes'][0]['kind']=='software'


@pytest.mark.parametrize('word',['spec','plan','report','guide','brief','proposal','essay','outline'])
def test_document(word):assert a.run(req([item(word)]))['routes'][0]['kind']=='document'


@pytest.mark.parametrize('word',['toy','aircraft','hotel','building','robot','vehicle','device','furniture','bridge','drone'])
def test_physical(word):
    r=a.run(req([item(word)]))['routes'][0]
    assert r['kind']=='physical' and r['allowed']==['spec','bom','safety_note'] and r['build'] is False


def test_priority_hint_and_no_keyword():
    xs=[item('tool report toy',kind_hint='software'),item('tool report',id='r2'),item('nothing',id='r3',kind_hint='software')]
    r=a.run(req(xs));assert [v['kind'] for v in r['routes']]==['physical','software','unclassified']
    assert r['routes'][0]['multiple_classes'] and r['routes'][0]['hint_conflict']
    assert r['routes'][2]['reason']=='no_keyword'
    assert r['coverage']==dict(requests=3,software=1,document=0,physical=1,unclassified=1)


@pytest.mark.parametrize('text',['toys','aircrafts','robotics','application','tooling','mytool','notebook','hotelier'])
def test_whole_words(text):assert a.run(req([item(text)]))['routes'][0]['kind']=='unclassified'


def test_casefold_and_punctuation():assert a.run(req([item('(TOOL)!')]))['routes'][0]['kind']=='software'


@pytest.mark.parametrize('key',['execute','build_physical','order','manufacture','ship'])
def test_physical_keys(key):refusal(req([item(**{key:False})]),'PHYSICAL_BUILD:'+key)


@pytest.mark.parametrize('key',['post','publish','deploy','register'])
def test_effect_keys(key):refusal(req([item(**{key:None})]),'EFFECT:'+key)


@pytest.mark.parametrize('key',['send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'])
def test_send_keys(key):refusal(req([item(**{key:0})]),'SEND:'+key)


@pytest.mark.parametrize('key',['pay','purchase','spend','buy','checkout','card_number'])
def test_spend_keys(key):refusal(req(**{key:False}),'SPEND:'+key)


@pytest.mark.parametrize('key',['login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd'])
def test_creds_keys(key):refusal(req(**{key:''}),'NOCREDS:'+key)


def test_recursive_precedence_normalized_and_sorted():
    refusal(req(extra={'Password':None,'nested':[{'SMTP-HOST':False,'APPROVE':0,'execute':0}]}),'SEND:approve')
    refusal(req(extra={'execute':0,'deploy':0,'pay':0}),'SPEND:pay')
    refusal(req(extra={'execute':0,'deploy':0}),'EFFECT:deploy')


def test_no_echo_unknown_keys_and_exact_normalization():
    refusal(req(secret_value_123='x'),'UNKNOWN:request')
    refusal(req([item(tokenized=True)]),'UNKNOWN:requests')
    refusal(req(extra={'prefix_send':True}),'UNKNOWN:request')


@pytest.mark.parametrize('x,code',[(None,'BAD_TYPE:request'),([], 'BAD_TYPE:request'),({1:'x'},'BAD_TYPE:key'),({'as_of':'x','requests':[]},'BAD_TYPE:as_of')])
def test_top_errors(x,code):refusal(x,code)


def test_nonstring_key_after_forbidden_scan():refusal(req(extra={1:0,'token':False}),'SEND:token')


@pytest.mark.parametrize('day',['2026-02-30','2026-1-01','2026-10-11\n',False])
def test_iso_day(day):refusal(req(as_of=day),'BAD_TYPE:as_of')


def test_empty_list():refusal(req([]),'EMPTY')


def test_caps_before_clean_text():
    refusal(req([item(id='a'*129)]),'OVERSIZE:id')
    refusal(req([item(text='a'*2001)]),'OVERSIZE:text')
    refusal(req([item(id=str(i)) for i in range(1001)]),'OVERSIZE:requests')


def test_exact_caps():
    assert a.run(req([item(id='a'*128,text='tool'+' '*1996)]))['coverage']['software']==1
    assert a.run(req([item(id=str(i)) for i in range(1000)]))['coverage']['requests']==1000


@pytest.mark.parametrize('hint',[False,1,'wrong',[],{}])
def test_bad_hint(hint):refusal(req([item(kind_hint=hint)]),'BAD_TYPE:kind_hint')


def test_duplicate_and_bad_fields():
    refusal(req([item(),item()]),'BAD_TYPE:requests')
    refusal(req([item(id=3)]),'BAD_TYPE:id')
    refusal(req([item(text=False)]),'BAD_TYPE:text')
    refusal(req([item(text=' ')]),'EMPTY:text')


def test_field_list_order_and_control():
    refusal(req([item(id='x\n',text='')]),'CONTROL_CHARS:id')
    refusal(req([item(text='x\n')]),'CONTROL_CHARS:text')


def test_fixture25_deterministic_copy_scope():
    xs=[item(['tool','plan','toy','nothing','tool toy'][i%5],id=str(i)) for i in range(25)]
    x=req(xs);before=copy.deepcopy(x);r=a.run(x)
    assert x==before and r==a.run(x)
    assert [v['id'] for v in r['routes']]==[str(i) for i in range(25)]
    assert r['coverage']==dict(requests=25,software=5,document=5,physical=10,unclassified=5)
    assert set(r['scope'])=={'implemented','not_implemented','data_source','as_of'}


def test_public_surface():
    import ast
    from pathlib import Path
    tree=ast.parse(Path(a.__file__).read_text())
    assert [n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and not n.name.startswith('_')]==['run']


def test_unknown_deep_scalar_container():refusal(req([item(kind_hint=[[[{'unexpected':0}]]])]),'UNKNOWN:kind_hint')


def test_caps_precede_earlier_field_hygiene():
    refusal(req([item(id='',text='x'),item(id='r2',text='x'*2001)]),'OVERSIZE:text')


def test_fixed_precedence_independent_of_key_order():
    refusal(req([item(pay=False,token=False,execute=False,password=False)]),'SEND:token')


def test_nonkeyword_hint_does_not_invent_class():
    r=a.run(req([item('opaque',kind_hint='physical')]))['routes'][0]
    assert r['kind']=='unclassified' and 'allowed' not in r


def test_kind_hint_nonempty_dict_is_unknown():
    refusal(req([item(kind_hint={'x': 1})]), 'UNKNOWN:kind_hint')


@pytest.mark.parametrize('hint', [['x'], [[1]]])
def test_kind_hint_nondict_list_is_bad_type(hint):
    refusal(req([item(kind_hint=hint)]), 'BAD_TYPE:kind_hint')


def test_flags_truth_table_false_cases():
    # single class, agreeing hint: both flags False
    r = a.run(req([item('tool', kind_hint='software')]))['routes'][0]
    assert r['multiple_classes'] is False and r['hint_conflict'] is False
    # single class, no hint
    r = a.run(req([item('tool', kind_hint=None)]))['routes'][0]
    assert r['multiple_classes'] is False and r['hint_conflict'] is False
    # hint present but no keyword match: no conflict flag
    r = a.run(req([item('opaque', kind_hint='software')]))['routes'][0]
    assert r['kind'] == 'unclassified' and r['hint_conflict'] is False
    # multiple classes with hint equal to chosen kind: multiple True, conflict False
    r = a.run(req([item('toy tool', kind_hint='physical')]))['routes'][0]
    assert r['kind'] == 'physical' and r['multiple_classes'] is True and r['hint_conflict'] is False
    # control: conflicting hint with a keyword match stays True
    r = a.run(req([item('tool', kind_hint='physical')]))['routes'][0]
    assert r['multiple_classes'] is False and r['hint_conflict'] is True


def test_exact_cap_accept_refuse_boundary():
    # id: 128 accepted, 129 refused with exact OVERSIZE:id
    assert a.run(req([item(id='a' * 128)]))['coverage']['requests'] == 1
    refusal(req([item(id='a' * 129)]), 'OVERSIZE:id')
    # text: 2000 accepted, 2001 refused with exact OVERSIZE:text
    assert a.run(req([item(text='tool ' + 'x' * 1995)]))['coverage']['requests'] == 1
    refusal(req([item(text='tool ' + 'x' * 1996)]), 'OVERSIZE:text')
