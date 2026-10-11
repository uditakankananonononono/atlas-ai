"""Closed lexical classification only. No building, planning or effects."""
from __future__ import annotations

from datetime import date
import re
import unicodedata
from app.modules.c30 import policy

_SEND = {'send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'}
_SPEND = {'pay','purchase','spend','buy','checkout','card_number'}
_PHYSICAL = {'execute','build_physical','order','manufacture','ship'}
_EFFECT = {'post','publish','deploy','register'}
_CREDS = {'login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd'}
_KEYWORDS = {
    'physical': {'toy','aircraft','hotel','building','robot','vehicle','device','furniture','bridge','drone'},
    'software': {'tool','app','script','api','website','bot','program','plugin','dashboard','scraper'},
    'document': {'spec','plan','report','guide','brief','proposal','essay','outline'},
}


def _refuse(reason, field=None):
    raise ValueError('VENT_REFUSED_' + reason + (':' + field if field else ''))


def _key_scan(value):
    keys, nonstring, active = set(), False, set()
    if len(value)>32:_refuse('OVERSIZE','request')
    rows=value.get('requests')
    if type(rows) is list:
        if len(rows)>1000:_refuse('OVERSIZE','requests')
        for row in rows:
            if type(row) is dict:
                if len(row)>32:_refuse('OVERSIZE','request')
                for field,cap in (('id',128),('text',2000),('kind_hint',200)):
                    v=row.get(field)
                    if type(v) is str and len(v)>cap:_refuse('OVERSIZE',field)
    day=value.get('as_of')
    if type(day) is str and len(day)>10:_refuse('OVERSIZE','as_of')
    stack=[(value,0,False,32)];nodes=0
    while stack:
        v,depth,leaving,cap=stack.pop()
        if leaving:active.remove(id(v));continue
        if type(v) in (dict,list,tuple):nodes+=1
        if nodes>10000 or depth>32:_refuse('OVERSIZE','request')
        if type(v) not in (dict,list,tuple):continue
        if len(v)>cap:_refuse('OVERSIZE','request')
        if id(v) in active:_refuse('BAD_TYPE','request')
        active.add(id(v));stack.append((v,depth,True,cap))
        if type(v) is dict:
            for k,item in reversed(list(v.items())):
                if type(k) is str:
                    if len(k)>200:_refuse('OVERSIZE','key')
                    if any(unicodedata.category(c) in {'Cc','Cf','Zl','Zp'} for c in k):_refuse('CONTROL_CHARS','key')
                    keys.add(k.casefold().replace('-', '_'))
                else:nonstring=True
                limit=1000 if depth==0 and k=='requests' and type(item) is list else (32 if type(item) is dict else 64)
                stack.append((item,depth+1,False,limit))
        else:
            stack.extend((item,depth+1,False,32 if type(item) is dict else 64) for item in reversed(v))
    for group, reason in ((_SEND,'SEND'),(_SPEND,'SPEND'),(_PHYSICAL|_EFFECT,'unit'),(_CREDS,'NOCREDS')):
        found = sorted(keys & group)
        if found:
            key = found[0]
            if reason == 'unit':
                reason = 'PHYSICAL_BUILD' if key in _PHYSICAL else 'EFFECT'
            _refuse(reason, key)
    if nonstring:
        _refuse('BAD_TYPE', 'key')


def _nested_keys(value):
    stack, seen = [value], set()
    while stack:
        v = stack.pop()
        if type(v) not in (dict, list, tuple) or id(v) in seen:
            continue
        seen.add(id(v))
        if type(v) is dict:
            if v:
                return True
        else:
            stack.extend(v)
    return False


def _unknown(request):
    if set(request) - {'as_of','requests'}:
        _refuse('UNKNOWN','request')
    rows = request.get('requests')
    if type(rows) is list:
        for row in rows:
            if type(row) is dict and set(row) - {'id','text','kind_hint'}:
                _refuse('UNKNOWN','requests')
            if type(row) is dict:
                for field, value in row.items():
                    if _nested_keys(value):
                        _refuse('UNKNOWN',field)
            elif _nested_keys(row):
                _refuse('UNKNOWN','requests')
    if _nested_keys(request.get('as_of')):
        _refuse('UNKNOWN','as_of')


def _validate(request):
    if type(request) is not dict:
        _refuse('BAD_TYPE','request')
    _key_scan(request)
    _unknown(request)
    day = request.get('as_of')
    if type(day) is not str or re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', day) is None:
        _refuse('BAD_TYPE','as_of')
    try:
        date.fromisoformat(day)
    except ValueError:
        _refuse('BAD_TYPE','as_of')
    rows = request.get('requests')
    if type(rows) is not list:
        _refuse('BAD_TYPE','requests')
    if not rows:
        _refuse('EMPTY')
    if len(rows) > 1000:
        _refuse('OVERSIZE','requests')
    for row in rows:
        if type(row) is dict:
            for field, cap in (('id',128),('text',2000)):
                if type(row.get(field)) is str and len(row[field]) > cap:
                    _refuse('OVERSIZE',field)
    policy.clean_text(day,'VENT','as_of',10)
    seen = set()
    for row in rows:
        if type(row) is not dict:
            _refuse('BAD_TYPE','requests')
        for field, cap in (('id',128),('text',2000)):
            if type(row.get(field)) is not str:
                _refuse('BAD_TYPE',field)
            policy.clean_text(row[field],'VENT',field,cap)
        if row['id'] in seen:
            _refuse('BAD_TYPE','requests')
        seen.add(row['id'])
        hint = row.get('kind_hint')
        if type(hint) is str:policy.clean_text(hint,'VENT','kind_hint',200)
        if hint is not None and (type(hint) is not str or hint not in _KEYWORDS):
            _refuse('BAD_TYPE','kind_hint')
    return rows


def run(request):
    """Classify supplied text with a closed whole-word table, preserving order."""
    rows = _validate(request)
    routes = []
    coverage = dict(requests=len(rows),software=0,document=0,physical=0,unclassified=0)
    for row in rows:
        words = set(re.findall(r'\w+', row['text'].casefold()))
        matched = [kind for kind in ('physical','software','document') if words & _KEYWORDS[kind]]
        kind = matched[0] if matched else 'unclassified'
        hint = row.get('kind_hint')
        route = dict(id=row['id'],kind=kind,reason='keyword' if matched else 'no_keyword',
                     multiple_classes=len(matched)>1,hint_conflict=hint is not None and bool(matched) and hint != kind)
        if kind == 'physical':
            route.update(allowed=['spec','bom','safety_note'],build=False)
        routes.append(route)
        coverage[kind] += 1
    return dict(routes=routes,coverage=coverage,
                scope=policy.scope(['closed keyword classification','physical-build key refusal','computed class counts'],
                                   ['feasibility','planning','artifacts','tool selection','approval','effects'],
                                   'supplied request text',request['as_of']))
