"""Offline packet preparation fixtures and refusal checks."""
import ast
import copy
import hashlib
import inspect
import json
import random

import pytest

from app.apply import pitch_drafts as pd

REFUSAL = pd.PitchRefusal


def guidelines(**kw):
    g = {"name": "Journal of Tiny Results", "source_url": "https://example.org/guidelines",
         "as_of": "2026-10-01", "scope_keywords": ["orbit", "photometry", "exoplanet"],
         "min_words": 1000, "max_words": 5000, "accepted_formats": ["pdf", "docx"],
         "required_sections": ["abstract", "methods"], "fee_usd": 0}
    g.update(kw)
    return g


def manuscript(**kw):
    m = {"title": "A small transit study", "words": 3000, "keywords": ["Orbit", "photometry"],
         "format": "pdf", "sections": ["abstract", "methods", "results"], "max_fee_usd": 0}
    m.update(kw)
    return m


def author(**kw):
    a = {"name": "Udita Phookan", "summary": "We measured transit depth for two targets."}
    a.update(kw)
    return a


def jtarget(**kw):
    t = {"name": "Journal of Tiny Results", "recipient": "editor@example.org"}
    t.update(kw)
    return t


def jdraft():
    fit = pd.score_fit(guidelines(), manuscript())
    return pd.make_journal_draft(jtarget(), manuscript(), author(), fit)


def pdraft(**kw):
    t = {"name": "Example Observatory", "recipient": "outreach@example.org"}
    return pd.make_org_pitch_draft(t, author(), kw.get("ask", "a 20 minute call about data access"))


def approval_for(d, **kw):
    a = {"draft_id": d["draft_id"], "recipient": d["recipient"], "text_sha256": d["text_sha256"],
         "approved_by": "owner"}
    a.update(kw)
    return a


# ---- known answers
def test_fit_known_all_pass():
    f = pd.score_fit(guidelines(), manuscript())
    assert f["score"] == 100 and f["verdict"] == "FIT_CONDITIONS_MET"
    assert [c["name"] for c in f["checks"]] == ["scope", "length", "format", "sections", "fee"]
    assert all(c["passed"] for c in f["checks"])
    assert f["honesty"] == {"semantic_fit_judged": False, "acceptance_predicted": False,
                            "sent": False}


def test_fit_known_partial_and_low():
    f = pd.score_fit(guidelines(), manuscript(format="odt"))
    assert f["score"] == 88 and f["verdict"] == "PARTIAL"  # 8 of 9 weight
    f = pd.score_fit(guidelines(), manuscript(keywords=["cats"], words=10, format="odt",
                                              sections=["results"], max_fee_usd=0))
    # only fee (weight 1) of 9 passes -> 11
    assert f["score"] == 11 and f["verdict"] == "LOW_FIT"
    f = pd.score_fit(guidelines(fee_usd=100), manuscript(max_fee_usd=99))
    assert f["checks"][-1]["passed"] is False and f["score"] == 88


def test_fit_fee_boundary():
    assert pd.score_fit(guidelines(fee_usd=100), manuscript(max_fee_usd=100))["score"] == 100
    assert pd.score_fit(guidelines(fee_usd=101), manuscript(max_fee_usd=100))["score"] < 100


def test_length_bounds_exact():
    g = guidelines()
    for w, ok in ((999, False), (1000, True), (5000, True), (5001, False)):
        f = pd.score_fit(g, manuscript(words=w))
        assert f["checks"][1]["passed"] is ok, w


def test_scope_overlap_rules():
    g = guidelines()
    one = pd.score_fit(g, manuscript(keywords=["orbit", "zzz"]))["checks"][0]
    assert one["passed"] is False and one["overlap"] == 1
    two = pd.score_fit(g, manuscript(keywords=["ORBIT", "Photometry", "zzz"]))["checks"][0]
    assert two["passed"] is True and two["overlap"] == 2
    single = pd.score_fit(g, manuscript(keywords=["orbit"]))["checks"][0]
    assert single["passed"] is True  # min(2, len) = 1
    # duplicates in keywords count once
    dup = pd.score_fit(g, manuscript(keywords=["orbit", "Orbit"]))["checks"][0]
    assert dup["overlap"] == 1 and dup["passed"] is True


