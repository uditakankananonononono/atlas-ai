"""Row 700 Semantic Versioning (scoped).

Finite SUPPLIED API signature snapshots -> breaking / additive /
no-public-change diff plus an EXACT next-semver recommendation.

Scope: declared API shapes only. This compares caller-supplied signature
snapshots; it says nothing about runtime behavior or compatibility. Caller
change labels are reported as claims, never used as evidence. No publishing,
no release authority, no persistence, no network. All inputs are bounded;
every refusal carries a stable machine-readable error code.
"""
import re

MAX_COMPONENT = 2**53 - 1  # exact-arithmetic bound for version components
MAX_SYMBOLS = 1024
MAX_PARAMS = 64
MAX_NAME = 200

_VERSION_RE = re.compile(
    r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
    r'(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)'
    r'(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?'
    r'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z')

_PARAM_KINDS = ('positional', 'keyword')
_OVERALL_LABELS = {'breaking', 'additive', 'none'}
_SYMBOL_LABELS = {'breaking', 'additive', 'identical'}
_CLASS_TO_LABEL = {
    'removed': 'breaking', 'modified-breaking': 'breaking',
    'added': 'additive', 'modified-additive': 'additive',
    'identical': 'identical'}
_BREAKING_CLASSES = {'removed', 'modified-breaking'}
_ADDITIVE_CLASSES = {'added', 'modified-additive'}
PRERELEASE_TREATMENT = 'development-line-core-bump'
SCOPE = 'declared-api-shapes-only'


class SemverError(ValueError):
    """Refusal with a stable machine-readable code."""

    def __init__(self, code, message):
        super().__init__(f'{code}: {message}')
        self.code = code


def parse_version(text):
    """Strict semver 2.0.0 parse with an exact component bound.

    Returns (major, minor, patch, prerelease, build). Refuses leading zeros,
    malformed shapes, and components above MAX_COMPONENT (E_VERSION_PARSE).
    """
    if not isinstance(text, str):
        raise SemverError('E_VERSION_PARSE', 'version must be a string')
    m = _VERSION_RE.fullmatch(text)
    if not m:
        raise SemverError('E_VERSION_PARSE', f'invalid semantic version: {text!r}')
    major, minor, patch = (int(g) for g in m.group(1, 2, 3))
    for comp in (major, minor, patch):
        if comp > MAX_COMPONENT:
            raise SemverError('E_VERSION_PARSE',
                              f'component {comp} exceeds exact bound {MAX_COMPONENT}')
    return major, minor, patch, m.group(4), m.group(5)


def _check_text(value, what):
    if not isinstance(value, str) or not value or len(value) > MAX_NAME:
        raise SemverError('E_SCHEMA', f'{what} must be a string of 1..{MAX_NAME} chars')


def _validate_snapshot(snapshot, side):
    if not isinstance(snapshot, dict) or set(snapshot) != {'symbols'}:
        raise SemverError('E_SCHEMA', f'{side} snapshot must be an object with exactly a symbols list')
    symbols = snapshot['symbols']
    if not isinstance(symbols, list) or len(symbols) > MAX_SYMBOLS:
        raise SemverError('E_SCHEMA', f'{side} symbols must be a list of 0..{MAX_SYMBOLS} entries')
    seen = set()
    for s in symbols:
        if not isinstance(s, dict) or set(s) != {'name', 'kind', 'signature'}:
            raise SemverError('E_SCHEMA', f'{side} symbol must have exactly name/kind/signature')
        _check_text(s['name'], f'{side} symbol name')
        if s['name'] in seen:
            raise SemverError('E_SCHEMA', f'{side} duplicate symbol name {s["name"]!r}')
        seen.add(s['name'])
        if s['kind'] != 'function':
            raise SemverError('E_SCHEMA', f'{side} symbol {s["name"]!r}: only kind function is supported')
        sig = s['signature']
        if not isinstance(sig, dict) or set(sig) != {'params', 'returns'}:
            raise SemverError('E_SCHEMA', f'{side} symbol {s["name"]!r}: signature must have exactly params/returns')
        params = sig['params']
        if not isinstance(params, list) or len(params) > MAX_PARAMS:
            raise SemverError('E_SCHEMA', f'{side} symbol {s["name"]!r}: params must be a list of 0..{MAX_PARAMS}')
        pnames = set()
        for p in params:
            if not isinstance(p, dict) or set(p) != {'name', 'kind', 'required', 'type'}:
                raise SemverError('E_SCHEMA', f'{side} symbol {s["name"]!r}: param must have exactly name/kind/required/type')
            _check_text(p['name'], f'{side} symbol {s["name"]!r} param name')
            if p['name'] in pnames:
                raise SemverError('E_SCHEMA', f'{side} symbol {s["name"]!r}: duplicate param name {p["name"]!r}')
            pnames.add(p['name'])
            if p['kind'] not in _PARAM_KINDS:
                raise SemverError('E_SCHEMA', f'{side} symbol {s["name"]!r}: param kind must be one of {_PARAM_KINDS}')
            if not isinstance(p['required'], bool):
                raise SemverError('E_SCHEMA', f'{side} symbol {s["name"]!r}: param required must be a bool')
            _check_text(p['type'], f'{side} symbol {s["name"]!r} param type')
        returns = sig['returns']
        if not isinstance(returns, str) or not returns or len(returns) > MAX_NAME:
            raise SemverError('E_SCHEMA', f'{side} symbol {s["name"]!r}: returns must be a string of 1..{MAX_NAME} chars')
    return symbols


