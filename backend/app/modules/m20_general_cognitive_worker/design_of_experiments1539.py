"""Row 1539 Design of Experiments: two-level fractional factorial plan structure.

The ledger row has an empty description, so the requirement title is the
whole spec. Delta against engineering_1510_1559.py:180 (_doe): that routine
builds a full factorial run matrix over arbitrary level lists and nothing
else. This unit builds two-level designs, including fractions 2^(k-g) from
caller generators such as D = A*B*C, and derives the defining relation, the
resolution and the alias classes. Plan structure only: no experiment is run,
run order is not randomized, no effect or causal claim is made.
"""
import itertools
import unicodedata

PREFIX = 'DESEXP1539'
MIN_FACTORS, MAX_FACTORS = 2, 12
MAX_GENERATORS = 6
MAX_BASE = 8
MAX_PRODUCT = 8
MAX_TEXT = 128
_BAD_FORMAT = frozenset(list(range(0x200B, 0x2010)) + list(range(0x202A, 0x202F))
                        + list(range(0x2066, 0x206A)) + [0xFEFF])

BOUNDARY = ('Plan structure only: coded two-level run matrix in standard order, defining '
            'relation, resolution and alias classes derived from the supplied generators. '
            'No experiment is run or scheduled, run order is not randomized, and no effect '
            'size, significance or causal claim is made.')


def _fail(code, message):
    raise ValueError(f'{PREFIX}: {code + ": " if code else ""}{message}')


def _unsafe_char(c):
    return unicodedata.category(c) in ('Cc', 'Zl', 'Zp') or ord(c) == 127 or ord(c) in _BAD_FORMAT


def _text(value, code, subject, plural, extra=None):
    """Length cap first, then the Unicode check; refusals name the field, never the value."""
    blank = f"{subject} require non-blank text without '*'" if plural else f'{subject} requires non-blank text'
    if type(value) is not str:
        _fail(code, blank)
    if len(value) > MAX_TEXT:
        _fail(code, f'{subject} {"exceed" if plural else "exceeds"} {MAX_TEXT} characters')
    if not value.strip() or (extra and extra in value):
        _fail(code, blank)
    if any(_unsafe_char(c) for c in value):
        _fail(code, f'{subject} {"contain" if plural else "contains"} disallowed characters')
    return value


def _product(product, declared):
    """List type, then length cap, then minimum; entries are exact text matched against the declared set."""
    if type(product) is not list:
        _fail('invalid_product_of', 'product_of requires a list')
    if len(product) > MAX_PRODUCT:
        _fail('invalid_count', f'product_of exceeds {MAX_PRODUCT} entries')
    if len(product) < 2:
        _fail('invalid_count', 'product_of requires at least 2 entries')
    for entry in product:
        if type(entry) is not str:
            _fail('invalid_product_of', 'product_of entries require text')
        if len(entry) > MAX_TEXT:
            _fail('invalid_product_of', f'product_of entries exceed {MAX_TEXT} characters')
        if any(_unsafe_char(c) for c in entry):
            _fail('invalid_product_of', 'product_of entries contain disallowed characters')
        if entry not in declared:
            _fail('invalid_product_of', 'product_of entries require declared factors')
    if len(set(product)) != len(product):
        _fail('invalid_product_of', 'product_of entries require distinct factors')


def _generators(payload, factors):
    raw = payload.get('generators', [])
    if type(raw) is not list or len(raw) > MAX_GENERATORS:
        _fail(None, f'generators requires a list of 0..{MAX_GENERATORS} records')
    generated = {}
    for row in raw:
        if type(row) is not dict:
            _fail(None, 'generator requires an object')
        if any(k not in ('factor', 'product_of') for k in row):
            _fail(None, 'unknown key in generator')
        factor = row.get('factor')
        if type(factor) is not str or factor not in factors:
            _fail(None, 'generator factor is not a declared factor')
        if factor in generated:
            _fail(None, 'duplicate generator factor')
        generated[factor] = row.get('product_of')
    declared = frozenset(factors)
    for factor, product in generated.items():
        _product(product, declared)
        if any(x in generated for x in product):
            _fail(None, 'product_of may only use base factors')
    return generated


def plan_two_level_design(payload):
    if type(payload) is not dict:
        _fail(None, 'payload requires an object')
    if any(k not in ('design_id', 'factors', 'generators') for k in payload):
        _fail(None, 'unknown key in payload')
    design_id = _text(payload.get('design_id'), 'invalid_design_id', 'design_id', False)
    factors = payload.get('factors')
    if type(factors) is not list or not MIN_FACTORS <= len(factors) <= MAX_FACTORS:
        _fail(None, f'factors requires a list of {MIN_FACTORS}..{MAX_FACTORS} names')
    seen = set()
    for f in factors:
        _text(f, 'invalid_factor', 'factor names', True, '*')
        if f in seen:
            _fail(None, 'duplicate factor name')
        seen.add(f)
    generated = _generators(payload, factors)
    base = [f for f in factors if f not in generated]
    if len(base) > MAX_BASE:
        _fail(None, f'base factors require at most {MAX_BASE} non-generated factors')
    order = {f: i for i, f in enumerate(factors)}

    def label(word):
        return '*'.join(sorted(word, key=order.get))

    def sort_key(word):
        return (len(word), sorted(order[f] for f in word))

    matrix = []
    for n in range(2 ** len(base)):
        row = {f: (1 if (n >> i) & 1 else -1) for i, f in enumerate(base)}
        for f in factors:
            if f in generated:
                value = 1
                for x in generated[f]:
                    value *= row[x]
                row[f] = value
        matrix.append({f: row[f] for f in factors})
    generator_words = [frozenset([f] + generated[f]) for f in factors if f in generated]
    subgroup = set()
    for size in range(1, len(generator_words) + 1):
        for combo in itertools.combinations(generator_words, size):
            word = frozenset()
            for w in combo:
                word = word ^ w
            subgroup.add(word)
    words = sorted(subgroup, key=sort_key)
    resolution = min((len(w) for w in subgroup), default=None)
    classes = set()
    effects = [frozenset(c) for n in (1, 2) for c in itertools.combinations(factors, n)]
    for effect in effects:
        members = {effect} | {effect ^ w for w in subgroup}
        members = [m for m in members if 1 <= len(m) <= 2]
        if len(members) >= 2:
            classes.add(tuple(sorted(members, key=sort_key)))
    ordered = sorted(classes, key=lambda t: [sort_key(m) for m in t])
    return {
        'design_id': design_id,
        'design_type': 'two_level_fractional_factorial' if generated else 'full_factorial',
        'fraction': f'2^({len(factors)}-{len(generated)})' if generated else f'2^{len(factors)}',
        'factor_count': len(factors), 'base_factors': base,
        'generated_factors': [{'factor': f, 'product_of': list(generated[f])}
                              for f in factors if f in generated],
        'run_count': len(matrix), 'run_matrix': matrix,
        'defining_relation': [label(w) for w in words], 'resolution': resolution,
        'alias_classes': [[label(m) for m in t] for t in ordered],
        'run_order': 'standard order, not randomized', 'randomization_required': True,
        'experiment_executed': False, 'causal_claims_made': False, 'boundary': BOUNDARY}
