"""S4.8 / c35.olympiad tests. Hermetic, stdlib unittest, offline.

Prep only: checklist, form-prefill and mock scoring over SUPPLIED data.
The 20-question fixture is SYNTHETIC arithmetic, not olympiad content.
"""
import copy, importlib.util, json, math, pathlib, sys, unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
_P = _ROOT / "backend/app/modules/c35/olympiad.py"
_spec = importlib.util.spec_from_file_location("c35_olympiad", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["c35_olympiad"] = m
_spec.loader.exec_module(m)

TAGS = ["add", "sub", "mul", "div"]
BANK = [{"id": "q%d" % i, "prompt": "synthetic %d + %d" % (i, i),
         "answer": "AB"[i % 2], "tags": [TAGS[i % 4]]} for i in range(1, 21)]
ALL_RIGHT = {q["id"]: q["answer"] for q in BANK}


def mock(**kw):
    r = {"as_of": "2026-10-11", "mode": "mock", "bank": copy.deepcopy(BANK),
         "answers": dict(ALL_RIGHT), "time_limit_s": 1800, "elapsed_s": 1500}
    r.update(kw)
    return r


def check(**kw):
    r = {"as_of": "2026-10-11", "mode": "checklist",
         "olympiad": {"name": "Synthetic Cup", "deadline": "2026-10-21",
                      "requirements": ["Full Name", "school", "parent consent"]},
         "profile": {"full_name": "Test Student", "school": "Test School"}}
    r.update(kw)
    return r


def refused(tc, req, code):
    with tc.assertRaises(ValueError) as cm:
        m.run(req)
    tc.assertEqual(str(cm.exception), code)


class Mock(unittest.TestCase):
    def test_full_score_timed(self):
        o = m.run(mock())
        self.assertEqual(o["score"], 1.0)
        self.assertEqual((o["correct"], o["total"], o["unanswered"]), (20, 20, 0))
        self.assertIs(o["over_time"], False)

    def test_partial_and_unanswered_wrong(self):
        a = dict(ALL_RIGHT)
        del a["q1"]
        a["q2"] = "Z"
        o = m.run(mock(answers=a))
        self.assertEqual((o["correct"], o["unanswered"]), (18, 1))
        self.assertEqual(o["score"], 0.9)

    def test_score_rounded_six(self):
        b = BANK[:3]
        o = m.run(mock(bank=b, answers={"q1": b[0]["answer"]}))
        self.assertEqual(o["score"], round(1 / 3, 6))
        self.assertEqual(o["score"], 0.333333)

    def test_over_time_flagged_score_kept(self):
        o = m.run(mock(elapsed_s=1801))
        self.assertIs(o["over_time"], True)
        self.assertEqual(o["score"], 1.0)

    def test_equality_not_over(self):
        self.assertIs(m.run(mock(elapsed_s=1800))["over_time"], False)
        self.assertIs(m.run(mock(elapsed_s=0))["over_time"], False)

    def test_tag_breakdown(self):
        a = dict(ALL_RIGHT)
        a["q1"] = "Z"  # q1 is tag sub (1 % 4 == 1)
        pt = m.run(mock(answers=a))["per_tag"]
        self.assertEqual(sorted(pt), ["add", "div", "mul", "sub"])
        self.assertEqual(pt["sub"], {"correct": 4, "total": 5, "score": 0.8})
        self.assertEqual(pt["add"], {"correct": 5, "total": 5, "score": 1.0})

    def test_multi_tag_counts_each_and_untagged(self):
        b = [{"id": "a", "prompt": "p", "answer": "1", "tags": ["x", "y"]},
             {"id": "b", "prompt": "p", "answer": "2"},
             {"id": "c", "prompt": "p", "answer": "3", "tags": []}]
        o = m.run(mock(bank=b, answers={"a": "1", "b": "2", "c": "3"}))
        self.assertEqual(o["per_tag"]["x"]["total"], 1)
        self.assertEqual(o["per_tag"]["y"]["total"], 1)
        self.assertEqual(o["per_tag"]["untagged"]["total"], 2)
        self.assertEqual(o["total"], 3)
        self.assertIn("tag", o["tag_note"].lower())

    def test_match_rules(self):
        b = [{"id": "s", "prompt": "p", "answer": "B"},
             {"id": "t", "prompt": "p", "answer": "Foo"},
             {"id": "u", "prompt": "p", "answer": " 12 "}]
        o = m.run(mock(bank=b, answers={"s": " b ", "t": "foo", "u": "12"}))
        res = {r["id"]: r["correct"] for r in o["results"]}
        self.assertEqual(res, {"s": True, "t": False, "u": True})

    def test_single_letter_needs_alpha_both_sides(self):
        b = [{"id": "s", "prompt": "p", "answer": "1"}]
        self.assertEqual(m.run(mock(bank=b, answers={"s": "1"}))["correct"], 1)
        b = [{"id": "s", "prompt": "p", "answer": "b"}]
        self.assertEqual(m.run(mock(bank=b, answers={"s": "B"}))["correct"], 1)
        self.assertEqual(m.run(mock(bank=b, answers={"s": "BB"}))["correct"], 0)

    def test_unknown_answer_ids_listed(self):
        a = dict(ALL_RIGHT)
        a["zz"] = "A"
        a["aa"] = "A"
        o = m.run(mock(answers=a))
        self.assertEqual(o["unknown_answer_ids"], ["aa", "zz"])
        self.assertEqual(o["correct"], 20)

    def test_validation(self):
        refused(self, mock(bank=[]), "APPLY_REFUSED_EMPTY:bank")
        d = copy.deepcopy(BANK)
        d[1]["id"] = "q1"
        refused(self, mock(bank=d), "APPLY_REFUSED_BAD_TYPE:bank")
        refused(self, mock(answers=[]), "APPLY_REFUSED_BAD_TYPE:answers")
        refused(self, mock(answers={"q1": 1}), "APPLY_REFUSED_BAD_TYPE:answer")
        refused(self, mock(answers={"nope": 1}), "APPLY_REFUSED_BAD_TYPE:answer")
        refused(self, mock(bank=BANK * 14), "APPLY_REFUSED_OVERSIZE:bank")
        big = copy.deepcopy(BANK)
        big[0]["prompt"] = "x" * 2001
        refused(self, mock(bank=big), "APPLY_REFUSED_OVERSIZE:prompt")
        ok = copy.deepcopy(BANK)
        ok[0]["prompt"] = "x" * 2000
        self.assertEqual(m.run(mock(bank=ok))["total"], 20)
        self.assertEqual(m.run(mock(bank=(BANK * 13)[:256] and
                                    [dict(BANK[0], id="i%d" % i) for i in range(256)],
                                    answers={}))["total"], 256)

    def test_time_validation(self):
        for k, v, f in [("time_limit_s", 0, "time_limit_s"), ("time_limit_s", -1, "time_limit_s"),
                        ("time_limit_s", 86401, "time_limit_s"), ("time_limit_s", True, "time_limit_s"),
                        ("time_limit_s", float("nan"), "time_limit_s"),
                        ("time_limit_s", "5", "time_limit_s"), ("time_limit_s", None, "time_limit_s"),
                        ("elapsed_s", -1, "elapsed_s"), ("elapsed_s", 604801, "elapsed_s"),
                        ("elapsed_s", False, "elapsed_s"), ("elapsed_s", float("inf"), "elapsed_s"),
                        ("elapsed_s", "5", "elapsed_s")]:
            refused(self, mock(**{k: v}), "APPLY_REFUSED_BAD_TYPE:" + f)
        self.assertEqual(m.run(mock(time_limit_s=86400, elapsed_s=604800))["over_time"], True)

    def test_floats_rounded(self):
        o = m.run(mock(elapsed_s=0.12345678, time_limit_s=1.5))
        self.assertEqual(o["elapsed_s"], 0.123457)

    def test_no_prompt_echo_and_scope(self):
        o = m.run(mock())
        self.assertNotIn("synthetic", json.dumps(o))
        self.assertIn("not an olympiad score", o["limits"])
        self.assertEqual(sorted(o["scope"]), ["as_of", "data_source", "implemented", "not_implemented"])
        self.assertEqual(o["scope"]["as_of"], "2026-10-11")


class Checklist(unittest.TestCase):
    def test_done_missing_prefill_days(self):
        o = m.run(check())
        st = {r["requirement"]: r["status"] for r in o["requirements"]}
        self.assertEqual(st, {"Full Name": "done", "school": "done", "parent consent": "missing"})
        self.assertEqual(o["requirements"][0]["key"], "full_name")
        self.assertEqual(o["prefill"], {"full_name": "Test Student", "school": "Test School"})
        self.assertEqual((o["done_count"], o["missing_count"]), (2, 1))
        self.assertEqual(o["days_left"], 10)
        self.assertEqual(o["status"], "open")

    def test_empty_values_missing(self):
        o = m.run(check(profile={"full_name": None, "school": "  ", "parent_consent": ""}))
        self.assertEqual(o["done_count"], 0)
        self.assertEqual(o["prefill"], {})

    def test_deadline_boundaries(self):
        o = m.run(check(as_of="2026-10-21"))
        self.assertEqual((o["days_left"], o["status"]), (0, "open"))
        o = m.run(check(as_of="2026-10-22"))
        self.assertEqual((o["days_left"], o["status"]), (-1, "expired"))
        self.assertEqual(len(o["requirements"]), 3)  # checklist still produced

    def test_bad_dates(self):
        ol = dict(check()["olympiad"])
        for bad in ["21/10/2026", "2026-13-01", "2026-10-21T00:00", "", 20261021, True]:
            ol["deadline"] = bad
            refused(self, check(olympiad=dict(ol)), "APPLY_REFUSED_BAD_TYPE:deadline")
        for bad in ["11-10-2026", "2026-02-30", None]:
            refused(self, check(as_of=bad), "APPLY_REFUSED_BAD_TYPE:as_of")

    def test_credential_and_id_keys_not_prefilled(self):
        reqs = ["school", "ssn", "aadhaar", "passport", "pan", "national_id", "card_number"]
        prof = {"school": "S", "ssn": "1", "aadhaar": "2", "passport": "3", "pan": "4",
                "national_id": "5", "card_number": "6"}
        o = m.run(check(olympiad={"name": "n", "deadline": "2026-10-21", "requirements": reqs}, profile=prof))
        self.assertEqual(o["prefill"], {"school": "S"})
        self.assertEqual(o["prefill_excluded"], sorted(reqs[1:]))
        self.assertEqual((o["done_count"], o["missing_count"]), (1, 0))
        self.assertEqual([r["status"] for r in o["requirements"]], ["done"] + ["prefill_excluded"] * 6)
        self.assertNotIn("6", json.dumps(o["prefill"]))

    def test_fee_ignored_never_output(self):
        a = m.run(check())
        ol = dict(check()["olympiad"], fee="USD 5000 secretfee")
        b = m.run(check(olympiad=ol))
        self.assertEqual(a, b)
        self.assertNotIn("secretfee", json.dumps(b))
        self.assertNotIn("fee", json.dumps(b).replace("prefill", ""))

    def test_validation(self):
        ol = check()["olympiad"]
        refused(self, check(olympiad=dict(ol, requirements=[])), "APPLY_REFUSED_EMPTY:requirements")
        refused(self, check(olympiad=dict(ol, requirements=["a"] * 65)), "APPLY_REFUSED_OVERSIZE:requirements")
        self.assertEqual(len(m.run(check(olympiad=dict(ol, requirements=["a"] * 64)))["requirements"]), 64)
        refused(self, check(olympiad=dict(ol, requirements=["a", 3])), "APPLY_REFUSED_BAD_TYPE:requirement")
        refused(self, check(olympiad=dict(ol, name="")), "APPLY_REFUSED_EMPTY:name")
        refused(self, check(olympiad=[]), "APPLY_REFUSED_BAD_TYPE:olympiad")
        refused(self, check(profile=[]), "APPLY_REFUSED_BAD_TYPE:profile")
        refused(self, check(profile={"school": ["x"]}), "APPLY_REFUSED_BAD_TYPE:profile")
        refused(self, check(mode="other"), "APPLY_REFUSED_UNKNOWN:mode")
        refused(self, check(mode="spend"), "APPLY_REFUSED_SPEND")
        refused(self, check(mode=5), "APPLY_REFUSED_BAD_TYPE:mode")
        refused(self, [], "APPLY_REFUSED_BAD_TYPE:request")


class Refusals(unittest.TestCase):
    TABLE = {
        "REGISTER": ["register", "submit"],
        "ATTEMPT": ["attempt", "take_exam"],
        "NOCREDS": ["login", "password", "username", "credentials", "otp", "api_key",
                    "access_token", "refresh_token", "bearer", "pass", "passwd"],
        "SPEND": ["pay", "waive_fee", "fee_action"],
        "SEND": ["send", "approve", "approved", "approval", "approval_token", "smtp", "token",
                 "email_send", "sender", "smtp_host", "smtp_port", "smtp_user"],
    }

    def test_every_key_every_class(self):
        for reason, keys in self.TABLE.items():
            for k in keys:
                for req in (check(), mock()):
                    r = copy.deepcopy(req)
                    r[k] = True
                    refused(self, r, "APPLY_REFUSED_%s:%s" % (reason, k))

    def test_depth_case_hyphen_lists(self):
        r = check()
        r["profile"]["extra"] = {"deep": [{"Take-Exam": 1}]}
        refused(self, r, "APPLY_REFUSED_ATTEMPT:take_exam")
        r = mock()
        r["answers"]["LOGIN"] = "A"
        refused(self, r, "APPLY_REFUSED_NOCREDS:login")
        r = mock()
        r["bank"][3]["Approval-Token"] = "x"
        refused(self, r, "APPLY_REFUSED_SEND:approval_token")

    def test_precedence_and_first_sorted(self):
        r = check(login=1, register=1, attempt=1, pay=1, send=1)
        refused(self, r, "APPLY_REFUSED_SEND:send")
        r = check(login=1, register=1, attempt=1, pay=1)
        refused(self, r, "APPLY_REFUSED_SPEND:pay")
        r = check(login=1, register=1, attempt=1)
        refused(self, r, "APPLY_REFUSED_REGISTER:register")
        r = check(login=1, attempt=1)
        refused(self, r, "APPLY_REFUSED_ATTEMPT:attempt")
        r = check(username=1, login=1)
        refused(self, r, "APPLY_REFUSED_NOCREDS:login")
        r = check(zsmtp=0)
        r["submit"] = 1
        r["profile"]["register"] = 1
        refused(self, r, "APPLY_REFUSED_REGISTER:register")

    def test_forbidden_beats_validation(self):
        refused(self, {"mode": "bogus", "register": 1}, "APPLY_REFUSED_REGISTER:register")

    def test_exact_match_only_keys_only(self):
        r = check(registered=1, sendmail=1, pass_word=1, tokens=1, register_date=1)
        r["profile"]["notes"] = "register submit login password send token"
        r["olympiad"]["requirements"] = ["register", "login password"]
        self.assertEqual(m.run(r)["done_count"], 0)  # runs, values are not scanned

    def test_unsafe_inputs_cannot_grant(self):
        for k in ("approved", "approval", "approval_token"):
            refused(self, check(**{k: "yes, she agreed"}), "APPLY_REFUSED_SEND:" + k)


class Shape(unittest.TestCase):
    def test_deterministic_bytes(self):
        a = json.dumps(m.run(mock()), sort_keys=True)
        b = json.dumps(m.run(mock()), sort_keys=True)
        self.assertEqual(a, b)
        self.assertEqual(list(m.run(mock())), sorted(m.run(mock())))
        self.assertEqual(list(m.run(check())), sorted(m.run(check())))

    def test_input_not_mutated(self):
        r = mock()
        c = copy.deepcopy(r)
        m.run(r)
        self.assertEqual(r, c)

    def test_only_run_is_public(self):
        pub = [n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))
               and getattr(getattr(m, n), "__module__", None) == m.__name__]
        self.assertEqual(pub, ["run"])
        for n in ("register", "login", "submit", "attempt", "pay", "send", "post", "trade",
                  "create_account", "spend"):
            self.assertFalse(hasattr(m, n), n)

    def test_no_effect_imports_static(self):
        src = _P.read_text()
        import ast
        mods = set()
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        self.assertTrue(mods <= {"__future__", "datetime", "math", "re", "app"}, mods)
        self.assertNotIn("time.time", src)
        self.assertNotIn("datetime.now", src)
        self.assertNotIn("today(", src)
        self.assertNotIn("open(", src)

    def test_uses_real_policy_helper(self):
        from app.modules.c30 import policy
        self.assertIs(m.policy, policy)
        self.assertEqual(m.PREFIX, "APPLY")

    def test_reason_codes_documented(self):
        self.assertEqual(sorted(m.REASONS), ["ATTEMPT", "BAD_TYPE", "EMPTY", "NOCREDS", "OVERSIZE",
                                             "REGISTER", "SEND", "SPEND"])