def _classify_symbol(base, cand):
    """Class one symbol present on both sides; returns (class, details)."""
    breaking, additive = [], []
    bp, cp = base['signature']['params'], cand['signature']['params']
    bpos = [p for p in bp if p['kind'] == 'positional']
    cpos = [p for p in cp if p['kind'] == 'positional']
    bkw = {p['name']: p for p in bp if p['kind'] == 'keyword'}
    ckw = {p['name']: p for p in cp if p['kind'] == 'keyword'}
    # Positional params are an ordered calling convention: compare by position.
    common = min(len(bpos), len(cpos))
    for i in range(common):
        b, c = bpos[i], cpos[i]
        if b['name'] != c['name']:
            breaking.append(f"positional-renamed-or-reordered:index{i}:{b['name']}->{c['name']}")
            continue
        if b['type'] != c['type']:
            breaking.append(f"param-type-changed:{b['name']}")
        if b['required'] and not c['required']:
            additive.append(f"param-made-optional:{b['name']}")
        if c['required'] and not b['required']:
            breaking.append(f"param-made-required:{b['name']}")
    for p in bpos[common:]:
        breaking.append(f"positional-removed:{p['name']}")
    for p in cpos[common:]:
        (additive if not p['required'] else breaking).append(
            f"param-added-{'optional' if not p['required'] else 'required'}:{p['name']}")
    # Keyword params are matched by name; order among them is not observable.
    for name in bkw.keys() - ckw.keys():
        breaking.append(f'param-removed:{name}')
    for name in ckw.keys() - bkw.keys():
        p = ckw[name]
        (additive if not p['required'] else breaking).append(
            f"param-added-{'optional' if not p['required'] else 'required'}:{name}")
    for name in bkw.keys() & ckw.keys():
        b, c = bkw[name], ckw[name]
        if b['type'] != c['type']:
            breaking.append(f'param-type-changed:{name}')
        if b['required'] and not c['required']:
            additive.append(f'param-made-optional:{name}')
        if c['required'] and not b['required']:
            breaking.append(f'param-made-required:{name}')
    if base['signature']['returns'] != cand['signature']['returns']:
        breaking.append(
            f"return-type-changed:{base['signature']['returns']}->{cand['signature']['returns']}")
    if breaking:
        return 'modified-breaking', sorted(breaking + additive)
    if additive:
        return 'modified-additive', sorted(additive)
    return 'identical', []


def _diff_symbols(baseline, candidate):
    bmap = {s['name']: s for s in baseline}
    cmap = {s['name']: s for s in candidate}
    changes = []
    for name in sorted(bmap.keys() | cmap.keys()):
        if name not in cmap:
            changes.append({'name': name, 'change': 'removed', 'details': ['symbol-removed']})
        elif name not in bmap:
            changes.append({'name': name, 'change': 'added', 'details': ['symbol-added']})
        else:
            cls, details = _classify_symbol(bmap[name], cmap[name])
            changes.append({'name': name, 'change': cls, 'details': details})
    return changes


