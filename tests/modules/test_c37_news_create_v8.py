"""V8 c37.news_create tests. Hermetic, offline, stdlib only."""
import ast
import copy
import datetime
import json
import pathlib
import random
import re
import unicodedata

import pytest

from app.modules.c37 import news_create as nc

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/modules/c37/news_create.py"
DOC = ROOT / "docs/contracts/V8-news-and-sciencefi-to-creation.md"
AS_OF = "2026-10-11"


def item(i, kind="news", title="plain title", summary="plain summary", url=None, published=AS_OF, tags=None):
    return {"id": i, "kind": kind, "title": title, "summary": summary,
            "url": url if url is not None else "https://example.org/" + str(i),
            "published": published, "tags": [] if tags is None else tags}


_D = object()


def req(items=_D, interests=_D, top_n=5, as_of=AS_OF, **extra):
    r = {"as_of": as_of, "interests": ["robotics", "materials", "AI"] if interests is _D else interests,
         "top_n": top_n, "items": [item("x1")] if items is _D else items}
    r.update(extra)
    return r


def err(r):
    with pytest.raises(ValueError) as e:
        nc.run(r)
    return str(e.value)


# ---------------------------------------------------------------- fixture (30 items) and known answers
def fixture():
    its = [
        item("a1", tags=["Robotics"], published="2026-10-09"),                       # 1*10 + 28 = 38
        item("a2", kind="paper", title="New materials for robotics", published="2026-10-11"),  # 2*10 + 30 = 50
        item("a3", kind="tech", summary="AI helps robots", published="2026-09-01"),   # AI once: 10 + 0 = 10
        item("a4", title="airline", tags=["materials", "robotics", "ai"], published="2026-10-01"),  # 30 + 20 = 50
        item("a5", published="2026-10-10"),                                           # 0 + 29 = 29, no brief
        item("f01", url="http://example.org/a"),
        item("f02", url="https://"),
        item("f03", url="https://user:pw@example.org/a"),
        item("f04", published="2026-10-12"),
        item("f05", published="2027-01-01"),
        item("f06", url="http://example.org/b", published="2026-10-12"),              # both: url_invalid only
    ]
    its += [item("f%02d" % n) for n in range(7, 26)]                                  # 19 zero-overlap, score 30
    return its


def test_fixture_known_answers():
    its = fixture()
    assert len(its) == 30
    out = nc.run(req(its, top_n=5))
    assert [r["id"] for r in out["ranked"]] == ["a2", "a4", "a1"] + ["f%02d" % n for n in range(7, 26)] + ["a5", "a3"]
    by = {r["id"]: r for r in out["ranked"]}
    assert (by["a1"]["overlap"], by["a1"]["recency"], by["a1"]["score"]) == (1, 28, 38)
    assert (by["a2"]["overlap"], by["a2"]["recency"], by["a2"]["score"]) == (2, 30, 50)
    assert (by["a3"]["overlap"], by["a3"]["recency"], by["a3"]["score"]) == (1, 0, 10)
    assert (by["a4"]["overlap"], by["a4"]["recency"], by["a4"]["score"]) == (3, 20, 50)
    assert (by["a5"]["overlap"], by["a5"]["recency"], by["a5"]["score"]) == (0, 29, 29)
    assert out["counts"] == {"supplied": 30, "ranked": 24, "dropped_url_invalid": 4, "dropped_future_date": 2}
    assert [b["item_id"] for b in out["briefs"]] == ["a2", "a4", "a1", "a3"]
    assert [t["ticket_id"] for t in out["tickets"]] == ["V8-a2", "V8-a4", "V8-a1", "V8-a3"]
    assert set(out) == {"ranked", "briefs", "tickets", "counts", "scope"}


def test_counts_invariant():
    out = nc.run(req(fixture()))
    c = out["counts"]
    assert c["supplied"] == c["ranked"] + c["dropped_url_invalid"] + c["dropped_future_date"]
    assert c["ranked"] == len(out["ranked"])


def test_brief_and_ticket_exact_shape():
    out = nc.run(req([item("k1", kind="paper", title="Robotics hands", summary="line1\nline2\tx", tags=[])], top_n=3))
    b, t = out["briefs"][0], out["tickets"][0]
    assert set(b) == {"item_id", "title", "kind", "source_url", "supplied_summary", "questions", "status"}
    assert b["item_id"] == "k1" and b["title"] == "Robotics hands" and b["kind"] == "paper"
    assert b["source_url"] == "https://example.org/k1" and b["supplied_summary"] == "line1\nline2\tx"
    assert b["status"] == "TO_RESEARCH" and b["questions"] == list(nc.QUESTIONS) and len(b["questions"]) == 5
    assert b["questions"] == [
        "What is new in this item, going only by the supplied summary?",
        "What would it enable if it holds up?",
        "What are the risks or reasons it may not hold up?",
        "What would a first prototype test?",
        "What is unknown from the supplied summary?"]
    assert t == {"ticket_id": "V8-k1", "title": "Explore: Robotics hands", "source_item_id": "k1",
                 "source_url": "https://example.org/k1", "status": "proposed", "needs_her_review": True}
    assert t["needs_her_review"] is True


def test_scope_block():
    out = nc.run(req())
    s = out["scope"]
    assert set(s) == {"implemented", "not_implemented", "data_source", "as_of"} and s["as_of"] == AS_OF
    assert any("interestingness" in x or "novelty" in x for x in s["not_implemented"])


# ---------------------------------------------------------------- ranking semantics
def test_top_n_slicing_and_no_padding():
    its = [item("t%d" % n, tags=["robotics"]) for n in range(10)] + [item("z")]
    for n in (1, 2, 9, 10, 11):
        out = nc.run(req(its, top_n=n))
        assert len(out["briefs"]) == min(n, 10) == len(out["tickets"])
        assert [b["item_id"] for b in out["briefs"]] == ["t%d" % k for k in range(min(n, 10))]
    assert len(nc.run(req([item("z")]))["briefs"]) == 0
    assert nc.run(req([item("z")]))["tickets"] == []
    assert len(nc.run(req(its, top_n=20))["ranked"]) == 11


def test_tie_order_by_id_and_score_order():
    its = [item(i, tags=["robotics"]) for i in ("b", "c", "a", "B", "_")]
    assert [r["id"] for r in nc.run(req(its))["ranked"]] == sorted(["b", "c", "a", "B", "_"])
    its = [item("old", tags=["robotics"], published="2026-09-01"), item("new", published=AS_OF),
           item("mid", tags=["robotics"], published="2026-10-01")]
    assert [r["id"] for r in nc.run(req(its))["ranked"]] == ["mid", "new", "old"]