def test_oracle_generated_corpus():
    rnd = random.Random(44)
    vocab = ["a", "b", "c", "d", "e", "f"]
    for _ in range(300):
        gk = rnd.sample(vocab, rnd.randint(1, 5))
        mk = [rnd.choice(vocab) for _ in range(rnd.randint(1, 5))]
        mn = rnd.randint(1, 50)
        mx = mn + rnd.randint(0, 50)
        w = rnd.randint(0, 120)
        fmts = rnd.sample(["pdf", "docx", "odt"], rnd.randint(1, 3))
        fmt = rnd.choice(["pdf", "docx", "odt"])
        req = rnd.sample(["x", "y", "z"], rnd.randint(0, 3))
        have = rnd.sample(["x", "y", "z"], rnd.randint(0, 3))
        fee = rnd.randint(0, 5)
        cap = rnd.randint(0, 5)
        g = guidelines(scope_keywords=gk, min_words=mn, max_words=mx, accepted_formats=fmts,
                       required_sections=req, fee_usd=fee)
        m = manuscript(keywords=mk, words=w, format=fmt, sections=have, max_fee_usd=cap)
        ov = len(set(gk) & set(mk))
        passes = [ov >= min(2, len(set(mk))) and ov > 0, mn <= w <= mx, fmt in fmts,
                  all(r in have for r in req), fee <= cap]
        weights = [3, 2, 1, 2, 1]
        pts = sum(wt for wt, p in zip(weights, passes) if p)
        f = pd.score_fit(g, m)
        assert f["score"] == pts * 100 // 9
        exp = "FIT_CONDITIONS_MET" if all(passes) else ("PARTIAL" if f["score"] >= 50 else "LOW_FIT")
        assert f["verdict"] == exp


# ---- drafts
def test_journal_draft_shape_and_hash():
    d = jdraft()
    assert d["kind"] == "journal" and d["status"] == "DRAFT" and d["recipient"] == "editor@example.org"
    assert "Udita Phookan" in d["body"] and "A small transit study" in d["body"]
    assert d["text_sha256"] == hashlib.sha256(
        (d["recipient"] + "\n" + d["subject"] + "\n" + d["body"]).encode()).hexdigest()
    assert d["draft_id"] == d["text_sha256"][:16]
    assert d["sent"] is False


def test_journal_no_unsupplied_claims():
    d = jdraft()
    assert "elsewhere" not in d["body"].lower()
    m = manuscript()
    fit = pd.score_fit(guidelines(), m)
    d2 = pd.make_journal_draft(jtarget(), m, author(not_under_review_elsewhere=True), fit)
    assert "not under review elsewhere" in d2["body"]
    d3 = pd.make_journal_draft(jtarget(), m, author(not_under_review_elsewhere=False), fit)
    assert "elsewhere" not in d3["body"].lower()


def test_pitch_length_bound():
    ok = pdraft()
    assert ok["kind"] == "org_pitch"
    n = len(ok["body"].split())
    assert n <= pd.MAX_PITCH_WORDS
    base = len(pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"},
                                       author(summary="x"), "y")["body"].split())
    room = pd.MAX_PITCH_WORDS - base
    s = " ".join(["w"] * (1 + room))
    pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(summary=s), "y")
    with pytest.raises(REFUSAL) as e:
        pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"},
                                author(summary=s + " w"), "y")
    assert str(e.value) == "pitch_drafts:too_long"


def test_line_count_invariant():
    a = jdraft()["body"].count("\n")
    m = manuscript(title="Other title", words=1200)
    fit = pd.score_fit(guidelines(name="Another"), m)
    b = pd.make_journal_draft(jtarget(name="Another"), m, author(name="Zed"), fit)["body"].count("\n")
    assert a == b
    assert pdraft()["body"].count("\n") == pdraft(ask="different ask")["body"].count("\n")


def test_recipient_rules():
    for bad in ["", "a", "a@b", "a@@b.org", "@b.org", "a@.org", "a b@c.org", "a@b.", "a@b..org"]:
        with pytest.raises(REFUSAL) as e:
            pd.make_org_pitch_draft({"name": "O", "recipient": bad}, author(), "y")
        assert str(e.value) == ("pitch_drafts:empty:target" if bad == "" else "pitch_drafts:bad_recipient"), bad
    with pytest.raises(REFUSAL) as e:
        pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org,c@d.org"}, author(), "y")
    assert str(e.value) == "APPLY_REFUSED_BULK"
    with pytest.raises(REFUSAL) as e:
        pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org;c@d.org"}, author(), "y")
    assert str(e.value) == "APPLY_REFUSED_BULK"


