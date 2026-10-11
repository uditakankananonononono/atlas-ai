"""U07 multi-account manager (oneofficial variant): registry of the
owner's own accounts ONLY - one official account per platform, hard
enforced. No automation-labeled accounts in this variant. Per-account
persona, calendar, analytics, free sign-up step plan with hard stops,
publish intents as m00 approval payloads only.

All refusals are ValueError prefixed 'ACCTU07:'. Nothing executes a
sign-up, send, submit, or post. Module loads via U07_MODULE_PATH.
"""
import importlib.util
import os

import pytest

_PATH = os.environ.get(
    "U07_MODULE_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "backend", "app",
                 "modules", "m06_social_media_manager", "multi_account_u07.py"))
_spec = importlib.util.spec_from_file_location("multi_account_u07", _PATH)
u07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(u07)


def account(**over):
    base = {
        "account_id": "acct_1", "platform": "instagram", "handle": "udita.lab",
        "ownership": "owner",
        "persona": {"display_name": "Udita Lab", "bio": "build notes", "voice": "curious"},
        "source_ref": "owner brief U07",
    }
    base.update(over)
    return base


class TestAccountRegistry:
    def test_create_owner_account(self):
        a = u07.create_account(account())
        assert a["account_id"] == "acct_1" and a["ownership"] == "owner"

    def test_automation_labeled_refuses(self):
        with pytest.raises(ValueError) as e:
            u07.create_account(account(ownership="automation_labeled"))
        assert "ACCTU07:" in str(e.value) and "owner" in str(e.value)

    def test_any_non_owner_refuses(self):
        for bad in ("automation", "bot", "fake", ""):
            with pytest.raises(ValueError):
                u07.create_account(account(ownership=bad))

    def test_fake_identity_refuses(self):
        with pytest.raises(ValueError) as e:
            u07.create_account(account(persona={"display_name": "Real Person",
                                                "claims_real_person": True}))
        assert "ACCTU07:" in str(e.value) and "real person" in str(e.value)

    def test_explicit_non_real_person_ok(self):
        a = u07.create_account(account(persona={"display_name": "Bot",
                                                "claims_real_person": False}))
        assert a["persona"]["display_name"] == "Bot"

    def test_one_owner_account_per_platform(self):
        fleet = u07.add_account(u07.new_fleet(), account())
        with pytest.raises(ValueError) as e:
            u07.add_account(fleet, account(account_id="acct_2", handle="udita.other"))
        assert "ACCTU07:" in str(e.value) and "one official account" in str(e.value)

    def test_owner_on_two_platforms_ok(self):
        fleet = u07.new_fleet()
        fleet = u07.add_account(fleet, account())
        fleet = u07.add_account(fleet, account(account_id="acct_2", platform="tiktok"))
        assert len(fleet["accounts"]) == 2

    def test_duplicate_account_id_refuses(self):
        fleet = u07.add_account(u07.new_fleet(), account())
        with pytest.raises(ValueError):
            u07.add_account(fleet, account(platform="tiktok"))

    def test_unknown_key_refuses(self):
        with pytest.raises(ValueError) as e:
            u07.create_account(account(password="not-a-real-value"))
        assert "ACCTU07:" in str(e.value)

    def test_handle_grammar(self):
        with pytest.raises(ValueError):
            u07.create_account(account(handle="bad handle!"))
        with pytest.raises(ValueError):
            u07.create_account(account(platform="myspace"))


class TestCalendar:
    def test_plan_calendar(self):
        cal = u07.plan_calendar(account(), [
            {"date": "2026-10-12", "title": "build log 1", "theme": "progress", "format": "carousel"},
            {"date": "2026-10-13", "title": "build log 2", "theme": "progress", "format": "article_post"},
        ])
        assert cal["account_id"] == "acct_1" and len(cal["entries"]) == 2
        assert all(e["status"] == "draft" for e in cal["entries"])

    def test_bad_date_refuses(self):
        with pytest.raises(ValueError) as e:
            u07.plan_calendar(account(), [{"date": "12/10/2026", "title": "x",
                                           "theme": "t", "format": "carousel"}])
        assert "ACCTU07:" in str(e.value)

    def test_entries_bounded(self):
        with pytest.raises(ValueError):
            u07.plan_calendar(account(), [{"date": "2026-10-12", "title": "x",
                                           "theme": "t", "format": "carousel"}] * 93)


class TestAnalytics:
    def test_record_and_summarize(self):
        recs = [u07.record_metrics(account(), {"date": "2026-10-10", "followers": 100,
                                               "impressions": 1000, "engagements": 50}),
                u07.record_metrics(account(), {"date": "2026-10-11", "followers": 110,
                                               "impressions": 500, "engagements": 25})]
        s = u07.summarize_metrics("acct_1", recs)
        assert s["records"] == 2 and s["impressions_total"] == 1500
        assert s["engagement_rate"] == "1/20"
        assert s["followers_latest"] == 110

    def test_zero_impressions_rate_none(self):
        recs = [u07.record_metrics(account(), {"date": "2026-10-10", "followers": 0,
                                               "impressions": 0, "engagements": 0})]
        assert u07.summarize_metrics("acct_1", recs)["engagement_rate"] is None

    def test_negative_metric_refuses(self):
        with pytest.raises(ValueError):
            u07.record_metrics(account(), {"date": "2026-10-10", "followers": -1,
                                           "impressions": 0, "engagements": 0})

    def test_summary_account_mismatch_refuses(self):
        recs = [u07.record_metrics(account(), {"date": "2026-10-10", "followers": 1,
                                               "impressions": 1, "engagements": 1})]
        with pytest.raises(ValueError):
            u07.summarize_metrics("acct_9", recs)