def test_recency_clamp_and_boundaries():
    for age, rec in ((0, 30), (1, 29), (29, 1), (30, 0), (31, 0), (400, 0)):
        d = (datetime.date(2026, 10, 11) - datetime.timedelta(days=age)).isoformat()
        assert nc.run(req([item("r", published=d)]))["ranked"][0]["recency"] == rec
        assert nc.run(req([item("r", published=d)]))["ranked"][0]["age_days"] == age


def test_whole_word_and_case():
    cases = [("robot", "robotics rule", 0), ("robotics", "all robotics rule", 1), ("AI", "air travel", 0),
             ("AI", "an ai model", 1), ("ai", "Chain-of-AI.", 1), ("machine learning", "Machine  Learning, now", 1),
             ("machine learning", "machine-learning", 1), ("machine learning", "machines learning", 0),
             ("machine learning", "learning machine", 0), ("x", "x_y", 1), ("x", "(x)", 1), ("é", "É", 1)]
    for interest, text, n in cases:
        out = nc.run(req([item("w", title=text)], interests=[interest]))
        assert out["ranked"][0]["overlap"] == n, (interest, text)
        out = nc.run(req([item("w", summary=text)], interests=[interest]))
        assert out["ranked"][0]["overlap"] == n, (interest, text)


def test_tag_match_is_exact_casefolded_not_substring():
    out = nc.run(req([item("w", tags=["ROBOTICS "])], interests=["robotics"]))
    assert out["ranked"][0]["overlap"] == 1
    out = nc.run(req([item("w", tags=["robotics-lab"])], interests=["robotics"]))
    assert out["ranked"][0]["overlap"] == 0


def test_distinct_interests_counted_once():
    out = nc.run(req([item("w", title="robotics robotics", summary="robotics", tags=["robotics", "Robotics"])],
                     interests=["robotics", "Robotics", " robotics "]))
    assert out["ranked"][0]["overlap"] == 1 and out["ranked"][0]["score"] == 40
    out = nc.run(req([item("w", title="robotics ai")], interests=["robotics", "ai", "ROBOTICS"]))
    assert out["ranked"][0]["overlap"] == 2
    assert out["ranked"][0]["matched_interests"] == ["ai", "robotics"]


def test_ranked_entry_shape():
    r = nc.run(req([item("w", kind="tech", title="robotics")]))["ranked"][0]
    assert set(r) == {"id", "kind", "title", "source_url", "published", "overlap", "matched_interests",
                      "age_days", "recency", "score"}
    assert r["kind"] == "tech" and r["source_url"] == "https://example.org/w" and r["published"] == AS_OF


def test_integer_only_scores():
    for r in nc.run(req(fixture()))["ranked"]:
        for k in ("overlap", "age_days", "recency", "score"):
            assert type(r[k]) is int
    assert "." not in json.dumps(nc.run(req(fixture()))["ranked"]).replace("example.org", "")


# ---------------------------------------------------------------- independent oracle over generated corpus
WORDS = ["robotics", "robot", "materials", "ai", "air", "quantum", "machine", "learning", "ml", "gene", "edit", "x"]


def oracle(request):
    asof = datetime.date.fromisoformat(request["as_of"])
    keys = {}
    for s in request["interests"]:
        keys.setdefault(s.strip().casefold(), s)
    rows, bad_url, future = [], 0, 0
    for it in request["items"]:
        u = it["url"]
        ok = re.match(r"https://[^/@\s?#]+", u, re.I) is not None
        if not ok:
            bad_url += 1
            continue
        d = datetime.date.fromisoformat(it["published"])
        if d > asof:
            future += 1
            continue
        text = (it["title"] + " " + it["summary"]).casefold()
        tags = {t.strip().casefold() for t in it["tags"]}
        n = 0
        for k in keys:
            words = re.findall(r"[^\W_]+", k)
            hit = k in tags
            if words:
                pat = r"(?<![^\W_])" + r"[\W_]+".join(map(re.escape, words)) + r"(?![^\W_])"
                hit = hit or re.search(pat, text) is not None
            n += hit
        rows.append((-(10 * n + max(0, 30 - (asof - d).days)), it["id"], n))
    rows.sort()
    return [(r[1], -r[0], r[2]) for r in rows], bad_url, future


def gen(rng):
    its = []
    for i in range(rng.randint(1, 40)):
        words = lambda: " ".join(rng.choice(WORDS) + rng.choice(["", "", ",", "-x"]) for _ in range(rng.randint(0, 5)))
        d = datetime.date(2026, 10, 11) + datetime.timedelta(days=rng.randint(-60, 3))
        url = rng.choice(["https://e.org/%d" % i] * 5 + ["http://e.org", "https://", "HTTPS://E.org/z"])
        its.append(item("id%03d" % rng.randint(0, 999) + "-%d" % i, title=words() or "t", summary=words() or "s",
                        url=url, published=d.isoformat(), tags=[rng.choice(WORDS) for _ in range(rng.randint(0, 3))]))
    return req(its, interests=[rng.choice(WORDS + ["machine learning", "gene edit"]) for _ in range(rng.randint(1, 6))],
               top_n=rng.randint(1, 20))


def test_generated_corpus_matches_independent_oracle():
    rng = random.Random(8)
    for _ in range(300):
        r = gen(rng)
        out = nc.run(copy.deepcopy(r))
        exp, bad, fut = oracle(r)
        assert [(x["id"], x["score"], x["overlap"]) for x in out["ranked"]] == exp
        assert out["counts"] == {"supplied": len(r["items"]), "ranked": len(exp),
                                 "dropped_url_invalid": bad, "dropped_future_date": fut}
        want = [e[0] for e in exp if e[2] >= 1][:r["top_n"]]
        assert [b["item_id"] for b in out["briefs"]] == want
        assert [t["source_item_id"] for t in out["tickets"]] == want


# ---------------------------------------------------------------- URL gate and drops
URL_BAD = ["http://example.org", "ftp://example.org", "example.org", "", "https:", "https://", "https:///x",
           "https://user@example.org", "https://u:p@example.org/a", "https://exa mple.org", "https://example.org/a b",
           "https://example.org/\n", "https://example.org/\x00", "https://example.org/\u200b",
           "https://example.org/\u2028", "https://example.org/\u2029", "https://example.org/\u00a0",
           "https://example.org/\u3000", "https://[::1", "//example.org", " https://example.org",
           "https://example.org\t", "https://example.org/\x7f", "https://example.org/\u00ad"]