def test_fit_must_match_inputs():
    m = manuscript()
    fit = pd.score_fit(guidelines(), m)
    forged = copy.deepcopy(fit)
    forged["score"] = 5
    with pytest.raises(REFUSAL) as e:
        pd.make_journal_draft(jtarget(), m, author(), forged)
    assert str(e.value) == "pitch_drafts:fit_mismatch"
    other = pd.score_fit(guidelines(), manuscript(title="Different"))
    with pytest.raises(REFUSAL) as e:
        pd.make_journal_draft(jtarget(), m, author(), other)
    assert str(e.value) == "pitch_drafts:fit_mismatch"


def test_low_fit_journal_draft_refused():
    m = manuscript(keywords=["cats"], words=10, format="odt", sections=["results"])
    fit = pd.score_fit(guidelines(), m)
    assert fit["verdict"] == "LOW_FIT"
    with pytest.raises(REFUSAL) as e:
        pd.make_journal_draft(jtarget(), m, author(), fit)
    assert str(e.value) == "pitch_drafts:low_fit"


# ---- queue and approval
def test_queue_add_and_bounds():
    q = pd.queue_add([], jdraft())
    assert len(q) == 1 and q[0]["status"] == "QUEUED"
    with pytest.raises(REFUSAL) as e:
        pd.queue_add(q, jdraft())
    assert str(e.value) == "pitch_drafts:duplicate"
    q = []
    for i in range(pd.MAX_QUEUE):
        q = pd.queue_add(q, pd.make_org_pitch_draft(
            {"name": "O%d" % i, "recipient": "a%d@b.org" % i}, author(), "y"))
    assert len(q) == pd.MAX_QUEUE
    with pytest.raises(REFUSAL) as e:
        pd.queue_add(q, pdraft())
    assert str(e.value) == "pitch_drafts:queue_full"


def test_release_without_approval_refused():
    q = pd.queue_add([], jdraft())
    for bad in (None, {}, "owner"):
        with pytest.raises(REFUSAL) as e:
            pd.release(q, bad)
        assert str(e.value) in ("APPLY_REFUSED_SEND", "pitch_drafts:bad_type:approval")


def test_release_happy_path_and_single_use():
    d = jdraft()
    q = pd.queue_add([], d)
    q2, packet = pd.release(q, approval_for(d))
    assert q2[0]["status"] == "APPROVED_FOR_MANUAL_SEND"
    assert packet["recipient"] == d["recipient"] and packet["body"] == d["body"]
    assert packet["sent"] is False and packet["send_instruction"] == "OWNER_SENDS_MANUALLY"
    assert q[0]["status"] == "QUEUED"  # input not mutated
    with pytest.raises(REFUSAL) as e:
        pd.release(q2, approval_for(d))
    assert str(e.value) == "APPLY_REFUSED_SEND"


@pytest.mark.parametrize("field,val", [
    ("recipient", "other@example.org"), ("text_sha256", "0" * 64), ("draft_id", "0" * 16),
    ("approved_by", "agent"), ("approved_by", "Owner")])
def test_release_mismatch_refused(field, val):
    d = jdraft()
    q = pd.queue_add([], d)
    with pytest.raises(REFUSAL) as e:
        pd.release(q, approval_for(d, **{field: val}))
    assert str(e.value) == "APPLY_REFUSED_SEND"


def test_release_edited_text_invalidates_approval():
    d = jdraft()
    approval = approval_for(d)
    q = pd.queue_add([], d)
    q[0] = dict(q[0], body=q[0]["body"] + " edited")
    with pytest.raises(REFUSAL) as e:
        pd.release(q, approval)
    assert str(e.value) == "pitch_drafts:bad_draft"


def test_release_approval_shape_strict():
    d = jdraft()
    q = pd.queue_add([], d)
    with pytest.raises(REFUSAL) as e:
        pd.release(q, dict(approval_for(d), extra=1))
    assert str(e.value) == "pitch_drafts:unknown_field:approval"
    a = approval_for(d)
    del a["approved_by"]
    with pytest.raises(REFUSAL) as e:
        pd.release(q, a)
    assert str(e.value) == "pitch_drafts:missing_field:approval"


