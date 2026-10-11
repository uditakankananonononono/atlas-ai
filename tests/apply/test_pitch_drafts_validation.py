"""S4.4 repair: one complete draft validation at queue_add AND release (audit finding)."""
import copy

import pytest

from app.apply import pitch_drafts as pd
from test_pitch_drafts import approval_for, jdraft, pdraft

R = pd.PitchRefusal


def msg(fn):
    with pytest.raises(R) as e:
        fn()
    return str(e.value)


def seal(d, **kw):
    d = dict(d, **kw)
    h = pd._sha(d["recipient"] + "\n" + d["subject"] + "\n" + d["body"])
    d["text_sha256"] = h
    d["draft_id"] = h[:16]
    return d


def stored(d, status="QUEUED"):
    return dict(d, status=status)


def hand(**kw):
    """A hand-built, correctly sealed draft that never went through a builder."""
    d = dict(jdraft(), **kw)
    return seal(d)


# ---- finding 1: bulk recipient bypass
@pytest.mark.parametrize("rcpt", ["one@example.org,two@example.org", "a@b.org;c@d.org"])
def test_hand_built_bulk_refused_at_queue_add(rcpt):
    assert msg(lambda: pd.queue_add([], hand(recipient=rcpt))) == pd.BULK


@pytest.mark.parametrize("rcpt", ["one@example.org,two@example.org", "a@b.org;c@d.org"])
def test_hand_built_bulk_refused_at_release(rcpt):
    d = hand(recipient=rcpt, status="QUEUED")
    ap = approval_for(d)
    assert msg(lambda: pd.release([d], ap)) == pd.BULK


def test_queue_add_validates_existing_entries():
    bad = hand(recipient="x@y.org,z@y.org", status="QUEUED")
    assert msg(lambda: pd.queue_add([bad], pdraft())) == pd.BULK


# ---- finding 3: no raw TypeError
@pytest.mark.parametrize("field,val", [
    ("recipient", None), ("recipient", 5), ("body", 5), ("body", None), ("subject", None),
    ("subject", 5), ("kind", 5), ("kind", None), ("target_name", None), ("target_name", 5),
    ("draft_id", 5), ("draft_id", None), ("status", None), ("status", 5),
    ("text_sha256", None), ("text_sha256", 5)])
def test_wrong_field_types_raise_pitch_refusal(field, val):
    d = dict(jdraft(), **{field: val})
    with pytest.raises(R):
        pd.queue_add([], d)
    q = dict(d, status="QUEUED")
    with pytest.raises(R):
        pd.release([q], {"draft_id": "x", "recipient": "x@y.org", "text_sha256": "0", "approved_by": "owner"})
    assert msg(lambda: pd.queue_add([], d)) == "pitch_drafts:bad_type:draft"


# ---- finding 2: complete validation of every field
def test_kind_status_sent_validation():
    assert msg(lambda: pd.queue_add([], seal(jdraft(), kind="other"))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], seal(jdraft(), status="QUEUED"))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], seal(jdraft(), status="APPROVED_FOR_MANUAL_SEND"))) == \
        "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], seal(jdraft(), sent=True))) == "pitch_drafts:bad_draft"
    d = stored(jdraft(), "SENT")
    assert msg(lambda: pd.release([d], approval_for(d))) == "pitch_drafts:bad_draft"
    d = stored(jdraft(), "DRAFT")
    assert msg(lambda: pd.release([d], approval_for(d))) == "pitch_drafts:bad_draft"
    d = stored(jdraft(), "QUEUED")
    d["sent"] = True
    assert msg(lambda: pd.release([d], approval_for(d))) == "pitch_drafts:bad_draft"


@pytest.mark.parametrize("rcpt", ["", "a", "a@b", "a@@b.org", "@b.org", "a b@c.org", "a@b.", "a@.b.org"])
def test_hand_built_bad_recipient_refused(rcpt):
    assert msg(lambda: pd.queue_add([], hand(recipient=rcpt))) == "pitch_drafts:bad_recipient"
    d = hand(recipient=rcpt, status="QUEUED")
    assert msg(lambda: pd.release([d], approval_for(d))) == "pitch_drafts:bad_recipient"


def test_recipient_length_fence_hand_built():
    ok = "a" * 194 + "@b.org"
    assert len(ok) == 200
    pd.queue_add([], hand(recipient=ok))
    assert msg(lambda: pd.queue_add([], hand(recipient="a" + ok))) == "pitch_drafts:bad_draft"


