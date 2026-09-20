from app.core.collection import CollectionSourceRow, CollectorType, estimate_daily_cost

def test_cost_dial_uses_daily_cap():
    source = CollectionSourceRow(tenant_id="t", source_key="x", collector_type=CollectorType.OFFICIAL_API.value, priority=50, cadence_seconds=60, enabled=True, cost_per_1000_requests_usd=2.0, daily_request_cap=100, config={}, next_run_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    assert estimate_daily_cost(source) == 0.2

def test_authorized_session_type_is_explicit():
    assert CollectorType.AUTHORIZED_SESSION.value == "authorized_session"
