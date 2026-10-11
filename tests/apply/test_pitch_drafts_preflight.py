"""S4.4 R3: Cf in the forbidden set, and a cardinality-first preflight (containers only counted,
raw key and raw string caps) that runs before any per-character scan. OVERSIZE codes win over
content errors."""
import pytest

from app.apply import pitch_drafts as pd
from test_pitch_drafts import approval_for, author, guidelines, jdraft, jtarget, manuscript, pdraft
from test_pitch_drafts_validation import hand, stored

R = pd.PitchRefusal


def msg(fn):
    with pytest.raises(R) as e:
        fn()
    return str(e.value)


CF = ["\u200b", "\u00ad", "\ufeff", "\u202e", "\u2060", "\u200d", "\u061c", "\U000e0001"]


# ---- Cf
def test_forbidden_categories_literal():
    assert pd._FORBIDDEN == ("Cc", "Zl", "Zp", "Cf")
    assert (pd.MAX_CONTAINERS, pd.MAX_DICT_KEYS, pd.MAX_LIST_ITEMS) == (256, 32, 64)
    assert (pd.MAX_KEY_CHARS, pd.MAX_RAW_STR) == (64, 10000)


@pytest.mark.parametrize("ch", CF)
def test_cf_refused_everywhere_not_echoed(ch):
    secret = "SEC" + ch + "RET"
    d = jdraft()
    calls = [
        ("guidelines", lambda: pd.score_fit(guidelines(name=secret), manuscript())),
        ("guidelines", lambda: pd.score_fit(guidelines(scope_keywords=[secret]), manuscript())),
        ("manuscript", lambda: pd.score_fit(guidelines(), manuscript(title=secret))),
        ("target", lambda: pd.make_org_pitch_draft({"name": secret, "recipient": "a@b.org"}, author(), "y")),
        ("target", lambda: pd.make_org_pitch_draft({"name": "O", "recipient": secret}, author(), "y")),
        ("author", lambda: pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(summary=secret), "y")),
        ("ask", lambda: pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(), secret)),
        ("approval", lambda: pd.release(pd.queue_add([], d), approval_for(d, approved_by=secret))),
        ("queue", lambda: pd.queue_add([], dict(d, subject=secret))),
        ("queue", lambda: pd.queue_add([], dict(d, body="a" + ch + "b"))),
        ("guidelines", lambda: pd.score_fit(dict(guidelines(), **{"k" + ch: 1}), manuscript())),
    ]
    for label, c in calls:
        m = msg(c)
        assert m == "pitch_drafts:control_chars:" + label, (label, m)
        assert "SEC" not in m and "RET" not in m


def test_body_keeps_only_cc_whitespace():
    d = jdraft()
    body = "a\tb\r\nc"
    h = pd._sha(d["recipient"] + "\n" + d["subject"] + "\n" + body)
    ok = dict(d, body=body, text_sha256=h, draft_id=h[:16])
    pd.queue_add([], ok)
    bad_body = body + "\u200b"
    h = pd._sha(d["recipient"] + "\n" + d["subject"] + "\n" + bad_body)
    assert msg(lambda: pd.queue_add([], dict(d, body=bad_body, text_sha256=h, draft_id=h[:16]))) == \
        "pitch_drafts:control_chars:queue"


# ---- cardinality caps
def test_dict_key_count_fence():
    g = guidelines()
    extra = {"x%d" % i: 1 for i in range(32 - len(g))}
    assert len(dict(g, **extra)) == 32
    assert msg(lambda: pd.score_fit(dict(g, **extra), manuscript())) == "pitch_drafts:unknown_field:guidelines"
    extra["one_more"] = 1
    assert msg(lambda: pd.score_fit(dict(g, **extra), manuscript())) == "pitch_drafts:oversize:guidelines"


def test_list_item_count_fence():
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=["k"] * 51), manuscript())) == \
        "pitch_drafts:list_size:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=["k"] * 64), manuscript())) == \
        "pitch_drafts:list_size:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=["k"] * 65), manuscript())) == \
        "pitch_drafts:oversize:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(sections=["s"] * 65))) == \
        "pitch_drafts:oversize:manuscript"


def test_key_length_fence():
    g = guidelines()
    assert msg(lambda: pd.score_fit(dict(g, **{"k" * 64: 1}), manuscript())) == \
        "pitch_drafts:unknown_field:guidelines"
    assert msg(lambda: pd.score_fit(dict(g, **{"k" * 65: 1}), manuscript())) == \
        "pitch_drafts:oversize:guidelines"
    assert msg(lambda: pd.score_fit(dict(g, **{"k" * 65 + "\x00": 1}), manuscript())) == \
        "pitch_drafts:oversize:guidelines"


def test_raw_string_fence():
    assert msg(lambda: pd.score_fit(guidelines(name="x" * 10000), manuscript())) == \
        "pitch_drafts:too_long_field:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(name="x" * 10001), manuscript())) == \
        "pitch_drafts:oversize:guidelines"
    t = {"name": "O", "recipient": "a@b.org"}
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), "x" * 10000)) == "pitch_drafts:too_long_field:ask"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), "x" * 10001)) == "pitch_drafts:oversize:ask"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), "x" * 10001 + "\x00")) == "pitch_drafts:oversize:ask"
    assert msg(lambda: pd.queue_add([], hand(body="x" * 10000))) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], hand(body="x" * 10001))) == "pitch_drafts:oversize:queue"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=["x" * 10001]), manuscript())) == \
        "pitch_drafts:oversize:guidelines"