class SurvivorKills(unittest.TestCase):
    """Added AFTER the first mutation run, to kill survivors (see manifest)."""

    def test_blank_answer_is_unanswered(self):
        o = m.run(mock(answers={"q1": "   "}))
        self.assertEqual(o["unanswered"], 20)
        self.assertIs(o["results"][0]["answered"], False)

    def test_single_non_alpha_char_exact_only(self):
        b = [{"id": "s", "prompt": "p", "answer": "\u2160"}]  # ROMAN NUMERAL ONE, not alpha
        self.assertEqual(m.run(mock(bank=b, answers={"s": "\u2170"}))["correct"], 0)
        self.assertEqual(m.run(mock(bank=b, answers={"s": "\u2160"}))["correct"], 1)

    def test_bank_cap_boundary(self):
        big = [dict(BANK[0], id="i%d" % i) for i in range(257)]
        refused(self, mock(bank=big, answers={}), "APPLY_REFUSED_OVERSIZE:bank")

    def test_prefill_sorted_and_float_rounded(self):
        o = m.run(check(olympiad={"name": "n", "deadline": "2026-10-21", "requirements": ["zeta", "alpha", "mid"]},
                        profile={"zeta": 0.12345678, "alpha": 1, "mid": True}))
        self.assertEqual(list(o["prefill"]), ["alpha", "mid", "zeta"])
        self.assertEqual(o["prefill"]["zeta"], 0.123457)
        o = m.run(check(olympiad={"name": "n", "deadline": "2026-10-21", "requirements": ["ssn", "passport", "pan"]},
                        profile={}))
        self.assertEqual(o["prefill_excluded"], ["pan", "passport", "ssn"])

    def test_results_in_bank_order(self):
        b = [{"id": i, "prompt": "p", "answer": "A"} for i in ("z", "a", "m")]
        o = m.run(mock(bank=b, answers={}))
        self.assertEqual([r["id"] for r in o["results"]], ["z", "a", "m"])

    def test_duplicate_tags_count_once(self):
        b = [{"id": "a", "prompt": "p", "answer": "1", "tags": ["x", "x"]}]
        o = m.run(mock(bank=b, answers={"a": "1"}))
        self.assertEqual(o["per_tag"], {"x": {"correct": 1, "score": 1.0, "total": 1}})

    def test_bank_id_validated(self):
        for bad, code in ((5, "BAD_TYPE:id"), ("", "EMPTY:id"), (None, "BAD_TYPE:id")):
            b = [{"id": bad, "prompt": "p", "answer": "A"}]
            refused(self, mock(bank=b, answers={}), "APPLY_REFUSED_" + code)


