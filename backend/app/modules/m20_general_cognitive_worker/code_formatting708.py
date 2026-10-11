"""Row 708 bounded code-formatting declaration bookkeeping (CODEFO708).

Caller-supplied before/after file contents and a declared style only. The
mechanism reports exact per-file facts (changed or not, hashes, character
counts, whether the change is whitespace-only) and counts declared-style
deviations in the supplied "after" text (line length, trailing whitespace,
indent character and width, line endings, final newline). It never runs a
formatter or any tool, never rewrites code, and claims no semantic
equivalence, idempotence proof or style authority; any request carrying an
execution or authority key is refused with a "CODEFO708:" prefixed ValueError.

Delta vs _format in software_practice_685_709.py:78: that function lists paths
whose raw before/after differ and pins two flags True, with no validation or
bounds. This unit validates and bounds every field, declares the style as
input, reports hashes and exact counts, separates whitespace-only changes,
compares an optional caller-supplied second pass for idempotence evidence, and
pins the non-claims as False.
"""
from __future__ import annotations

import hashlib
import unicodedata

MAX_FILES = 64
MAX_PATH = 256
MAX_NAME = 64
MAX_CONTENT = 100000
MAX_TOTAL = 1000000
MAX_LISTED = 20
MAX_KEYS = 16
MAX_STYLE_KEYS = 16
MAX_FILE_KEYS = 8
MAX_ENUM = 8

_REFUSED_CATEGORIES = ('Cc', 'Cf', 'Zl', 'Zp')
_CONTENT_WS = ('\n', '\r', '\t')

_FIELDS = ('style', 'files')
_EXEC_KEYS = ('run', 'command', 'execute', 'formatter_command', 'apply', 'write', 'commit', 'push')
_CLAIM_KEYS = ('certify', 'approve', 'style_authority', 'release')
_STYLE_KEYS = ('name', 'indent', 'indent_width', 'max_line_length', 'line_ending', 'final_newline')
_FILE_KEYS = ('path', 'before', 'after', 'second_pass')
_FILE_REQUIRED = ('path', 'before', 'after')

LIMITS = [
    'No formatter or other tool is run and no code is rewritten; contents are only what the caller supplied.',
    'Whitespace-only means equal after removing all whitespace; whitespace can be meaningful in some languages, so no semantic equivalence is claimed.',
    'A second pass equal to the after text is caller-supplied evidence; idempotence is not proven here.',
    'Style observations apply the declared style to the after text only; they are not a style authority, lint, or quality claim.',
    'Counts and listings are over supplied text; nothing is verified against any repository, and human review governs any use.',
]


def _fail(msg: str):
    raise ValueError('CODEFO708:' + msg)


def _has_refused_char(value: str, allow_ws: bool = False) -> bool:
    """True when value holds a Cc, Cf, Zl or Zp character (Zs is accepted)."""
    return any(unicodedata.category(c) in _REFUSED_CATEGORIES and not (allow_ws and c in _CONTENT_WS)
               for c in value)


def _is_int(value) -> bool:
    return type(value) is int


def _style(raw) -> dict:
    if type(raw) is not dict:
        _fail('BAD_TYPE:style')
    if len(raw) > MAX_STYLE_KEYS:
        _fail('OVERSIZE:style.keys')
    for key in raw:
        if type(key) is not str or key not in _STYLE_KEYS:
            _fail('UNKNOWN_KEY:style')
    for key in _STYLE_KEYS:
        if key not in raw:
            _fail('MISSING:style.' + key)
    name = raw['name']
    if type(name) is not str:
        _fail('BAD_TYPE:style.name')
    if len(name) > MAX_NAME:
        _fail('OVERSIZE:style.name')
    if not name.strip():
        _fail('BAD_TYPE:style.name')
    if _has_refused_char(name):
        _fail('CONTROL_CHARS:style.name')
    for key, allowed in (('indent', ('spaces', 'tabs')), ('line_ending', ('lf', 'crlf'))):
        value = raw[key]
        if type(value) is not str:
            _fail('BAD_TYPE:style.' + key)
        if len(value) > MAX_ENUM:
            _fail('OVERSIZE:style.' + key)
        if value not in allowed:
            _fail('BAD_STYLE:' + key)
    for key, lo, hi in (('indent_width', 1, 16), ('max_line_length', 20, 400)):
        value = raw[key]
        if not _is_int(value):
            _fail('BAD_TYPE:style.' + key)
        if not lo <= value <= hi:
            _fail('BAD_RANGE:style.' + key)
    if type(raw['final_newline']) is not bool:
        _fail('BAD_TYPE:style.final_newline')
    return {key: raw[key] for key in _STYLE_KEYS}


def _path(value) -> str:
    if type(value) is not str:
        _fail('BAD_TYPE:file.path')
    if len(value) > MAX_PATH:
        _fail('OVERSIZE:path')
    if (not value.strip() or value.startswith('/') or '\\' in value or ':' in value
            or _has_refused_char(value)
            or '..' in value.split('/')):
        _fail('BAD_PATH')
    return value


