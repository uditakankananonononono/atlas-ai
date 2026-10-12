"""G115: judge panel wiring - adapters, parsing, receipts, aggregation, facade scan."""
from __future__ import annotations

import pytest

from app.validation import judges

RESP = {"chatgpt": "VERDICT: PASS\nReal logic, requirement covered.",
        "deepseek": "VERDICT: FAIL\nNo live data path exists.",
        "claude": "VERDICT: PASS\nImplementation is substantive.",
        "perplexity": "VERDICT: FACADE\nline 40 is a renamed shell."}


def _transport():
    return judges.FixtureTransport(dict(RESP))


def test_packet_contains_requirement_and_code_and_rules():
    p = judges.build_packet("predict markets", "def f(): return 1", "chatgpt")
    assert "predict markets" in p and "def f(): return 1" in p
    assert "VERDICT: PASS" in p and "FACADE" in p
    with pytest.raises(ValueError, match="JUDGE_REFUSED_BAD_PROVIDER"):
        judges.build_packet("x", "y", "bing")


def test_parse_verdict_strict_first_line():
    out = judges.parse_verdict("VERDICT: FAIL\ncriticism one\ncriticism two")
    assert out == {"verdict": "FAIL", "criticism": ["criticism one", "criticism two"]}
    with pytest.raises(ValueError, match="JUDGE_REFUSED_NO_VERDICT"):
        judges.parse_verdict("I think it passes because...")


def test_panel_aggregation_facade_poisons():
    out = judges.judge_requirement("predict markets with real models",
                                   "def predict(x):\n    return 42.0", _transport())
    assert out["counts"] == {"PASS": 2, "FAIL": 1, "FACADE": 1}
    assert out["consensus"] == "FACADE"
    assert out["disagreement"] is True
    assert out["final"] == "FACADE"
    assert len(out["judges"]) == 4


def test_receipts_bind_prompt_and_response():
    out = judges.judge_requirement("req text", "real code body", _transport())
    r = out["judges"][0]["receipt"]
    assert len(r["sha256"]) == 64
    assert r["transport"] == "recorded_fixture"
    out2 = judges.judge_requirement("req text", "real code body", _transport())
    assert out2["judges"][0]["receipt"]["sha256"] == r["sha256"]
    out3 = judges.judge_requirement("req text CHANGED", "real code body", _transport())
    assert out3["judges"][0]["receipt"]["sha256"] != r["sha256"]


def test_facade_scan_finds_stubs():
    scan = judges.facade_scan("def f():\n    pass\n# TODO real impl\n")
    assert scan["facade_suspect"] is True and scan["marker_count"] >= 2
    clean = judges.facade_scan("def f():\n    return 1 + 1\n")
    assert clean["facade_suspect"] is False


def test_unanimous_pass_stays_pass_when_scan_clean():
    ft = judges.FixtureTransport({p: "VERDICT: PASS\nsolid" for p in judges.PROVIDERS})
    out = judges.judge_requirement("req", "def f():\n    total = 1 + 1\n    return total", ft)
    assert out["consensus"] == "PASS" and out["final"] == "PASS"
    assert out["disagreement"] is False


def test_browser_transport_pacing_and_validation():
    calls = []
    def driver(url, prompt):
        calls.append(url)
        return "VERDICT: PASS\nok"
    bt = judges.BrowserSessionTransport(driver, min_interval_s=5)
    assert bt.kind() == "live_browser_session"
    bt.complete("chatgpt", "prompt", now=100.0)
    assert calls == ["https://chatgpt.com/"]
    with pytest.raises(ValueError, match="JUDGE_REFUSED_PACED"):
        bt.complete("chatgpt", "prompt", now=102.0)  # human-speed pacing enforced
    bt.complete("deepseek", "prompt", now=106.0)
    with pytest.raises(ValueError, match="JUDGE_REFUSED_BAD_TYPE"):
        judges.BrowserSessionTransport("not callable")


def test_missing_fixture_refuses():
    ft = judges.FixtureTransport({"chatgpt": "VERDICT: PASS\nok"})
    with pytest.raises(ValueError, match="JUDGE_REFUSED_NO_FIXTURE"):
        judges.judge_requirement("req", "code", ft, providers=("claude",))
