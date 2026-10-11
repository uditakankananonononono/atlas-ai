"""Closed local citation component schemas, not a legal citation style guide."""
from __future__ import annotations

import re

PREFIX = 'CITE1287: '
SCHEMAS = {
    'reporter_case': ({'case_name','volume','reporter','page','court','year'}, {'pinpoint'}),
    'neutral_case': ({'case_name','year','court_code','number'}, {'paragraph'}),
    'codified_section': ({'code_title','section'}, {'year'}),
}


def _refuse(message):
    raise ValueError(PREFIX + message)


def _text(value, field):
    if (not isinstance(value,str) or not value.strip() or len(value)>500 or
            any(ord(c)<32 or ord(c)==127 for c in value)):
        _refuse(field + ' must be text of 1..500 characters without controls')
    return re.sub(r' +',' ',value.strip())


def _integer(value, field, maximum=9999999):
    if type(value) is not int or not 1 <= value <= maximum:
        _refuse(field + f' must be an integer in 1..{maximum}')
    return value


def normalize_citation(data: dict) -> dict:
    """Validate components and render a deterministic local-schema citation.

    No source lookup, legal-authority validation, style compliance or advice.
    """
    if not isinstance(data,dict):_refuse('input must be an object')
    format_name=data.get('format')
    if not isinstance(format_name,str) or format_name not in SCHEMAS:
        _refuse('unsupported format')
    required,optional=SCHEMAS[format_name]
    if any(not isinstance(k,str) for k in data):_refuse('field names must be strings')
    unknown=set(data)-required-optional-{'format'}
    if unknown:_refuse('unknown fields: '+', '.join(sorted(unknown)))
    missing=required-set(data)
    if missing:_refuse('missing fields: '+', '.join(sorted(missing)))
    components={}
    for field in sorted(required|optional):
        if field not in data:continue
        if field=='year':components[field]=_integer(data[field],field,9999)
        elif field in {'volume','page','pinpoint','number','paragraph'}:
            components[field]=_integer(data[field],field)
        else:components[field]=_text(data[field],field)
    if format_name=='neutral_case':
        if not re.fullmatch(r'[A-Z][A-Z0-9]{0,19}',components['court_code']):
            _refuse('court_code must match [A-Z][A-Z0-9]{0,19}')
    if format_name=='codified_section':
        if not re.fullmatch(r'[0-9A-Za-z]+(?:[.\-][0-9A-Za-z]+)*(?:\([0-9A-Za-z]+\))*',components['section']):
            _refuse('section must be an alphanumeric local section token')
    x=components
    if format_name=='reporter_case':
        normalized=f"{x['case_name']}, {x['volume']} {x['reporter']} {x['page']}"
        if 'pinpoint' in x:normalized+=f", {x['pinpoint']}"
        normalized+=f" ({x['court']} {x['year']})"
    elif format_name=='neutral_case':
        normalized=f"{x['case_name']}, {x['year']} {x['court_code']} {x['number']}"
        if 'paragraph' in x:normalized+=f" [{x['paragraph']}]"
    else:
        normalized=f"{x['code_title']} § {x['section']}"
        if 'year' in x:normalized+=f" ({x['year']})"
    return {'format':format_name,'components':components,'normalized':normalized,
            'status':'local_syntax_only','authority_verified':False,
            'style_compliant':False,'counsel_review_required':True}
