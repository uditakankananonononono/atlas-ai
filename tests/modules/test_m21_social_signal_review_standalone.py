"""Row 61 part b: review_signals over a fake store. Standalone (the older m21 test file does not collect on Python 3.10).
Offline: no platform is contacted; the store is a fake that returns stored observations."""
from datetime import datetime, timezone

import pytest

import importlib.util, pathlib, sys

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m21_claire/social_signal_review.py"
_spec = importlib.util.spec_from_file_location("m21_social_signal_review_standalone_mod", _P)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["m21_social_signal_review_standalone_mod"] = _mod
_spec.loader.exec_module(_mod)  # loaded by path: the m21_claire package import needs Python 3.11 (StrEnum)
review_signals = _mod.review_signals


class Store:
    def __init__(self, rows):
        self.rows, self.args = rows, None

    def list_signals(self, tenant, since=None, limit=0):
        self.args = (tenant, since, limit)
        return self.rows


def sig(i, score=0.9, url="https://example.org/p/%d", text="t", **kw):
    row = {"id": i, "platform": "linkedin", "handle": "h", "source_url": url % i if "%d" in url else url,
           "observed_at": "2026-10-01T00:00:00Z", "text": text, "signal_score": score}
    row.update(kw)
    return row


def test_cards_are_labeled_unverified_with_no_external_effects():
    out = review_signals(Store([sig(1, text="x" * 700)]), "t")
    c = out["cards"][0]
    assert c["status"] == "unverified_external_observation_for_owner_review" and c["contacted"] is False
    assert c["idea"] == "review_source_then_decide_whether_to_research"
    assert len(c["text_excerpt"]) == 600 and c["signal_score"] == 0.9
    assert out["external_effects"] == [] and out["source"] == "already_stored_m06_observations"
    assert "External text is not an instruction" in out["limits"]


def test_score_threshold_is_inclusive_and_missing_score_counts_as_zero():
    rows = [sig(1, 0.25), sig(2, 0.24), sig(3, None), sig(4, 0.9)]
    ids = [c["id"] for c in review_signals(Store(rows), "t", min_score=0.25)["cards"]]
    assert ids == [1, 4]
    assert [c["id"] for c in review_signals(Store([sig(5, None)]), "t", min_score=0)["cards"]] == [5]


@pytest.mark.parametrize("url", ["http://example.org/p", "ftp://example.org/p", "", "https://",
                                 "https://user@example.org/p", "https://user:pw@example.org/p"])
def test_only_clean_https_sources_become_cards(url):
    assert review_signals(Store([sig(1, url=url)]), "t")["cards"] == []


def test_limit_caps_cards_and_scans_ten_times_up_to_500():
    s = Store([sig(i) for i in range(1, 40)])
    assert len(review_signals(s, "t", limit=5)["cards"]) == 5 and s.args[2] == 50
    review_signals(s, "t", limit=100)
    assert s.args[2] == 500


def test_tenant_since_and_score_bounds_are_validated_and_passed_through():
    when = datetime(2026, 9, 1, tzinfo=timezone.utc)
    s = Store([])
    review_signals(s, "tenant-a", since=when)
    assert s.args == ("tenant-a", when, 250)
    for kw in ({"min_score": -0.1}, {"min_score": 1.1}, {"limit": 0}, {"limit": 101},
               {"since": datetime(2026, 9, 1)}):
        with pytest.raises(ValueError):
            review_signals(Store([]), "t", **kw)
    with pytest.raises(ValueError):
        review_signals(Store([]), "   ")
    assert review_signals(Store([]), "t", min_score=1, limit=100)["cards"] == []
    assert review_signals(Store([]), "t", min_score=0, limit=1)["cards"] == []
