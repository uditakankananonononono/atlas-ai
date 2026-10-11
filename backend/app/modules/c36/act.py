"""S5.8 supplied ideas to proposed tickets. Offline, no external effects."""
from datetime import date
import unicodedata
from app.modules.c30 import policy

PREFIX = 'VENT'
TABLES = (
    ('SEND', frozenset({'send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'})),
    ('SPEND', frozenset({'pay','purchase','spend','buy','checkout','card_number'})),
    ('EFFECT', frozenset({'act','execute','run','launch','publish','post','deploy','register','build','upload'})),
    ('NOCREDS', frozenset({'login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd'})),
)
FIELDS = {'id':128, 'title':200, 'body':4000, 'category':200}
COLLECTIONS = {'acceptance':(10,300), 'concepts':(20,100)}
CATEGORIES = ('entrepreneurship','aesthetic','cute','other')
TEMPLATES = ('Output exists and is readable.', 'Owner has reviewed the output.', 'No spend, send or account action occurred.')


def fail(code):
    raise ValueError(PREFIX+'_REFUSED_'+code)


def cap(value, limit, field):
    if len(value)>limit:
        fail('OVERSIZE:'+field)


def _children(node):
    return node.items() if type(node) is dict else enumerate(node)


def _admit(node, field, context, depth, active, budget):
    if depth>32:
        fail('OVERSIZE:request')
    if type(node) not in (dict,list,tuple):
        if isinstance(node,(dict,list,tuple)):
            fail('BAD_TYPE:'+field)
        return
    budget[0]+=1
    if budget[0]>10000:
        fail('OVERSIZE:request')
    if id(node) in active:
        fail('BAD_TYPE:request')
    limit=32 if type(node) is dict else 64
    if type(node) in (list,tuple):
        if context=='ideas':limit=2000
        if context in COLLECTIONS:limit=COLLECTIONS[context][0]
    cap(node,limit,field if type(node) in (list,tuple) and context in ('ideas','acceptance','concepts') else 'request')
    if type(node) is dict:
        for key in node:
            if type(key) is not str:fail('BAD_TYPE:key')
            cap(key,200,'key')
            if any(unicodedata.category(c) in ('Cc','Cf','Zl','Zp') for c in key):fail('CONTROL_CHARS:key')
    active.add(id(node))
    for key,child in _children(node):
        child_context='generic';child_field=field
        if type(node) is dict:
            if context=='root' and key=='ideas':child_context='ideas';child_field='ideas'
            elif context=='idea' and key in COLLECTIONS:child_context=key;child_field=key
        elif context=='ideas':child_context='idea';child_field='ideas'
        _admit(child,child_field,child_context,depth+1,active,budget)
    active.remove(id(node))


def _raw_caps(request):
    value=request.get('as_of')
    if type(value) is str:cap(value,10,'as_of')
    ideas=request.get('ideas')
    if type(ideas) is not list:return
    cap(ideas,2000,'ideas')
    for row in ideas:
        if type(row) is not dict:continue
        for field,limit in FIELDS.items():
            value=row.get(field)
            if type(value) is str:cap(value,limit,field)
        for field,(count,limit) in COLLECTIONS.items():
            value=row.get(field)
            if type(value) is list:
                cap(value,count,field)
                for item in value:
                    if type(item) is str:cap(item,limit,field)


def _forbidden(node, found):
    if type(node) is dict:
        for key,child in node.items():
            found.add(key.casefold().replace('-','_'))
            _forbidden(child,found)
    elif type(node) in (list,tuple):
        for child in node:_forbidden(child,found)


def _has_keys(node):
    if type(node) is dict:
        return bool(node) or any(_has_keys(child) for child in node.values())
    if type(node) in (list,tuple):return any(_has_keys(child) for child in node)
    return False


def clean(value,field,limit):
    if type(value) is not str:fail('BAD_TYPE:'+field)
    cap(value,limit,field)
    return policy.clean_text(value,PREFIX,field,limit)


def run(request):
    if type(request) is not dict:fail('BAD_TYPE:request')
    _admit(request,'request','root',0,set(),[0])
    _raw_caps(request)
    found=set();_forbidden(request,found)
    for reason,table in TABLES:
        hits=sorted(found & table)
        if hits:fail(reason+':'+hits[0])
    if set(request)-{'as_of','ideas'}:fail('UNKNOWN:request')
    ideas=request.get('ideas')
    if type(ideas) is list:
        for row in ideas:
            if type(row) is dict:
                if set(row)-set(FIELDS)-set(COLLECTIONS):fail('UNKNOWN:ideas')
                for field,value in row.items():
                    if _has_keys(value):fail('UNKNOWN:'+field)
    as_of=clean(request.get('as_of'),'as_of',10)
    try:parsed=date.fromisoformat(as_of)
    except ValueError:fail('BAD_TYPE:as_of')
    if parsed.isoformat()!=as_of:fail('BAD_TYPE:as_of')
    if type(ideas) is not list:fail('BAD_TYPE:ideas')
    if not ideas:fail('EMPTY')
    ids=set();admitted=[]
    for row in ideas:
        if type(row) is not dict:fail('BAD_TYPE:ideas')
        values={field:clean(row.get(field),field,limit) for field,limit in FIELDS.items()}
        if values['category'] not in CATEGORIES:fail('UNKNOWN:category')
        if values['id'] in ids:fail('BAD_TYPE:ideas')
        ids.add(values['id'])
        for field,(count,limit) in COLLECTIONS.items():
            value=row.get(field)
            if value is None:value=[]
            if type(value) is not list:fail('BAD_TYPE:'+field)
            cap(value,count,field)
            values[field]=[clean(item,field,limit) for item in value]
        admitted.append(values)
    merged={};duplicates=0
    for row in admitted:
        key=' '.join(row['title'].casefold().split())
        if key not in merged:
            merged[key]=dict(row,concepts=set(row['concepts']),acceptance=list(dict.fromkeys(row['acceptance'])))
        else:
            duplicates+=1;first=merged[key];first['concepts'].update(row['concepts'])
            for criterion in row['acceptance']:
                if criterion not in first['acceptance']:first['acceptance'].append(criterion)
    tickets=[]
    for rank,row in enumerate(sorted(merged.values(),key=lambda r:(CATEGORIES.index(r['category']),r['id'])),1):
        criteria=([{'text':text,'status':'supplied'} for text in row['acceptance']] if row['acceptance'] else [{'text':text,'status':'TO_WRITE'} for text in TEMPLATES])
        tickets.append({'ticket_id':'S58-'+row['id'],'title':row['title'],'category':row['category'],'body':row['body'],'concepts':sorted(row['concepts']),'acceptance_tests':criteria,'status':'proposed','needs_her_review':True,'rank':rank})
    return {'tickets':tickets,'counts':{'supplied':len(ideas),'tickets':len(tickets),'merged_duplicate':duplicates},'scope':policy.scope(['supplied idea title merge and category/id-ordered proposed tickets'],['execution','sending','spending','publishing','building','feasibility validation','routes'],'supplied-ideas',as_of)}
