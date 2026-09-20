from datetime import date

from app.modules.m01_opportunity_discovery.models import Opportunity, OpportunityKind
from app.modules.m01_opportunity_discovery.normalization import make_provenance
from app.modules.m01_opportunity_discovery.store import SqliteOpportunityStore


def item(id="x", description="first"):
    return Opportunity(id, "Open grant", description, OpportunityKind.GRANT, "Sponsor", "posted", date(2026, 1, 1), date(2027, 1, 1), 10, 20, "USD", ("US",), (), (), f"https://example.org/{id}", (make_provenance("test", id, f"https://example.org/{id}", {"description": description}),))


def test_store_round_trip_and_monitor_isolation(tmp_path):
    store = SqliteOpportunityStore(tmp_path / "opportunities.sqlite")
    expected = item()
    assert [x.kind for x in store.replace_and_diff("one", [expected])] == ["new"]
    assert store.replace_and_diff("one", [expected]) == ()
    assert [x.kind for x in store.replace_and_diff("two", [expected])] == ["new"]
    loaded = store.load("one")
    assert loaded == (expected,)
    assert loaded[0].provenance[0].raw_sha256 == expected.provenance[0].raw_sha256


def test_store_updated_removed_and_delete(tmp_path):
    store = SqliteOpportunityStore(tmp_path / "opportunities.sqlite")
    store.replace_and_diff("key", [item()])
    changes = store.replace_and_diff("key", [item(description="changed")])
    assert len(changes) == 1 and changes[0].kind == "updated"
    changes = store.replace_and_diff("key", [])
    assert len(changes) == 1 and changes[0].kind == "removed"
    store.replace_and_diff("key", [item("a"), item("b")])
    assert store.delete_monitor("key") == 2
    assert store.load("key") == ()
