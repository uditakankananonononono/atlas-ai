"""Owner-profile to observed-form-field prefill planning for student platforms.

Pure and deterministic. It only maps profile keys onto field descriptors that were
read from the live page (M13 inspect). It never invents selectors, never fills
credential, government-id, payment or free-text essay fields, and never submits:
its output feeds StudentBrowser.stage, then M02's per-application approval.

Binding integrity: M13 stage() does NOT trust our selector choice. It re-matches
every non-password descriptor against the approved data keys with
match_fields_detailed. So every planned key is simulated through that same
function; a key is kept only if stage would bind it to exactly the intended
selector and to nothing else. Anything else fails closed and is reported.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from app.modules.m13_browser_agent.forms import FieldDescriptor, match_fields_detailed
from app.modules.m13_browser_agent.value_guard import forbidden_value  # noqa: F401  (shared guard; re-exported)

_ALIASES = {
    'full_name': {'full name', 'name', 'fullname', 'your name'},
    'first_name': {'first name', 'firstname', 'given name'},
    'last_name': {'last name', 'lastname', 'surname', 'family name'},
    'email': {'email', 'email address', 'e mail'},
    'phone': {'phone', 'phone number', 'mobile', 'mobile number', 'telephone'},
    'school': {'school', 'school name', 'high school', 'college', 'university', 'institution'},
    'graduation_year': {'graduation year', 'grad year', 'year of graduation', 'expected graduation'},
    'city': {'city', 'town'},
    'country': {'country'},
    'github_url': {'github', 'github url', 'github profile'},
    'linkedin_url': {'linkedin', 'linkedin url', 'linkedin profile'},
    'website': {'website', 'portfolio', 'portfolio url', 'personal website'},
}
# Withheld even if present on the page and in the profile: owner types these.
_WITHHELD = re.compile(r'password|passcode|\bssn\b|social security|aadhaar|passport|card number|cvv|iban|'
                       r'bank|date of birth|\bdob\b|birth|gender|ethnic|race|religion|income|essay|statement|why', re.I)
# Fields about somebody or something other than the owner, or a different entity.
_OTHER_PARTY = re.compile(r'guardian|parent|mother|father|recommend|referee|reference|teacher|counsel+or|mentor|'
                          r'advisor|adviser|emergency|sponsor|supervisor|principal|team|project|organi[sz]ation|'
                          r'company|employer|club|event|hackathon|spouse|partner|sibling', re.I)
_SKIP_TYPES = {'password', 'checkbox', 'radio', 'select', 'file', 'hidden', 'textarea', 'submit', 'button'}

def _norm(text: str) -> str:
    return ' '.join(re.findall(r'[a-z0-9]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', text or '').lower().replace('_', ' ')))


def _texts(d: dict) -> tuple[set[str], set[str]]:
    """(match texts, all texts). The HTML name attribute is only used when the page gives no
    visible label or placeholder, so name='name' cannot override a 'Team name' label."""
    label = {_norm(d.get(k, '')) for k in ('label', 'placeholder')} - {''}
    name = {_norm(d.get('name', ''))} - {''}
    ctx = {_norm(d.get('context', ''))} - {''}
    return (label or name), (label | name | ctx)


def descriptor_digest(descriptors: Iterable[dict]) -> str:
    """Digest of the exact page descriptors a plan was made from; stage compares it to a fresh extraction."""
    rows = [{k: d.get(k, '') for k in ('selector', 'label', 'name', 'placeholder', 'input_type', 'required', 'context')}
            for d in descriptors]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def plan_token(page_url: str, descriptors: Iterable[dict], fields: dict, submit_selector: str) -> str:
    """Binds page URL + exact descriptors + exact field values + submit selector. Stage recomputes it
    from a fresh inspect, so any drift in page, fields or submit control refuses the stage."""
    blob = json.dumps({'url': page_url, 'descriptors': descriptor_digest(descriptors),
                       'fields': {k: fields[k] for k in sorted(fields)}, 'submit': submit_selector}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _stage_binding(descriptors: list[dict], data: dict[str, str]) -> dict[str, str]:
    """Exactly what M13 stage() would bind: every non-password descriptor, fuzzy-matched."""
    fields = [FieldDescriptor(selector=d['selector'], label=d.get('label', ''), name=d.get('name', ''),
                              placeholder=d.get('placeholder', ''), input_type=(d.get('input_type') or 'text'),
                              required=bool(d.get('required')))
              for d in descriptors if (d.get('input_type') or 'text') != 'password']
    mapping, _ = match_fields_detailed(fields, data)
    return mapping


def plan_prefill(profile: dict[str, Any], descriptors: Iterable[dict]) -> dict[str, Any]:
    """Return a plan; 'fields' is keyed by canonical profile key, never by page selector.

    Keys that stage() would bind to a different/extra field, or two fields claiming one key,
    are dropped and listed in 'binding_conflicts'. Nothing ambiguous is filled.
    """
    descriptors = list(descriptors)
    wanted, refused_values = {}, []
    for key, aliases in _ALIASES.items():
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            if forbidden_value(key, value):
                refused_values.append(key)
                continue
            wanted[key] = (value.strip(), {_norm(a) for a in aliases})
    claims: dict[str, list[dict]] = {}
    unlabeled_email: list[dict] = []
    withheld, other_party, unmatched_required, unmatched_optional = [], [], [], []
    for d in descriptors:
        match_texts, all_texts = _texts(d)
        itype = (d.get('input_type') or 'text').lower()
        if itype in _SKIP_TYPES or any(_WITHHELD.search(t) for t in all_texts):
            withheld.append(d['selector'])
            continue
        if any(_OTHER_PARTY.search(t) for t in all_texts):
            other_party.append(d['selector'])
            continue
        hit = next((k for k, (_, al) in wanted.items() if match_texts & al), None)
        if hit is None and itype == 'email' and 'email' in wanted and not (all_texts - {''}):
            unlabeled_email.append(d)  # decided below: only if it is the page's single non-other-party email control
            continue
        if hit is None:
            (unmatched_required if d.get('required') else unmatched_optional).append(d['selector'])
        else:
            claims.setdefault(hit, []).append(d)
    # An unlabeled email control is the owner's only if no other email-typed control (other than
    # excluded other-party ones) is on the page. The drop is scoped to those fields, not to the key.
    other = set(other_party)
    email_typed = [d for d in descriptors if (d.get('input_type') or '').lower() == 'email' and d['selector'] not in other]
    for d in unlabeled_email:
        if len(email_typed) == 1:
            claims.setdefault('email', []).append(d)
        else:
            (unmatched_required if d.get('required') else unmatched_optional).append(d['selector'])
    candidate, conflicts = {}, []
    for key, ds in claims.items():
        if len(ds) > 1:
            conflicts += [{'key': key, 'selector': d['selector'], 'reason': 'two fields claim this key'} for d in ds]
            for d in ds:
                (unmatched_required if d.get('required') else unmatched_optional).append(d['selector'])
            continue
        candidate[key] = ds[0]
    # Simulate stage() per key, then together. Keep only exact intended bindings.
    def exact(keys):
        data = {k: wanted[k][0] for k in keys}
        got = _stage_binding(descriptors, data)
        return {sel: val for sel, val in got.items()}, data
    kept = []
    for key, d in candidate.items():
        got, _ = exact([key])
        if got == {d['selector']: wanted[key][0]}:
            kept.append(key)
        else:
            conflicts.append({'key': key, 'selector': d['selector'], 'reason': 'stage would bind ' + str(sorted(got)) + ' not the intended field'})
            (unmatched_required if d.get('required') else unmatched_optional).append(d['selector'])
    while kept:
        got, _ = exact(kept)
        expected = {candidate[k]['selector']: wanted[k][0] for k in kept}
        if got == expected:
            break
        bad = [k for k in kept if got.get(candidate[k]['selector']) != wanted[k][0]] or kept[-1:]
        for k in bad:
            kept.remove(k)
            conflicts.append({'key': k, 'selector': candidate[k]['selector'], 'reason': 'combined stage binding differs from plan'})
    fields = {k: wanted[k][0] for k in kept}
    matched = {candidate[k]['selector']: k for k in kept}
    return {'fields': fields, 'matched': matched, 'withheld': withheld, 'other_party': other_party,
            'refused_value_keys': refused_values, 'binding_conflicts': conflicts,
            'unmatched_required': sorted(set(unmatched_required)),
            'unmatched_optional': sorted(set(unmatched_optional)), 'submitted': False,
            'descriptor_digest': descriptor_digest(descriptors)}
