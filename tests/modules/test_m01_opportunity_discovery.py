from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.modules.m01_opportunity_discovery.adapters import GrantsGovAdapter, SamGovAdapter, TedAdapter
from app.modules.m01_opportunity_discovery.models import Opportunity, OpportunityKind, SearchQuery
from app.modules.m01_opportunity_discovery.normalization import canonical_url, deduplicate, make_provenance, parse_date, parse_money
from app.modules.m01_opportunity_discovery.ranking import rank_all
from app.modules.m01_opportunity_discovery.lane_service import OpportunityDiscoveryService, OpportunityMonitor


class FakeTransport:
    def __init__(self, payload): self.payload, self.calls = payload, []
    def request(self, method, url, *, body=None, headers=None):
        self.calls.append((method, url, body))
        return self.payload


def opp(id="1", title="Cancer research fellowship", source="a", close=date(2027, 1, 1), description="genomics research"):
    raw = {"id": id, "title": title}
    return Opportunity(id, title, description, OpportunityKind.GRANT, "NIH", "posted", date(2026, 1, 1), close, 100, 1000, "USD", ("US",), ("student",), ("biology",), f"https://example.org/{id}", (make_provenance(source, id, f"https://example.org/{id}", raw),))


def test_normalizers_are_defensive():
    assert parse_date("2026-10-03T12:00:00Z") == date(2026, 10, 3)
    assert parse_money("$1,234.60") == 1235
    assert canonical_url("HTTPS://Example.Org/a/?utm_source=x&b=2&a=1#frag") == "https://example.org/a?a=1&b=2"


def test_grants_adapter_maps_official_shape_and_provenance():
    tx = FakeTransport({"data": {"oppHits": [{"id": "99", "title": "STEM grant", "agencyName": "NSF", "openDate": "09/01/2026", "closeDate": "10/31/2026", "awardFloor": "1000", "awardCeiling": "5000", "eligibility": "students, nonprofits"}]}})
    item = GrantsGovAdapter(tx).search(SearchQuery("STEM"))[0]
    assert item.id == "grants-gov:99" and item.sponsor == "NSF"
    assert item.amount_min == 1000 and item.amount_max == 5000
    assert item.provenance[0].source == "grants.gov" and len(item.provenance[0].raw_sha256) == 64
    assert tx.calls[0][0] == "POST"


def test_sam_adapter_requires_key_and_never_puts_it_in_model():
    with pytest.raises(ValueError): SamGovAdapter("")
    tx = FakeTransport({"opportunitiesData": [{"noticeId": "n1", "title": "Microscope", "department": "HHS", "postedDate": "2026-09-01", "responseDeadLine": "2026-10-01", "uiLink": "https://sam.gov/opp/n1/view"}]})
    item = SamGovAdapter("secret", tx).search(SearchQuery("microscope"))[0]
    assert item.kind is OpportunityKind.PROCUREMENT
    assert "secret" not in repr(item)
    assert "api_key=secret" in tx.calls[0][1]


def test_ted_adapter_maps_notice():
    tx = FakeTransport({"notices": [{"publication-number": "123-2026", "notice-title": "Sequencing", "buyer-name": "EU Lab", "deadline": "2026-12-01", "estimated-value": {"value": "120000", "currency": "EUR"}}]})
    item = TedAdapter(tx).search(SearchQuery("sequencing"))[0]
    assert item.id == "ted:123-2026" and item.amount_max == 120000 and item.currency == "EUR"


def test_dedupe_merges_sources_and_richer_description():
    a = opp(source="grants.gov", description="short")
    b = Opportunity("other", a.title, "a much richer description", a.kind, a.sponsor, a.source_status, a.open_date, a.close_date, a.amount_min, 2000, a.currency, a.countries, a.eligibility, ("new",), a.canonical_url + "?utm_source=x", (make_provenance("mirror", "z", a.canonical_url, {}),))
    merged = deduplicate([a, b])
    assert len(merged) == 1 and len(merged[0].provenance) == 2
    assert merged[0].amount_max == 2000 and "new" in merged[0].tags


def test_ranking_is_explainable_and_deterministic():
    ranked = rank_all([opp("b", "Unrelated"), opp("a")], SearchQuery("cancer fellowship", eligibility=("student",)), today=date(2026, 9, 20))
    assert ranked[0].opportunity.id == "a"
    assert ranked[0].score > ranked[1].score
    assert any("title matches" in reason for reason in ranked[0].reasons)


def test_service_isolates_adapter_failure():
    class Good:
        name = "good"
        def search(self, query): return [opp()]
    class Bad:
        name = "bad"
        def search(self, query): raise TimeoutError("down")
    result = OpportunityDiscoveryService([Bad(), Good()]).search(SearchQuery("cancer"))
    assert len(result.items) == 1
    assert result.failures[0].adapter == "bad" and result.failures[0].error_type == "TimeoutError"


def test_monitor_emits_new_updated_removed_and_noop():
    monitor = OpportunityMonitor()
    assert [x.kind for x in monitor.update([opp()])] == ["new"]
    assert monitor.update([opp()]) == ()
    changed = opp(description="changed")
    assert [x.kind for x in monitor.update([changed])] == ["updated"]
    assert [x.kind for x in monitor.update([])] == ["removed"]


def test_transport_error_redacts_api_key(monkeypatch):
    from app.modules.m01_opportunity_discovery.http import UrllibJsonTransport
    import app.modules.m01_opportunity_discovery.http as module
    def fail(*args, **kwargs): raise module.URLError("offline")
    monkeypatch.setattr(module, "urlopen", fail)
    with pytest.raises(Exception) as exc:
        UrllibJsonTransport(attempts=1).request("GET", "https://example.org?q=x&api_key=super-secret")
    assert "super-secret" not in str(exc.value)
    assert "%5BREDACTED%5D" in str(exc.value) or "REDACTED" in str(exc.value)
