"""Regression for the two E1 failure classes against the SQL-backed PersistentJournal.

Class 1: a corrected decision's stale original ranked first (a correction never surfaced).
Class 2: re-captured same-topic decision: the older copy won the tie.
include_superseded=True is the raw ranking the store shipped before the repair; it is used here
to show the failure reproduces on the pre-repair ranking.
"""
import random

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.modules.m21_claire.persistent_journal import PersistentJournal

SYL = ["ka", "to", "ri", "mu", "ze", "ph", "lo", "an", "vi", "su", "de", "qu"]


def _word(rng):
    return "".join(rng.choice(SYL) for _ in range(4))


def _store(tmp_path, name="j.db"):
    return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/name}"))


def test_class1_corrected_original_never_outranks_correction(tmp_path):
    shipped_top1 = effective_top1 = total = 0
    for seed in range(5):
        rng = random.Random(seed)
        j = PersistentJournal("t", f"owner{seed}", _store(tmp_path, f"c1_{seed}.db"))
        cases = []
        for i in range(100):
            text = f"{_word(rng)} {_word(rng)} {_word(rng)} plan"
            d = j.capture(text, "stable reason", f"ctx {_word(rng)}", f"msg-{i}")
            c = j.correction(text, f"replace with {_word(rng)} approach", f"fix {_word(rng)}", f"fix-{i}")
            cases.append((text, d["id"], c["id"]))
        for text, d_id, c_id in cases:
            total += 1
            shipped = j.retrieve(text, k=3, include_superseded=True)
            effective = j.retrieve(text, k=3)
            shipped_top1 += shipped[0]["id"] == c_id
            effective_top1 += effective[0]["id"] == c_id
            assert d_id not in [h["id"] for h in effective]          # stale original never surfaces
            assert effective[0]["kind"] == "correction" and effective[0]["supersedes"] == [d_id]
            assert effective[0]["stale_original"] == text
    assert total == 500
    assert shipped_top1 == 0          # the shipped ranker never put the correction first
    assert effective_top1 == 500


def test_class2_recaptured_same_topic_decision_newest_wins(tmp_path):
    shipped_top1 = effective_top1 = total = 0
    for seed in range(5):
        rng = random.Random(100 + seed)
        j = PersistentJournal("t", f"owner{seed}", _store(tmp_path, f"c2_{seed}.db"))
        cases = []
        for i in range(100):
            text = f"{_word(rng)} {_word(rng)} {_word(rng)} choice"
            old = j.capture(text, "first stance", "ctx", f"old-{i}")
            new = j.capture(text, "first stance", "ctx", f"new-{i}")   # identical text: exact tie
            cases.append((text, old["id"], new["id"]))
        for text, old_id, new_id in cases:
            total += 1
            shipped_top1 += j.retrieve(text, k=3, include_superseded=True)[0]["id"] == new_id
            eff = j.retrieve(text, k=3)
            effective_top1 += eff[0]["id"] == new_id
            assert old_id not in [h["id"] for h in eff]
    assert total == 500
    assert shipped_top1 == 0
    assert effective_top1 == 500


def test_chain_normalization_and_unlinked_corrections(tmp_path):
    j = PersistentJournal("t", "a", _store(tmp_path))
    d = j.capture("Send   Formal Email", "polite", "outreach", "m1")
    c1 = j.correction("send formal email", "send short email", "outreach", "m2")      # case/space-insensitive link
    c2 = j.correction("Send short email", "send a two-line email", "outreach", "m3")   # correction of the correction
    lone = j.correction("never captured phrase xyz", "something else", "misc", "m4")
    hits = j.retrieve("formal email outreach", k=5)
    assert [h["id"] for h in hits] == [c2["id"]]
    assert hits[0]["supersedes"] == [c1["id"]] and hits[0]["decision"] == "send a two-line email"
    assert lone["id"] not in [h["id"] for h in j.retrieve("never captured phrase xyz")]  # unlinked: not a decision
    assert [h["id"] for h in j.retrieve("never captured", kind="correction")] == [lone["id"]]
    raw = j.retrieve("formal email", kind="decision", include_superseded=True)
    assert [h["id"] for h in raw] == [d["id"]]                                # raw behaviour unchanged


def test_query_on_corrected_wording_finds_the_correction(tmp_path):
    j = PersistentJournal("t", "a", _store(tmp_path))
    j.capture("book window seat", "likes view", "travel", "m1")
    c = j.correction("book window seat", "book aisle seat", "travel", "m2")
    assert j.retrieve("aisle")[0]["id"] == c["id"]


def test_delete_of_correction_restores_original_and_isolation(tmp_path):
    s = _store(tmp_path)
    a, b = PersistentJournal("t", "a", s), PersistentJournal("t", "b", s)
    d = a.capture("pick grant alpha", "fit", "funding", "m1")
    c = a.correction("pick grant alpha", "pick grant beta", "funding", "m2")
    assert b.correction("pick grant alpha", "other owner", "funding", "m9") and b.retrieve("grant") == []
    assert [h["id"] for h in a.retrieve("grant alpha")] == [c["id"]]
    assert a.delete(c["id"])
    assert [h["id"] for h in a.retrieve("grant alpha")] == [d["id"]]


def test_hit_shape_and_limits_still_enforced(tmp_path):
    j = PersistentJournal("t", "a", _store(tmp_path))
    d = j.capture("alpha beta", "r", "c", "m1")
    h = j.retrieve("alpha beta")[0]
    assert h["id"] == d["id"] and h["kind"] == "decision" and h["retrieval"] == "lexical_not_semantic"
    for bad in (0, 21):
        try:
            j.retrieve("alpha", k=bad)
            assert False
        except ValueError:
            pass
    try:
        j.retrieve("  ")
        assert False
    except ValueError:
        pass
