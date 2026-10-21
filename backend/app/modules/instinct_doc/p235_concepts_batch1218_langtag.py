"""b1218 RFC 5646 (BCP 47) language-tag syntax: well-formed tags only (section 2.1 ABNF).
language_tag_ok(tag) -> bool: True when the tag is well-formed (a langtag, a private use tag or one of the 26 grandfathered tags of section 2.1). Tags are ASCII, compared without regard to case (section 2.1.1) and never trimmed. An exact str of 1..255 characters is checked; a non-str raises bad_type:tag and a longer str raises bad_value:tag.length before any scan. Other bad text returns False.
parse_language_tag(tag) -> dict with the keys kind, language, extlangs, script, region, variants, extensions, privateuse, grandfathered, subtags kept in the case given. kind is langtag, privateuse, regular (one of the nine regular grandfathered tags, which also match the langtag production, so their subtags are kept and grandfathered holds the registered form) or irregular (one of the 17 irregular tags: only grandfathered is set). Bad text raises bad_value:tag.syntax.
format_language_tag(parts) -> str: the section 2.1.1 convention case (script Titlecase, two-letter region uppercase, all else lowercase) for a dict of the parse shape. Every field is checked by type and range, and the dict must be the one parse would give for that text.
Limits: tags and formatted tags are at most 255 characters (OURS, section 4.4 asks for at least 35); a tuple field longer than 255 is refused before it is walked.
Errata on RFC 5646 (3 records on errata.json): EID 8711 Held for Document Update Technical section 3.1.5, EID 8712 Held for Document Update Technical section 3.5 (both about the Latin script wording of Description fields, registry text this module does not use) and EID 5457 Reported Technical section 2.2.9 (validity text; this module checks well-formedness only). None is applied. RFC 5234 has 12 errata records (EID 1423 2820 2914 2968 3076 3096 4040 4361 4564 5110 6172 6173); none is applied.
Extended language subtags follow the language only when it is 2 or 3 letters and number at most three (section 2.2.2); duplicate variants, duplicate singletons and registry membership are validity, not well-formedness, and are not checked.
"""
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:
        raise

    def make_fail(name):
        """Fallback used only when the shared registry module is absent: return a failer for the named function."""
        def fail(code):
            """Raise ValueError with the P235 name and code."""
            raise ValueError('P235:%s:%s' % (name, code))
        return fail
CLAIMS = False
SCOPE = 'PARTIAL: RFC 5646 section 2.1 well-formed language tags over caller text, no registry lookup and no validity checking'
NOT_CLAIMED = ('registry validity', 'duplicate variant or singleton checks', 'canonicalization to preferred values', 'RFC 4647 matching or lookup', 'production readiness')
ADJACENT = ('b1062 RFC 8187 ext-value language field, a looser own grammar', 'RFC 4647 language ranges', 'RFC 7231 Accept-Language')
MAX_TAG = 255
_ALPHA = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
_DIGIT = '0123456789'
_ALNUM = _ALPHA + _DIGIT
_TAGCHARS = _ALNUM + '-'
_KEYS = ('kind', 'language', 'extlangs', 'script', 'region', 'variants', 'extensions', 'privateuse', 'grandfathered')
_GRAND = {'en-gb-oed': ('irregular', 'en-GB-oed'), 'i-ami': ('irregular', 'i-ami'), 'i-bnn': ('irregular', 'i-bnn'), 'i-default': ('irregular', 'i-default'), 'i-enochian': ('irregular', 'i-enochian'), 'i-hak': ('irregular', 'i-hak'), 'i-klingon': ('irregular', 'i-klingon'), 'i-lux': ('irregular', 'i-lux'), 'i-mingo': ('irregular', 'i-mingo'), 'i-navajo': ('irregular', 'i-navajo'), 'i-pwn': ('irregular', 'i-pwn'), 'i-tao': ('irregular', 'i-tao'), 'i-tay': ('irregular', 'i-tay'), 'i-tsu': ('irregular', 'i-tsu'), 'sgn-be-fr': ('irregular', 'sgn-BE-FR'), 'sgn-be-nl': ('irregular', 'sgn-BE-NL'), 'sgn-ch-de': ('irregular', 'sgn-CH-DE'), 'art-lojban': ('regular', 'art-lojban'), 'cel-gaulish': ('regular', 'cel-gaulish'), 'no-bok': ('regular', 'no-bok'), 'no-nyn': ('regular', 'no-nyn'), 'zh-guoyu': ('regular', 'zh-guoyu'), 'zh-hakka': ('regular', 'zh-hakka'), 'zh-min': ('regular', 'zh-min'), 'zh-min-nan': ('regular', 'zh-min-nan'), 'zh-xiang': ('regular', 'zh-xiang')}