def test_container_budget_fence():
    def build(total_inner):
        # outer list of 4 mid lists, each holding up to 64 empty leaf lists; total_inner counts mid+leaf
        leaves = total_inner - 4
        sizes = [leaves // 4 + (1 if i < leaves % 4 else 0) for i in range(4)]
        return [[[] for _ in range(n)] for n in sizes]
    # root dict + three lists in guidelines() (keywords, formats, sections) + inner containers: 256 allowed
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=build(252)), manuscript())) == \
        "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=build(253)), manuscript())) == \
        "pitch_drafts:oversize:guidelines"


def test_oversize_wins_over_content_errors():
    big = {"x%d" % i: object() for i in range(40)}
    assert msg(lambda: pd.score_fit(big, manuscript())) == "pitch_drafts:oversize:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(name="a\x00", source_url="x" * 10001), manuscript())) == \
        "pitch_drafts:oversize:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(name="a\u200b", scope_keywords=["k"] * 65), manuscript())) == \
        "pitch_drafts:oversize:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(name="a\x00", scope_keywords=[1.5, "k" * 10001]), manuscript())) == \
        "pitch_drafts:oversize:guidelines"


def test_hostile_unbounded_inputs_refused_without_scan():
    huge_dict = {str(i): 1 for i in range(200000)}
    huge_list = list(range(200000))
    huge_str = "x" * 5000000 + "\x00"
    assert msg(lambda: pd.score_fit(huge_dict, manuscript())) == "pitch_drafts:oversize:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=huge_list), manuscript())) == \
        "pitch_drafts:oversize:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(name=huge_str), manuscript())) == \
        "pitch_drafts:oversize:guidelines"
    d = jdraft()
    q = pd.queue_add([], d)
    assert msg(lambda: pd.release(q, dict(approval_for(d), draft_id=huge_str))) == "pitch_drafts:oversize:approval"
    assert msg(lambda: pd.release(q, huge_dict)) == "pitch_drafts:oversize:approval"
    assert msg(lambda: pd.release(huge_list, approval_for(d))) == "pitch_drafts:oversize:queue"
    assert msg(lambda: pd.queue_add([], dict(d, body=huge_str))) == "pitch_drafts:oversize:queue"
    assert msg(lambda: pd.queue_add([], huge_dict)) == "pitch_drafts:oversize:queue"
    assert msg(lambda: pd.make_journal_draft(jtarget(name=huge_str), manuscript(), author(), {})) == \
        "pitch_drafts:oversize:target"
    assert msg(lambda: pd.make_journal_draft(jtarget(), manuscript(), author(summary=huge_str), {})) == \
        "pitch_drafts:oversize:author"


def test_queue_surfaces():
    d = jdraft()
    assert msg(lambda: pd.queue_add([], dict(d, **{"k" * 65: 1}))) == "pitch_drafts:oversize:queue"
    extra = {"x%d" % i: 1 for i in range(33 - len(d))}
    assert msg(lambda: pd.queue_add([], dict(d, **extra))) == "pitch_drafts:oversize:queue"
    q = [stored(jdraft()) for _ in range(65)]
    assert msg(lambda: pd.release(q, approval_for(d))) == "pitch_drafts:oversize:queue"
    # 51 entries still reach the size check
    assert msg(lambda: pd.release([stored(d)] * 51, approval_for(d))) == "pitch_drafts:queue_full"
    # the list and its 50 drafts are 51 containers
    many = []
    for i in range(50):
        many = pd.queue_add(many, pd.make_org_pitch_draft(
            {"name": "O%d" % i, "recipient": "a%d@b.org" % i}, author(), "y"))
    pd.release(many, approval_for(many[0]))


def test_fit_and_approval_surfaces():
    f = pd.score_fit(guidelines(), manuscript())
    f["checks"] = f["checks"] * 14
    assert msg(lambda: pd.make_journal_draft(jtarget(), manuscript(), author(), f)) == "pitch_drafts:oversize:fit"
    f = pd.score_fit(guidelines(), manuscript())
    f["x" * 65] = 1
    assert msg(lambda: pd.make_journal_draft(jtarget(), manuscript(), author(), f)) == "pitch_drafts:oversize:fit"
    d = jdraft()
    q = pd.queue_add([], d)
    ap = dict(approval_for(d), **{"x%d" % i: 1 for i in range(40)})
    assert msg(lambda: pd.release(q, ap)) == "pitch_drafts:oversize:approval"


def test_depth_still_enforced_by_preflight():
    def nest(k):
        v = "a"
        for _ in range(k):
            v = [v]
        return v
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=nest(5)), manuscript())) != "pitch_drafts:too_deep"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=nest(6)), manuscript())) == "pitch_drafts:too_deep"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=nest(6) + ["k" * 10001]), manuscript())) in (
        "pitch_drafts:too_deep", "pitch_drafts:oversize:guidelines")


def test_subclass_containers_refused_without_len_call():
    class D(dict):
        def __len__(self):
            raise AssertionError("len called on a subclass")

    class L(list):
        def __len__(self):
            raise AssertionError("len called on a subclass")
    assert msg(lambda: pd.score_fit(D(guidelines()), manuscript())) == "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=L(["a"])), manuscript())) == "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=[D()]), manuscript())) == "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.queue_add(L(), jdraft())) == "pitch_drafts:bad_type:queue"


def test_doc_hygiene():
    import pathlib
    t = (pathlib.Path(__file__).resolve().parents[2] / "docs" / "contracts" / "S4.4-pitch-drafts.md").read_text()
    low = t.lower()
    for bad in ("private ledger", "pin offsets", "integrator", "adopt", 'approved_by == "owner"'):
        assert bad not in low, bad
    assert "data-integrity string" in t and "not owner authentication" in t
    assert "fixed approver marker" in t