def test_release_only_named_draft():
    d1, d2 = jdraft(), pdraft()
    q = pd.queue_add(pd.queue_add([], d1), d2)
    q2, _ = pd.release(q, approval_for(d2))
    assert [x["status"] for x in q2] == ["QUEUED", "APPROVED_FOR_MANUAL_SEND"]


def test_release_unknown_draft_refused():
    q = pd.queue_add([], jdraft())
    d = pdraft()
    with pytest.raises(REFUSAL) as e:
        pd.release(q, approval_for(d))
    assert str(e.value) == "APPLY_REFUSED_SEND"


# ---- strict types, control chars, no echo
class S(str):
    pass


class I(int):
    pass


class D(dict):
    pass


class L(list):
    pass


def test_strict_types():
    with pytest.raises(REFUSAL):
        pd.score_fit(D(guidelines()), manuscript())
    with pytest.raises(REFUSAL):
        pd.score_fit(guidelines(name=S("x")), manuscript())
    with pytest.raises(REFUSAL):
        pd.score_fit(guidelines(min_words=I(1)), manuscript())
    with pytest.raises(REFUSAL):
        pd.score_fit(guidelines(min_words=True), manuscript())
    with pytest.raises(REFUSAL):
        pd.score_fit(guidelines(scope_keywords=L(["a"])), manuscript())
    with pytest.raises(REFUSAL):
        pd.score_fit(guidelines(), manuscript(words=1000.0))
    with pytest.raises(REFUSAL):
        pd.make_org_pitch_draft({"name": "O", "recipient": S("a@b.org")}, author(), "y")
    d = jdraft()
    q = pd.queue_add([], d)
    with pytest.raises(REFUSAL):
        pd.release(L(q), approval_for(d))
    with pytest.raises(REFUSAL):
        pd.release(q, D(approval_for(d)))
    with pytest.raises(REFUSAL):
        pd.queue_add(tuple(), d)


@pytest.mark.parametrize("ch", ["\n", "\r", "\t", "\x00", "\x1b", "\u2028", "\u2029", "\x7f", "\x85"])
def test_control_chars_refused_not_echoed(ch):
    secret = "SECRET" + ch + "VALUE"
    calls = [
        lambda: pd.score_fit(guidelines(name=secret), manuscript()),
        lambda: pd.score_fit(guidelines(scope_keywords=[secret]), manuscript()),
        lambda: pd.score_fit(guidelines(), manuscript(title=secret)),
        lambda: pd.make_org_pitch_draft({"name": secret, "recipient": "a@b.org"}, author(), "y"),
        lambda: pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(summary=secret), "y"),
        lambda: pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(), secret),
        lambda: pd.make_org_pitch_draft({"name": "O", "recipient": secret}, author(), "y"),
    ]
    for c in calls:
        with pytest.raises(REFUSAL) as e:
            c()
        assert "SECRET" not in str(e.value) and "VALUE" not in str(e.value)
        assert str(e.value).startswith("pitch_drafts:")
    # keys too
    with pytest.raises(REFUSAL) as e:
        pd.score_fit(dict(guidelines(), **{"k" + ch + "SECRET": 1}), manuscript())
    assert "SECRET" not in str(e.value)
    d = jdraft()
    with pytest.raises(REFUSAL) as e:
        pd.release(pd.queue_add([], d), approval_for(d, approved_by=secret))
    assert "SECRET" not in str(e.value)


# ---- limits on inputs
@pytest.mark.parametrize("field,n", [("name", 200), ("summary", 1200)])
def test_string_length_bounds(field, n):
    pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"},
                            author(**{field: "x" * (n if field == "name" else 1)}), "y")
    if field == "name":
        pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(name="x" * n), "y")
        with pytest.raises(REFUSAL) as e:
            pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(name="x" * (n + 1)), "y")
        assert str(e.value) == "pitch_drafts:too_long_field:author"


def test_keyword_list_bounds():
    kws = ["k%d" % i for i in range(pd.MAX_KEYWORDS)]
    pd.score_fit(guidelines(scope_keywords=kws), manuscript())
    with pytest.raises(REFUSAL):
        pd.score_fit(guidelines(scope_keywords=kws + ["extra"]), manuscript())
    with pytest.raises(REFUSAL):
        pd.score_fit(guidelines(scope_keywords=[]), manuscript())


