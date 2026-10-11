"""Row 1305 Legal Billing: bounded draft-invoice preparation from caller records.

The caller supplies time/fee records (entry id, matter, hours and hourly rate
as rational decimal strings). This engine validates the records, groups them
into one draft invoice per matter and totals them under a 64-significant-digit
decimal context; batch-level total_hours and grand_total are re-summed and
normalized outside that context at the default 28 significant digits, so
totals may round beyond those digits.
Duplicate entry ids, non-string or non-finite numbers, and out-of-range
values refuse. It neither executes payment nor posts anything: output is a
draft for licensed-counsel approval. Cites the existing row-1305 surfaces
(legal_support_1260_1309 billing_review_map template, m12 legal_support OPS
variance rows); the delta is validated decimal-string invoice preparation
with duplicate/negative refusal, which neither surface performs.
"""
from decimal import Decimal, InvalidOperation, localcontext

PREFIX = 'BILL1305'
MAX_ENTRIES = 256
MAX_HOURS = Decimal(24)
MAX_RATE = Decimal(100000)
ARITHMETIC_PRECISION = 64


def _fail(message):
    raise ValueError(f'{PREFIX}: {message}')


def _text(value, field):
    if type(value) is not str or not value.strip():
        _fail(f'{field} requires non-empty text')
    return value


def _optional_text(value, field):
    if value is None:
        return None
    if type(value) is not str:
        _fail(f'{field} requires text when present')
    return value


def _decimal(value, field, maximum, exclusive_minimum):
    if type(value) is not str:
        _fail(f'{field} requires a rational decimal string')
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        _fail(f'{field} requires a rational decimal string')
    if not parsed.is_finite():
        _fail(f'{field} requires a finite decimal value')
    below = parsed <= 0 if exclusive_minimum else parsed < 0
    if below or parsed > maximum:
        op = '<' if exclusive_minimum else '<='
        _fail(f'{field} requires 0 {op} {field} <= {maximum}')
    return parsed


def _out(amount):
    return format(amount.normalize(), 'f')


def prepare_invoices(payload):
    if type(payload) is not dict:
        _fail('payload requires an object')
    batch_id = _text(payload.get('batch_id'), 'batch_id')
    raw = payload.get('entries')
    if type(raw) is not list or not 1 <= len(raw) <= MAX_ENTRIES:
        _fail(f'entries requires a list of 1..{MAX_ENTRIES} records')
    seen = set()
    entries = []
    for row in raw:
        if type(row) is not dict:
            _fail('entry requires an object')
        entry_id = _text(row.get('entry_id'), 'entry_id')
        if entry_id in seen:
            _fail(f'duplicate entry_id {entry_id!r}')
        seen.add(entry_id)
        entries.append({
            'entry_id': entry_id,
            'matter_id': _text(row.get('matter_id'), 'matter_id'),
            'timekeeper': _optional_text(row.get('timekeeper'), 'timekeeper'),
            'narrative': _optional_text(row.get('narrative'), 'narrative'),
            'hours': _decimal(row.get('hours'), 'hours', MAX_HOURS, True),
            'rate': _decimal(row.get('rate'), 'rate', MAX_RATE, False)})
    with localcontext() as ctx:
        ctx.prec = ARITHMETIC_PRECISION
        by_matter = {}
        for entry in entries:
            by_matter.setdefault(entry['matter_id'], []).append(entry)
        invoices = []
        for matter_id in sorted(by_matter):
            group = by_matter[matter_id]
            hours_sum = sum((e['hours'] for e in group), Decimal(0))
            subtotal = sum((e['hours'] * e['rate'] for e in group), Decimal(0))
            invoices.append({
                'matter_id': matter_id,
                'entry_ids': [e['entry_id'] for e in group],
                'entry_count': len(group),
                'total_hours': _out(hours_sum),
                'subtotal': _out(subtotal),
                'status': 'prepared_draft',
                'approval_granted': False})
        total_hours = sum((Decimal(i['total_hours']) for i in invoices), Decimal(0))
        grand_total = sum((Decimal(i['subtotal']) for i in invoices), Decimal(0))
    return {'batch_id': batch_id, 'invoice_count': len(invoices),
            'invoices': invoices,
            'total_hours': _out(total_hours), 'grand_total': _out(grand_total),
            'payment_executed': False, 'posted_to_ledger': False,
            'trust_accounting_performed': False, 'records_verified_as_true': False,
            'boundary': 'Caller-supplied time and fee records are validated and grouped '
                        'into one draft invoice per matter; subtotals are rounded at 64 '
                        'significant digits and batch totals at 28. '
                        'These are computations over supplied records only: no payment is '
                        'executed, no ledger is posted, no trust accounting is performed, '
                        'and the records are not verified as true.'}
