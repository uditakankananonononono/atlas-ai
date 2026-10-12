"""G116: bookmarks executor - decomposition, actions, ledger, corpus commitment."""
from __future__ import annotations

import inspect

import pytest

from app.modules.c35 import bookmarks_data, bookmarks_exec

FIXTURE = [
    ("Astra Girls Program 2026 Entry", "https://form.jotform.com/000000000000000"),
    ("Brag Sheet Template - Docs", "https://docs.google.com/document/d/1abc"),
    ("Apply to the Accelerator", "https://apply.example.org/accelerator"),
    ("Biology Olympiad Practice", "https://olypara.bio/tests"),
    ("Summer School Scholarships", "https://iefa.org/scholarships/x"),
    ("How to Write the Supplement", "https://blog.example.com/x"),
    ("Team Workspace", "https://app.slack.com/client/T0/D0"),
    ("Open Fellowship Call 2026", "https://fellowship.example.org/apply"),
    ("Community Forum Rules", "https://discord.com/invite/x"),
    ("Plain Reference Page", "https://example.com/post"),
]


def test_repo_carries_metadata_only_no_corpus_rows():
    src = inspect.getsource(bookmarks_data)
    assert "http://" not in src and "https://" not in src
    assert not hasattr(bookmarks_data, "BOOKMARKS")
    md = bookmarks_data.metadata()
    assert md["row_count"] == 436
    assert sum(md["category_structure"].values()) == 436
    assert len(md["corpus_sha256"]) == 64
    assert md["provenance"]["content_in_repo"] is False


def test_load_corpus_binds_count_and_hash():
    with pytest.raises(ValueError, match="BOOKMARKS_REFUSED_CORPUS_COUNT"):
        bookmarks_data.load_corpus(FIXTURE)
    fake436 = [["t%d" % i, "https://example.com/%d" % i] for i in range(436)]
    with pytest.raises(ValueError, match="BOOKMARKS_REFUSED_CORPUS_HASH"):
        bookmarks_data.load_corpus(fake436)


def test_canonical_serialization_is_stable():
    a = bookmarks_data.canonical_bytes([["A b", "https://x.example/1"]])
    b = bookmarks_data.canonical_bytes([["A b", "https://x.example/1"]])
    assert a == b == '[["A b","https://x.example/1"]]'.encode("utf-8")
    assert bookmarks_data.corpus_sha256([["A b", "https://x.example/1"]]) != \
        bookmarks_data.CORPUS_SHA256


def test_fixture_decomposed_fully_with_kinds():
    out = bookmarks_exec.run({"as_of": "2026-10-12", "bookmarks": FIXTURE})
    assert out["source"] == "runtime_supplied"
    assert out["coverage"]["unique_urls"] == len(FIXTURE)
    kinds = {p["kind"] for p in out["ledger"]}
    assert "application_form" in kinds and "reference" in kinds
    for p in out["ledger"]:
        assert p["kind"] in bookmarks_exec.KINDS
        assert p["actions"] and p["status"]
        assert p["url"].startswith("http")


def test_stale_season_flagged_and_signin_gated():
    rows = FIXTURE + [["Old Program 2025 Entry", "https://typeform.com/old-2025"]]
    out = bookmarks_exec.run({"as_of": "2026-10-12", "bookmarks": rows})
    assert out["coverage"]["stale_season_check"] > 0
    assert out["coverage"]["needs_owner_signin"] > 0
    signins = [p for p in out["ledger"] if p["status"] == "needs_owner_signin"]
    assert all("owner_signs_in_herself" in p["actions"] for p in signins)


def test_plan_orders_forms_first_and_is_deterministic():
    out = bookmarks_exec.run({"as_of": "2026-10-12", "bookmarks": FIXTURE})
    by_seq = {p["seq"]: p for p in out["ledger"]}
    kinds = [by_seq[s]["kind"] for s in out["execution_plan"]]
    assert kinds[0] == "application_form"
    last_form = max(i for i, k in enumerate(kinds) if k == "application_form")
    first_ref = min(i for i, k in enumerate(kinds) if k == "reference")
    assert last_form < first_ref
    again = bookmarks_exec.run({"as_of": "2026-10-12", "bookmarks": FIXTURE})
    assert out == again


def test_kind_filter_and_refusals():
    a = bookmarks_exec.run({"as_of": "2026-10-12", "bookmarks": FIXTURE,
                            "kinds": ["application_form"]})
    assert all(p["kind"] == "application_form" for p in a["ledger"]) and a["ledger"]
    with pytest.raises(ValueError, match="APPLY_REFUSED_SUBMIT"):
        bookmarks_exec.run({"as_of": "2026-10-12", "bookmarks": FIXTURE, "submit": True})
    with pytest.raises(ValueError, match="APPLY_REFUSED_NOCREDS"):
        bookmarks_exec.run({"as_of": "2026-10-12", "bookmarks": FIXTURE, "password": "x"})
    with pytest.raises(ValueError, match="APPLY_REFUSED_BAD_TYPE:url"):
        bookmarks_exec.run({"as_of": "2026-10-12", "bookmarks": [("t", "not-a-url")]})
    with pytest.raises(ValueError, match="APPLY_REFUSED_BAD_TYPE:bookmarks"):
        bookmarks_exec.run({"as_of": "2026-10-12"})
