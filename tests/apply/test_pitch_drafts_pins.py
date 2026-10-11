"""S4.4 pins added after the first mutation battery (added after the red commit; see contract doc)."""
import copy

import pytest

from app.apply import pitch_drafts as pd
from test_pitch_drafts import (approval_for, author, guidelines, jdraft, jtarget,
                                           manuscript, pdraft)

R = pd.PitchRefusal


def msg(fn):
    with pytest.raises(R) as e:
        fn()
    return str(e.value)


def reseal(fit):
    body = {k: fit[k] for k in pd._FIT_KEYS if k not in ("honesty", "fit_sha256")}
    fit["fit_sha256"] = pd._sha(pd._canon(body))
    return fit


def fresh_fit():
    return pd.score_fit(guidelines(), manuscript())


def test_date_validity_table():
    ok = ["2026-01-31", "2026-02-28", "2024-02-29", "2000-02-29", "2026-03-31", "2026-04-30",
          "2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30", "2026-10-31",
          "2026-11-30", "2026-12-31", "0001-01-01"]
    bad = ["2026-02-29", "1900-02-29", "2100-02-29", "2026-04-31", "2026-06-31", "2026-09-31",
           "2026-11-31", "2026-01-32", "2026-03-32", "2026-02-30", "2026-00-10", "2026-13-01",
           "2026-10-00", "0000-10-10", "2026-10-1", "2026-1-010", "2026-10x01", "2026x10-01",
           "2026/10/01", "abcd-10-01", "2026-ab-01", "2026-10-ab", "2026-10-011", "20261001--",
           "\u0662\u0660\u0662\u0666-10-01", "2026-\u0661\u0660-01", "2026-10-\u0660\u0661", ""]
    for d in ok:
        pd.score_fit(guidelines(as_of=d), manuscript())
    for d in bad:
        m = msg(lambda: pd.score_fit(guidelines(as_of=d), manuscript()))
        assert m in (pd.NOSOURCE, "pitch_drafts:empty:guidelines"), d
        if d:
            assert m == pd.NOSOURCE, d


def test_source_url_rules():
    pd.score_fit(guidelines(source_url="https://a"), manuscript())
    for u in ["https://", "http://example.org", "https:/x", "https://a b", "HTTPS://a"]:
        assert msg(lambda: pd.score_fit(guidelines(source_url=u), manuscript())) == pd.NOSOURCE


def test_exact_messages_dict_labels():
    g, m, a, t = guidelines(), manuscript(), author(), jtarget()
    assert msg(lambda: pd.score_fit([], m)) == "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(g, [])) == "pitch_drafts:bad_type:manuscript"
    assert msg(lambda: pd.make_journal_draft([], m, a, fresh_fit())) == "pitch_drafts:bad_type:target"
    assert msg(lambda: pd.make_journal_draft(t, m, [], fresh_fit())) == "pitch_drafts:bad_type:author"
    assert msg(lambda: pd.make_journal_draft(t, m, a, [])) == "pitch_drafts:bad_type:fit"
    for label, call in [
        ("guidelines", lambda **k: pd.score_fit(guidelines(**k), m)),
        ("manuscript", lambda **k: pd.score_fit(g, manuscript(**k))),
        ("target", lambda **k: pd.make_org_pitch_draft(jtarget(**k), a, "y")),
        ("author", lambda **k: pd.make_org_pitch_draft(t, author(**k), "y")),
    ]:
        assert msg(lambda: call(zzz=1)) == "pitch_drafts:unknown_field:" + label
        assert msg(lambda: call(name="a\x00b")) == "pitch_drafts:control_chars:" + label \
            or label == "manuscript"
        assert msg(lambda: call(name=5)) == "pitch_drafts:bad_type:" + label \
            or label == "manuscript"
        assert msg(lambda: call(name="")) == "pitch_drafts:empty:" + label or label == "manuscript"
        assert msg(lambda: call(name="x" * 201)) == "pitch_drafts:too_long_field:" + label \
            or label == "manuscript"
    assert msg(lambda: pd.score_fit(g, manuscript(title=5))) == "pitch_drafts:bad_type:manuscript"
    assert msg(lambda: pd.score_fit(g, manuscript(title=""))) == "pitch_drafts:empty:manuscript"
    assert msg(lambda: pd.score_fit(g, manuscript(title="x" * 201))) == \
        "pitch_drafts:too_long_field:manuscript"
    assert msg(lambda: pd.score_fit(g, manuscript(title="a\u2028b"))) == \
        "pitch_drafts:control_chars:manuscript"
    pd.score_fit(g, manuscript(title="x" * 200))


