"""S4.4 R4: each field's OWN semantic raw cap runs before that field's content scan.
An oversized value is refused (declared too_long/bad_item/bad_draft/bad_recipient code, never a
control_chars code) before any per-character work on it."""
import pytest

from app.apply import pitch_drafts as pd
from test_pitch_drafts import approval_for, author, guidelines, jdraft, jtarget, manuscript
from test_pitch_drafts_validation import hand, stored

R = pd.PitchRefusal
BAD = ["\x00", "\u200b", "\u2028", "\n"]


def msg(fn):
    with pytest.raises(R) as e:
        fn()
    return str(e.value)


@pytest.mark.parametrize("bad", BAD)
def test_guidelines_manuscript_fields(bad):
    g, m = guidelines, manuscript
    over = bad + "x" * 200          # 201 chars with a bad char
    at = bad + "x" * 199            # exactly 200 chars with a bad char -> content error
    for key in ("name", "source_url", "as_of"):
        assert msg(lambda: pd.score_fit(g(**{key: over}), m())) == "pitch_drafts:too_long_field:guidelines", key
        assert msg(lambda: pd.score_fit(g(**{key: at}), m())) == "pitch_drafts:control_chars:guidelines", key
    for key in ("scope_keywords", "accepted_formats", "required_sections"):
        assert msg(lambda: pd.score_fit(g(**{key: [over]}), m())) == "pitch_drafts:bad_item:guidelines", key
        assert msg(lambda: pd.score_fit(g(**{key: [at]}), m())) == "pitch_drafts:control_chars:guidelines", key
    for key in ("title", "format"):
        assert msg(lambda: pd.score_fit(g(), m(**{key: over}))) == "pitch_drafts:too_long_field:manuscript", key
        assert msg(lambda: pd.score_fit(g(), m(**{key: at}))) == "pitch_drafts:control_chars:manuscript", key
    for key in ("keywords", "sections"):
        assert msg(lambda: pd.score_fit(g(), m(**{key: [over]}))) == "pitch_drafts:bad_item:manuscript", key
        assert msg(lambda: pd.score_fit(g(), m(**{key: [at]}))) == "pitch_drafts:control_chars:manuscript", key


@pytest.mark.parametrize("bad", BAD)
def test_target_author_ask(bad):
    t = {"name": "O", "recipient": "a@b.org"}
    for key in ("name", "recipient"):
        assert msg(lambda: pd.make_org_pitch_draft(dict(t, **{key: bad + "x" * 200}), author(), "y")) == \
            "pitch_drafts:too_long_field:target", key
        assert msg(lambda: pd.make_org_pitch_draft(dict(t, **{key: bad + "x" * 199}), author(), "y")) == \
            "pitch_drafts:control_chars:target", key
    assert msg(lambda: pd.make_org_pitch_draft(t, author(name=bad + "x" * 200), "y")) == \
        "pitch_drafts:too_long_field:author"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(name=bad + "x" * 199), "y")) == \
        "pitch_drafts:control_chars:author"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(summary=bad + "x" * 1200), "y")) == \
        "pitch_drafts:too_long_field:author"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(summary=bad + "x" * 1199), "y")) == \
        "pitch_drafts:control_chars:author"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), bad + "x" * 200)) == "pitch_drafts:too_long_field:ask"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), bad + "x" * 199)) == "pitch_drafts:control_chars:ask"


