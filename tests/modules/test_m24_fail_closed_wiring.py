import asyncio

import pytest

from app.modules.m24_billing.routes import get_service
from app.modules.m24_billing.stripe_client import UnconfiguredStripeClient


def test_read_only_billing_surface_loads_without_provider_secret(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    service = get_service()
    assert len(service.plans()) >= 1
    assert isinstance(service.stripe, UnconfiguredStripeClient)


def test_unconfigured_provider_cannot_claim_external_execution():
    client = UnconfiguredStripeClient()
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY is required"):
        asyncio.run(client.create_checkout(None, "", "", "tenant", "approval"))