def test_missing_fields_labels():
    g, m, a, t = guidelines(), manuscript(), author(), jtarget()
    for label, build in [
        ("guidelines", lambda d: pd.score_fit(d, m)),
        ("manuscript", lambda d: pd.score_fit(g, d)),
        ("target", lambda d: pd.make_org_pitch_draft(d, a, "y")),
        ("author", lambda d: pd.make_org_pitch_draft(t, d, "y")),
    ]:
        src = {"guidelines": g, "manuscript": m, "target": t, "author": a}[label]
        for k in list(src):
            if label == "author" and k == "not_under_review_elsewhere":
                continue
            d = {kk: vv for kk, vv in src.items() if kk != k}
            assert msg(lambda: build(d)) in ("pitch_drafts:missing_field:" + label, pd.NOSOURCE), (label, k)
            if k != "source_url":
                assert msg(lambda: build(d)) == "pitch_drafts:missing_field:" + label


def test_ints_and_lists_messages():
    m = manuscript()
    assert msg(lambda: pd.score_fit(guidelines(min_words=1.5), m)) == "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(min_words=-1), m)) == "pitch_drafts:range:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(min_words=2, max_words=1), m)) == \
        "pitch_drafts:range:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(max_words=pd.MAX_INT + 1), m)) == \
        "pitch_drafts:range:guidelines"
    pd.score_fit(guidelines(max_words=pd.MAX_INT), m)
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(words=pd.MAX_INT + 1))) == \
        "pitch_drafts:range:manuscript"
    assert msg(lambda: pd.score_fit(guidelines(fee_usd=pd.MAX_INT + 1), m)) == \
        "pitch_drafts:range:guidelines"
    pd.score_fit(guidelines(fee_usd=pd.MAX_INT), manuscript(max_fee_usd=pd.MAX_INT))
    assert pd.MAX_INT == 10 ** 7 and pd.MAX_STR == 200 and pd.MAX_SUMMARY == 1200
    assert pd.MAX_KEYWORDS == 50 and pd.MAX_QUEUE == 50 and pd.MAX_PITCH_WORDS == 200
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords="abc"), m)) == \
        "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=[]), m)) == \
        "pitch_drafts:list_size:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=["k"] * 51), m)) == \
        "pitch_drafts:list_size:guidelines"
    pd.score_fit(guidelines(scope_keywords=["k"] * 50), m)
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=[5]), m)) == \
        "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=[""]), m)) == \
        "pitch_drafts:bad_item:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=["x" * 201]), m)) == \
        "pitch_drafts:bad_item:guidelines"
    pd.score_fit(guidelines(scope_keywords=["x" * 200]), m)
    pd.score_fit(guidelines(required_sections=[]), m)
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(sections=["s"] * 51))) == \
        "pitch_drafts:list_size:manuscript"
    pd.score_fit(guidelines(), manuscript(sections=["s"] * 50))
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(keywords=[]))) == \
        "pitch_drafts:list_size:manuscript"


def test_summary_and_author_bounds():
    t = {"name": "O", "recipient": "a@b.org"}
    pd.make_org_pitch_draft(t, author(summary="x" * 1200), "y") if False else None
    # 1200 chars of one-letter words exceeds the pitch cap, so test the field cap on the journal path
    m = manuscript()
    fit = fresh_fit()
    pd.make_journal_draft(jtarget(), m, author(summary="x" * 1200), fit)
    assert msg(lambda: pd.make_journal_draft(jtarget(), m, author(summary="x" * 1201), fit)) == \
        "pitch_drafts:too_long_field:author"
    assert msg(lambda: pd.make_journal_draft(jtarget(), m, author(not_under_review_elsewhere=1), fit)) \
        == "pitch_drafts:bad_type:author"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(not_under_review_elsewhere=True), "y")) == \
        "pitch_drafts:unknown_field:author"