class TestSignupPlan:
    def test_free_steps_with_stops(self):
        plan = u07.signup_plan("instagram")
        assert plan["platform"] == "instagram" and plan["executes"] is False
        kinds = [s["kind"] for s in plan["steps"]]
        assert "fill_profile" in kinds and "stop" in kinds
        stop_reasons = {s["reason"] for s in plan["steps"] if s["kind"] == "stop"}
        assert {"captcha", "phone", "id", "payment"} <= stop_reasons

    def test_every_step_is_free(self):
        for p in ("instagram", "tiktok", "twitter", "linkedin"):
            assert all(s["cost"] == "free" for s in u07.signup_plan(p)["steps"])

    def test_unknown_platform_refuses(self):
        with pytest.raises(ValueError):
            u07.signup_plan("myspace")


class TestPublishIntent:
    def test_original_content_proposes_approval(self):
        r = u07.propose_post(account(), {"text": "shipped the glow renderer today",
                                         "origin": "original"})
        assert r["action"] == "publish" and r["status"] == "awaiting_human_approval"
        assert r["executes"] is False and r["account_id"] == "acct_1"
        assert set(r) == {"action", "status", "executes", "account_id", "platform",
                          "text", "origin", "credit_source", "interpretation"}

    def test_credited_content_ok(self):
        r = u07.propose_post(account(), {"text": "great thread by X",
                                         "origin": "credited", "credit_source": "https://x.com/y/1"})
        assert r["status"] == "awaiting_human_approval"

    def test_altered_repost_refuses(self):
        with pytest.raises(ValueError) as e:
            u07.propose_post(account(), {"text": "someone else's post, tweaked",
                                         "origin": "altered_repost"})
        assert "ACCTU07:" in str(e.value) and "altered repost" in str(e.value)

    def test_credited_without_source_refuses(self):
        with pytest.raises(ValueError):
            u07.propose_post(account(), {"text": "thread", "origin": "credited"})

    def test_empty_text_refuses(self):
        with pytest.raises(ValueError):
            u07.propose_post(account(), {"text": "  ", "origin": "original"})


