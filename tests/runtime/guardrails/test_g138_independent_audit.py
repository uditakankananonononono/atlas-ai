import hashlib,itertools,re,unicodedata
import pytest
from app.runtime.guardrails import claim_lint_gate as g
from app.runtime.guardrails import _fields as f
from app.runtime.guardrails.errors import GuardrailRefusal
T='2026-10-12T08:00:00Z'
def oracle(s):
    # Independent character-index oracle, policy collapses ASCII body separators only.
    expanded=[]
    for i,c in enumerate(s):
        for low in c.lower():expanded.append((low,i))
    raw=''.join(c for c,i in expanded)
    groups=list(re.finditer(r'[ \t\r\n]+|[^ \t\r\n]',s))
    collapsed=[]
    for m in groups:
        for c in (' ' if m.group()[0] in ' \t\r\n' else m.group()).lower():collapsed.append((c,m.start()))
    collapsed_s=''.join(c for c,i in collapsed)
    for category,phrases in g.PROHIBITED_CLAIMS:
        for phrase in phrases:
            pos=raw.find(phrase)
            if pos>=0:return category,phrase,expanded[pos][1]
            pos=collapsed_s.find(phrase)
            if pos>=0:return category,phrase,collapsed[pos][1]
    return None

def test_all_phrases_separator_product_and_case():
    count=0
    for cat,ps in g.PROHIBITED_CLAIMS:
        for phrase in ps:
            for seps in itertools.product([' ','  ','\t','\n','\r\n'],repeat=phrase.count(' ')):
                words=phrase.split(' '); s='İ prefix\r\n'+''.join(w.upper()+(seps[i] if i<len(seps) else '') for i,w in enumerate(words))
                expected=oracle(s);assert g.lint(s)==expected
                with pytest.raises(GuardrailRefusal) as e:g.emit('e',s,channel='ui',now=T)
                assert e.value.details['offset']==expected[2]
                rec=e.value.ledger[-1]['record'];assert rec['text_sha256']==hashlib.sha256(s.encode()).hexdigest()
                assert g.loads(g.dumps(e.value.ledger))==e.value.ledger
                count+=1
    print('phrase_cases',count)

def test_validator_all_controls_and_unicode_samples():
    count=0
    for i in range(0x110000):
        c=chr(i)
        if unicodedata.category(c) not in ('Cc','Cf','Zl','Zp'):continue
        s='a'+c+'b'
        if c in '\n\t':assert f.body_text(s,'text',fail=g._fail,max_len=100)==s
        else:
            with pytest.raises(ValueError,match='LINT:bad_chars:text'):f.body_text(s,'text',fail=g._fail,max_len=100)
        count+=1
    print('control_cases',count)
    for c in ['é','中','😀','\u00a0','\u2000']:
        assert f.body_text('x'+c,'text',fail=g._fail,max_len=10)=='x'+c

def test_strict_types_blank_order_limits_and_controls():
    class S(str):pass
    for x in [None,True,0,[],{},S('abc')]:
        with pytest.raises(ValueError,match='bad_type:text'):g.emit('e',x,channel='ui',now=T)
    for s in ['',' ','\t','\n','\r\n']:
        with pytest.raises(ValueError,match='empty_field:text'):g.emit('e',s,channel='ui',now=T)
    for s in ['x'*16385,'x'*16383+'\r\n']:
        with pytest.raises(ValueError,match='text_too_long:text'):g.emit('e',s,channel='ui',now=T)
    for s in ['a\r\nb','a\n\tb','a\r\n\r\nb','x'*16384]:
        _,r=g.emit('e',s,channel='ui',now=T);assert r['text_sha256']==hashlib.sha256(s.encode()).hexdigest()
    for s in ['x\r','x\ry','x\r\r\ny']:
        with pytest.raises(ValueError,match='bad_chars:text'):g.emit('e',s,channel='ui',now=T)
    for field in ['channel','emission_id']:
        for c in ['\r\n','\n','\t']:
            kw=dict(emission_id='e',body='okay',channel='ui',now=T);kw[field]='x'+c+'y'
            with pytest.raises(ValueError,match='bad_chars:'+field):g.emit(**kw)

def test_precedence_lower_expansion_and_nonclaims():
    for s in ['İ\r\n ATLAS\tIS\tAN\tAGI; i am sentient','i am\nsentient then i am sentient','İ i am\tALIVE','Atlas is not sentient.\nno claims','i am\u00a0sentient','NOTHING\r\nHERE']:
        assert g.lint(s)==oracle(s)