def test_ask_messages():
    t = {"name": "O", "recipient": "a@b.org"}
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), 5)) == "pitch_drafts:bad_type:ask"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), "a\x00")) == "pitch_drafts:control_chars:ask"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), "")) == "pitch_drafts:too_long_field:ask"
    assert msg(lambda: pd.make_org_pitch_draft(t, author(), "x" * 201)) == "pitch_drafts:too_long_field:ask"
    pd.make_org_pitch_draft(t, author(), "x" * 200)


def test_recipient_length_and_bulk():
    base = "a@b.org"
    for n, good in ((200, True), (201, False)):
        addr = "a" * (n - len(base) + 1) + "@b.org"
        assert len(addr) == n
        if good:
            pd.make_org_pitch_draft({"name": "O", "recipient": addr}, author(), "y")
        else:
            assert msg(lambda: pd.make_org_pitch_draft({"name": "O", "recipient": addr}, author(), "y")) \
                == "pitch_drafts:too_long_field:target"
    for bad in ["a@b.org,c", "a@b.org;c", "a,b", "a;b"]:
        assert msg(lambda: pd.make_org_pitch_draft({"name": "O", "recipient": bad}, author(), "y")) == pd.BULK
    for bad in ["ab.org", "a@b@c.org", "a b@c.org", "a@b c.org", "a@b.org.", "a@.b.org", "@b.org"]:
        assert msg(lambda: pd.make_org_pitch_draft({"name": "O", "recipient": bad}, author(), "y")) \
            == "pitch_drafts:bad_recipient"
    pd.make_org_pitch_draft({"name": "O", "recipient": "a@b.org"}, author(), "y")
    pd.make_org_pitch_draft({"name": "O", "recipient": "x@y.z.org"}, author(), "y")


def test_depth_limit():
    def nest(k):
        v = "a"
        for _ in range(k):
            v = [v]
        return v
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=nest(5)), manuscript())) != \
        "pitch_drafts:too_deep"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=nest(6)), manuscript())) == \
        "pitch_drafts:too_deep"


def test_foreign_leaf_types():
    assert msg(lambda: pd.score_fit(guidelines(extra_ok=None), manuscript())) == \
        "pitch_drafts:unknown_field:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(scope_keywords=[(1,)]), manuscript())) == \
        "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit({1: 2}, manuscript())) == "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(words=object()))) == \
        "pitch_drafts:bad_type:manuscript"


