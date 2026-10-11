"""Row 1305 Legal Billing: bounded invoice preparation from caller records."""
import pytest
from app.modules.m20_general_cognitive_worker.legal_billing1305 import prepare_invoices

BOUNDARY = ('Caller-supplied time and fee records are validated and grouped into one '
            'draft invoice per matter; subtotals are rounded at 64 significant '
            'digits and batch totals at 28. These are computations over supplied '
            'records only: no payment is executed, no ledger is posted, no trust '
            'accounting is performed, and the records are not verified as true.')

def payload():
    return {'batch_id': 'b1', 'entries': [
        {'entry_id': 'e1', 'matter_id': 'm-acer', 'timekeeper': 'asha',
         'hours': '1.5', 'rate': '250.00', 'narrative': 'draft motion'},
        {'entry_id': 'e2', 'matter_id': 'm-boro', 'timekeeper': 'biren',
         'hours': '2.25', 'rate': '180.0'},
        {'entry_id': 'e3', 'matter_id': 'm-acer', 'timekeeper': 'asha',
         'hours': '2.25', 'rate': '250.00', 'narrative': 'review'}]}

def refuse(p, message):
    with pytest.raises(ValueError) as ei:
        prepare_invoices(p)
    assert str(ei.value) == message

def test_sound_batch_exact_envelope():
    r = prepare_invoices(payload())
    assert r == {'batch_id': 'b1', 'invoice_count': 2,
        'invoices': [
            {'matter_id': 'm-acer', 'entry_ids': ['e1', 'e3'], 'entry_count': 2,
             'total_hours': '3.75', 'subtotal': '937.5', 'status': 'prepared_draft',
             'approval_granted': False},
            {'matter_id': 'm-boro', 'entry_ids': ['e2'], 'entry_count': 1,
             'total_hours': '2.25', 'subtotal': '405', 'status': 'prepared_draft',
             'approval_granted': False}],
        'total_hours': '6', 'grand_total': '1342.5',
        'payment_executed': False, 'posted_to_ledger': False,
        'trust_accounting_performed': False, 'records_verified_as_true': False,
        'boundary': BOUNDARY}

def test_minimal_entry_optionals_absent():
    r = prepare_invoices({'batch_id': 'b2', 'entries': [
        {'entry_id': 'x1', 'matter_id': 'm1', 'hours': '1', 'rate': '100'}]})
    assert r['invoice_count'] == 1
    assert r['invoices'][0] == {'matter_id': 'm1', 'entry_ids': ['x1'],
        'entry_count': 1, 'total_hours': '1', 'subtotal': '100',
        'status': 'prepared_draft', 'approval_granted': False}
    assert r['total_hours'] == '1' and r['grand_total'] == '100'

def test_exact_rational_arithmetic_and_normalization():
    r = prepare_invoices({'batch_id': 'b3', 'entries': [
        {'entry_id': 'a', 'matter_id': 'm1', 'hours': '0.1', 'rate': '0.1'},
        {'entry_id': 'b', 'matter_id': 'm1', 'hours': '1.5', 'rate': '250.00'},
        {'entry_id': 'c', 'matter_id': 'm2', 'hours': '2.50', 'rate': '10.000'}]})
    assert r['invoices'][0]['total_hours'] == '1.6'
    assert r['invoices'][0]['subtotal'] == '375.01'
    assert r['invoices'][1]['total_hours'] == '2.5'
    assert r['invoices'][1]['subtotal'] == '25'
    assert r['total_hours'] == '4.1' and r['grand_total'] == '400.01'

def test_zero_rate_is_pro_bono_not_refused():
    r = prepare_invoices({'batch_id': 'b4', 'entries': [
        {'entry_id': 'a', 'matter_id': 'm1', 'hours': '3', 'rate': '0'}]})
    assert r['grand_total'] == '0' and r['invoices'][0]['subtotal'] == '0'

def test_duplicate_entry_id_refused_across_matters():
    p = payload()
    p['entries'][2]['entry_id'] = 'e1'
    refuse(p, "BILL1305: duplicate entry_id 'e1'")

def test_negative_hours_refused():
    p = payload(); p['entries'][0]['hours'] = '-1.5'
    refuse(p, 'BILL1305: hours requires 0 < hours <= 24')

def test_negative_rate_refused():
    p = payload(); p['entries'][0]['rate'] = '-0.01'
    refuse(p, 'BILL1305: rate requires 0 <= rate <= 100000')

def test_zero_hours_refused():
    p = payload(); p['entries'][0]['hours'] = '0'
    refuse(p, 'BILL1305: hours requires 0 < hours <= 24')

def test_hours_upper_bound_both_sides():
    p = payload(); p['entries'] = [dict(p['entries'][0], hours='24')]
    assert prepare_invoices(p)['invoices'][0]['total_hours'] == '24'
    p['entries'][0]['hours'] = '24.0001'
    refuse(p, 'BILL1305: hours requires 0 < hours <= 24')
    p['entries'][0]['hours'] = '25'
    refuse(p, 'BILL1305: hours requires 0 < hours <= 24')

