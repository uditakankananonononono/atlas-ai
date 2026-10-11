"""Supplied-section assembly and character-equivalent estimates, not pagination."""
from __future__ import annotations

from collections import Counter
import hashlib
from app.modules.c30 import policy

_CAP = 15_000_000
_BASIS = 3000


def _bad(field):
    raise ValueError('PLAN_REFUSED_BAD_TYPE:' + field)


def _text(value, field, blank=False, body=False):
    if type(value) is not str:
        _bad(field)
    return policy.clean_text(value, 'PLAN', field, _CAP if body else 1000,
                             allow_blank=blank, allow_ws=body)


def _windows(body):
    normalized = ' '.join(body.split())
    return [hashlib.sha256(normalized[i:i+200].encode('utf-8')).digest()
            for i in range(0, len(normalized)-199, 50)]


def _validate(request):
    if type(request) is not dict or set(request) - {'as_of', 'target_pages', 'volumes'}:
        _bad('request')
    _text(request.get('as_of'), 'as_of')
    target = request.get('target_pages', 5000)
    if type(target) is not int or not 0 < target <= 100000:
        _bad('target_pages')
    volumes = request.get('volumes')
    if type(volumes) is not list:
        _bad('volumes')
    if not volumes:
        raise ValueError('PLAN_REFUSED_NOSECTIONS')
    vids, sids, rows = set(), set(), []
    total = 0
    for v in volumes:
        if type(v) is not dict or set(v) != {'id', 'title', 'sections'}:
            _bad('volume')
        _text(v['id'], 'volume_id')
        _text(v['title'], 'title')
        if v['id'] in vids:
            _bad('volume_id')
        vids.add(v['id'])
        if type(v['sections']) is not list:
            _bad('sections')
        for s in v['sections']:
            if type(s) is not dict or set(s) - {'id', 'heading', 'body', 'source_ref'}:
                _bad('section')
            _text(s.get('id'), 'section_id')
            _text(s.get('heading'), 'heading')
            if s['id'] in sids:
                _bad('section_id')
            sids.add(s['id'])
            body, ref = s.get('body', ''), s.get('source_ref', '')
            if type(body) is not str:
                _bad('body')
            total += len(body)
            if total > _CAP:
                _bad('oversize')
            _text(body, 'body', blank=True, body=True)
            _text(ref, 'source_ref', blank=True)
            rows.append((v['id'], s['id'], s['heading'], body, ref))
    if not rows:
        raise ValueError('PLAN_REFUSED_NOSECTIONS')
    return target, rows


def run(request):
    """Return supplied Markdown sections, receipts and explicit estimate shortfall."""
    target, rows = _validate(request)
    windows = {}
    counts = Counter()
    for vi, si, heading, body, ref in rows:
        if body.strip() and ref.strip():
            hashes = _windows(body)
            windows[si] = hashes
            counts.update(hashes)
    receipts, contents, rendered = [], [], {}
    chars, unfilled, excluded = 0, 0, 0
    for vi, si, heading, body, ref in rows:
        if not body.strip() or not ref.strip():
            status, text = 'unfilled', f'[UNFILLED: {heading}]'
            unfilled += 1
        elif any(counts[h] > 3 for h in windows[si]):
            status, text = 'excluded_repetition', f'[EXCLUDED_REPETITION: {heading}]'
            excluded += 1
        else:
            status, text = 'accepted', body.strip()
            chars += len(text)
        rendered[si] = text
        receipts.append(dict(volume_id=vi, section_id=si, heading=heading, source_ref=ref,
                             evidence_verified=False, status=status, accepted_body_chars=len(text) if status=='accepted' else 0))
        contents.append(dict(volume_id=vi, section_id=si, heading=heading))
    if not any(r['status'] == 'accepted' for r in receipts):
        raise ValueError('PLAN_REFUSED_UNSOURCED')
    volumes = []
    for v in request['volumes']:
        lines = [f"# {v['title']}"]
        for s in v['sections']:
            lines.extend(['', f"## {s['heading']}", '', rendered[s['id']]])
        volumes.append(dict(id=v['id'], title=v['title'], markdown='\n'.join(lines)+'\n'))
    estimated = (chars + _BASIS - 1) // _BASIS
    limit = ('Input cap is 15,000,000 body characters, at most 5,000 estimated text pages at 3000 characters each. '
             'Targets above the cap cannot be reached in one call. No 5000+ fulfillment or rendered-page count is claimed.')
    return dict(volumes=volumes, table_of_contents=contents, section_receipts=receipts,
                estimated_text_pages=estimated, target_estimated_text_pages=target,
                estimated_shortfall=max(0, target-estimated), estimate_basis_chars=_BASIS,
                target_exceeds_cap=target*_BASIS > _CAP, accepted_body_chars=chars,
                unfilled_count=unfilled, excluded_count=excluded, estimate_limit=limit,
                scope=policy.scope(['supplied section assembly', 'unfilled and repetition receipts', 'character-equivalent estimate'],
                                   ['content generation', 'source authentication', 'rendered pagination', '5000+ fulfillment', 'effects', 'persistence'],
                                   'caller-supplied sections and unresolved references', request['as_of']))