def test_fit_forgery_variants_all_refused():
    m = manuscript()
    t = jtarget()
    a = author()

    def refused(mut, code="pitch_drafts:fit_mismatch"):
        f = fresh_fit()
        mut(f)
        reseal(f)
        assert msg(lambda: pd.make_journal_draft(t, m, a, f)) == code

    refused(lambda f: f["honesty"].update(sent=True))
    refused(lambda f: f.update(checks={"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}))
    def drop(f):
        f["checks"] = f["checks"][:4]
        f["score"] = 88
        f["verdict"] = "PARTIAL"
    refused(drop)
    def extra(f):
        f["checks"] = f["checks"] + [dict(f["checks"][0])]
    refused(extra)
    refused(lambda f: f["checks"].__setitem__(0, "x"))
    refused(lambda f: f["checks"][0].update(name="other"))
    refused(lambda f: f["checks"][0].update(weight=4))
    refused(lambda f: f["checks"][0].update(passed=1))
    refused(lambda f: f["checks"][0].pop("passed"))
    refused(lambda f: f.update(score=99))
    refused(lambda f: f.update(verdict="PARTIAL"))
    refused(lambda f: f.update(manuscript_sha256="0" * 64))
    refused(lambda f: f.update(target_name="Other"))
    # honest consistent downgrade is accepted for LOW_FIT detection
    def low(f):
        for c in f["checks"][:4]:
            c["passed"] = False
        f["score"] = 11
        f["verdict"] = "LOW_FIT"
    refused(low, "pitch_drafts:low_fit")
    # verdict flip only with matching score refused
    f = fresh_fit()
    f["checks"][4]["passed"] = False
    f["score"] = 88
    f["verdict"] = "FIT_CONDITIONS_MET"
    assert msg(lambda: pd.make_journal_draft(t, m, a, reseal(f))) == "pitch_drafts:fit_mismatch"
    # unsealed tamper
    f = fresh_fit()
    f["target_name"] = "x"
    assert msg(lambda: pd.make_journal_draft(t, m, a, f)) == "pitch_drafts:fit_mismatch"
    f = fresh_fit()
    f["zzz"] = 1
    assert msg(lambda: pd.make_journal_draft(t, m, a, f)) == "pitch_drafts:unknown_field:fit"
    f = fresh_fit()
    del f["as_of"]
    assert msg(lambda: pd.make_journal_draft(t, m, a, f)) == "pitch_drafts:missing_field:fit"
    f = fresh_fit()
    f["as_of"] = "a\x00"
    assert msg(lambda: pd.make_journal_draft(t, m, a, f)) == "pitch_drafts:control_chars:fit"


def test_partial_cutoff_exact():
    # weights: scope3 length2 format1 sections2 fee1 of 9. score 55 = 5 points, 44 = 4 points
    g = guidelines()
    f5 = pd.score_fit(g, manuscript(words=10, format="odt"))        # fails length+format -> 6/9=66
    assert f5["score"] == 66 and f5["verdict"] == "PARTIAL"
    f4 = pd.score_fit(g, manuscript(keywords=["zzz"]))              # fails scope -> 6/9=66
    assert f4["score"] == 66
    f = pd.score_fit(g, manuscript(keywords=["zzz"], format="odt", words=10))  # sections+fee = 3/9 = 33
    assert f["score"] == 33 and f["verdict"] == "LOW_FIT"
    f = pd.score_fit(g, manuscript(keywords=["zzz"], sections=[]))  # length+format+fee = 4/9 = 44
    assert f["score"] == 44 and f["verdict"] == "LOW_FIT"
    f = pd.score_fit(g, manuscript(words=10, sections=[]))          # scope+format+fee = 5/9 = 55
    assert f["score"] == 55 and f["verdict"] == "PARTIAL"


def test_scope_zero_overlap_with_single_keyword():
    c = pd.score_fit(guidelines(), manuscript(keywords=["zzz"]))["checks"][0]
    assert c["passed"] is False and c["overlap"] == 0


def test_draft_body_pinned():
    d = jdraft()
    assert d["body"] == ('Dear Editor,\n\nI would like to submit the manuscript "A small transit study" '
                         '(3000 words, pdf) for consideration in Journal of Tiny Results.\n\n'
                         'We measured transit depth for two targets.\n\nSincerely,\nUdita Phookan')
    assert d["subject"] == "Submission enquiry: A small transit study"
    assert d["kind"] == "journal" and d["target_name"] == "Journal of Tiny Results"
    p = pdraft()
    assert p["body"] == ("Dear Example Observatory team,\n\nMy name is Udita Phookan. We measured transit "
                         "depth for two targets.\n\nI would like to ask for a 20 minute call about data "
                         "access.\n\nThank you for your time.\n\nUdita Phookan")
    assert p["subject"] == "Enquiry from Udita Phookan" and p["kind"] == "org_pitch"
    assert p["status"] == "DRAFT" and p["sent"] is False


def test_queue_validation_messages():
    d = jdraft()
    assert msg(lambda: pd.queue_add({}, d)) == "pitch_drafts:bad_type:queue"
    assert msg(lambda: pd.queue_add([5], d)) == "pitch_drafts:bad_type:queue"
    assert msg(lambda: pd.queue_add([], 5)) == "pitch_drafts:bad_type:queue"
    assert msg(lambda: pd.queue_add([], {})) == "pitch_drafts:bad_draft"
    assert msg(lambda: pd.queue_add([], dict(d, extra=1))) == "pitch_drafts:bad_draft"
    d2 = dict(d)
    del d2["kind"]
    assert msg(lambda: pd.queue_add([], d2)) == "pitch_drafts:bad_draft"
    d3 = dict(d)
    del d3["text_sha256"]
    d3["zzz"] = 1
    assert msg(lambda: pd.queue_add([], d3)) == "pitch_drafts:bad_draft"
    for k, v in [("status", "QUEUED"), ("sent", True), ("sent", 0), ("text_sha256", "0" * 64),
                 ("draft_id", "0" * 16), ("body", d["body"] + "x"), ("recipient", "z@example.org"),
                 ("subject", "other")]:
        assert msg(lambda: pd.queue_add([], dict(d, **{k: v}))) == "pitch_drafts:bad_draft", k
    assert msg(lambda: pd.queue_add([], dict(d, body="a\x00"))) == "pitch_drafts:control_chars:queue"
    assert msg(lambda: pd.queue_add([], dict(d, **{"k\x00": 1}))) == "pitch_drafts:control_chars:queue"
    # body may keep tab/CR/LF, but then the hash must be right
    body = "a\tb\r\nc"
    h = pd._sha(d["recipient"] + "\n" + d["subject"] + "\n" + body)
    ok = dict(d, body=body, text_sha256=h, draft_id=h[:16])
    assert pd.queue_add([], ok)[0]["body"] == body
    # other fields refuse tab
    h2 = pd._sha(d["recipient"] + "\n" + "s\tx" + "\n" + d["body"])
    bad = dict(d, subject="s\tx", text_sha256=h2, draft_id=h2[:16])
    assert msg(lambda: pd.queue_add([], bad)) == "pitch_drafts:control_chars:queue"


def test_queue_add_exact_size_fence():
    q = []
    for i in range(49):
        q = pd.queue_add(q, pd.make_org_pitch_draft(
            {"name": "O%d" % i, "recipient": "a%d@b.org" % i}, author(), "y"))
    q = pd.queue_add(q, pdraft())          # 50th accepted
    assert len(q) == 50
    assert msg(lambda: pd.queue_add(q, jdraft())) == "pitch_drafts:queue_full"
    assert msg(lambda: pd.queue_add(q, pdraft())) == "pitch_drafts:duplicate"  # duplicate beats full


def test_release_messages_and_order():
    d = jdraft()
    q = pd.queue_add([], d)
    assert msg(lambda: pd.release({}, approval_for(d))) == "pitch_drafts:bad_type:queue"
    assert msg(lambda: pd.release([5], approval_for(d))) == "pitch_drafts:bad_type:queue"
    assert msg(lambda: pd.release(q, 0)) == pd.SEND
    assert msg(lambda: pd.release(q, {})) == pd.SEND
    for k in ("draft_id", "recipient", "text_sha256", "approved_by"):
        assert msg(lambda: pd.release(q, approval_for(d, **{k: 5}))) == "pitch_drafts:bad_type:approval"
        assert msg(lambda: pd.release(q, approval_for(d, **{k: "a\x00"}))) == \
            "pitch_drafts:control_chars:approval"
    # the item recorded hash is also checked, not only the approval's
    q2 = copy.deepcopy(q)
    q2[0]["text_sha256"] = "0" * 64
    assert msg(lambda: pd.release(q2, approval_for(d))) == "pitch_drafts:bad_draft"
    q3 = copy.deepcopy(q)
    q3[0]["status"] = "DRAFT"
    assert msg(lambda: pd.release(q3, approval_for(d))) == "pitch_drafts:bad_draft"
    # approval for a changed recipient on the stored item is refused
    q4 = copy.deepcopy(q)
    q4[0]["recipient"] = "z@example.org"
    assert msg(lambda: pd.release(q4, approval_for(d))) == "pitch_drafts:bad_draft"
    out, packet = pd.release(q, approval_for(d))
    assert set(packet) == {"draft_id", "kind", "recipient", "subject", "body", "text_sha256", "sent",
                           "send_instruction"}
    assert packet["kind"] == "journal" and packet["subject"] == d["subject"]
    assert packet["text_sha256"] == d["text_sha256"] and packet["draft_id"] == d["draft_id"]
    assert out[0]["body"] == d["body"] and out[0]["sent"] is False


def test_honesty_and_codes_constants():
    assert pd.HONESTY == {"semantic_fit_judged": False, "acceptance_predicted": False, "sent": False}
    assert pd.UNIT == "pitch_drafts" and pd.TOTAL_WEIGHT == 9
    assert [w for _, w in pd.WEIGHTS] == [3, 2, 1, 2, 1]
    f = fresh_fit()
    assert f["source_url"] == "https://example.org/guidelines" and f["as_of"] == "2026-10-01"
    assert f["target_name"] == "Journal of Tiny Results"
    assert [c["weight"] for c in f["checks"]] == [3, 2, 1, 2, 1]
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(format=5))) == "pitch_drafts:bad_type:manuscript"


def test_int_fields_refuse_bool_with_label():
    m = manuscript()
    for k in ("min_words", "max_words", "fee_usd"):
        assert msg(lambda: pd.score_fit(guidelines(**{k: True}), m)) == "pitch_drafts:bad_type:guidelines"
    for k in ("words", "max_fee_usd"):
        assert msg(lambda: pd.score_fit(guidelines(), manuscript(**{k: True}))) == \
            "pitch_drafts:bad_type:manuscript"
        assert msg(lambda: pd.score_fit(guidelines(), manuscript(**{k: -1}))) == \
            "pitch_drafts:range:manuscript"
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(max_fee_usd=pd.MAX_INT + 1))) == \
        "pitch_drafts:range:manuscript"


