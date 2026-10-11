"""S3.4 supplied-industry hierarchy audit. Pure offline, no industry creation."""
from __future__ import annotations

import json
import math
import re
from app.modules.c30 import policy

PREFIX = 'PROTO'
MAX_TAXONOMY = 1024
MAX_NEEDS = 1024
MAX_CAPABILITIES = 256
MAX_TOUCHED = 4096
STOPWORDS = frozenset('a an the and or of to in on for with is are was were it its by from as at be this that'.split())
_WORD = re.compile(r'[a-z0-9]+')


def _refuse(reason):
    raise ValueError('PROTO_REFUSED_' + reason)


def _text(value, name, limit=256):
    return policy.clean_text(value, PREFIX, name, limit)


def _list(value, name, cap):
    if not isinstance(value, list):
        _refuse('BAD_TYPE:' + name)
    if len(value) > cap:
        _refuse('BAD_TYPE:' + name + '_size')
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1 or not math.isfinite(value):
        _refuse('BAD_TYPE:' + name)
    return value


def _terms(text):
    return set(_WORD.findall(text.lower())) - STOPWORDS


def _percent(n, d):
    return round(100 * n / d, 1)


def _canonical(value):
    def rounded(item):
        if isinstance(item, float):
            return round(item, 6)
        if isinstance(item, dict):
            return {k: rounded(v) for k, v in item.items()}
        if isinstance(item, list):
            return [rounded(v) for v in item]
        return item
    value = rounded(value)
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))