@pytest.mark.parametrize("bad", BAD)
def test_draft_fields_public_schema(bad):
    d = jdraft()
    cases = {"subject": 300, "target_name": 200, "kind": 200, "status": 200, "draft_id": 200,
             "text_sha256": 200}
    for key, cap in cases.items():
        assert msg(lambda: pd.queue_add([], dict(d, **{key: bad + "x" * cap}))) == "pitch_drafts:bad_draft", key
        assert msg(lambda: pd.queue_add([], dict(d, **{key: bad + "x" * (cap - 1)}))) == \
            "pitch_drafts:control_chars:queue", key
    # recipient public cap is 254 (the address limit); beyond it bad_recipient, before the scan
    assert msg(lambda: pd.queue_add([], dict(d, recipient=bad + "x" * 254))) == "pitch_drafts:bad_recipient"
    assert msg(lambda: pd.queue_add([], dict(d, recipient=bad + "x" * 253))) == "pitch_drafts:control_chars:queue"
    # body cap 5000; body may keep tab/CR/LF but not the rest
    assert msg(lambda: pd.queue_add([], dict(d, body=bad + "x" * 5000))) == "pitch_drafts:bad_draft"
    s = stored(d)
    assert msg(lambda: pd.release([dict(s, subject=bad + "x" * 300)], approval_for(d))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.release([dict(s, body=bad + "x" * 5000)], approval_for(d))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.release([dict(s, recipient=bad + "x" * 254)], approval_for(d))) == "pitch_drafts:bad_recipient"


@pytest.mark.parametrize("bad", BAD)
def test_fit_and_approval_strings(bad):
    f = pd.score_fit(guidelines(), manuscript())
    f2 = dict(f, target_name=bad + "x" * 200)
    assert msg(lambda: pd.make_journal_draft(jtarget(), manuscript(), author(), f2)) == \
        "pitch_drafts:too_long_field:fit"
    f3 = dict(f, target_name=bad + "x" * 199)
    assert msg(lambda: pd.make_journal_draft(jtarget(), manuscript(), author(), f3)) == \
        "pitch_drafts:control_chars:fit"
    d = jdraft()
    q = pd.queue_add([], d)
    for key in ("draft_id", "recipient", "text_sha256", "approved_by"):
        assert msg(lambda: pd.release(q, approval_for(d, **{key: bad + "x" * 200}))) == \
            "pitch_drafts:too_long_field:approval", key
        assert msg(lambda: pd.release(q, approval_for(d, **{key: bad + "x" * 199}))) == \
            "pitch_drafts:control_chars:approval", key


def test_unknown_field_values_use_default_cap():
    assert msg(lambda: pd.score_fit(guidelines(extra="x" * 201), manuscript())) == \
        "pitch_drafts:too_long_field:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(extra="x" * 200), manuscript())) == \
        "pitch_drafts:unknown_field:guidelines"


def test_global_fence_still_wins():
    assert msg(lambda: pd.score_fit(guidelines(name="\x00" + "x" * 10000), manuscript())) == \
        "pitch_drafts:oversize:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(name="x" * 10000), manuscript())) == \
        "pitch_drafts:too_long_field:guidelines"


def test_exact_caps_accepted_when_clean():
    pd.score_fit(guidelines(name="x" * 200, scope_keywords=["x" * 200]), manuscript(title="y" * 200))
    pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(name="n" * 100), "z" * 200)
    pd.queue_add([], hand(subject="s" * 300, target_name="t" * 200, body="b" * 5000))


def test_doc_has_no_artifact_references():
    import pathlib
    t = (pathlib.Path(__file__).resolve().parents[2] / "docs" / "contracts" / "S4.4-pitch-drafts.md").read_text()
    low = t.lower()
    for bad in (".jsonl", ".json", "delivery folder", "invalid_run", "mutation_run", "doc hygiene",
                "private", "ledger", "mutation.jsonl", "stale_docs"):
        assert bad not in low, bad
    for keep in ("stale `.pyc`", "void", "LIMITS", "INTERPRETATION CHOICE"):
        assert keep in t, keep


def test_author_summary_type_and_empty_codes_pinned():
    for bad, code in (("", "empty:author"), (5, "bad_type:author")):
        m = msg(lambda: pd.make_org_pitch_draft(jtarget(), author(summary=bad), "ask"))
        assert m.endswith(code), m
        m = msg(lambda: pd.make_org_pitch_draft(jtarget(), author(name=bad), "ask"))
        assert m.endswith(code), m