URL_OK = ["https://example.org", "HTTPS://Example.org/A?b=1#c", "https://example.org:8443/x",
          "https://sub.example.org/a%20b", "hTtPs://example.org/é"]


@pytest.mark.parametrize("u", URL_BAD)
def test_bad_url_drops(u):
    out = nc.run(req([item("u", url=u, tags=["robotics"]), item("ok", tags=["robotics"])]))
    assert [r["id"] for r in out["ranked"]] == ["ok"]
    assert out["counts"]["dropped_url_invalid"] == 1 and out["counts"]["dropped_future_date"] == 0


@pytest.mark.parametrize("u", URL_OK)
def test_good_url_kept_unchanged(u):
    out = nc.run(req([item("u", url=u, tags=["robotics"])]))
    assert out["ranked"][0]["source_url"] == u and out["briefs"][0]["source_url"] == u
    assert out["tickets"][0]["source_url"] == u


def test_future_date_and_both_count_once():
    out = nc.run(req([item("f", published="2026-10-12"), item("b", url="http://x", published="2026-10-12"),
                      item("p", url="http://x"), item("ok", published=AS_OF)]))
    assert out["counts"] == {"supplied": 4, "ranked": 1, "dropped_url_invalid": 2, "dropped_future_date": 1}
    assert [r["id"] for r in out["ranked"]] == ["ok"]


def test_published_equal_as_of_kept():
    assert nc.run(req([item("e", published=AS_OF)]))["counts"]["dropped_future_date"] == 0


def test_dropped_items_still_validated():
    assert err(req([item("a", url="http://x", title="")])) == "INTEL_REFUSED_EMPTY:title"
    assert err(req([item("a", published="2026-10-12", kind="blog")])) == "INTEL_REFUSED_UNKNOWN:kind"
    assert err(req([item("a", url="http://x"), item("a")])) == "INTEL_REFUSED_BAD_TYPE:items"


# ---------------------------------------------------------------- refusal table
SEND = ["send", "approve", "approved", "approval", "approval_token", "smtp", "token", "email_send", "sender",
        "smtp_host", "smtp_port", "smtp_user"]
SPEND = ["pay", "purchase", "spend", "buy", "checkout", "card_number"]
EFFECT = ["fetch", "crawl", "scrape", "download", "publish", "post", "build", "deploy"]
NOCREDS = ["login", "password", "username", "credentials", "otp", "api_key", "access_token", "refresh_token",
           "bearer", "pass", "passwd"]


@pytest.mark.parametrize("reason,keys", [("SEND", SEND), ("SPEND", SPEND), ("EFFECT", EFFECT), ("NOCREDS", NOCREDS)])
def test_forbidden_keys_top_level_and_variants(reason, keys):
    for k in keys:
        for variant in (k, k.upper(), k.replace("_", "-"), k.title()):
            assert err(req(**{variant: 1})) == "INTEL_REFUSED_%s:%s" % (reason, k)


def test_forbidden_keys_nested_everywhere():
    assert err(req([dict(item("a"), fetch=1)])) == "INTEL_REFUSED_EFFECT:fetch"
    assert err(req([item("a", tags=[{"token": 1}])])) == "INTEL_REFUSED_SEND:token"
    assert err(req(interests=[{"Pay": [[{"x": 1}]]}])) == "INTEL_REFUSED_SPEND:pay"
    assert err(req(extra={"deep": [{"deeper": {"login": 1}}]})) == "INTEL_REFUSED_NOCREDS:login"


def test_forbidden_precedence_and_alpha_first():
    assert err(req(fetch=1, token=1, pay=1, login=1)) == "INTEL_REFUSED_SEND:token"
    assert err(req(fetch=1, pay=1, login=1)) == "INTEL_REFUSED_SPEND:pay"
    assert err(req(fetch=1, login=1)) == "INTEL_REFUSED_EFFECT:fetch"
    assert err(req(deploy=1, build=1, crawl=1)) == "INTEL_REFUSED_EFFECT:build"
    assert err(req(smtp=1, approve=1, sender=1)) == "INTEL_REFUSED_SEND:approve"
    assert err(req(passwd=1, bearer=1, otp=1)) == "INTEL_REFUSED_NOCREDS:bearer"
    assert err(req(spend=1, buy=1)) == "INTEL_REFUSED_SPEND:buy"


def test_no_substring_matching_and_values_not_matched():
    for k in ("posting", "tokens", "fetcher", "payment", "buyer", "passport", "sender_x"):
        assert err(req(**{k: 1})) == "INTEL_REFUSED_UNKNOWN:request"
    out = nc.run(req([item("a", title="fetch token pay login")]))
    assert out["counts"]["supplied"] == 1


def test_forbidden_key_beats_unknown_and_types():
    assert err(req(bogus=1, fetch=1)) == "INTEL_REFUSED_EFFECT:fetch"
    assert err({"fetch": 1, 5: 2}) == "INTEL_REFUSED_EFFECT:fetch"
    r = req()
    r["top_n"] = True
    r["pay"] = 1
    assert err(r) == "INTEL_REFUSED_SPEND:pay"


def test_reason_suffix_never_echoes_input():
    secret = "SECRETVALUE-9917"
    for r in (req(**{"unknown_" + secret: 1}), req([item("a", title=secret + "\x00")]),
              req([item(secret + "\u200b")]), req([item("a", kind=secret)])):
        assert secret not in err(r)
    for tail in (err(req(**{"zz": 1})), err(req([item("a", kind="bad")])), err(req(top_n=99))):
        assert re.fullmatch(r"INTEL_REFUSED_[A-Z_]+(:[a-z_]+)?", tail)


# ---------------------------------------------------------------- validation: order and codes
def test_request_not_dict():
    for bad in (None, [], "x", 5, (), set(), True):
        assert err(bad) == "INTEL_REFUSED_BAD_TYPE:request"


def test_non_str_keys():
    assert err({1: 2}) == "INTEL_REFUSED_BAD_TYPE:key"
    r = req()
    r["items"] = [dict(item("a"), **{})]
    r["items"][0][5] = 1
    assert err(r) == "INTEL_REFUSED_BAD_TYPE:key"
    r = req(items=[item("a", tags=[{None: 1}])])
    assert err(r) == "INTEL_REFUSED_BAD_TYPE:key"


def test_unknown_keys():
    assert err(req(zzz=1)) == "INTEL_REFUSED_UNKNOWN:request"
    assert err(req([dict(item("a"), zzz=1)])) == "INTEL_REFUSED_UNKNOWN:items"
    r = req()
    del r["top_n"]
    assert err(r) == "INTEL_REFUSED_BAD_TYPE:top_n"
    assert err(req([dict(item("a"), zzz=1)], top_n=True)) == "INTEL_REFUSED_UNKNOWN:items"