def test_guideline_validation():
    for kw in [{"source_url": "http://example.org"}, {"source_url": ""}, {"as_of": "2026-13-01"},
               {"as_of": "10/01/2026"}, {"min_words": 6000}, {"min_words": -1},
               {"fee_usd": -1}, {"accepted_formats": []}, {"extra": 1}]:
        with pytest.raises(REFUSAL):
            pd.score_fit(guidelines(**kw), manuscript())
    g = guidelines()
    del g["source_url"]
    with pytest.raises(REFUSAL) as e:
        pd.score_fit(g, manuscript())
    assert str(e.value) in ("APPLY_REFUSED_NOSOURCE", "pitch_drafts:missing_field:guidelines")
    g = guidelines(min_words=7, max_words=7)
    assert pd.score_fit(g, manuscript(words=7))["checks"][1]["passed"]


def test_nosource_code():
    with pytest.raises(REFUSAL) as e:
        pd.score_fit(guidelines(source_url="ftp://x"), manuscript())
    assert str(e.value) == "APPLY_REFUSED_NOSOURCE"
    with pytest.raises(REFUSAL) as e:
        pd.score_fit(guidelines(as_of="not-a-date"), manuscript())
    assert str(e.value) == "APPLY_REFUSED_NOSOURCE"


# ---- determinism, no mutation
def test_deterministic_and_inputs_unmutated():
    g, m, a, t = guidelines(), manuscript(), author(), jtarget()
    snap = copy.deepcopy((g, m, a, t))
    f1 = pd.score_fit(g, m)
    d1 = pd.make_journal_draft(t, m, a, f1)
    f2 = pd.score_fit(g, m)
    d2 = pd.make_journal_draft(t, m, a, f2)
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
    assert (g, m, a, t) == snap
    q = pd.queue_add([], d1)
    qs = copy.deepcopy(q)
    ap = approval_for(d1)
    aps = copy.deepcopy(ap)
    pd.release(q, ap)
    assert q == qs and ap == aps


def test_returned_structures_not_aliased():
    d = jdraft()
    q = pd.queue_add([], d)
    q[0]["body"] = "tampered"
    assert d["body"] != "tampered"


# ---- AST purity: no I/O, no send path
def test_ast_purity():
    src = inspect.getsource(pd)
    tree = ast.parse(src)
    banned = {"socket", "smtplib", "http", "urllib", "requests", "subprocess", "os", "sys",
              "shutil", "pathlib", "ftplib", "email", "imaplib", "ssl", "random", "time",
              "datetime", "importlib", "builtins", "pickle", "ctypes", "asyncio", "threading"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not any(a.name.split(".")[0] in banned for a in n.names)
        if isinstance(n, ast.ImportFrom):
            assert (n.module or "").split(".")[0] not in banned
        if isinstance(n, ast.Name):
            assert n.id not in ("open", "eval", "exec", "compile", "__import__", "input", "print")
        if isinstance(n, ast.Attribute):
            assert n.attr not in ("send", "sendmail", "post", "request", "urlopen", "write", "system")
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            assert [a.arg for a in n.args.args] is not None
    public = {n.name for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}
    assert public == {"score_fit", "make_journal_draft", "make_org_pitch_draft", "queue_add", "release"}
    assert not any(name in public for name in ("send", "submit", "post", "email"))


def test_no_callable_params():
    for fn in (pd.score_fit, pd.make_journal_draft, pd.make_org_pitch_draft, pd.queue_add, pd.release):
        for p in inspect.signature(fn).parameters.values():
            assert p.default is inspect._empty  # no defaults, no injected hooks
            assert p.kind == p.POSITIONAL_OR_KEYWORD


def test_refusal_codes_prefixed():
    assert pd.SEND == "APPLY_REFUSED_SEND" and pd.BULK == "APPLY_REFUSED_BULK"
    assert pd.NOSOURCE == "APPLY_REFUSED_NOSOURCE"
    assert not hasattr(pd, "SPEND_OK")


def test_contract_doc_has_interpretation_tags_and_pin():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[2] / "docs" / "contracts" / "S4.4-pitch-drafts.md"
    t = p.read_text()
    assert t.count("INTERPRETATION CHOICE") >= 6
    assert "sends research to reputed journals, with my approval" in t
    assert "short pitches to organisations maybe like nasa, or non profits, cern etc. with my permission" in t
    assert "prototype" in t.lower() and "LIMITS" in t