def _label_conflicts(labels, level, changes):
    """Caller labels are claims: validated, reported, never consulted."""
    if labels is None:
        return []
    if not isinstance(labels, dict) or set(labels) - {'overall', 'symbols'}:
        raise SemverError('E_SCHEMA', 'caller_labels may only carry overall/symbols')
    conflicts = []
    overall = labels.get('overall')
    if overall is not None:
        if overall not in _OVERALL_LABELS:
            raise SemverError('E_SCHEMA', f'unknown overall label {overall!r}')
        if overall != {'breaking': 'breaking', 'additive': 'additive', 'no-public-change': 'none'}[level]:
            conflicts.append(f'caller-overall:{overall}!={level}')
    symlabels = labels.get('symbols')
    if symlabels is not None:
        if not isinstance(symlabels, dict):
            raise SemverError('E_SCHEMA', 'caller_labels.symbols must be an object')
        class_by_name = {c['name']: c['change'] for c in changes}
        for name, lab in symlabels.items():
            if lab not in _SYMBOL_LABELS:
                raise SemverError('E_SCHEMA', f'unknown symbol label {lab!r}')
            if name not in class_by_name:
                raise SemverError('E_SCHEMA', f'label for unknown symbol {name!r}')
            if _CLASS_TO_LABEL[class_by_name[name]] != lab:
                conflicts.append(f'symbol:{name}:label-{lab}!={class_by_name[name]}')
    return sorted(conflicts)


def diff_api_snapshots(current_version, baseline_snapshot, candidate_snapshot, caller_labels=None):
    """Diff two supplied API signature snapshots and recommend the next semver.

    Deterministic and pure: identical inputs give byte-identical output and
    the result is independent of symbol order. Raises SemverError with
    E_VERSION_PARSE / E_SCHEMA / E_OVERFLOW on refusal.
    """
    major, minor, patch, _pre, _build = parse_version(current_version)
    baseline = _validate_snapshot(baseline_snapshot, 'baseline')
    candidate = _validate_snapshot(candidate_snapshot, 'candidate')
    changes = _diff_symbols(baseline, candidate)
    classes = {c['change'] for c in changes}
    if classes & _BREAKING_CLASSES:
        level, bump = 'breaking', 'major'
        if major >= MAX_COMPONENT:
            raise SemverError('E_OVERFLOW', f'major bump from {MAX_COMPONENT} exceeds exact bound')
        nxt = f'{major + 1}.0.0'
    elif classes & _ADDITIVE_CLASSES:
        level, bump = 'additive', 'minor'
        if minor >= MAX_COMPONENT:
            raise SemverError('E_OVERFLOW', f'minor bump from {MAX_COMPONENT} exceeds exact bound')
        nxt = f'{major}.{minor + 1}.0'
    else:
        level, bump = 'no-public-change', 'patch'
        if patch >= MAX_COMPONENT:
            raise SemverError('E_OVERFLOW', f'patch bump from {MAX_COMPONENT} exceeds exact bound')
        nxt = f'{major}.{minor}.{patch + 1}'
    return {
        'method': 'semantic_versioning_diff',
        'current_version': current_version,
        'stable_core': f'{major}.{minor}.{patch}',
        'prerelease_treatment': PRERELEASE_TREATMENT,
        'diff': level,
        'bump': bump,
        'next_version': nxt,
        'symbol_changes': changes,
        'counts': {
            'removed': sum(1 for c in changes if c['change'] == 'removed'),
            'added': sum(1 for c in changes if c['change'] == 'added'),
            'modified_breaking': sum(1 for c in changes if c['change'] == 'modified-breaking'),
            'modified_additive': sum(1 for c in changes if c['change'] == 'modified-additive'),
            'identical': sum(1 for c in changes if c['change'] == 'identical'),
        },
        'label_conflicts': _label_conflicts(caller_labels, level, changes),
        'scope': SCOPE,
        'human_review_required': True,
    }


def analyze(d):
    """Adapter for the software_practice_685_709 dispatcher (integrator wiring).

    Expects current_version, baseline_snapshot, candidate_snapshot and an
    optional caller_labels. Kept here so the integrator's wiring patch stays a
    one-line delegation.
    """
    if not isinstance(d, dict):
        raise SemverError('E_SCHEMA', 'payload must be an object')
    for key in ('current_version', 'baseline_snapshot', 'candidate_snapshot'):
        if key not in d:
            raise SemverError('E_SCHEMA', f'missing field {key}')
    return diff_api_snapshots(d['current_version'], d['baseline_snapshot'],
                              d['candidate_snapshot'], caller_labels=d.get('caller_labels'))