def _all_in(text, allowed):
    """True when every character of the exact str is in allowed (an empty str is True)."""
    for ch in text:
        if ch not in allowed:
            return False
    return True


def _is_variant(sub):
    """True for 5 to 8 alphanumerics, or a digit then 3 alphanumerics (section 2.1 variant)."""
    if 5 <= len(sub) <= 8:
        return _all_in(sub, _ALNUM)
    return len(sub) == 4 and sub[0] in _DIGIT and _all_in(sub, _ALNUM)


def _mk(kind, language, extlangs, script, region, variants, extensions, privateuse, grandfathered):
    """Build the result dict in the fixed key order."""
    return {'kind': kind, 'language': language, 'extlangs': extlangs, 'script': script, 'region': region, 'variants': variants, 'extensions': extensions, 'privateuse': privateuse, 'grandfathered': grandfathered}


def _langtag(subs):
    """Match the langtag or privateuse production on the split subtags; return the result dict or None."""
    n = len(subs)
    first = subs[0]
    if first == 'x' or first == 'X':
        if n < 2:
            return None
        for sub in subs[1:]:
            if not 1 <= len(sub) <= 8 or not _all_in(sub, _ALNUM):
                return None
        return _mk('privateuse', None, (), None, None, (), (), tuple(subs[1:]), None)
    if not 2 <= len(first) <= 8 or not _all_in(first, _ALPHA):
        return None
    i = 1
    extlangs = []
    if len(first) <= 3:
        while i < n and len(extlangs) < 3 and len(subs[i]) == 3 and _all_in(subs[i], _ALPHA):
            extlangs.append(subs[i])
            i += 1
    script = None
    if i < n and len(subs[i]) == 4 and _all_in(subs[i], _ALPHA):
        script = subs[i]
        i += 1
    region = None
    if i < n and ((len(subs[i]) == 2 and _all_in(subs[i], _ALPHA)) or (len(subs[i]) == 3 and _all_in(subs[i], _DIGIT))):
        region = subs[i]
        i += 1
    variants = []
    while i < n and _is_variant(subs[i]):
        variants.append(subs[i])
        i += 1
    extensions = []
    while i < n and len(subs[i]) == 1 and subs[i] != 'x' and subs[i] != 'X' and _all_in(subs[i], _ALNUM):
        singleton = subs[i]
        i += 1
        body = []
        while i < n and 2 <= len(subs[i]) <= 8 and _all_in(subs[i], _ALNUM):
            body.append(subs[i])
            i += 1
        if not body:
            return None
        extensions.append((singleton, tuple(body)))
    private = []
    if i < n and (subs[i] == 'x' or subs[i] == 'X'):
        if i + 1 >= n:
            return None
        for sub in subs[i + 1:]:
            if not 1 <= len(sub) <= 8 or not _all_in(sub, _ALNUM):
                return None
        private = subs[i + 1:]
        i = n
    if i != n:
        return None
    return _mk('langtag', first, tuple(extlangs), script, region, tuple(variants), tuple(extensions), tuple(private), None)


def _parse(tag):
    """Parse an exact str already length-checked; return the result dict or None."""
    if tag == '' or not _all_in(tag, _TAGCHARS):
        return None
    found = _GRAND.get(tag.lower())
    if found is not None and found[0] == 'irregular':
        return _mk('irregular', None, (), None, None, (), (), (), found[1])
    parsed = _langtag(tag.split('-'))
    if parsed is not None and found is not None:
        parsed['kind'] = 'regular'
        parsed['grandfathered'] = found[1]
    return parsed


def _arg(fail, tag):
    """Check the exact type and the length cap of a tag argument."""
    if type(tag) is not str:
        fail('bad_type:tag')
    if len(tag) > MAX_TAG:
        fail('bad_value:tag.length')


def language_tag_ok(tag):
    """True when the exact str is a well-formed RFC 5646 language tag."""
    fail = make_fail('language_tag_ok')
    _arg(fail, tag)
    return _parse(tag) is not None


def parse_language_tag(tag):
    """Return the parsed fields of a well-formed language tag; refuse any other text."""
    fail = make_fail('parse_language_tag')
    _arg(fail, tag)
    parsed = _parse(tag)
    if parsed is None:
        fail('bad_value:tag.syntax')
    return parsed


def _sub(fail, field, value, lo, hi, allowed):
    """Check one subtag: exact str, lo..hi characters, all in allowed."""
    if type(value) is not str:
        fail('bad_type:parts.' + field)
    if not lo <= len(value) <= hi or not _all_in(value, allowed):
        fail('bad_value:parts.' + field)


def _tup(fail, field, value, low):
    """Check an exact tuple field and its length cap; return its length."""
    if type(value) is not tuple:
        fail('bad_type:parts.' + field)
    if len(value) > MAX_TAG:
        fail('bad_value:parts.' + field + '.length')
    if len(value) < low:
        fail('bad_value:parts.' + field)
    return len(value)