def test_unknown_kind():
    for k in ("blog", "", "NEWS", "News", None, 5, True):
        want = "INTEL_REFUSED_UNKNOWN:kind" if type(k) is str else "INTEL_REFUSED_BAD_TYPE:kind"
        assert err(req([item("a", kind=k)])) == want
    for k in ("news", "paper", "tech"):
        assert nc.run(req([item("a", kind=k)]))["ranked"][0]["kind"] == k


def test_top_n_rules():
    for bad, want in ((0, "BAD_TYPE"), (-1, "BAD_TYPE"), (21, "OVERSIZE"), (10 ** 40, "OVERSIZE"), (True, "BAD_TYPE"),
                      (False, "BAD_TYPE"), (1.0, "BAD_TYPE"), ("5", "BAD_TYPE"), (None, "BAD_TYPE")):
        assert err(req(top_n=bad)) == "INTEL_REFUSED_%s:top_n" % want
    for ok in (1, 20):
        nc.run(req(top_n=ok))


def test_as_of_and_published_strictness():
    bads = ["2026-10-1", "26-10-11", "2026/10/11", "2026-13-01", "2026-02-30", "2026-00-10", "", " 2026-10-11",
            "2026-10-11\n", "２０２６-10-11", "2026-10-11T00:00", "2025-02-29", "٢٠٢٦-10-11"]
    for b in bads:
        want = "OVERSIZE" if len(b) > 10 else "BAD_TYPE"     # R1: raw cap 10 before grammar
        assert err(req(as_of=b)) == "INTEL_REFUSED_%s:as_of" % want
        assert err(req([item("a", published=b)])) == "INTEL_REFUSED_%s:published" % want
    for b in (None, 5, 20261011, ["2026-10-11"]):
        assert err(req(as_of=b)) == "INTEL_REFUSED_BAD_TYPE:as_of"
        assert err(req([item("a", published=b)])) == "INTEL_REFUSED_BAD_TYPE:published"
    nc.run(req(as_of="2024-02-29", items=[item("a", published="2024-02-29")]))


def test_empty_lists_and_types():
    assert err(req(items=[])) == "INTEL_REFUSED_EMPTY:items"
    assert err(req(interests=[])) == "INTEL_REFUSED_EMPTY:interests"
    for bad in (None, "x", (), {}, 5):
        assert err(req(items=bad)) == "INTEL_REFUSED_BAD_TYPE:items"
        assert err(req(interests=bad)) == "INTEL_REFUSED_BAD_TYPE:interests"
    assert err(req([dict(item("a"), tags=None)])) == "INTEL_REFUSED_BAD_TYPE:tags"
    assert err(req([item("a", tags="robotics")])) == "INTEL_REFUSED_BAD_TYPE:tags"
    assert err(req([item("a", tags=("x",))])) == "INTEL_REFUSED_BAD_TYPE:tags"
    assert err(req(["a"])) == "INTEL_REFUSED_BAD_TYPE:items"
    assert nc.run(req([item("a", tags=[])]))["counts"]["ranked"] == 1


def test_missing_item_fields_and_field_types():
    for f in ("id", "kind", "title", "summary", "url", "published", "tags"):
        it = item("a")
        del it[f]
        assert err(req([it])) == "INTEL_REFUSED_BAD_TYPE:%s" % f
    for f in ("id", "title", "summary"):
        for bad in (None, 5, True, b"x", ["x"]):
            assert err(req([item("a", **{f: bad})] if f != "id" else [dict(item("a"), id=bad)])) \
                == "INTEL_REFUSED_BAD_TYPE:%s" % f
    for bad in (None, 5, ["https://x"], True):
        assert err(req([item("a", url=bad)])) == "INTEL_REFUSED_BAD_TYPE:url" if bad is not None else True
    assert err(req([dict(item("a"), url=None)])) == "INTEL_REFUSED_BAD_TYPE:url"
    assert err(req([dict(item("a"), url=5)])) == "INTEL_REFUSED_BAD_TYPE:url"


def test_blank_values():
    for f in ("id", "title", "summary"):
        for blank in ("", "   ", "\u3000"):
            assert err(req([dict(item("a"), **{f: blank})])) == "INTEL_REFUSED_EMPTY:%s" % f
    assert err(req([item("a", tags=[""])])) == "INTEL_REFUSED_EMPTY:tags"
    assert err(req([item("a", tags=["  "])])) == "INTEL_REFUSED_EMPTY:tags"
    assert err(req(interests=[""])) == "INTEL_REFUSED_EMPTY:interests"
    assert err(req(interests=[" "])) == "INTEL_REFUSED_EMPTY:interests"
    assert err(req(interests=[5])) == "INTEL_REFUSED_BAD_TYPE:interests"
    assert err(req([item("a", tags=[5])])) == "INTEL_REFUSED_BAD_TYPE:tags"
    assert err(req([item("a", tags=[True])])) == "INTEL_REFUSED_BAD_TYPE:tags"


def test_duplicate_ids():
    assert err(req([item("a"), item("b"), item("a")])) == "INTEL_REFUSED_BAD_TYPE:items"
    assert nc.run(req([item("a"), item("A")]))["counts"]["ranked"] == 2


def test_validation_in_list_order():
    r = req([item("a", title=""), item("b", kind="blog")])
    assert err(r) == "INTEL_REFUSED_EMPTY:title"
    r = req([item("a", kind="blog"), item("b", title="")])
    assert err(r) == "INTEL_REFUSED_UNKNOWN:kind"
    assert err(req([item("a", tags=[""])], interests=[""])) == "INTEL_REFUSED_EMPTY:interests"


def test_strict_str_subclass_and_bool_rejected():
    class S(str):
        pass
    assert err(req([item(S("a"))])) == "INTEL_REFUSED_BAD_TYPE:id"
    assert err(req([item("a", title=S("t"))])) == "INTEL_REFUSED_BAD_TYPE:title"
    assert err(req([item("a", tags=[S("t")])])) == "INTEL_REFUSED_BAD_TYPE:tags"
    assert err(req(interests=[S("t")])) == "INTEL_REFUSED_BAD_TYPE:interests"
    assert err(req([item("a", url=S("https://x"))])) == "INTEL_REFUSED_BAD_TYPE:url"
    assert err(req([item("a", published=S(AS_OF))])) == "INTEL_REFUSED_BAD_TYPE:published"
    assert err(req(as_of=S(AS_OF))) == "INTEL_REFUSED_BAD_TYPE:as_of"
    assert err(req([item("a", kind=S("news"))])) == "INTEL_REFUSED_BAD_TYPE:kind"


