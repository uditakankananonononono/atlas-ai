"""Fail-closed code-only policy. Payload approvals never authorize execution."""
from urllib.parse import urlsplit
import math

class Refusal(ValueError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(code + (': ' + detail if detail else ''))

EFFECTS = {
    'spend':'POLICY_REFUSED_SPEND', 'trade':'POLICY_REFUSED_TRADE',
    'outreach':'POLICY_REFUSED_OUTREACH', 'file':'INTEL_REFUSED_FILE',
    'install':'PROTO_REFUSED_INSTALL', 'fake_account':'POLICY_REFUSED_FAKEACCT',
    'autopost':'POLICY_REFUSED_AUTOPOST', 'restricted_scrape':'POLICY_REFUSED_SCRAPE',
    'impersonate':'MONEY_REFUSED_IMPERSONATE', 'guarantee_income':'MONEY_REFUSED_GUARANTEE',
}

def guard(payload):
    action = payload.get('action', 'draft')
    if not isinstance(action,str):
        raise Refusal('POLICY_REFUSED_ACTION')
    if action in EFFECTS:
        raise Refusal(EFFECTS[action])
    if action not in {'draft', 'analyze', 'simulate'}:
        raise Refusal('POLICY_REFUSED_ACTION')
    for name, code in EFFECTS.items():
        if payload.get(name):
            raise Refusal(code)
    if not isinstance(payload.get('as_of'), str) or not payload['as_of'].strip():
        raise Refusal('PLAN_REFUSED_ASOF')
    sources = payload.get('sources')
    if not isinstance(sources, list) or not sources or len(sources)>1000:
        raise Refusal('PLAN_REFUSED_NOSOURCE')
    ids=set()
    for source in sources:
        if not isinstance(source,dict) or not isinstance(source.get('id'),str) or not source['id'] or source['id'] in ids:
            raise Refusal('PLAN_REFUSED_SOURCE')
        validate_url(source.get('url',''))
        ids.add(source['id'])
    return {s['id']:s for s in sources}

def validate_url(value):
    if not isinstance(value,str) or len(value)>4096:
        raise Refusal('PLAN_REFUSED_SOURCE')
    try:
        url=urlsplit(value)
        hostname=url.hostname
        port=url.port
    except ValueError as exc:
        raise Refusal('PLAN_REFUSED_SOURCE') from exc
    if url.scheme not in {'https','http'} or not hostname or url.username or url.password:
        raise Refusal('PLAN_REFUSED_SOURCE')
    return value

def number(value, code='PLAN_REFUSED_NUMBER', minimum=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise Refusal(code)
    if minimum is not None and value<minimum: raise Refusal(code)
    return value

def text(value,code='PLAN_REFUSED_INPUT',limit=20000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit: raise Refusal(code)
    return value.strip()

def citation(item,sources):
    if item.get('source_id') not in sources: raise Refusal('PLAN_REFUSED_SOURCE')
    return item['source_id']