class RepairWave2(unittest.TestCase):
    """Repair child tests (peer rulings 1-5). Added before the runtime change."""

    def test_non_str_key_any_depth(self):
        r = check()
        r[5] = 1
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:key")
        r = check()
        r["profile"]["extra"] = [{"ok": {None: 1}}]
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:key")
        r = mock()
        r["answers"][3] = "A"
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:key")

    def test_non_str_key_after_forbidden_scan(self):
        r = check()
        r[5] = 1
        r["register"] = 1
        refused(self, r, "APPLY_REFUSED_REGISTER:register")
        r = check()
        r["profile"]["deep"] = {7: 1, "Login": 2}
        refused(self, r, "APPLY_REFUSED_NOCREDS:login")

    def test_non_str_key_before_top_types_and_mode(self):
        refused(self, {"mode": 5, "as_of": 3, 9: 1}, "APPLY_REFUSED_BAD_TYPE:key")

    def test_profile_value_types(self):
        for bad in (float("nan"), float("inf"), float("-inf"), {"a": 1}, [1], (1,), b"x", object()):
            refused(self, check(profile={"school": bad}), "APPLY_REFUSED_BAD_TYPE:profile")
        for good in (None, "s", 0, -3, 2.5, True, False):
            m.run(check(profile={"school": good}))

    def test_mode_rules(self):
        refused(self, check(mode=None), "APPLY_REFUSED_BAD_TYPE:mode")
        refused(self, check(mode=["mock"]), "APPLY_REFUSED_BAD_TYPE:mode")
        refused(self, check(mode="MOCK"), "APPLY_REFUSED_UNKNOWN:mode")
        refused(self, check(mode="register_now"), "APPLY_REFUSED_UNKNOWN:mode")
        refused(self, check(mode=" mock"), "APPLY_REFUSED_UNKNOWN:mode")  # no normalisation
        for rule, code in (("spend", "SPEND"), ("outreach", "OUTREACH"), ("scrape", "SCRAPE"),
                           ("trade", "TRADE"), ("autopost", "AUTOPOST"), ("fakeacct", "FAKEACCT")):
            refused(self, check(mode=rule), "APPLY_REFUSED_" + code)  # standing-rule names, no value suffix

    def test_unknown_mode_error_never_echoes_value(self):
        for bad in ("zzzSECRETzzz", "Mock", "unknown", "a:b"):
            with self.assertRaises(ValueError) as cm:
                m.run(check(mode=bad))
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_UNKNOWN:mode")
            self.assertNotIn(bad, str(cm.exception))

    def test_order_top_types_before_caps(self):
        # answers not a dict AND bank oversize -> top type first
        refused(self, mock(bank=BANK * 14, answers=[]), "APPLY_REFUSED_BAD_TYPE:answers")
        refused(self, check(olympiad={"name": "n", "deadline": "2026-10-21", "requirements": ["a"] * 65},
                            profile=[]), "APPLY_REFUSED_BAD_TYPE:profile")
        refused(self, mock(bank="x", elapsed_s=-1), "APPLY_REFUSED_BAD_TYPE:bank")

    def test_order_mode_before_caps_and_fields(self):
        refused(self, mock(mode="zzz", bank=BANK * 14), "APPLY_REFUSED_UNKNOWN:mode")
        refused(self, mock(as_of="bad", bank=BANK * 14), "APPLY_REFUSED_BAD_TYPE:as_of")

    def test_order_caps_before_per_field(self):
        bad_first = [{"id": 1, "prompt": "p", "answer": "A"}] + [dict(BANK[0], id="i%d" % i) for i in range(256)]
        refused(self, mock(bank=bad_first, answers={}), "APPLY_REFUSED_OVERSIZE:bank")
        b = [{"id": 1, "prompt": "p", "answer": "A"}, {"id": "ok", "prompt": "x" * 2001, "answer": "A"}]
        refused(self, mock(bank=b, answers={}), "APPLY_REFUSED_OVERSIZE:prompt")
        refused(self, mock(bank=[], answers={"q": 3}), "APPLY_REFUSED_EMPTY:bank")
        ol = {"name": "", "deadline": "bad", "requirements": ["a"] * 65}
        refused(self, check(olympiad=ol), "APPLY_REFUSED_OVERSIZE:requirements")
        ol = {"name": "", "deadline": "bad", "requirements": []}
        refused(self, check(olympiad=ol), "APPLY_REFUSED_EMPTY:requirements")

    def test_order_forbidden_before_everything(self):
        refused(self, {"mode": 5, "as_of": 3, "send": 1}, "APPLY_REFUSED_SEND:send")
        refused(self, {"bank": "x", "pay": 1}, "APPLY_REFUSED_SPEND:pay")

    def test_credential_requirements_prefill_excluded_status(self):
        reqs = ["school", "ssn", "Password", "parent consent", "OTP", "Passport"]
        o = m.run(check(olympiad={"name": "n", "deadline": "2026-10-21", "requirements": reqs},
                        profile={"school": "S", "ssn": "123", "passport": "hunter2"}))
        self.assertEqual([r["status"] for r in o["requirements"]],
                         ["done", "prefill_excluded", "prefill_excluded", "missing", "prefill_excluded",
                          "prefill_excluded"])
        self.assertEqual(o["coverage"], {"done": 1, "missing": 1, "prefill_excluded": 4})
        self.assertEqual((o["done_count"], o["missing_count"]), (1, 1))
        self.assertEqual(o["prefill"], {"school": "S"})
        self.assertEqual(o["prefill_excluded"], ["otp", "passport", "password", "ssn"])
        blob = json.dumps(o)
        for secret in ("123", "hunter2"):
            self.assertNotIn(secret, blob)

    def test_credential_requirement_never_missing_or_done_even_absent_from_profile(self):
        o = m.run(check(olympiad={"name": "n", "deadline": "2026-10-21", "requirements": ["aadhaar"]},
                        profile={}))
        self.assertEqual(o["requirements"][0]["status"], "prefill_excluded")
        self.assertEqual(o["coverage"], {"done": 0, "missing": 0, "prefill_excluded": 1})

    def test_coverage_present_for_plain_checklist(self):
        o = m.run(check())
        self.assertEqual(o["coverage"], {"done": 2, "missing": 1, "prefill_excluded": 0})