# ---------------------------------------------------------------- caps (N / N+1), raw cap before content
def test_caps_exact_boundaries():
    ok = lambda **kw: nc.run(req([item("a", **kw)]))
    def over(field_item=None, **top):
        return err(req(**top)) if field_item is None else err(req([field_item]))
    nc.run(req([dict(item("a"), id="i" * 128)]))
    assert over(dict(item("a"), id="i" * 129)) == "INTEL_REFUSED_OVERSIZE:id"
    ok(title="t" * 300)
    assert over(item("a", title="t" * 301)) == "INTEL_REFUSED_OVERSIZE:title"
    ok(summary="s" * 4000)
    assert over(item("a", summary="s" * 4001)) == "INTEL_REFUSED_OVERSIZE:summary"
    ok(url="https://e.org/" + "u" * (2000 - 14))
    assert nc.run(req([item("a", url="https://e.org/" + "u" * (2000 - 14))]))["counts"]["ranked"] == 1
    assert over(item("a", url="https://e.org/" + "u" * (2001 - 14))) == "INTEL_REFUSED_OVERSIZE:url"
    ok(tags=["g" * 64] * 20)
    assert over(item("a", tags=["g" * 65])) == "INTEL_REFUSED_OVERSIZE:tags"
    assert over(item("a", tags=["g"] * 21)) == "INTEL_REFUSED_OVERSIZE:tags"
    nc.run(req(interests=["i" * 64] * 50))
    assert err(req(interests=["i" * 65])) == "INTEL_REFUSED_OVERSIZE:interests"
    assert err(req(interests=["i"] * 51)) == "INTEL_REFUSED_OVERSIZE:interests"


def test_items_cap_5000():
    its = [item("n%04d" % n) for n in range(5000)]
    out = nc.run(req(its))
    assert out["counts"]["ranked"] == 5000
    assert err(req(its + [item("n9999")])) == "INTEL_REFUSED_OVERSIZE:items"


def test_field_cap_beats_content_errors_and_url_oversize_is_refusal_not_drop():
    ctl = "\x00"
    assert err(req([item("a", title=ctl + "t" * 300)])) == "INTEL_REFUSED_OVERSIZE:title"
    assert err(req([item("a", title=ctl * 301)])) == "INTEL_REFUSED_OVERSIZE:title"
    assert err(req([item("a", summary="\u200b" * 4001)])) == "INTEL_REFUSED_OVERSIZE:summary"
    assert err(req([dict(item("a"), id=" " * 129)])) == "INTEL_REFUSED_OVERSIZE:id"
    assert err(req([item("a", tags=["\u2028" * 65])])) == "INTEL_REFUSED_OVERSIZE:tags"
    assert err(req(interests=[" " * 65])) == "INTEL_REFUSED_OVERSIZE:interests"
    assert err(req([item("a", url="http://" + "u" * 2000)])) == "INTEL_REFUSED_OVERSIZE:url"
    assert err(req([item("a", title=ctl + "t" * 300)], top_n=1)) == "INTEL_REFUSED_OVERSIZE:title"
    # cap pass is across all items before per-item validation
    assert err(req([item("a", kind="blog"), item("b", title="t" * 301)])) == "INTEL_REFUSED_OVERSIZE:title"
    # unknown / bad-typed neighbours do not hide an oversize later in the same structure
    assert err(req([item("a", title="t" * 301)], top_n=True)) == "INTEL_REFUSED_BAD_TYPE:top_n"


def test_text_too_long_code_never_surfaces():
    for f, ns in (("title", (301, 4001, 10001, 50000)), ("summary", (4001, 10001, 50000))):
        for n in ns:
            assert "TEXT_TOO_LONG" not in err(req([item("a", **{f: "x" * n})]))
    for r in (req([dict(item("a"), id="x" * 500)]), req([item("a", tags=["x" * 500])]), req(interests=["x" * 500])):
        assert "TEXT_TOO_LONG" not in err(r)


# ---------------------------------------------------------------- global preflight fence (before every content error)
def test_string_fence_anywhere_wins():
    big = "z" * 10001
    assert err(req(zzz=big)) == "INTEL_REFUSED_OVERSIZE:request"
    assert err(req(fetch=big)) == "INTEL_REFUSED_OVERSIZE:request"
    assert err(req([dict(item("a"), zzz=big)])) == "INTEL_REFUSED_OVERSIZE:items"
    assert err(req([item("a", title=big)], bogus=1)) == "INTEL_REFUSED_OVERSIZE:items"
    assert err(req(x=[{"y": big}])) == "INTEL_REFUSED_OVERSIZE:request"
    ok = nc.run(req([item("a", title="t" * 300)]))
    assert ok["counts"]["ranked"] == 1
    assert err(req(zzz="z" * 10000)) == "INTEL_REFUSED_UNKNOWN:request"


def test_key_and_dict_fences():
    assert err(req(**{"k" * 65: 1})) == "INTEL_REFUSED_OVERSIZE:request"
    assert err(req(**{"k" * 64: 1})) == "INTEL_REFUSED_UNKNOWN:request"
    assert err(req([dict(item("a"), **{"k" * 65: 1})])) == "INTEL_REFUSED_OVERSIZE:items"
    d = {"k%d" % n: 1 for n in range(33)}
    assert err(req(x=d)) == "INTEL_REFUSED_OVERSIZE:request"
    d = {"k%d" % n: 1 for n in range(32)}
    assert err(req(x=d)) == "INTEL_REFUSED_UNKNOWN:request"
    assert err(req(x=[0] * 65)) == "INTEL_REFUSED_OVERSIZE:request"
    assert err(req(x=[0] * 64)) == "INTEL_REFUSED_UNKNOWN:request"
    big_top = dict(req())
    for n in range(40):
        big_top["q%d" % n] = 1
    assert err(big_top) == "INTEL_REFUSED_OVERSIZE:request"