def run(request):
    """Audit supplied coverage, needs and lexical draft candidates; execute nothing."""
    required = {'taxonomy', 'touched', 'needs', 'capabilities', 'min_gap_severity'}
    if not isinstance(request, dict):
        _refuse('BAD_TYPE:request')
    if not required <= set(request) or set(request) - required - {'as_of', 'coverage_assertion'}:
        _refuse('BAD_TYPE:request_fields')
    tax = request['taxonomy']
    if not isinstance(tax, list) or not tax:
        _refuse('NOTAXONOMY')
    _list(tax, 'taxonomy', MAX_TAXONOMY)
    nodes = {}
    for row in tax:
        if not isinstance(row, dict) or set(row) != {'code', 'name', 'parent'}:
            _refuse('BAD_TYPE:taxonomy_row')
        code = _text(row['code'], 'code', 128)
        name = _text(row['name'], 'name')
        parent = None if row['parent'] is None else _text(row['parent'], 'parent', 128)
        if code in nodes:
            _refuse('NOTAXONOMY:duplicate')
        nodes[code] = {'code': code, 'name': name, 'parent': parent}
    for node in nodes.values():
        if node['parent'] is not None and node['parent'] not in nodes:
            _refuse('NOTAXONOMY:parent')
    paths = {}
    for code in sorted(nodes):
        chain = []; cur = code
        while cur is not None:
            if cur in chain:
                _refuse('NOTAXONOMY:cycle')
            chain.append(cur); cur = nodes[cur]['parent']
        paths[code] = chain
    depth = {c: len(p) - 1 for c, p in paths.items()}
    parents = {n['parent'] for n in nodes.values() if n['parent'] is not None}
    leaves = set(nodes) - parents
    direct = set(); references = []
    for row in _list(request['touched'], 'touched', MAX_TOUCHED):
        if not isinstance(row, dict) or set(row) != {'code', 'unit_id', 'evidence'}:
            _refuse('BAD_TYPE:touched_row')
        code = _text(row['code'], 'code', 128)
        if code not in nodes:
            _refuse('NOTAXONOMY:touched_code')
        references.append({'code': code, 'unit_id': _text(row['unit_id'], 'unit_id', 128),
                           'evidence': _text(row['evidence'], 'evidence', 2048)})
        direct.add(code)
    rolled = set()
    for code in direct:
        rolled.update(paths[code])
    levels = []
    for d in sorted(set(depth.values())):
        codes = {c for c in nodes if depth[c] == d}; n = len(codes & rolled)
        levels.append({'depth': d, 'touched': n, 'total': len(codes), 'coverage_percent': _percent(n, len(codes))})
    ancestors = []
    for c in sorted(parents):
        subtree = {x for x in nodes if c in paths[x]}; n = len(subtree & rolled)
        ancestors.append({'code': c, 'touched': n, 'total': len(subtree), 'coverage_percent': _percent(n, len(subtree))})
    threshold = _number(request['min_gap_severity'], 'min_gap_severity')
    needs = []; seen = set(); counts = {c: 0 for c in nodes}; excluded = []
    for row in _list(request['needs'], 'needs', MAX_NEEDS):
        if not isinstance(row, dict) or not {'id','text','codes','severity'} <= set(row) or set(row) - {'id','text','codes','severity','evidence_url'}:
            _refuse('BAD_TYPE:need_row')
        nid = _text(row['id'], 'need_id', 128)
        if nid in seen:
            _refuse('BAD_TYPE:need_id')
        seen.add(nid)
        text = _text(row['text'], 'need_text', 2048)
        codes = row['codes']
        if not isinstance(codes, list):
            _refuse('BAD_TYPE:need_codes')
        if not codes:
            _refuse('EMPTY:need_codes')
        parsed = [_text(c, 'need_code', 128) for c in codes]
        if len(parsed) != len(set(parsed)):
            _refuse('BAD_TYPE:need_codes')
        if any(c not in nodes for c in parsed):
            _refuse('NOTAXONOMY:need_code')
        severity = _number(row['severity'], 'severity')
        url = row.get('evidence_url', '')
        url = policy.clean_text(url, PREFIX, 'evidence_url', 2048, allow_blank=True)
        if not url.strip():
            excluded.append({'id': nid, 'code': 'PROTO_REFUSED_NOSOURCE'})
        for c in parsed:
            counts[c] += 1
        needs.append({'id':nid,'text':text,'codes':sorted(parsed),'severity':severity,'evidence_url':url})
    caps = []; seen = set()
    for row in _list(request['capabilities'], 'capabilities', MAX_CAPABILITIES):
        if not isinstance(row, dict) or set(row) != {'id','text'}:
            _refuse('BAD_TYPE:capability_row')
        cid = _text(row['id'], 'capability_id', 128)
        if cid in seen:
            _refuse('BAD_TYPE:capability_id')
        seen.add(cid);caps.append({'id':cid,'text':_text(row['text'],'capability_text',2048)})
    gaps = []
    for need in needs:
        untouched = sorted(set(need['codes']) - rolled)
        if need['severity'] >= threshold and untouched:
            touched = sorted(set(need['codes']) & rolled)
            gaps.append({**need, 'status':'partial_gap' if touched else 'open_gap',
                         'touched_codes':touched,'untouched_codes':untouched,
                         'gap_score':round(need['severity'] * len(untouched) / len(need['codes']),6)})
    gaps.sort(key=lambda g:(-g['gap_score'],g['id']))
    candidates = []; omitted = []
    for need in gaps:
        if not need['evidence_url'].strip():
            continue
        for cap in sorted(caps,key=lambda c:c['id']):
            shared = _terms(need['text']) & _terms(cap['text'])
            if not shared:
                continue
            name = need['text'] + ' / ' + cap['text']
            terms = _terms(need['text']) | _terms(cap['text'])
            matched = []
            for c in sorted(nodes):
                existing = _terms(nodes[c]['name'])
                if terms and existing and (terms <= existing or existing <= terms):
                    matched.append(c)
            candidate = {'name':name,'need_id':need['id'],'capability_id':cap['id'],
                         'codes':need['codes'],'shared_terms':sorted(shared),'key_terms':sorted(terms),
                         'evidence_url':need['evidence_url'],'novelty_verified':False,'industry_created':False,
                         'kind':'keyword_recombination_draft','physical_execution':False}
            if matched:
                omitted.append({**candidate,'code':'OVERCLAIM','matched_taxonomy_codes':matched})
            else:
                candidates.append(candidate)
    candidates.sort(key=lambda c:(c['need_id'],c['capability_id']))
    omitted.sort(key=lambda c:(c['need_id'],c['capability_id']))
    coverage = {'touched':len(rolled),'total':len(nodes),'coverage_percent':_percent(len(rolled),len(nodes))}
    if 'coverage_assertion' in request:
        assertion=request['coverage_assertion']
        if not isinstance(assertion,dict) or set(assertion)!={'word','coverage_percent'} or assertion['word'] not in ('all','every','covered'):
            _refuse('BAD_TYPE:coverage_assertion')
        number=assertion['coverage_percent']
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not 0<=number<=100 or not math.isfinite(number):
            _refuse('BAD_TYPE:coverage_assertion')
        if number != coverage['coverage_percent']:
            _refuse('OVERCLAIM')
    as_of = _text(request['as_of'],'as_of',128) if 'as_of' in request else 'supplied-input'
    return _canonical({'coverage':coverage,'coverage_basis':'supplied taxonomy only; touched references are caller supplied',
        'levels':levels,'leaf_coverage':{'touched':len(leaves & direct),'total':len(leaves),'coverage_percent':_percent(len(leaves & direct),len(leaves))},
        'ancestor_coverage':ancestors,'direct_touched_codes':sorted(direct),'rolled_touched_codes':sorted(rolled),
        'touched_references':sorted(references,key=lambda r:(r['code'],r['unit_id'],r['evidence'])),
        'untouched':[{'code':c,'need_count':counts[c]} for c in sorted(set(nodes)-rolled,key=lambda c:(-counts[c],c))],
        'gaps':gaps,'candidates':candidates,'omitted_candidates':omitted,
        'excluded_candidate_needs':sorted(excluded,key=lambda n:n['id']),'source_evidence_verified':False,
        'scope':policy.scope(['supplied hierarchy coverage','source-indexed supplied need gaps','lexical candidate drafts'],
          ['need discovery','market validation or real new industries','live evidence verification','effects or host routing'],
          'supplied taxonomy, touched references, needs and capabilities',as_of)})