def test_guideline_field_labels():
    m = manuscript()
    assert msg(lambda: pd.score_fit(guidelines(source_url=5), m)) == "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(as_of=5), m)) == "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(accepted_formats=[]), m)) == "pitch_drafts:list_size:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(required_sections=["x"] * 51), m)) == \
        "pitch_drafts:list_size:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(accepted_formats="pdf"), m)) == \
        "pitch_drafts:bad_type:guidelines"
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(sections="x"))) == \
        "pitch_drafts:bad_type:manuscript"
    assert msg(lambda: pd.score_fit(guidelines(), manuscript(keywords=[""]))) == \
        "pitch_drafts:bad_item:manuscript"


def test_days_in_month_fence():
    for mo, n in ((1, 31), (2, 28), (3, 31), (4, 30), (5, 31), (6, 30), (7, 31), (8, 31), (9, 30),
                  (10, 31), (11, 30), (12, 31)):
        pd.score_fit(guidelines(as_of="2026-%02d-%02d" % (mo, n)), manuscript())
        assert msg(lambda: pd.score_fit(guidelines(as_of="2026-%02d-%02d" % (mo, n + 1)), manuscript())) \
            == pd.NOSOURCE, mo
    pd.score_fit(guidelines(as_of="2024-02-29"), manuscript())
    assert msg(lambda: pd.score_fit(guidelines(as_of="2024-02-30"), manuscript())) == pd.NOSOURCE