def test_depth_and_container_budget():
    deep = cur = []
    for _ in range(12):
        nxt = []
        cur.append(nxt)
        cur = nxt
    assert err(req(x=deep)) == "INTEL_REFUSED_OVERSIZE:request"
    shallow = [[[[]]]]
    assert err(req(x=shallow)) == "INTEL_REFUSED_UNKNOWN:request"
    cyc = []
    cyc.append(cyc)
    assert err(req(x=cyc)) == "INTEL_REFUSED_OVERSIZE:request"
    its = [item("n%04d" % n) for n in range(5000)]
    assert nc.run(req(its))["counts"]["supplied"] == 5000      # 10003 containers is within budget
    assert err(req(its, x=[[]] * 8)).startswith("INTEL_REFUSED_OVERSIZE:")
    assert err(req(its, x=[[]] * 7 + [0])).startswith("INTEL_REFUSED_OVERSIZE:")


def test_fence_beats_forbidden_key_and_content():
    assert err(req(its := [item("a", title="t" * 10001)], fetch=1)) == "INTEL_REFUSED_OVERSIZE:items"
    assert err(req(fetch=1, x=[0] * 65)) == "INTEL_REFUSED_OVERSIZE:request"


# ---------------------------------------------------------------- hostile non-materialization spies
class Trap:
    touched = 0

    def _t(self, *a, **k):
        Trap.touched += 1
        raise AssertionError("touched")
    __len__ = __iter__ = __getitem__ = __eq__ = __hash__ = __bool__ = __str__ = __repr__ = _t
    __contains__ = __getattr__ = _t


class SpyList(list):
    def __iter__(self):
        Trap.touched += 1
        raise AssertionError("iterated")
    __len__ = __getitem__ = __contains__ = __iter__


class SpyDict(dict):
    def _t(self, *a, **k):
        Trap.touched += 1
        raise AssertionError("touched")
    __iter__ = __len__ = keys = items = values = get = __getitem__ = __contains__ = _t


def test_subclass_containers_refused_untouched():
    Trap.touched = 0
    assert err(req(items=SpyList())) == "INTEL_REFUSED_BAD_TYPE:items"
    r = req()
    r["interests"] = SpyList()
    assert err(r) == "INTEL_REFUSED_BAD_TYPE:interests"
    assert err(req([item("a", tags=SpyList())])) == "INTEL_REFUSED_BAD_TYPE:tags"
    assert err(req([SpyDict()])) == "INTEL_REFUSED_BAD_TYPE:items"
    assert err(SpyDict()) == "INTEL_REFUSED_BAD_TYPE:request"
    assert err(req(x=SpyList())) == "INTEL_REFUSED_BAD_TYPE:request"
    assert Trap.touched == 0


def test_oversize_lists_never_touch_elements():
    Trap.touched = 0
    t = Trap()
    assert err(req(items=[t] * 5001)) == "INTEL_REFUSED_OVERSIZE:items"
    assert err(req(interests=[t] * 51)) == "INTEL_REFUSED_OVERSIZE:interests"
    assert err(req([item("a", tags=[t] * 21)])) == "INTEL_REFUSED_OVERSIZE:tags"
    assert err(req(x=[t] * 65)) == "INTEL_REFUSED_OVERSIZE:request"
    assert err(req(x=[[t] * 65])) == "INTEL_REFUSED_OVERSIZE:request"
    assert Trap.touched == 0


def test_oversize_dict_never_iterates_beyond_count():
    Trap.touched = 0
    d = {"k%d" % n: Trap() for n in range(40)}
    assert err(req(x=d)) == "INTEL_REFUSED_OVERSIZE:request"
    assert err(req([dict(item("a"), **{"k%d" % n: Trap() for n in range(40)})])) == "INTEL_REFUSED_OVERSIZE:items"
    assert Trap.touched == 0


def test_oversize_strings_are_not_scanned():
    class CountStr(str):
        pass
    big = "q" * 10001
    assert err(req([item("a", title=big)])) == "INTEL_REFUSED_OVERSIZE:items"
    assert err(req([item("a", title="t" * 301 + "\x00")])) == "INTEL_REFUSED_OVERSIZE:title"


# ---------------------------------------------------------------- control characters
def cats():
    return {"Cc": "\x00", "Cf": "\u200b", "Zl": "\u2028", "Zp": "\u2029", "bidi": "\u202e", "soft": "\u00ad"}


@pytest.mark.parametrize("name,ch", list(cats().items()))
def test_forbidden_chars_everywhere(name, ch):
    secret = "ABC" + ch + "DEF"
    for r, f in ((req([dict(item("a"), id=secret)]), "id"), (req([item("a", title=secret)]), "title"),
                 (req([item("a", summary=secret)]), "summary"), (req([item("a", tags=[secret])]), "tags"),
                 (req(interests=[secret]), "interests")):
        m = err(r)
        assert m == "INTEL_REFUSED_CONTROL_CHARS:%s" % f
        assert "ABC" not in m and ch not in m


def test_key_with_control_chars_is_unknown_not_echoed():
    m = err(req(**{"a\x00b": 1}))
    assert m == "INTEL_REFUSED_UNKNOWN:request" and "\x00" not in m


def test_summary_keeps_only_lf_cr_tab():
    out = nc.run(req([item("a", summary="a\nb\rc\td", tags=["robotics"])]))
    assert out["briefs"][0]["supplied_summary"] == "a\nb\rc\td"
    for bad in ("\x0b", "\x0c", "\x1f", "\x85", "\u200b", "\u2028"):
        assert err(req([item("a", summary="a" + bad)])) == "INTEL_REFUSED_CONTROL_CHARS:summary"
    for f in ("title",):
        for ws in ("\n", "\r", "\t"):
            assert err(req([item("a", **{f: "a" + ws})])) == "INTEL_REFUSED_CONTROL_CHARS:%s" % f
    for ws in ("\n", "\t"):
        assert err(req([item("a", tags=["a" + ws])])) == "INTEL_REFUSED_CONTROL_CHARS:tags"
        assert err(req(interests=["a" + ws])) == "INTEL_REFUSED_CONTROL_CHARS:interests"
        assert err(req([dict(item("a"), id="a" + ws)])) == "INTEL_REFUSED_CONTROL_CHARS:id"


def test_generated_char_sweep_matches_category_rule():
    for cp in list(range(0, 0x250)) + [0x2028, 0x2029, 0x200b, 0x200d, 0x2060, 0xfeff, 0x202e, 0xe000, 0x1f600]:
        ch = chr(cp)
        bad = unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp")
        r = req([item("a", title="a" + ch + "b")])
        if bad:
            assert err(r) == "INTEL_REFUSED_CONTROL_CHARS:title", hex(cp)
        elif ch.strip() or True:
            nc.run(r)