def format_language_tag(parts):
    """Render a parse-shaped dict in the section 2.1.1 convention case; refuse anything parse would not give."""
    fail = make_fail('format_language_tag')
    if type(parts) is not dict:
        fail('bad_type:parts')
    if len(parts) != len(_KEYS):
        fail('bad_value:parts.keys')
    for key in parts:
        if type(key) is not str:
            fail('bad_type:parts.key')
    for key in _KEYS:
        if key not in parts:
            fail('bad_value:parts.keys')
    kind = parts['kind']
    if type(kind) is not str:
        fail('bad_type:parts.kind')
    if kind not in ('langtag', 'privateuse', 'regular', 'irregular'):
        fail('bad_value:parts.kind')
    gf = parts['grandfathered']
    if kind == 'irregular' or kind == 'regular':
        if type(gf) is not str:
            fail('bad_type:parts.grandfathered')
        if len(gf) > MAX_TAG or not _all_in(gf, _TAGCHARS):
            fail('bad_value:parts.grandfathered')
        entry = _GRAND.get(gf.lower())
        if entry is None or entry[0] != kind or entry[1] != gf:
            fail('bad_value:parts.grandfathered')
    elif gf is not None:
        fail('bad_value:parts.grandfathered')
    if kind == 'irregular':
        if parts['language'] is not None or parts['script'] is not None or parts['region'] is not None:
            fail('bad_value:parts.language')
        for key in ('extlangs', 'variants', 'extensions', 'privateuse'):
            if type(parts[key]) is not tuple:
                fail('bad_type:parts.' + key)
            if len(parts[key]) != 0:
                fail('bad_value:parts.' + key)
        return gf
    out = []
    if kind == 'privateuse':
        if parts['language'] is not None or parts['script'] is not None or parts['region'] is not None:
            fail('bad_value:parts.language')
        for key in ('extlangs', 'variants', 'extensions'):
            if type(parts[key]) is not tuple:
                fail('bad_type:parts.' + key)
            if len(parts[key]) != 0:
                fail('bad_value:parts.' + key)
    else:
        language = parts['language']
        _sub(fail, 'language', language, 2, 8, _ALPHA)
        out.append(language.lower())
        extlangs = parts['extlangs']
        count = _tup(fail, 'extlangs', extlangs, 0)
        if count > 3 or (count > 0 and len(language) > 3):
            fail('bad_value:parts.extlangs')
        for sub in extlangs:
            _sub(fail, 'extlangs', sub, 3, 3, _ALPHA)
            out.append(sub.lower())
        script = parts['script']
        if script is not None:
            _sub(fail, 'script', script, 4, 4, _ALPHA)
            out.append(script[0].upper() + script[1:].lower())
        region = parts['region']
        if region is not None:
            if type(region) is not str:
                fail('bad_type:parts.region')
            if not ((len(region) == 2 and _all_in(region, _ALPHA)) or (len(region) == 3 and _all_in(region, _DIGIT))):
                fail('bad_value:parts.region')
            out.append(region.upper())
        variants = parts['variants']
        _tup(fail, 'variants', variants, 0)
        for sub in variants:
            if type(sub) is not str:
                fail('bad_type:parts.variants')
            if not _is_variant(sub):
                fail('bad_value:parts.variants')
            out.append(sub.lower())
        extensions = parts['extensions']
        _tup(fail, 'extensions', extensions, 0)
        for ext in extensions:
            if type(ext) is not tuple:
                fail('bad_type:parts.extensions')
            if len(ext) != 2:
                fail('bad_value:parts.extensions')
            singleton = ext[0]
            _sub(fail, 'extensions', singleton, 1, 1, _ALNUM)
            if singleton == 'x' or singleton == 'X':
                fail('bad_value:parts.extensions')
            body = ext[1]
            _tup(fail, 'extensions', body, 1)
            out.append(singleton.lower())
            for sub in body:
                _sub(fail, 'extensions', sub, 2, 8, _ALNUM)
                out.append(sub.lower())
    private = parts['privateuse']
    _tup(fail, 'privateuse', private, 1 if kind == 'privateuse' else 0)
    if len(private) > 0:
        out.append('x')
        for sub in private:
            _sub(fail, 'privateuse', sub, 1, 8, _ALNUM)
            out.append(sub.lower())
    text = '-'.join(out)
    if len(text) > MAX_TAG:
        fail('bad_value:tag.length')
    entry = _GRAND.get(text.lower())
    if kind == 'regular':
        if entry is None or entry[1] != gf:
            fail('bad_value:parts.grandfathered')
    elif entry is not None:
        fail('bad_value:parts.kind')
    return text