class RepairSurvivorKills(unittest.TestCase):
    """Added AFTER the repair mutation run 1 (see manifest)."""

    def test_profile_string_control_chars_refused(self):
        refused(self, check(profile={"school": "a\x00b"}), "APPLY_REFUSED_CONTROL_CHARS:profile")
        refused(self, check(profile={"school": "x" * 2001}), "APPLY_REFUSED_TEXT_TOO_LONG:profile")

    def test_top_type_order_olympiad_then_profile(self):
        refused(self, check(olympiad=[], profile=[]), "APPLY_REFUSED_BAD_TYPE:olympiad")
        refused(self, check(profile=[], olympiad={"name": "n", "deadline": "2026-10-21", "requirements": "x"}),
                "APPLY_REFUSED_BAD_TYPE:requirements")


class ForbiddenSuffixTableKey(unittest.TestCase):
    """Repair-3: the suffix is the matched normalized TABLE key, never request-derived text."""

    def test_within_class_first_sorted_table_key_not_path_order(self):
        r = check()
        r["zzz"] = {"smtp_user": 1}
        r["aaa"] = {"approve": 1}  # path aaa.approve sorts first, table key approve also first
        refused(self, r, "APPLY_REFUSED_SEND:approve")
        r = check()
        r["aaa"] = {"smtp_user": 1}  # path sorts first, but table key approve must win
        r["zzz"] = {"approve": 1}
        refused(self, r, "APPLY_REFUSED_SEND:approve")
        r = check(username=1)
        r["z"] = {"passwd": 1}
        r["a"] = {"pass": 1}
        refused(self, r, "APPLY_REFUSED_NOCREDS:pass")
        r = check(waive_fee=1, pay=1)
        refused(self, r, "APPLY_REFUSED_SPEND:pay")

    def test_no_request_derived_text_in_reason(self):
        for k in ("Take-Exam", "TAKE_EXAM", "take-exam"):
            r = check()
            r["deep"] = {"SECRETPATH": [{k: 1}]}
            with self.assertRaises(ValueError) as cm:
                m.run(r)
            self.assertEqual(str(cm.exception), "APPLY_REFUSED_ATTEMPT:take_exam")
            self.assertNotIn("SECRETPATH", str(cm.exception))
            self.assertNotIn("deep", str(cm.exception))
        for k in ("Approval-Token", "APPROVAL_TOKEN"):
            r = mock()
            r["answers"][k] = "A"
            refused(self, r, "APPLY_REFUSED_SEND:approval_token")

    def test_mode_partition_uses_policy_rules(self):
        from app.modules.c30 import policy
        self.assertEqual(sorted(policy.RULES), ["autopost", "fakeacct", "outreach", "scrape", "spend", "trade"])
        for rule in policy.RULES:
            refused(self, check(mode=rule), "APPLY_REFUSED_" + policy.RULES[rule])
        for notrule in ("Spend", "spend ", "SPEND", "check", "classify", "offline"):
            refused(self, check(mode=notrule), "APPLY_REFUSED_UNKNOWN:mode")


