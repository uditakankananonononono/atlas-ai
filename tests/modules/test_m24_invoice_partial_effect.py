"""Legacy invoice entry refuses before any provider work since dec4c06d.
Partial effects of authorized durable invoice dispatch are tested in test_m24_invoice_dispatcher.
"""
import httpx
import pytest
from app.modules.m24_billing.stripe_client import StripeClient

@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['http','json'])
async def test_unbound_invoice_refusal_before_partial_effect(failure):
    calls=[]
    async def handler(request):
        calls.append(request)
        return httpx.Response(500 if failure=='http' else 200,content=b'invalid json')
    with pytest.raises(PermissionError,match='EFFECT_UNBOUND_REFUSED'):
        await StripeClient('sk_test_fixture',httpx.MockTransport(handler)).create_invoice(
            'cus_fixture','fixture',100,'usd','approval-fixture')
    assert calls==[]