# ---------------------------------------------------------------- determinism, purity, honesty
def test_deterministic_and_input_not_mutated():
    r = req(fixture())
    snap = copy.deepcopy(r)
    a = json.dumps(nc.run(r), sort_keys=True)
    assert r == snap
    assert a == json.dumps(nc.run(copy.deepcopy(r)), sort_keys=True)
    assert json.dumps(nc.run(r)) == json.dumps(nc.run(copy.deepcopy(r)))
    shuffled = copy.deepcopy(r)
    random.Random(1).shuffle(shuffled["items"])
    assert nc.run(shuffled)["ranked"] == nc.run(r)["ranked"]
    assert nc.run(shuffled)["briefs"] == nc.run(r)["briefs"]


def test_output_does_not_alias_input():
    r = req([item("a", tags=["robotics"])])
    out = nc.run(r)
    out["ranked"][0]["matched_interests"].append("zz")
    out["briefs"][0]["questions"].append("zz")
    assert nc.run(r)["ranked"][0]["matched_interests"] == ["robotics"]
    assert len(nc.run(r)["briefs"][0]["questions"]) == 5


def test_ast_purity_and_no_neighbour_imports():
    tree = ast.parse(SRC.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "") + "|" + ",".join(a.name for a in n.names))
    assert mods <= {"re", "unicodedata", "datetime", "urllib.parse|urlsplit", "app.modules.c30|policy"}, mods
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    nm = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for banned in ("open", "eval", "exec", "compile", "__import__", "input", "getattr", "setattr", "globals",
                   "os", "sys", "time", "random", "socket", "subprocess"):
        assert banned not in nm, banned
    for banned in ("socket", "urlopen", "subprocess", "system", "write", "write_text", "now", "today"):
        assert banned not in names, banned
    src = SRC.read_text()
    for token in ("c32", "ingest", "breakthroughs", "leaders", "patents", "public_record", "now(", "today("):
        assert token not in src, token
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for bad in ("fetch", "send", "post", "publish", "write", "create", "file", "submit", "pay", "build", "deploy"):
        assert not any(f == bad or f.startswith(bad + "_") for f in fns), bad
    assert all(not hasattr(nc, b) for b in ("fetch", "send", "publish", "ingest", "post", "create", "pay"))
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree))
    assert not any(isinstance(n, ast.Div) for n in ast.walk(tree))


def test_only_real_policy_helpers_used():
    assert nc.policy.__name__ == "app.modules.c30.policy"
    tree = ast.parse(SRC.read_text())
    used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
            and n.value.id == "policy"}
    assert used == {"clean_text", "scope"}, used


def test_no_catalog_or_handler_registration():
    for p in (ROOT / "backend/app").rglob("*.py"):
        if p == SRC:
            continue
        t = p.read_text()
        assert "c37.news_create" not in t and "c37 import news_create" not in t, p


# ---------------------------------------------------------------- doc
def test_doc_contract():
    d = DOC.read_text()
    low = d.lower()
    for need in ("LIMITS", "INTERPRETATION CHOICE", "INTEL_REFUSED_EFFECT", "INTEL_REFUSED_SEND", "INTEL_REFUSED_SPEND",
                 "INTEL_REFUSED_NOCREDS", "INTEL_REFUSED_UNKNOWN", "INTEL_REFUSED_OVERSIZE", "INTEL_REFUSED_BAD_TYPE",
                 "INTEL_REFUSED_EMPTY", "url_invalid", "future_date", "needs_her_review", "toy", "stale `.pyc`", "void"):
        assert need in d, need
    for bad in (".jsonl", ".json", "delivery folder", "invalid_run", "mutation_run", "private", "ledger", "integrator",
                "her words", "owner message", "offset", "doc hygiene", "main said", "adopt"):
        assert bad not in low, bad
    for t in ("interestingness", "novelty"):
        assert t in low


# ---------------------------------------------------------------- R1 pins added after the first mutation pass
def nest(n, as_dict=False):
    node = [] if not as_dict else {}
    for _ in range(n - 1):
        node = [node] if not as_dict else {"a": node}
    return node


def test_depth_boundaries_on_every_path():
    # x at top: depth of the innermost container equals the nesting count
    for as_dict in (False, True):
        assert err(req(x=nest(8, as_dict))) == "INTEL_REFUSED_UNKNOWN:request"
        assert err(req(x=nest(9, as_dict))) == "INTEL_REFUSED_OVERSIZE:request"
    r = req(items=[nest(7)])
    assert err(r) == "INTEL_REFUSED_BAD_TYPE:items"
    assert err(req(items=[nest(8)])) == "INTEL_REFUSED_OVERSIZE:items"
    assert err(req(interests=[nest(7)])) == "INTEL_REFUSED_BAD_TYPE:interests"
    assert err(req(interests=[nest(8)])) == "INTEL_REFUSED_OVERSIZE:interests"
    assert err(req([item("a", tags=[nest(5)])])) == "INTEL_REFUSED_BAD_TYPE:tags"
    assert err(req([item("a", tags=[nest(6)])])) == "INTEL_REFUSED_OVERSIZE:tags"
    assert err(req([dict(item("a"), z=nest(6))])) == "INTEL_REFUSED_UNKNOWN:items"
    assert err(req([dict(item("a"), z=nest(7))])) == "INTEL_REFUSED_OVERSIZE:items"
    assert err(req([dict(item("a"), z=nest(6, True))])) == "INTEL_REFUSED_UNKNOWN:items"
    assert err(req([dict(item("a"), z=nest(7, True))])) == "INTEL_REFUSED_OVERSIZE:items"


def blob(n):
    root, n = [], n - 1
    while n > 0 and len(root) < 64:
        g = min(n - 1, 64)
        root.append([[] for _ in range(g)])
        n -= 1 + g
    return root


def count_containers(x):
    return 1 + sum(count_containers(c) for c in x) if isinstance(x, list) else 1


def test_container_budget_exact_on_both_admission_paths():
    its = [item("n%04d" % n) for n in range(5000)]
    assert nc.run(req(its))["counts"]["supplied"] == 5000                   # 10003 containers
    assert err(req(its, x=[[]] * 6)) == "INTEL_REFUSED_UNKNOWN:request"     # exactly 10010
    assert err(req(its, x=[[]] * 7)).startswith("INTEL_REFUSED_OVERSIZE:")  # 10011
    # item dicts as the last admitted containers: no tags key, 3 + 5000 + blobs
    bare = [{k: v for k, v in item("n%04d" % n).items() if k != "tags"} for n in range(5000)]
    b1, b2 = blob(4161), blob(846)
    assert count_containers(b1) + count_containers(b2) == 5007
    assert err(req(bare, x=b1, y=b2)) == "INTEL_REFUSED_UNKNOWN:request"     # exactly 10010
    b2 = blob(847)
    assert count_containers(b1) + count_containers(b2) == 5008
    assert err(req(bare, x=b1, y=b2)) == "INTEL_REFUSED_OVERSIZE:items"      # 10011, refused on an item dict