def test_body_subject_target_bounds():
    d = hand(body="x" * pd.MAX_BODY)
    pd.queue_add([], d)
    assert msg(lambda: pd.queue_add([], hand(body="x" * (pd.MAX_BODY + 1)))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], hand(body=""))) == "pitch_drafts:bad_draft"
    pd.queue_add([], hand(subject="s" * pd.MAX_SUBJECT))
    assert msg(lambda: pd.queue_add([], hand(subject="s" * (pd.MAX_SUBJECT + 1)))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], hand(subject=""))) == "pitch_drafts:bad_draft"
    pd.queue_add([], hand(target_name="t" * 200))
    assert msg(lambda: pd.queue_add([], hand(target_name="t" * 201))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], hand(target_name=""))) == "pitch_drafts:bad_draft"
    big = hand(body="x" * (pd.MAX_BODY + 1), status="QUEUED")
    assert msg(lambda: pd.release([big], approval_for(big))) == "pitch_drafts:bad_draft"


def test_word_caps_per_kind():
    p = pdraft()
    pd.queue_add([], seal(p, body=" ".join(["w"] * pd.MAX_PITCH_WORDS)))
    assert msg(lambda: pd.queue_add([], seal(p, body=" ".join(["w"] * (pd.MAX_PITCH_WORDS + 1))))) == \
        "pitch_drafts:bad_draft"
    pd.queue_add([], seal(jdraft(), body=" ".join(["w"] * pd.MAX_JOURNAL_WORDS)))
    assert msg(lambda: pd.queue_add([], seal(jdraft(), body=" ".join(["w"] * (pd.MAX_JOURNAL_WORDS + 1))))) \
        == "pitch_drafts:bad_draft"
    over = stored(seal(p, body=" ".join(["w"] * 201)))
    assert msg(lambda: pd.release([over], approval_for(over))) == "pitch_drafts:bad_draft"


def test_hash_and_id_exact_hand_built():
    d = jdraft()
    assert msg(lambda: pd.queue_add([], dict(d, draft_id="0" * 16))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], dict(d, text_sha256="0" * 64))) == "pitch_drafts:bad_draft"
    s = stored(d)
    s["draft_id"] = "0" * 16
    assert msg(lambda: pd.release([s], approval_for(d))) == "pitch_drafts:bad_draft"


def test_stored_queue_shape_checks():
    d = stored(jdraft())
    a = approval_for(d)
    assert msg(lambda: pd.release([d, copy.deepcopy(d)], a)) == "pitch_drafts:bad_draft"
    many = []
    for i in range(pd.MAX_QUEUE):
        many = pd.queue_add(many, pd.make_org_pitch_draft(
            {"name": "O%d" % i, "recipient": "a%d@b.org" % i}, {"name": "N", "summary": "s"}, "y"))
    pd.release(many, approval_for(many[0]))
    extra = stored(jdraft())
    assert msg(lambda: pd.release(many + [extra], approval_for(extra))) == "pitch_drafts:queue_full"


def test_valid_hand_built_draft_accepted_and_released():
    d = hand(recipient="solo@example.org")
    q = pd.queue_add([], d)
    q2, packet = pd.release(q, approval_for(q[0]))
    assert packet["recipient"] == "solo@example.org" and packet["sent"] is False
    assert q2[0]["status"] == "APPROVED_FOR_MANUAL_SEND"
    assert msg(lambda: pd.release(q2, approval_for(q2[0]))) == pd.SEND


def test_approved_by_is_a_data_string_not_auth_documented():
    import pathlib
    t = (pathlib.Path(__file__).resolve().parents[2] / "docs" / "contracts" / "S4.4-pitch-drafts.md").read_text()
    assert "data-integrity string" in t and "not owner authentication" in t


def test_fuzz_only_pitch_refusal_or_valid():
    import random
    rnd = random.Random(7)
    junk = [None, 5, 1.5, True, [], {}, (), "", "a", "a@b.org", "x" * 6000, "a\x00", b"b", ["a"]]
    base = jdraft()
    n_ok = 0
    for _ in range(600):
        d = dict(base)
        for k in rnd.sample(sorted(d), rnd.randint(1, 3)):
            d[k] = rnd.choice(junk)
        if rnd.random() < 0.2:
            d.pop(rnd.choice(sorted(d)))
        try:
            q = pd.queue_add([], d)
            n_ok += 1
            pd.release(q, approval_for(q[0]))
        except R:
            pass
    assert n_ok == 0 or n_ok < 600
    # every accepted-by-queue_add draft is by construction one the builders could have produced
    for _ in range(200):
        d = seal(base, recipient=rnd.choice(["a@b.org", "a@b.org,c@d.org", "x", None.__class__.__name__ + "@y.org"]))
        try:
            q = pd.queue_add([], d)
            assert "," not in q[0]["recipient"] and ";" not in q[0]["recipient"]
        except R:
            pass


