from app.modules.m04_research_scientist.models import Paper, SearchQuery
from app.modules.m04_research_scientist.lane_surveillance import SurveillanceStore, parse_syndication_feed, validate_public_feed_url

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>https://doi.org/10.1/ABC</id>
<title>A finding</title><summary>Evidence text</summary><published>2026-01-02</published>
<link href="https://example.org/paper"/><author><name>Ada</name></author></entry></feed>"""


def test_parse_atom_and_normalize_doi():
    papers = parse_syndication_feed(ATOM, "test-feed")
    assert len(papers) == 1
    assert papers[0].doi == "10.1/abc"
    assert papers[0].title == "A finding"


def test_store_is_idempotent_and_deduplicates_by_doi():
    store = SurveillanceStore()
    store.save_query(SearchQuery("q1", "cancer"))
    first = Paper("p1", "One", doi="10.1/SAME")
    alias = Paper("p2", "Duplicate", doi="https://doi.org/10.1/same")
    assert store.ingest("q1", [first]) == [first]
    assert store.ingest("q1", [alias]) == []
    assert [p.paper_id for p in store.list_results("q1")] == ["p1"]


def test_reject_unknown_query_and_local_urls():
    store = SurveillanceStore()
    try:
        store.ingest("missing", [])
    except KeyError:
        pass
    else:
        raise AssertionError("unknown query accepted")
    for value in ("file:///secret", "http://localhost/feed", "https://thing.local/x"):
        try:
            validate_public_feed_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(value)
