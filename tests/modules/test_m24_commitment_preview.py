from datetime import datetime,timezone
import pytest
from app.modules.m24_billing.precommit import preview_commitment
PLAN={'id':'pro','name':'Pro','monthly_price_usd':29}
NOW=datetime(2026,9,22,tzinfo=timezone.utc)
def test_preview_binds_exact_annual_charge_tax_cancellation_and_hash():
 out=preview_commitment(plan=PLAN,quantity=2,tax_rate_percent=10,renewal_interval='year',cancellation_policy='Cancel before renewal.',cancellation_deadline=datetime(2026,10,1,tzinfo=timezone.utc),as_of=NOW)
 assert (out['subtotal'],out['tax'],out['exact_charge'])==('696.00','69.60','765.60')
 assert len(out['preview_sha256'])==64 and out['requires_exact_charge_approval'] and not out['executed']
def test_preview_refuses_currency_conversion_and_naive_deadline():
 with pytest.raises(ValueError,match='exchange rate'):preview_commitment(plan=PLAN,currency='EUR',cancellation_policy='cancel',as_of=NOW)
 with pytest.raises(ValueError,match='timezone-aware'):preview_commitment(plan=PLAN,cancellation_policy='cancel',cancellation_deadline=datetime(2026,10,1),as_of=NOW)
def test_preview_flags_expired_cancellation_deadline():
 out=preview_commitment(plan=PLAN,cancellation_policy='nonrefundable after deadline',cancellation_deadline=datetime(2026,9,1,tzinfo=timezone.utc),as_of=NOW)
 assert out['warnings']==['Cancellation deadline has passed.']