# ---- audit addition: the _scan leaf guard (floats and foreign values) is pinned publicly
@pytest.mark.parametrize("val", [1.5, 3.0, float("nan"), float("inf"), (1,), b"x", object(), {1, 2}])
def test_scan_leaf_guard_draft_fields(val):
    d = jdraft()
    for k in ("subject", "recipient", "kind", "target_name", "sent", "draft_id"):
        assert msg(lambda: pd.queue_add([], dict(d, **{k: val}))) == "pitch_drafts:bad_type:queue", k
    s = stored(d)
    for k in ("subject", "sent", "status"):
        assert msg(lambda: pd.release([dict(s, **{k: val})], approval_for(d))) == "pitch_drafts:bad_type:queue", k
    assert msg(lambda: pd.queue_add([], dict(d, **{"extra": val}))) == "pitch_drafts:bad_type:queue"


@pytest.mark.parametrize("val", [3.0, 100.0, 88.0, 0.0, float("nan")])
def test_scan_leaf_guard_fit_and_approval(val):
    f = pd.score_fit({"name": "Journal of Tiny Results", "source_url": "https://example.org/guidelines",
                      "as_of": "2026-10-01", "scope_keywords": ["orbit", "photometry"], "min_words": 1000,
                      "max_words": 5000, "accepted_formats": ["pdf"], "required_sections": ["abstract"],
                      "fee_usd": 0},
                     {"title": "A small transit study", "words": 3000, "keywords": ["orbit", "photometry"],
                      "format": "pdf", "sections": ["abstract"], "max_fee_usd": 0})
    from test_pitch_drafts import author, jtarget, manuscript
    m = manuscript(sections=["abstract"])
    g = {"name": "Journal of Tiny Results", "source_url": "https://example.org/guidelines",
         "as_of": "2026-10-01", "scope_keywords": ["orbit", "photometry"], "min_words": 1000,
         "max_words": 5000, "accepted_formats": ["pdf"], "required_sections": ["abstract"], "fee_usd": 0}
    f = pd.score_fit(g, m)
    assert f["score"] == 100
    for mut in (lambda x: x.update(score=val), lambda x: x["checks"][0].update(weight=val),
                lambda x: x["checks"][0].update(overlap=val), lambda x: x["checks"][1].update(passed=val)):
        x = copy.deepcopy(f)
        mut(x)
        body = {k: x[k] for k in pd._FIT_KEYS if k not in ("honesty", "fit_sha256")}
        x["fit_sha256"] = "0" * 64
        assert msg(lambda: pd.make_journal_draft(jtarget(), m, author(), x)) == "pitch_drafts:bad_type:fit"
    d = jdraft()
    q = pd.queue_add([], d)
    for k in ("draft_id", "recipient", "text_sha256", "approved_by"):
        assert msg(lambda: pd.release(q, dict(approval_for(d), **{k: val}))) == "pitch_drafts:bad_type:approval"


def test_recipient_254_guard_is_live_on_public_queue_schema():
    def addr(n):
        return "a" * (n - len("@b.org")) + "@b.org"
    assert msg(lambda: pd.queue_add([], hand(recipient=addr(254)))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], hand(recipient=addr(255)))) == "pitch_drafts:bad_recipient"
    assert msg(lambda: pd.queue_add([], hand(recipient=addr(201)))) == "pitch_drafts:bad_draft"
    pd.queue_add([], hand(recipient=addr(200)))


def test_public_schema_literal_limits_and_min_lengths():
    assert (pd.MAX_JOURNAL_WORDS, pd.MAX_BODY, pd.MAX_SUBJECT) == (1000, 5000, 300)
    pd.queue_add([], hand(body="x" * 5000))
    assert msg(lambda: pd.queue_add([], hand(body="x" * 5001))) == "pitch_drafts:bad_draft"
    pd.queue_add([], hand(subject="s" * 300))
    assert msg(lambda: pd.queue_add([], hand(subject="s" * 301))) == "pitch_drafts:bad_draft"
    pd.queue_add([], hand(body=" ".join(["w"] * 1000)))
    assert msg(lambda: pd.queue_add([], hand(body=" ".join(["w"] * 1001)))) == "pitch_drafts:bad_draft"
    # one-character fields are valid
    pd.queue_add([], hand(subject="s"))
    pd.queue_add([], hand(target_name="t"))
    pd.queue_add([], hand(body="b"))
