"""C3: finite supplied-data reasoning pipeline, not human-mind replication.

No network, model, tool execution, account access, or side effects. Source text
is data, never executable instructions. Facts remain caller assertions.
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit

MAX_TEXT = 20000
MAX_ROWS = 128
MAX_REQUIREMENTS = 32
STAGES = ['requirements', 'advice_search', 'tool_selection', 'outline', 'draft', 'authenticity', 'critique']
FIELDS = {'goal', 'requirements_text', 'advice_sources', 'tools', 'facts', 'evidence_map', 'draft_claims', 'action', 'as_of'}


class Refusal(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(code + ': ' + detail)


def refuse(reason, detail):
    raise Refusal('FLEET_REFUSED_' + reason, detail)


def c3_policy(packet):
    """Fail closed: this unit only prepares a draft, even with approval tokens."""
    action = packet.get('action', 'draft')
    if not isinstance(action, str):
        refuse('SCHEMA', 'action must be text')
    codes = {'send': 'OUTREACH', 'submit': 'OUTREACH', 'spend': 'SPEND',
             'auto_post': 'AUTOPOST', 'fake_account': 'FAKEACCT', 'trade': 'TRADE', 'scrape': 'SCRAPE'}
    if action in codes:
        raise Refusal('POLICY_REFUSED_' + codes[action], 'C3 cannot execute external actions')
    if action != 'draft':
        refuse('ACTION', 'only draft preparation is supported')


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        refuse('SCHEMA', label + ' must be nonempty text')
    if len(value) > MAX_TEXT:
        refuse('LIMIT', label + ' exceeds text cap')
    return value.strip()


def rows(value, label):
    if not isinstance(value, list):
        refuse('SCHEMA', label + ' must be a list')
    if len(value) > MAX_ROWS:
        refuse('LIMIT', label + ' exceeds row cap')
    if any(not isinstance(r, dict) for r in value):
        refuse('SCHEMA', label + ' entries must be objects')
    return value


def tokens(value):
    stop = {'a', 'an', 'the', 'and', 'or', 'to', 'of', 'in', 'for', 'i', 'my', 'is', 'with', 'should'}
    return set(re.findall(r'[a-z0-9]+', value.lower())) - stop


def references(value, known, label):
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        refuse('SCHEMA', label + ' must be string IDs')
    if len(value) > MAX_ROWS:
        refuse('LIMIT', label + ' exceeds reference cap')
    if len(set(value)) != len(value):
        refuse('DUPLICATE', label + ' contains duplicate IDs')
    if not set(value) <= known:
        refuse('REFERENCE', label + ' contains unknown IDs')
    return value


def unique(bank, ident, label):
    if ident in bank:
        refuse('DUPLICATE', 'duplicate ' + label + ' id')


def run(packet):
    if not isinstance(packet, dict) or not set(packet) <= FIELDS:
        refuse('SCHEMA', 'expected C3 object with documented fields only')
    try:
        encoded = json.dumps(packet, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        refuse('SCHEMA', 'packet must be finite JSON data')
    if len(encoded) > 1000000:
        refuse('LIMIT', 'packet exceeds one million characters')
    # This call is mandatory and intentionally easy to mutation-audit.
    c3_policy(packet)
    goal = text(packet.get('goal'), 'goal')
    if isinstance(packet.get('requirements_text'), str) and not packet['requirements_text'].strip():
        refuse('REQUIREMENTS', 'at least one explicit requirement is needed')
    raw_requirements = text(packet.get('requirements_text'), 'requirements_text')
    as_of = packet.get('as_of')
    if as_of is not None:
        as_of = text(as_of, 'as_of')
    requirement_texts = list(dict.fromkeys(line.strip(' \t-*') for line in raw_requirements.splitlines() if line.strip(' \t-*')))
    if not requirement_texts:
        refuse('REQUIREMENTS', 'at least one explicit requirement is needed')
    if len(requirement_texts) > MAX_REQUIREMENTS:
        refuse('LIMIT', 'requirements exceed cap')
    requirements = [{'id': 'r' + str(i + 1), 'text': line, 'origin': 'requirements_text'}
                    for i, line in enumerate(requirement_texts)]
    facts = {}
    for row in rows(packet.get('facts', []), 'facts'):
        ident = text(row.get('id'), 'fact ID'); unique(facts, ident, 'fact')
        facts[ident] = {'id': ident, 'text': text(row.get('text'), 'fact text'),
                        'source_id': text(row.get('source_id'), 'fact source'), 'truth_verified': False}
    sources = {}
    for row in rows(packet.get('advice_sources', []), 'advice_sources'):
        ident = text(row.get('id'), 'advice ID'); unique(sources, ident, 'advice')
        if row.get('access') not in ('public', 'user_supplied'):
            raise Refusal('POLICY_REFUSED_SCRAPE', 'only public or explicitly supplied advice is accepted')
        url = text(row.get('url'), 'advice URL')
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
        except ValueError:
            refuse('SOURCE', 'invalid advice URL')
        if parsed.scheme != 'https' or not host or parsed.username or parsed.password:
            refuse('SOURCE', 'advice URL must be credential-free HTTPS')
        sources[ident] = {'id': ident, 'url': url, 'text': text(row.get('text'), 'advice text'),
                          'as_of': text(row.get('as_of'), 'advice as_of'), 'untrusted_data': True}
    mapping = packet.get('evidence_map', {})
    if not isinstance(mapping, dict) or not set(mapping) <= {r['id'] for r in requirements}:
        refuse('REFERENCE', 'evidence_map must reference extracted requirement IDs')
    for key, ids in mapping.items():
        references(ids, set(facts), key + ' facts')
    tools = {}; rejected = []
    for row in rows(packet.get('tools', []), 'tools'):
        ident = text(row.get('id'), 'tool ID'); unique(tools, ident, 'tool')
        caps = row.get('capabilities')
        if not isinstance(caps, list) or len(caps) > MAX_ROWS:
            refuse('SCHEMA', 'tool capabilities must be a bounded list')
        captext = ' '.join(text(c, 'capability') for c in caps)
        cost = row.get('cost')
        free = type(cost) in (int, float) and cost == 0
        tools[ident] = {'id': ident, 'capabilities': caps, 'free': free,
                        'matches': [r['id'] for r in requirements if tokens(captext) & tokens(r['text'])]}
        if not free:
            rejected.append({'id': ident, 'reason': 'paid_or_unverified_cost'})
    stages = []

    def log(stage, output, source_refs):
        stages.append({'stage': stage, 'output': output, 'source_refs': source_refs})

    log('requirements', requirements, ['requirements_text'])
    advice = []
    for req in requirements:
        ranked = sorted(((len(tokens(req['text']) & tokens(s['text'])), sid) for sid, s in sources.items()),
                        key=lambda pair: (-pair[0], pair[1]))
        matches = [sid for score, sid in ranked if score > 0][:3]
        advice.append({'requirement_id': req['id'], 'source_ids': matches,
                       'excerpts': [{'source_id': sid, 'url': sources[sid]['url'], 'text': sources[sid]['text'],
                                    'as_of': sources[sid]['as_of'], 'untrusted_data': sources[sid]['untrusted_data']} for sid in matches],
                       'method': 'token_overlap_on_supplied_text', 'untrusted_data': True})
    log('advice_search', advice, sorted(sources))
    selected = sorted((tool for tool in tools.values() if tool['free'] and tool['matches']),
                      key=lambda t: (-len(t['matches']), t['id']))
    selection = {'selected_ids': [t['id'] for t in selected], 'matches': {t['id']: t['matches'] for t in selected},
                 'rejected': rejected, 'executed': False, 'costs_independently_verified': False}
    log('tool_selection', selection, sorted(tools))
    outline = [{'requirement_id': r['id'], 'heading': r['text'], 'fact_ids': list(mapping.get(r['id'], [])),
                'advice_source_ids': advice[i]['source_ids']} for i, r in enumerate(requirements)]
    log('outline', outline, sorted(facts))
    proposed = packet.get('draft_claims')
    if proposed is None:
        claim_ids = list(dict.fromkeys(fid for section in outline for fid in section['fact_ids']))
        claims = [{'text': facts[fid]['text'], 'fact_ids': [fid]} for fid in claim_ids]
    else:
        claims = []
        for row in rows(proposed, 'draft_claims'):
            claim = text(row.get('text'), 'claim text')
            ids = references(row.get('fact_ids'), set(facts), 'claim facts')
            # Conservative extractive support, not a model's opinion about truth.
            if not ids or any(claim != facts[fid]['text'] for fid in ids):
                refuse('FABRICATE', 'claim must equal an attributed supplied fact')
            claims.append({'text': claim, 'fact_ids': ids})
    by_fact = {fid: [] for fid in facts}
    for claim in claims:
        for fid in claim['fact_ids']:
            if claim['text'] == facts[fid]['text']:
                by_fact[fid].append(claim['text'])
    parts = []; missing = []
    for section in outline:
        claimtexts = list(dict.fromkeys(c for fid in section['fact_ids'] for c in by_fact[fid]))
        if not claimtexts:
            missing.append(section['requirement_id'])
            claimtexts = ['[Evidence needed for ' + section['requirement_id'] + ']']
        parts.append(section['heading'] + '\n' + ' '.join(claimtexts))
    draft = '\n\n'.join(parts)
    log('draft', {'text': draft, 'claims': claims, 'status': 'review_required'}, sorted(facts))
    authenticity = {'method': 'exact_fact_attribution', 'unsupported_claims': [],
                    'source_truth_verified': False, 'user_review_required': True,
                    'fact_ids_used': sorted(fid for fid, values in by_fact.items() if values)}
    log('authenticity', authenticity, authenticity['fact_ids_used'])
    critique = {'missing_requirements': missing,
                'requirements_without_advice': [a['requirement_id'] for a in advice if not a['source_ids']],
                'unused_facts': sorted(set(facts) - set(authenticity['fact_ids_used'])),
                'review_questions': ['Confirm the supplied facts are true.', 'Check the draft against the original requirements.',
                                     'Revise the extractive wording in your own voice.'],
                'limitations': ['Exact attribution does not establish relevance or truth.',
                                'Advice and tool metadata were not fetched or verified.']}
    log('critique', critique, [r['id'] for r in requirements])
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    return {'unit': 'C3', 'goal': goal, 'status': 'needs_facts' if missing else 'draft_for_review',
            'input_sha256': digest, 'requirements': requirements, 'advice': advice, 'tool_selection': selection,
            'outline': outline, 'draft': draft, 'authenticity': authenticity, 'critique': critique, 'stages': stages,
            'coverage': {'requirements': len(requirements), 'supported': len(requirements) - len(missing), 'unsupported': len(missing)},
            'scope': {'implemented': STAGES[:], 'not_implemented': ['live search', 'tool execution', 'human mind replication',
                        'generative prose', 'independent fact verification', 'sending or submission'],
                      'data_source': 'caller-supplied requirements, advice, tool metadata and fact assertions',
                      'as_of': as_of, 'source_truth_verified': False, 'human_mind_replication': False},
            'validation': 'external_validator_pending'}