class TestModuleShape:
    def test_stdlib_only(self):
        import ast, pathlib
        tree = ast.parse(pathlib.Path(u07.__file__).read_text())
        allowed = {"__future__", "re", "fractions", "datetime"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", None) or node.names[0].name
                assert mod.split(".")[0] in allowed, mod


# ======================================================================
# Repair round: defect pins and boundary/constant pins (added after the
# candidate's own tests; see the contract's repair section)
# ======================================================================
import copy


def refuses(fn, *args, contains=None):
    with pytest.raises(ValueError) as e:
        fn(*args)
    msg = str(e.value)
    assert msg.startswith("ACCTU07: "), msg
    if contains is not None:
        assert contains in msg, msg
    return msg


def entry(**over):
    base = {"date": "2026-10-12", "title": "t", "theme": "th", "format": "carousel"}
    base.update(over)
    return base


def metrics(**over):
    base = {"date": "2026-10-10", "followers": 5, "impressions": 100, "engagements": 10}
    base.update(over)
    return base


def record(**over):
    base = dict(metrics(), account_id="acct_1")
    base.update(over)
    return base


# ---------------------------------------------------------------- defect 1: trailing newline
def test_trailing_newline_refused_in_handle_and_account_id_and_dates():
    refuses(u07.create_account, account(handle="abc\n"))
    refuses(u07.create_account, account(account_id="abc\n"))
    refuses(u07.plan_calendar, account(), [entry(date="2026-10-12\n")])
    refuses(u07.record_metrics, account(), metrics(date="2026-10-12\n"))
    refuses(u07.summarize_metrics, "acct_1", [record(date="2026-10-12\n")])


# ---------------------------------------------------------------- defect 2: summarize validates like record_metrics
def test_summarize_refuses_every_bad_record_as_acctu07():
    good = record()
    for bad in (
        {k: v for k, v in good.items() if k != "impressions"},
        {k: v for k, v in good.items() if k != "engagements"},
        {k: v for k, v in good.items() if k != "followers"},
        {k: v for k, v in good.items() if k != "date"},
        {k: v for k, v in good.items() if k != "account_id"},
        record(impressions="100"),
        record(impressions=-1),
        record(impressions=1.5),
        record(impressions=True),
        record(engagements="1"),
        record(engagements=-1),
        record(engagements=2.0),
        record(engagements=False),
        record(followers="1"),
        record(followers=-1),
        record(followers=1.0),
        record(followers=True),
        record(date="2026-13-45"),
        record(date="12/10/2026"),
        record(date=20261012),
        record(account_id=7),
        record(account_id=None),
        record(extra=1),
        "not a dict",
        None,
        [],
    ):
        refuses(u07.summarize_metrics, "acct_1", [bad])
    # a bad record after good ones is still found
    refuses(u07.summarize_metrics, "acct_1", [good, good, record(impressions=-5)])


def test_summarize_arguments():
    refuses(u07.summarize_metrics, "acct_1", [])
    refuses(u07.summarize_metrics, "acct_1", "nope")
    refuses(u07.summarize_metrics, "acct_1", None)
    refuses(u07.summarize_metrics, "acct_1", ({},))
    refuses(u07.summarize_metrics, "bad id!", [record(account_id="bad id!")])
    refuses(u07.summarize_metrics, 5, [record(account_id=5)])
    refuses(u07.summarize_metrics, "acct_1", [record(account_id="acct_9")], contains="does not belong")


def test_summarize_known_answers_and_rate_format():
    s = u07.summarize_metrics("acct_1", [record(date="2026-10-11", followers=9, impressions=40, engagements=2),
                                         record(date="2026-10-12", followers=7, impressions=60, engagements=3),
                                         record(date="2026-10-10", followers=1, impressions=0, engagements=0)])
    assert s == {"account_id": "acct_1", "records": 3, "impressions_total": 100, "engagements_total": 5,
                 "engagement_rate": "1/20", "followers_latest": 7}
    # denominator of one prints a bare integer, a proper fraction keeps its slash
    whole = u07.summarize_metrics("acct_1", [record(impressions=5, engagements=10)])
    assert whole["engagement_rate"] == "2"
    third = u07.summarize_metrics("acct_1", [record(impressions=3, engagements=1)])
    assert third["engagement_rate"] == "1/3"
    reduced = u07.summarize_metrics("acct_1", [record(impressions=10, engagements=5)])
    assert reduced["engagement_rate"] == "1/2"
    zero = u07.summarize_metrics("acct_1", [record(impressions=0, engagements=0)])
    assert zero["engagement_rate"] is None
    assert set(zero) == {"account_id", "records", "impressions_total", "engagements_total",
                         "engagement_rate", "followers_latest"}


def test_summarize_does_not_mutate_records():
    recs = [record(date="2026-10-11"), record(date="2026-10-12")]
    before = copy.deepcopy(recs)
    u07.summarize_metrics("acct_1", recs)
    assert recs == before


def test_add_account_refuses_malformed_fleet_entries_as_acctu07():
    ok = u07.add_account(u07.new_fleet(), account())
    cases = [
        {"accounts": [{"platform": "tiktok"}]},                       # no account_id
        {"accounts": [{"account_id": "x"}]},                          # no platform
        {"accounts": [{"account_id": 7, "platform": "tiktok"}]},      # non-str id
        {"accounts": [{"account_id": "x", "platform": 7}]},           # non-str platform
        {"accounts": ["nope"]},
        {"accounts": [None]},
        {"accounts": [[]]},
    ]
    for fleet in cases:
        refuses(u07.add_account, fleet, account(account_id="acct_2", platform="twitter"))
    refuses(u07.add_account, {"accounts": "x"}, account())
    refuses(u07.add_account, {"accounts": ()}, account())
    refuses(u07.add_account, {}, account())
    refuses(u07.add_account, {"accounts": [], "extra": 1}, account(), contains="unknown key")
    refuses(u07.add_account, [], account(), contains="fleet must be an object")
    refuses(u07.add_account, None, account())
    assert len(ok["accounts"]) == 1


def test_add_account_does_not_mutate_input_fleet_and_returns_new_list():
    fleet = u07.add_account(u07.new_fleet(), account())
    before = copy.deepcopy(fleet)
    out = u07.add_account(fleet, account(account_id="acct_2", platform="tiktok"))
    assert fleet == before and len(fleet["accounts"]) == 1
    assert len(out["accounts"]) == 2 and out["accounts"] is not fleet["accounts"]
    assert out["accounts"][0] == fleet["accounts"][0]
    empty = u07.new_fleet()
    u07.add_account(empty, account())
    assert empty == {"accounts": []}
    assert u07.new_fleet() is not u07.new_fleet()


def test_fleet_checks_run_before_the_account_is_accepted_and_each_order_is_stable():
    fleet = u07.add_account(u07.new_fleet(), account())
    refuses(u07.add_account, fleet, account(account_id="acct_1", platform="tiktok"), contains="duplicate account_id")
    refuses(u07.add_account, fleet, account(account_id="acct_2"), contains="one official account")
    refuses(u07.add_account, fleet, account(account_id="acct_2", platform="tiktok", ownership="bot"),
            contains="ownership")


# ---------------------------------------------------------------- defect 3: credit_source validated and capped
def test_credit_source_validated_and_bounded():
    post = lambda **kw: u07.propose_post(account(), dict({"text": "hi"}, **kw))
    # original content carries no credit
    assert post(origin="original")["credit_source"] is None
    assert post(origin="original", credit_source=None)["credit_source"] is None
    for junk in ("src", "", {"a": 1}, ["x"], 5, True, object()):
        with pytest.raises(ValueError) as e:
            post(origin="original", credit_source=junk)
        assert str(e.value).startswith("ACCTU07: ") and "credit_source" in str(e.value)
    # credited content names a bounded source
    assert post(origin="credited", credit_source="s" * 200)["credit_source"] == "s" * 200
    with pytest.raises(ValueError) as e201:
        post(origin="credited", credit_source="s" * 201)
    assert str(e201.value).startswith("ACCTU07: ") and "credit_source" in str(e201.value)
    for junk in (None, "", "  ", 5, ["x"], {"a": 1}, True, b"x"):
        with pytest.raises(ValueError) as e:
            post(origin="credited", credit_source=junk)
        assert str(e.value).startswith("ACCTU07: ") and "credit_source" in str(e.value)
    # the echo is the supplied string unchanged
    assert post(origin="credited", credit_source=" https://x.com/y ")["credit_source"] == " https://x.com/y "


# ---------------------------------------------------------------- boundaries
def test_calendar_entry_count_boundary():
    for n in (1, 91, 92):
        assert len(u07.plan_calendar(account(), [entry()] * n)["entries"]) == n
    refuses(u07.plan_calendar, account(), [entry()] * 93, contains="exceed 92")
    refuses(u07.plan_calendar, account(), [], contains="non-empty list")
    refuses(u07.plan_calendar, account(), None)
    refuses(u07.plan_calendar, account(), ())
    refuses(u07.plan_calendar, account(), "x")
    assert u07.MAX_CALENDAR_ENTRIES == 92 and u07.MAX_HANDLE == 30 and u07.MAX_TEXT == 5000 and u07.MAX_BIO == 500


def test_calendar_entry_fields():
    for k in ("title", "theme", "format"):
        assert u07.plan_calendar(account(), [entry(**{k: "x" * 200})])["entries"][0][k] == "x" * 200
        for bad in ("x" * 201, "", "  ", None, 5, ["x"]):
            refuses(u07.plan_calendar, account(), [entry(**{k: bad})], contains="entries[0] " + k)
        missing = entry()
        del missing[k]
        refuses(u07.plan_calendar, account(), [missing])
    refuses(u07.plan_calendar, account(), [entry(), entry(extra=1)], contains="entries[1]")
    refuses(u07.plan_calendar, account(), [entry(), "x"], contains="entries[1]")
    refuses(u07.plan_calendar, account(), [None])
    refuses(u07.plan_calendar, account(), [entry(date=None)], contains="entries[0] date")


def test_calendar_output_exact():
    out = u07.plan_calendar(account(), [entry(title="A", theme="B", format="C"), entry(date="2026-10-13")])
    assert out == {"account_id": "acct_1", "entries": [
        {"date": "2026-10-12", "title": "A", "theme": "B", "format": "C", "status": "draft"},
        {"date": "2026-10-13", "title": "t", "theme": "th", "format": "carousel", "status": "draft"}]}
    es = [entry()]
    before = copy.deepcopy(es)
    u07.plan_calendar(account(), es)
    assert es == before


def test_handle_boundaries_and_first_character():
    assert u07.create_account(account(handle="a" * 30))["handle"] == "a" * 30
    refuses(u07.create_account, account(handle="a" * 31))
    assert u07.create_account(account(handle="a"))["handle"] == "a"
    for good in ("0abc", "Zed", "a.b", "a_b", "a-b", "a.-_9"):
        assert u07.create_account(account(handle=good))["handle"] == good
    for bad in (".abc", "-abc", "_abc", "", " abc", "ab c", "ab/c", "é", "abé", "a" * 31 + "\n", 5, None, ["a"]):
        refuses(u07.create_account, account(handle=bad), contains="handle")
    # handle is read, never rewritten
    assert u07.create_account(account(handle="MiXeD"))["handle"] == "MiXeD"


def test_account_id_boundaries():
    assert u07.create_account(account(account_id="a" * 40))["account_id"] == "a" * 40
    refuses(u07.create_account, account(account_id="a" * 41), contains="account_id")
    for good in ("a", "_", "-", "A9_-"):
        assert u07.create_account(account(account_id=good))["account_id"] == good
    for bad in ("", "a b", "a.b", "a/b", "é", 5, None, ["a"]):
        refuses(u07.create_account, account(account_id=bad), contains="account_id")
    with pytest.raises(ValueError):
        u07.create_account({k: v for k, v in account().items() if k != "account_id"})


def test_persona_rules():
    for k in ("display_name", "bio", "voice"):
        p = {"display_name": "N", "bio": "", "voice": ""}
        p[k] = "x" * 500
        assert u07.create_account(account(persona=p))["persona"][k] == "x" * 500
        p[k] = "x" * 501
        refuses(u07.create_account, account(persona=p), contains="persona " + k)
    for k in ("bio", "voice"):
        p = {"display_name": "N", k: 5}
        refuses(u07.create_account, account(persona=p), contains="persona " + k)
        p = {"display_name": "N", k: None}
        refuses(u07.create_account, account(persona=p), contains="persona " + k)
    for bad in ("", "  ", "\t\n", None, 5, ["N"]):
        refuses(u07.create_account, account(persona={"display_name": bad}), contains="display_name")
    refuses(u07.create_account, account(persona={"bio": "b"}), contains="display_name")
    for bad in ("x", None, 5, [], ()):
        refuses(u07.create_account, account(persona=bad), contains="persona")
    refuses(u07.create_account, account(persona={"display_name": "N", "age": 3}), contains="unknown key")
    for truthy in (True, 1, "yes", "false", [0], {"a": 1}):
        refuses(u07.create_account, account(persona={"display_name": "N", "claims_real_person": truthy}),
                contains="real person")
    for falsy in (False, 0, None, "", []):
        assert u07.create_account(account(persona={"display_name": "N", "claims_real_person": falsy}))
    out = u07.create_account(account(persona={"display_name": " N ", "claims_real_person": False}))
    assert out["persona"] == {"display_name": " N ", "bio": "", "voice": ""}
    assert "claims_real_person" not in out["persona"]


def test_source_ref_rules():
    assert u07.create_account(account(source_ref="s" * 200))["source_ref"] == "s" * 200
    for bad in ("s" * 201, "", "  ", None, 5, ["s"]):
        refuses(u07.create_account, account(source_ref=bad), contains="source_ref")
    with pytest.raises(ValueError):
        u07.create_account({k: v for k, v in account().items() if k != "source_ref"})


def test_platform_and_ownership_sets():
    assert u07.PLATFORMS == ("instagram", "tiktok", "twitter", "linkedin")
    assert u07.OWNERSHIP_KINDS == ("owner",)
    assert u07.CONTENT_ORIGINS == ("original", "credited")
    assert u07.STOP_REASONS == ("captcha", "phone", "id", "payment")
    for p in u07.PLATFORMS:
        assert u07.create_account(account(platform=p))["platform"] == p
    for bad in ("myspace", "", "Instagram", "x", None, ["instagram"], 5):
        refuses(u07.create_account, account(platform=bad), contains="platform")
    for bad in ("", "Owner", "bot", None, ["owner"], 5):
        refuses(u07.create_account, account(ownership=bad), contains="ownership")
    with pytest.raises(ValueError):
        u07.create_account({k: v for k, v in account().items() if k != "platform"})
    with pytest.raises(ValueError):
        u07.create_account({k: v for k, v in account().items() if k != "ownership"})
    with pytest.raises(ValueError):
        u07.create_account({k: v for k, v in account().items() if k != "persona"})


def test_unknown_keys_everywhere():
    refuses(u07.create_account, account(extra=1), contains="unknown key 'extra' in account")
    refuses(u07.create_account, "x", contains="account must be an object")
    refuses(u07.create_account, None)
    refuses(u07.record_metrics, account(), metrics(extra=1), contains="unknown key 'extra' in metrics")
    refuses(u07.record_metrics, account(), "x", contains="metrics must be an object")
    refuses(u07.summarize_metrics, "acct_1", [record(extra=1)], contains="in record")
    refuses(u07.propose_post, account(), {"text": "t", "origin": "original", "extra": 1}, contains="in content")
    refuses(u07.propose_post, account(), "x", contains="content must be an object")
    refuses(u07.add_account, {"accounts": [], "x": 1}, account(), contains="in fleet")


def test_accounts_are_validated_by_every_entry_point():
    bad = account(ownership="bot")
    refuses(u07.plan_calendar, bad, [entry()], contains="ownership")
    refuses(u07.record_metrics, bad, metrics(), contains="ownership")
    refuses(u07.propose_post, bad, {"text": "t", "origin": "original"}, contains="ownership")
    refuses(u07.add_account, u07.new_fleet(), bad, contains="ownership")


def test_dates_format_and_real_calendar_days():
    for good in ("2026-10-12", "2024-02-29", "0001-01-01", "9999-12-31"):
        assert u07.record_metrics(account(), metrics(date=good))["date"] == good
    # right length and character class but wrong shape
    for bad in ("2026-10-1-", "----------", "2026101-12", "2026-1-123", "-026-10-12", "2026-10-12-", "202610-12-"):
        refuses(u07.record_metrics, account(), metrics(date=bad), contains="ISO YYYY-MM-DD")
    for bad in ("2026-10-1", "2026-10-123", "26-10-12", "2026/10/12", "12/10/2026", "", " 2026-10-12", "2026-10-12 ",
                "\u0662\u0660\u0662\u0666-10-12", None, 20261012, ["2026-10-12"], b"2026-10-12"):
        refuses(u07.record_metrics, account(), metrics(date=bad), contains="ISO YYYY-MM-DD")
    for bad in ("2026-02-30", "2026-02-29", "2026-13-01", "2026-00-10", "2026-10-00", "2026-10-32", "2026-04-31",
                "0000-01-01"):
        refuses(u07.record_metrics, account(), metrics(date=bad), contains="not a real calendar day")
    refuses(u07.plan_calendar, account(), [entry(date="2026-02-30")], contains="entries[0] date")


def test_metrics_values():
    out = u07.record_metrics(account(), metrics(followers=0, impressions=0, engagements=0))
    assert out == {"account_id": "acct_1", "date": "2026-10-10", "followers": 0, "impressions": 0, "engagements": 0}
    for k in ("followers", "impressions", "engagements"):
        for bad in (-1, 1.0, 1.5, True, False, "1", None, [1], float("nan")):
            refuses(u07.record_metrics, account(), metrics(**{k: bad}), contains="metrics " + k)
        missing = metrics()
        del missing[k]
        refuses(u07.record_metrics, account(), missing, contains="metrics " + k)
    missing = metrics()
    del missing["date"]
    refuses(u07.record_metrics, account(), missing, contains="date")
    big = u07.record_metrics(account(), metrics(followers=10 ** 12))
    assert big["followers"] == 10 ** 12


# ---------------------------------------------------------------- outputs and echoes
def test_create_account_output_exact_and_limits_not_aliased():
    out = u07.create_account(account(persona={"display_name": "Udita Lab"}))
    assert out == {"account_id": "acct_1", "platform": "instagram", "handle": "udita.lab", "ownership": "owner",
                   "persona": {"display_name": "Udita Lab", "bio": "", "voice": ""},
                   "source_ref": "owner brief U07", "limits": u07.LIMITS}
    assert out["limits"] is not u07.LIMITS and len(out["limits"]) == 5
    out["limits"].append("x")
    assert len(u07.LIMITS) == 5 and len(u07.create_account(account())["limits"]) == 5
    again = u07.create_account(account())
    assert again["persona"] == {"display_name": "Udita Lab", "bio": "build notes", "voice": "curious"}


def test_limits_text_is_pinned():
    L = u07.LIMITS
    assert L[0].startswith("This unit plans and records only: it never creates accounts, signs up, autofills portals")
    assert L[0].endswith("stays awaiting human approval.")
    assert L[1] == "Accounts must be the owner's own: one official account per platform, and any other ownership kind refuses."
    assert L[2] == "Content must be original or carry a credit source; altered reposts of other people's content refuse."
    assert L[3].startswith("The sign-up plan lists free steps and stops at CAPTCHA, phone, ID, and payment gates")
    assert L[3].endswith("a human completes any real sign-up themselves.")
    assert L[4] == "Analytics summarize only metrics supplied to this unit; nothing is scraped or fetched."
    assert u07.INTERPRETATION == ("one official account per platform, owned by the owner; "
                                  "every publish is an approval request, never an execution")


def test_signup_plan_exact():
    for p in u07.PLATFORMS:
        plan = u07.signup_plan(p)
        assert plan == {"platform": p, "executes": False, "steps": [
            {"kind": "open_site", "detail": "open the official %s sign-up page" % p, "cost": "free"},
            {"kind": "fill_profile", "detail": "enter the persona display name, handle and bio", "cost": "free"},
            {"kind": "stop", "reason": "captcha", "detail": "CAPTCHA challenge: a human completes it", "cost": "free"},
            {"kind": "stop", "reason": "phone", "detail": "phone verification: ask the owner", "cost": "free"},
            {"kind": "stop", "reason": "id", "detail": "ID verification: ask the owner", "cost": "free"},
            {"kind": "stop", "reason": "payment", "detail": "any payment step: stop, free sign-ups only", "cost": "free"}]}
    for bad in ("myspace", "", None, ["instagram"], 5, "Instagram"):
        refuses(u07.signup_plan, bad, contains="platform")


def test_propose_post_output_exact_and_text_is_echoed_unchanged():
    r = u07.propose_post(account(platform="tiktok", account_id="acct_7"), {"text": "  hi there \n", "origin": "original"})
    assert r == {"action": "publish", "status": "awaiting_human_approval", "executes": False,
                 "account_id": "acct_7", "platform": "tiktok", "text": "  hi there \n", "origin": "original",
                 "credit_source": None, "interpretation": u07.INTERPRETATION}
    c = u07.propose_post(account(), {"text": "t", "origin": "credited", "credit_source": "src"})
    assert c["origin"] == "credited" and c["credit_source"] == "src"


def test_propose_post_text_and_origin_rules():
    assert u07.propose_post(account(), {"text": "t" * 5000, "origin": "original"})["text"] == "t" * 5000
    refuses(u07.propose_post, account(), {"text": "t" * 5001, "origin": "original"}, contains="5000")
    for bad in ("", " ", "\n\t", None, 5, ["t"], b"t"):
        refuses(u07.propose_post, account(), {"text": bad, "origin": "original"}, contains="content text")
    refuses(u07.propose_post, account(), {"origin": "original"}, contains="content text")
    refuses(u07.propose_post, account(), {"text": "t", "origin": "altered_repost"}, contains="altered reposts")
    for bad in ("", "Original", "repost", "other", None, 5, ["original"], True):
        msg = refuses(u07.propose_post, account(), {"text": "t", "origin": bad}, contains="content origin")
        assert "altered" not in msg
    refuses(u07.propose_post, account(), {"text": "t"}, contains="content origin")
    refuses(u07.propose_post, account(), {"text": "t", "origin": "altered_repost", "credit_source": "s"},
            contains="altered reposts")


def test_approval_only_never_executes_flags():
    r = u07.propose_post(account(), {"text": "t", "origin": "original"})
    assert r["executes"] is False and r["status"] == "awaiting_human_approval" and r["action"] == "publish"
    assert u07.signup_plan("instagram")["executes"] is False
    assert u07.record_metrics(account(), metrics())["account_id"] == "acct_1"


def test_inputs_not_mutated():
    a = account()
    before = copy.deepcopy(a)
    u07.create_account(a)
    u07.plan_calendar(a, [entry()])
    u07.record_metrics(a, metrics())
    u07.propose_post(a, {"text": "t", "origin": "original"})
    assert a == before


def test_no_exception_other_than_acctu07_on_hostile_shapes():
    hostile = [None, 0, 1.5, "", "x", b"x", [], (), {}, set(), object(), [None], {"a": []}, True]
    calls = [lambda x: u07.create_account(x), lambda x: u07.add_account(x, account()),
             lambda x: u07.add_account(u07.new_fleet(), x), lambda x: u07.plan_calendar(account(), x),
             lambda x: u07.plan_calendar(x, [entry()]), lambda x: u07.record_metrics(account(), x),
             lambda x: u07.record_metrics(x, metrics()), lambda x: u07.summarize_metrics("acct_1", x),
             lambda x: u07.summarize_metrics(x, [record()]), lambda x: u07.propose_post(account(), x),
             lambda x: u07.propose_post(x, {"text": "t", "origin": "original"}), lambda x: u07.signup_plan(x)]
    for h in hostile:
        for c in calls:
            try:
                c(h)
            except ValueError as e:
                assert str(e).startswith("ACCTU07: ")


def test_doc_is_neutral_and_documents_the_repair():
    import pathlib
    doc = (pathlib.Path(__file__).resolve().parents[2] / "docs" / "M06_MULTI_ACCOUNT_U07_CONTRACT.md").read_text()
    for banned in ("4529384d", "review/acct-u07", "candidate branch", "Submitted for review", "Not landed",
                   "not accepted", "unaccepted", "built fresh"):
        assert banned not in doc, banned
    assert "ACCTU07:" in doc and "## What is refused" in doc and "## Limits of this unit's checks" in doc
    assert "credit_source" in doc and "trailing newline" in doc


# ---------------------------------------------------------------- exact refusal text (added after the first battery)
A, E, M, R = account, entry, metrics, record
fleet1 = u07.add_account(u07.new_fleet(), account())

MESSAGES = {
    'ca_ownership': "ACCTU07: ownership must be 'owner'; only the owner's own official accounts are managed",
    'ca_account_id': 'ACCTU07: account_id must be 1-40 chars of [A-Za-z0-9_-]',
    'ca_platform': "ACCTU07: platform must be one of ['instagram', 'tiktok', 'twitter', 'linkedin']",
    'ca_handle': 'ACCTU07: handle must match [A-Za-z0-9][A-Za-z0-9._-]{0,29} and be at most 30 chars',
    'ca_not_obj': 'ACCTU07: account must be an object',
    'ca_unknown': "ACCTU07: unknown key 'extra' in account",
    'ca_persona_not_obj': 'ACCTU07: persona must be an object',
    'ca_persona_unknown': "ACCTU07: unknown key 'age' in persona",
    'ca_real': 'ACCTU07: persona must not claim to be a real person',
    'ca_blank_name': 'ACCTU07: persona display_name must be non-blank',
    'ca_long_bio': 'ACCTU07: persona bio must be a string of at most 500 chars',
    'ca_long_voice': 'ACCTU07: persona voice must be a string of at most 500 chars',
    'ca_source': 'ACCTU07: source_ref must be a non-blank string of at most 200 chars',
    'aa_not_obj': 'ACCTU07: fleet must be an object',
    'aa_not_list': 'ACCTU07: fleet accounts must be a list',
    'aa_bad_entry': 'ACCTU07: fleet accounts must be account records with an account_id and a known platform',
    'aa_dup': "ACCTU07: duplicate account_id 'acct_1'",
    'aa_platform': "ACCTU07: platform 'instagram' already has its one official account",
    'pc_empty': 'ACCTU07: calendar entries must be a non-empty list',
    'pc_many': 'ACCTU07: calendar entries exceed 92',
    'pc_entry_not_obj': 'ACCTU07: entries[0] must be an object',
    'pc_entry_unknown': "ACCTU07: unknown key 'extra' in entries[1]",
    'pc_date': 'ACCTU07: entries[0] date must be ISO YYYY-MM-DD',
    'pc_date_real': "ACCTU07: entries[0] date '2026-02-30' is not a real calendar day",
    'pc_title': 'ACCTU07: entries[0] title must be a non-blank string of at most 200 chars',
    'pc_theme': 'ACCTU07: entries[0] theme must be a non-blank string of at most 200 chars',
    'pc_format': 'ACCTU07: entries[0] format must be a non-blank string of at most 200 chars',
    'rm_not_obj': 'ACCTU07: metrics must be an object',
    'rm_unknown': "ACCTU07: unknown key 'extra' in metrics",
    'rm_date': 'ACCTU07: metrics date must be ISO YYYY-MM-DD',
    'rm_date_real': "ACCTU07: metrics date '2026-13-01' is not a real calendar day",
    'rm_followers': 'ACCTU07: metrics followers must be a non-negative integer',
    'rm_impressions': 'ACCTU07: metrics impressions must be a non-negative integer',
    'rm_engagements': 'ACCTU07: metrics engagements must be a non-negative integer',
    'sm_empty': 'ACCTU07: records must be a non-empty list',
    'sm_id': 'ACCTU07: account_id must be 1-40 chars of [A-Za-z0-9_-]',
    'sm_not_obj': 'ACCTU07: record must be an object',
    'sm_unknown': "ACCTU07: unknown key 'extra' in record",
    'sm_mismatch': 'ACCTU07: record account_id does not belong to this account',
    'sm_date': 'ACCTU07: record date must be ISO YYYY-MM-DD',
    'sm_date_real': "ACCTU07: record date '2026-02-30' is not a real calendar day",
    'sm_followers': 'ACCTU07: record followers must be a non-negative integer',
    'sm_impressions': 'ACCTU07: record impressions must be a non-negative integer',
    'sm_engagements': 'ACCTU07: record engagements must be a non-negative integer',
    'sp_platform': "ACCTU07: platform must be one of ['instagram', 'tiktok', 'twitter', 'linkedin']",
    'pp_not_obj': 'ACCTU07: content must be an object',
    'pp_unknown': "ACCTU07: unknown key 'extra' in content",
    'pp_text': 'ACCTU07: content text must be non-blank and at most 5000 chars',
    'pp_text_long': 'ACCTU07: content text must be non-blank and at most 5000 chars',
    'pp_altered': "ACCTU07: altered reposts of other people's content refuse; content must be original or credited",
    'pp_origin': "ACCTU07: content origin must be one of ['original', 'credited']",
    'pp_original_credit': 'ACCTU07: original content must not carry a credit_source',
    'pp_credited_none': 'ACCTU07: credited content must name its credit_source as a non-blank string of at most 200 chars',
    'pp_credited_long': 'ACCTU07: credited content must name its credit_source as a non-blank string of at most 200 chars',
}
CASES = {
    'ca_ownership': lambda: u07.create_account(A(ownership='bot')),
    'ca_account_id': lambda: u07.create_account(A(account_id='a b')),
    'ca_platform': lambda: u07.create_account(A(platform='myspace')),
    'ca_handle': lambda: u07.create_account(A(handle='bad handle!')),
    'ca_not_obj': lambda: u07.create_account('x'),
    'ca_unknown': lambda: u07.create_account(A(extra=1)),
    'ca_persona_not_obj': lambda: u07.create_account(A(persona='x')),
    'ca_persona_unknown': lambda: u07.create_account(A(persona={'display_name':'N','age':3})),
    'ca_real': lambda: u07.create_account(A(persona={'display_name':'N','claims_real_person':True})),
    'ca_blank_name': lambda: u07.create_account(A(persona={'display_name':' '})),
    'ca_long_bio': lambda: u07.create_account(A(persona={'display_name':'N','bio':'x'*501})),
    'ca_long_voice': lambda: u07.create_account(A(persona={'display_name':'N','voice':5})),
    'ca_source': lambda: u07.create_account(A(source_ref='')),
    'aa_not_obj': lambda: u07.add_account([],A()),
    'aa_not_list': lambda: u07.add_account({'accounts':'x'},A()),
    'aa_bad_entry': lambda: u07.add_account({'accounts':['x']},A()),
    'aa_dup': lambda: u07.add_account(fleet1,A(platform='tiktok')),
    'aa_platform': lambda: u07.add_account(fleet1,A(account_id='acct_2')),
    'pc_empty': lambda: u07.plan_calendar(A(),[]),
    'pc_many': lambda: u07.plan_calendar(A(),[E()]*93),
    'pc_entry_not_obj': lambda: u07.plan_calendar(A(),['x']),
    'pc_entry_unknown': lambda: u07.plan_calendar(A(),[E(),E(extra=1)]),
    'pc_date': lambda: u07.plan_calendar(A(),[E(date='12/10/2026')]),
    'pc_date_real': lambda: u07.plan_calendar(A(),[E(date='2026-02-30')]),
    'pc_title': lambda: u07.plan_calendar(A(),[E(title='')]),
    'pc_theme': lambda: u07.plan_calendar(A(),[E(theme='x'*201)]),
    'pc_format': lambda: u07.plan_calendar(A(),[E(format=None)]),
    'rm_not_obj': lambda: u07.record_metrics(A(),'x'),
    'rm_unknown': lambda: u07.record_metrics(A(),M(extra=1)),
    'rm_date': lambda: u07.record_metrics(A(),M(date='x')),
    'rm_date_real': lambda: u07.record_metrics(A(),M(date='2026-13-01')),
    'rm_followers': lambda: u07.record_metrics(A(),M(followers=-1)),
    'rm_impressions': lambda: u07.record_metrics(A(),M(impressions=1.5)),
    'rm_engagements': lambda: u07.record_metrics(A(),M(engagements=True)),
    'sm_empty': lambda: u07.summarize_metrics('acct_1',[]),
    'sm_id': lambda: u07.summarize_metrics('bad id',[R()]),
    'sm_not_obj': lambda: u07.summarize_metrics('acct_1',['x']),
    'sm_unknown': lambda: u07.summarize_metrics('acct_1',[R(extra=1)]),
    'sm_mismatch': lambda: u07.summarize_metrics('acct_9',[R()]),
    'sm_date': lambda: u07.summarize_metrics('acct_1',[R(date='x')]),
    'sm_date_real': lambda: u07.summarize_metrics('acct_1',[R(date='2026-02-30')]),
    'sm_followers': lambda: u07.summarize_metrics('acct_1',[R(followers='1')]),
    'sm_impressions': lambda: u07.summarize_metrics('acct_1',[R(impressions=-1)]),
    'sm_engagements': lambda: u07.summarize_metrics('acct_1',[R(engagements=2.5)]),
    'sp_platform': lambda: u07.signup_plan('myspace'),
    'pp_not_obj': lambda: u07.propose_post(A(),'x'),
    'pp_unknown': lambda: u07.propose_post(A(),{'text':'t','origin':'original','extra':1}),
    'pp_text': lambda: u07.propose_post(A(),{'text':' ','origin':'original'}),
    'pp_text_long': lambda: u07.propose_post(A(),{'text':'t'*5001,'origin':'original'}),
    'pp_altered': lambda: u07.propose_post(A(),{'text':'t','origin':'altered_repost'}),
    'pp_origin': lambda: u07.propose_post(A(),{'text':'t','origin':'x'}),
    'pp_original_credit': lambda: u07.propose_post(A(),{'text':'t','origin':'original','credit_source':'s'}),
    'pp_credited_none': lambda: u07.propose_post(A(),{'text':'t','origin':'credited'}),
    'pp_credited_long': lambda: u07.propose_post(A(),{'text':'t','origin':'credited','credit_source':'s'*201}),
}


def test_every_refusal_has_its_exact_documented_text():
    assert set(MESSAGES) == set(CASES)
    for k, fn in CASES.items():
        with pytest.raises(ValueError) as e:
            fn()
        assert str(e.value) == MESSAGES[k], k