def test_rate_upper_bound_both_sides():
    p = payload(); p['entries'] = [dict(p['entries'][0], rate='100000')]
    assert prepare_invoices(p)['grand_total'] == '150000'
    p['entries'][0]['rate'] = '100000.01'
    refuse(p, 'BILL1305: rate requires 0 <= rate <= 100000')

def test_non_string_numbers_refused():
    p = payload(); p['entries'][0]['hours'] = 1.5
    refuse(p, 'BILL1305: hours requires a rational decimal string')
    p = payload(); p['entries'][0]['rate'] = 250
    refuse(p, 'BILL1305: rate requires a rational decimal string')

def test_non_finite_decimals_refused():
    p = payload(); p['entries'][0]['hours'] = 'NaN'
    refuse(p, 'BILL1305: hours requires a finite decimal value')
    p = payload(); p['entries'][0]['rate'] = 'Infinity'
    refuse(p, 'BILL1305: rate requires a finite decimal value')

def test_unparseable_decimal_refused():
    p = payload(); p['entries'][0]['hours'] = 'one.point.five'
    refuse(p, 'BILL1305: hours requires a rational decimal string')

def test_entries_list_bounds():
    refuse({'batch_id': 'b1', 'entries': []},
           'BILL1305: entries requires a list of 1..256 records')
    big = {'batch_id': 'b1', 'entries': [
        {'entry_id': f'e{i}', 'matter_id': 'm', 'hours': '1', 'rate': '1'}
        for i in range(257)]}
    refuse(big, 'BILL1305: entries requires a list of 1..256 records')
    refuse({'batch_id': 'b1', 'entries': 'e1'},
           'BILL1305: entries requires a list of 1..256 records')

def test_required_text_fields_refused():
    p = payload(); del p['batch_id']
    refuse(p, 'BILL1305: batch_id requires non-empty text')
    p = payload(); p['entries'][0]['entry_id'] = '  '
    refuse(p, 'BILL1305: entry_id requires non-empty text')
    p = payload(); p['entries'][0]['matter_id'] = ''
    refuse(p, 'BILL1305: matter_id requires non-empty text')
    p = payload(); p['entries'][0]['narrative'] = 7
    refuse(p, 'BILL1305: narrative requires text when present')

def test_invoices_sorted_entries_keep_input_order():
    r = prepare_invoices({'batch_id': 'b5', 'entries': [
        {'entry_id': 'z1', 'matter_id': 'm-zed', 'hours': '1', 'rate': '10'},
        {'entry_id': 'a1', 'matter_id': 'm-alpha', 'hours': '2', 'rate': '10'},
        {'entry_id': 'z2', 'matter_id': 'm-zed', 'hours': '3', 'rate': '10'},
        {'entry_id': 'a2', 'matter_id': 'm-alpha', 'hours': '4', 'rate': '10'}]})
    assert [i['matter_id'] for i in r['invoices']] == ['m-alpha', 'm-zed']
    assert r['invoices'][0]['entry_ids'] == ['a1', 'a2']
    assert r['invoices'][1]['entry_ids'] == ['z1', 'z2']

def test_honesty_labels_and_no_payment():
    r = prepare_invoices(payload())
    assert r['payment_executed'] is False
    assert r['posted_to_ledger'] is False
    assert r['trust_accounting_performed'] is False
    assert r['records_verified_as_true'] is False
    assert all(i['approval_granted'] is False and i['status'] == 'prepared_draft'
               for i in r['invoices'])

def test_precision_64_rounding_output_pinned():
    # Peer audit survivor 1 (ARITHMETIC_PRECISION +/-1): a 65-significant-digit
    # rate puts nonzero digits at fraction positions 63 and 64, so the invoice
    # subtotal rounds differently at precision 63 ('1'), 64 ('1.0...01') and
    # 65 ('1.0...011'). This pins the exact 64-digit rounding output and kills
    # +/-1 precision mutants. Batch totals re-normalize outside the precision
    # block at the default 28 digits, so grand_total collapses to '1'. Pins
    # the frozen core's current behavior; totals may round.
    rate = '1.' + '0' * 62 + '11'
    r = prepare_invoices({'batch_id': 'bp', 'entries': [
        {'entry_id': 'e1', 'matter_id': 'm1', 'hours': '1', 'rate': rate}]})
    assert r['invoices'][0]['subtotal'] == (
        '1.000000000000000000000000000000000000000000000000000000000000001')
    assert r['invoices'][0]['total_hours'] == '1'
    assert r['grand_total'] == '1'
    assert r['total_hours'] == '1'

def test_exactly_256_entries_accepted():
    entries = [{'entry_id': f'e{i}', 'matter_id': 'm1', 'hours': '1', 'rate': '1'}
               for i in range(256)]
    r = prepare_invoices({'batch_id': 'b256', 'entries': entries})
    assert r['invoice_count'] == 1
    assert r['invoices'][0]['entry_count'] == 256
    assert r['invoices'][0]['total_hours'] == '256'
    assert r['invoices'][0]['subtotal'] == '256'
    assert r['total_hours'] == '256' and r['grand_total'] == '256'
    assert len(r['invoices'][0]['entry_ids']) == 256