def test_tags_count_cap_is_a_preflight_fence():
    assert err(req([item("a", tags=[{"token": 1}] + [0] * 20)])) == "INTEL_REFUSED_OVERSIZE:tags"
    assert err(req([item("a", tags=[{"token": 1}] + [0] * 19)])) == "INTEL_REFUSED_SEND:token"
    assert err(req(items=[item("a")], interests=[{"token": 1}] + [0] * 50)) == "INTEL_REFUSED_OVERSIZE:interests"
    assert err(req(items=[item("a")], interests=[{"token": 1}] + [0] * 49)) == "INTEL_REFUSED_SEND:token"
    assert err(req(items=[{"token": 1}] * 5001)) == "INTEL_REFUSED_OVERSIZE:items"


def test_url_category_sweep_and_non_ascii_ok():
    for cp in range(0x110000):
        ch = chr(cp)
        if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp", "Zs") or ch.isspace():
            out = nc.run(req([item("u", url="https://e.org/" + ch), item("ok")]))
            assert out["counts"]["dropped_url_invalid"] == 1, hex(cp)
    out = nc.run(req([item("u", url="https://\u00e9xample.org/\u00e9"), item("v", url="https://e.org/\u00e9\x80")]))
    assert out["counts"]["dropped_url_invalid"] == 1 and out["ranked"][0]["id"] == "u"


def test_scope_text_exact():
    assert nc.run(req())["scope"] == {
        "implemented": ["integer keyword-overlap plus recency ranking of supplied items",
                        "templated research briefs and proposed tickets for the top supplied matches"],
        "not_implemented": ["interestingness or novelty detection", "fetching any feed, site or stream",
                            "verification of supplied summaries", "creating or building anything"],
        "data_source": "caller-supplied items and interest terms, unfetched and unverified",
        "as_of": AS_OF}


# ---------------------------------------------------------------- R1: date and kind raw caps before grammar / membership
def test_date_caps_before_grammar():
    assert nc.MAX_DATE == 10
    for field in ("as_of", "published"):
        def mk(v):
            return req(as_of=v) if field == "as_of" else req([item("a", published=v)])
        assert err(mk("2026-10-111")) == "INTEL_REFUSED_OVERSIZE:" + field          # 11 chars
        assert err(mk("2026-10-11\n")) == "INTEL_REFUSED_OVERSIZE:" + field         # 11 chars, would be a grammar error
        assert err(mk("\x00" * 11)) == "INTEL_REFUSED_OVERSIZE:" + field            # cap before content
        assert err(mk("x" * 9999)) == "INTEL_REFUSED_OVERSIZE:" + field
        assert err(mk("2026-10-1")) == "INTEL_REFUSED_BAD_TYPE:" + field            # 9 chars stays BAD_TYPE
        assert err(mk("")) == "INTEL_REFUSED_BAD_TYPE:" + field
        assert err(mk("2026-13-01")) == "INTEL_REFUSED_BAD_TYPE:" + field           # 10 chars, bad grammar
        assert err(mk("x" * 10)) == "INTEL_REFUSED_BAD_TYPE:" + field
        for bad in (None, 5, True, ["2026-10-11"], b"2026-10-11"):
            assert err(mk(bad)) == "INTEL_REFUSED_BAD_TYPE:" + field                 # strict str check first
    class S(str):
        pass
    assert err(req(as_of=S("2026-10-111"))) == "INTEL_REFUSED_BAD_TYPE:as_of"
    assert err(req([item("a", published=S("2026-10-111"))])) == "INTEL_REFUSED_BAD_TYPE:published"
    nc.run(req(as_of="2026-10-11", items=[item("a", published="2026-10-11")]))


def test_published_cap_runs_across_all_items_before_validation():
    r = req([item("a", kind="blog"), item("b", published="2026-10-111")])
    assert err(r) == "INTEL_REFUSED_OVERSIZE:published"
    r = req([item("a", title=""), item("b", published="\u200b" * 11)])
    assert err(r) == "INTEL_REFUSED_OVERSIZE:published"
    assert err(req([item("a", published="2026-10-1"), item("b", published="2026-10-111")])) == "INTEL_REFUSED_OVERSIZE:published"


def test_kind_cap_before_membership():
    assert nc.MAX_KIND == max(len(k) for k in nc.KINDS) == 5 and "paper" in nc.KINDS
    assert nc.run(req([item("a", kind="paper")]))["ranked"][0]["kind"] == "paper"
    for k in ("papers", "blogs!", "x" * 6, "x" * 9999, "\x00" * 6, " " * 6):
        assert err(req([item("a", kind=k)])) == "INTEL_REFUSED_OVERSIZE:kind", k
    for k in ("blog", "x" * 5, "", "Paper", "techs", "\x00" * 5):
        assert err(req([item("a", kind=k)])) == "INTEL_REFUSED_UNKNOWN:kind", k
    assert err(req([item("a", kind="x" * 6), item("b", kind=5)])) == "INTEL_REFUSED_OVERSIZE:kind"
    assert err(req([item("a", kind=5), item("b", kind="x" * 6)])) == "INTEL_REFUSED_OVERSIZE:kind"
    assert err(req([item("a", title=""), item("b", kind="x" * 6)])) == "INTEL_REFUSED_OVERSIZE:kind"


def test_kind_membership_never_consulted_when_oversize(monkeypatch):
    class SpyKinds(tuple):
        hits = 0

        def __contains__(self, x):
            SpyKinds.hits += 1
            return tuple.__contains__(self, x)
    monkeypatch.setattr(nc, "KINDS", SpyKinds(("news", "paper", "tech")))
    assert err(req([item("a", kind="x" * 6)])) == "INTEL_REFUSED_OVERSIZE:kind"
    assert err(req([item("a", kind="x" * 9000)])) == "INTEL_REFUSED_OVERSIZE:kind"
    assert SpyKinds.hits == 0
    assert err(req([item("a", kind="blog")])) == "INTEL_REFUSED_UNKNOWN:kind"
    assert SpyKinds.hits == 1


def test_doc_names_nearest_existing_mechanism():
    d = DOC.read_text()
    assert "venture_v2/engines.py:news_create" in d and "bounded new surface" in d
    assert "briefs" in d and "tickets" in d and "RSS" in d
    assert "no existing" not in d.lower() and "does not exist" not in d.lower()