def _text(value, field) -> str:
    if type(value) is not str:
        _fail('BAD_TYPE:file.' + field)
    if len(value) > MAX_CONTENT:
        _fail('OVERSIZE:content')
    if _has_refused_char(value, allow_ws=True):
        _fail('CONTROL_CHARS:' + field)
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        _fail('ENCODING:' + field)
    return value


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _observe(after: str, st: dict) -> dict:
    lines = after.split('\n')
    last_has_newline = after.endswith('\n')
    if last_has_newline:
        lines.pop()
    found = {'long': [], 'trailing': [], 'indent': [], 'width': [], 'ending': []}
    counts = {key: 0 for key in found}

    def note(kind, number):
        counts[kind] += 1
        if len(found[kind]) < MAX_LISTED:
            found[kind].append(number)

    for index, raw in enumerate(lines, start=1):
        has_ending = last_has_newline or index < len(lines)
        content = raw[:-1] if raw.endswith('\r') else raw
        if has_ending:
            is_crlf = raw.endswith('\r')
            if is_crlf != (st['line_ending'] == 'crlf'):
                note('ending', index)
        if len(content) > st['max_line_length']:
            note('long', index)
        if content != content.rstrip(' \t'):
            note('trailing', index)
        if content.strip(' \t'):
            lead = content[:len(content) - len(content.lstrip(' \t'))]
            if st['indent'] == 'spaces':
                if '\t' in lead:
                    note('indent', index)
                elif len(lead) % st['indent_width']:
                    note('width', index)
            elif ' ' in lead:
                note('indent', index)
    ends = after.endswith('\n')
    final_ok = True if after == '' else ends == st['final_newline']
    has = any(counts.values()) or not final_ok
    return {
        'long_lines': found['long'], 'long_line_count': counts['long'],
        'trailing_whitespace_lines': found['trailing'], 'trailing_whitespace_count': counts['trailing'],
        'indent_mismatch_lines': found['indent'], 'indent_mismatch_count': counts['indent'],
        'indent_width_lines': found['width'], 'indent_width_count': counts['width'],
        'wrong_line_ending_lines': found['ending'], 'wrong_line_ending_count': counts['ending'],
        'final_newline_ok': final_ok,
    }, has


def run(request: dict) -> dict:
    """Report declared before/after facts and declared-style observations; never format."""
    if type(request) is not dict:
        _fail('BAD_TYPE:request')
    if len(request) > MAX_KEYS:
        _fail('OVERSIZE:keys')
    for key in request:
        if type(key) is not str:
            _fail('UNKNOWN_KEY:request')
        if key in _EXEC_KEYS:
            _fail('EXEC_REQUEST:' + _EXEC_KEYS[_EXEC_KEYS.index(key)])
        if key in _CLAIM_KEYS:
            _fail('CLAIM_REQUEST:' + _CLAIM_KEYS[_CLAIM_KEYS.index(key)])
        if key not in _FIELDS:
            _fail('UNKNOWN_KEY:request')
    for key in _FIELDS:
        if key not in request:
            _fail('MISSING:' + key)
    st = _style(request['style'])
    raw_files = request['files']
    if type(raw_files) is not list:
        _fail('BAD_TYPE:files')
    if len(raw_files) > MAX_FILES:
        _fail('OVERSIZE:files')

    entries = []
    seen = set()
    total = 0
    for item in raw_files:
        if type(item) is not dict:
            _fail('BAD_TYPE:file')
        if len(item) > MAX_FILE_KEYS:
            _fail('OVERSIZE:file.keys')
        for key in item:
            if type(key) is not str or key not in _FILE_KEYS:
                _fail('UNKNOWN_KEY:file')
        for key in _FILE_REQUIRED:
            if key not in item:
                _fail('MISSING:file.' + key)
        path = _path(item['path'])
        before = _text(item['before'], 'before')
        after = _text(item['after'], 'after')
        second = _text(item['second_pass'], 'second_pass') if 'second_pass' in item else None
        if path in seen:
            _fail('DUPLICATE:path')
        seen.add(path)
        total += len(before) + len(after) + (len(second) if second is not None else 0)
        entries.append((path, before, after, second))
    if total > MAX_TOTAL:
        _fail('OVERSIZE:total')

    files = []
    changed_paths = []
    counts = {'files': len(entries), 'changed': 0, 'unchanged': 0, 'whitespace_only': 0, 'with_style_findings': 0}
    idem = {'second_pass_equal': 0, 'second_pass_differs': 0, 'second_pass_not_supplied': 0}
    for path, before, after, second in entries:
        changed = before != after
        ws_only = changed and ''.join(before.split()) == ''.join(after.split())
        if second is None:
            state = 'second_pass_not_supplied'
        else:
            state = 'second_pass_equal' if second == after else 'second_pass_differs'
        findings, has = _observe(after, st)
        files.append({
            'path': path, 'changed': changed, 'whitespace_only_change': ws_only,
            'before_sha256': _sha(before), 'after_sha256': _sha(after),
            'before_chars': len(before), 'after_chars': len(after),
            'idempotence': state, 'style_findings': findings, 'has_style_findings': has,
        })
        idem[state] += 1
        if changed:
            counts['changed'] += 1
            changed_paths.append(path)
        else:
            counts['unchanged'] += 1
        if ws_only:
            counts['whitespace_only'] += 1
        if has:
            counts['with_style_findings'] += 1
    return {
        'style': st, 'files': files, 'changed_paths': changed_paths, 'counts': counts,
        'idempotence_counts': idem,
        'formatter_executed': False, 'semantics_verified': False,
        'style_authority': False, 'idempotence_proven': False,
        'limits': list(LIMITS),
    }