def test_journal_flag_exact_body():
    m = manuscript()
    d = pd.make_journal_draft(jtarget(), m, author(not_under_review_elsewhere=True), fresh_fit())
    assert "We measured transit depth for two targets. This manuscript is not under review elsewhere.\n\n" \
        "Sincerely,\nUdita Phookan" in d["body"]


def test_seal_is_order_independent_and_pinned():
    f = fresh_fit()
    g = {k: f[k] for k in reversed(list(f))}
    g["checks"] = [dict(reversed(list(c.items()))) for c in f["checks"]]
    d = pd.make_journal_draft(jtarget(), manuscript(), author(), g)
    assert d["kind"] == "journal"
    # regression pins (computed from this implementation, not an independent oracle)
    assert f["manuscript_sha256"] == "278f56442eae0f0fbf8c2546ce331fb712b26e8859f73bcdd30542cb7080c6b4"
    assert f["fit_sha256"] == "de9e645e70feb01302218c8634efff1cd5ca92fc90bf3f0a2cbdb8f991df0949"


def test_manuscript_hash_sensitive_to_every_field():
    base = fresh_fit()["manuscript_sha256"]
    for kw in (dict(title="T2"), dict(words=3001), dict(keywords=["orbit"]), dict(format="docx"),
               dict(sections=["abstract"]), dict(max_fee_usd=1)):
        assert pd.score_fit(guidelines(), manuscript(**kw))["manuscript_sha256"] != base, kw
    same = pd.score_fit(guidelines(), manuscript(keywords=["PHOTOMETRY", "orbit", "orbit"],
                                                 sections=["methods", "abstract", "results", "results"]))
    assert same["manuscript_sha256"] == base