class Wave7Pins(unittest.TestCase):
    """Mode rule (exact compare, no clean_text, no cap) and boundary pins."""

    def test_mode_weird_strings_unknown(self):
        for bad in ("", " ", "x\n", "x" * 32, "x" * 33, "x" * 300, "mock\n", " checklist", "Mock",
                    "\x00", "mock\u200b", "\u2028"):
            for mk in (check, mock):
                with self.assertRaises(ValueError) as cm:
                    m.run(mk(mode=bad))
                self.assertEqual(str(cm.exception), "APPLY_REFUSED_UNKNOWN:mode", repr(bad))
        for good_rule in ("spend", "trade"):
            refused(self, check(mode=good_rule), "APPLY_REFUSED_" + good_rule.upper())
        for bad in (None, 5, 1.5, True, b"mock", ["mock"], {"a": 1}):
            refused(self, check(mode=bad), "APPLY_REFUSED_BAD_TYPE:mode")

    def test_mode_absent_is_bad_type(self):
        r = check()
        del r["mode"]
        refused(self, r, "APPLY_REFUSED_BAD_TYPE:mode")

    def _cap(self, build, ok, over, code):
        build(ok)
        with self.assertRaises(ValueError) as cm:
            build(over)
        self.assertEqual(str(cm.exception), code)

    def test_cap_name_256(self):
        def b(n):
            return m.run(check(olympiad={"name": n, "deadline": "2026-10-21", "requirements": ["a"]}))
        self._cap(b, "x" * 256, "x" * 257, "APPLY_REFUSED_TEXT_TOO_LONG:name")

    def test_cap_requirement_256(self):
        def b(n):
            return m.run(check(olympiad={"name": "n", "deadline": "2026-10-21", "requirements": [n]}))
        self._cap(b, "x" * 256, "x" * 257, "APPLY_REFUSED_TEXT_TOO_LONG:requirement")

    def test_cap_profile_2000(self):
        def b(n):
            return m.run(check(profile={"school": n}))
        self._cap(b, "x" * 2000, "x" * 2001, "APPLY_REFUSED_TEXT_TOO_LONG:profile")

    def test_cap_id_64(self):
        def b(n):
            return m.run(mock(bank=[{"id": n, "prompt": "p", "answer": "A"}], answers={}))
        self._cap(b, "i" * 64, "i" * 65, "APPLY_REFUSED_TEXT_TOO_LONG:id")

    def test_cap_bank_answer_256(self):
        def b(n):
            return m.run(mock(bank=[{"id": "q", "prompt": "p", "answer": n}], answers={}))
        self._cap(b, "a" * 256, "a" * 257, "APPLY_REFUSED_TEXT_TOO_LONG:answer")

    def test_cap_given_answer_256_and_blank_ok(self):
        def b(n):
            return m.run(mock(answers={"q1": n}))
        self._cap(b, "a" * 256, "a" * 257, "APPLY_REFUSED_TEXT_TOO_LONG:answer")
        self._cap(b, " " * 256, " " * 257, "APPLY_REFUSED_TEXT_TOO_LONG:answer")
        self.assertEqual(m.run(mock(answers={"q1": ""}))["unanswered"], 20)
        self.assertEqual(m.run(mock(answers={"q1": " " * 256}))["unanswered"], 20)

    def test_cap_tag_64(self):
        def b(n):
            return m.run(mock(bank=[{"id": "q", "prompt": "p", "answer": "A", "tags": [n]}], answers={}))
        self._cap(b, "t" * 64, "t" * 65, "APPLY_REFUSED_TEXT_TOO_LONG:tag")

    def test_time_limit_fraction_and_zero(self):
        o = m.run(mock(time_limit_s=0.5, elapsed_s=0.25))
        self.assertEqual((o["time_limit_s"], o["over_time"]), (0.5, False))
        o = m.run(mock(time_limit_s=0.000001, elapsed_s=0.000002))
        self.assertEqual((o["time_limit_s"], o["over_time"]), (0.000001, True))
        refused(self, mock(time_limit_s=0), "APPLY_REFUSED_BAD_TYPE:time_limit_s")
        refused(self, mock(time_limit_s=0.0), "APPLY_REFUSED_BAD_TYPE:time_limit_s")
        self.assertEqual(m.run(mock(time_limit_s=1, elapsed_s=0))["elapsed_s"], 0)

    def test_deadline_years(self):
        for d, days in (("2026-10-11", 0), ("2027-10-11", 365), ("2027-12-31", 446)):
            ol = dict(check()["olympiad"], deadline=d)
            self.assertEqual(m.run(check(olympiad=ol))["days_left"], days, d)
        for d in ("2000-02-29", "0001-01-01", "9999-12-31"):
            ol = dict(check()["olympiad"], deadline=d)
            self.assertEqual(m.run(check(olympiad=ol))["olympiad"]["deadline"], d)
        for d in ("2100-02-29", "1900-02-29", "0000-01-01", "2026-00-10", "2026-10-00", "2026-1-1",
                  "2026-10-1", "2026-1-10", "２０２６-10-21"):
            ol = dict(check()["olympiad"], deadline=d)
            refused(self, check(olympiad=ol), "APPLY_REFUSED_BAD_TYPE:deadline")
        self.assertEqual(m.run(check(as_of="2027-01-01"))["days_left"], -72)

    def test_per_tag_third_rounded_six(self):
        b = [{"id": "a%d" % i, "prompt": "p", "answer": "A", "tags": ["t"]} for i in range(3)]
        o = m.run(mock(bank=b, answers={"a0": "A"}))
        self.assertEqual(o["per_tag"]["t"], {"correct": 1, "score": 0.333333, "total": 3})
        o = m.run(mock(bank=b, answers={"a0": "A", "a1": "A"}))
        self.assertEqual(o["per_tag"]["t"]["score"], 0.666667)
        self.assertEqual(o["score"], 0.666667)


if __name__ == "__main__":
    unittest.main()
