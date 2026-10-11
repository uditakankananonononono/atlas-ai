"""Row 1540 TAGUCH1540 tests. Hermetic, stdlib unittest, N/N+1 pins."""
import copy, importlib.util, pathlib, sys, unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/m20_general_cognitive_worker/taguchi_methods1540.py"
_spec = importlib.util.spec_from_file_location("taguchi_methods1540", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["taguchi_methods1540"] = m
_spec.loader.exec_module(m)

L4 = [[1, 1, 1], [1, 2, 2], [2, 1, 2], [2, 2, 1]]


def run_rec(i, levels, responses):
    return {"id": i, "levels": levels, "responses": responses}


def packet(goal="larger", **kw):
    d = {"goal": goal, "factors": ["A", "B", "C"],
         "runs": [run_rec("r%d" % (k + 1), L4[k], ["1", "2"]) for k in range(4)]}
    d.update(kw)
    return d


def single(goal, responses, **kw):
    return packet(goal, factors=["A"], runs=[run_rec("r1", [1], responses)], **kw)


def go(p):
    return m.analyze_taguchi_runs(p)


def sn(goal, responses):
    return go(single(goal, responses))["runs"][0]["signal_to_noise_db"]


def refusal(test, p):
    with test.assertRaises(ValueError) as cm:
        go(p)
    return str(cm.exception)


class Compute(unittest.TestCase):
    def test_sn_known_values(self):
        self.assertEqual(sn("larger", ["2", "2"]), "6.020600")
        self.assertEqual(sn("smaller", ["2", "2"]), "-6.020600")
        self.assertEqual(sn("larger", ["1", "2"]), "2.041200")
        self.assertEqual(sn("smaller", ["1", "2"]), "-3.979400")
        self.assertEqual(sn("nominal", ["1", "3"]), "6.020600")
        self.assertEqual(sn("nominal", ["1", "2", "3"]), "7.781513")
        self.assertEqual(sn("nominal", ["2", "4"]), "9.542425")

    def test_zero_sn_has_no_negative_zero(self):
        self.assertEqual(sn("larger", ["1"]), "0.000000")
        self.assertEqual(sn("smaller", ["1"]), "0.000000")

    def test_nominal_sign_of_mean_irrelevant(self):
        self.assertEqual(sn("nominal", ["-2", "-4"]), "9.542425")

    def test_smaller_accepts_negative_and_zero_mixed(self):
        self.assertEqual(sn("smaller", ["-2", "0", "2"]), "-4.259687")   # mean square 8/3

    def test_larger_requires_positive(self):
        self.assertEqual(refusal(self, single("larger", ["0"])), "TAGUCH1540:undefined_sn")
        self.assertEqual(refusal(self, single("larger", ["1", "-1"])), "TAGUCH1540:undefined_sn")
        self.assertEqual(sn("larger", ["0.000001"]), "-120.000000")

    def test_smaller_all_zero_degenerate(self):
        self.assertEqual(refusal(self, single("smaller", ["0", "0"])), "TAGUCH1540:undefined_sn")
        self.assertEqual(sn("smaller", ["0.000001"]), "120.000000")

    def test_nominal_degenerate(self):
        for r in (["2"], ["2", "2"], ["-1", "1"], ["0", "0"]):
            self.assertEqual(refusal(self, single("nominal", r)), "TAGUCH1540:undefined_sn")

    def test_array_orthogonal_l4(self):
        r = go(packet())
        self.assertEqual(r["array_status"], "pairwise_balanced")
        self.assertEqual(r["factor_summaries"][0], {"factor": "A", "observed_levels": [1, 2], "balanced": True,
                                                     "level_mean_sn": {"1": "2.041200", "2": "2.041200"}})
        self.assertEqual(r["run_count"], 4)

    def test_array_not_orthogonal(self):
        rows = [[1, 1, 1], [1, 2, 2], [2, 1, 2], [2, 1, 1]]
        p = packet(runs=[run_rec("r%d" % (k + 1), rows[k], ["1", "2"]) for k in range(4)])
        self.assertEqual(refusal(self, p), "TAGUCH1540:not_orthogonal")

    def test_pairwise_check_needs_all_combinations(self):
        rows = [[1, 1], [1, 1], [2, 2], [2, 2]]   # each factor balanced, pair combos missing
        p = packet(factors=["A", "B"], runs=[run_rec("r%d" % (k + 1), rows[k], ["1"]) for k in range(4)])
        self.assertEqual(refusal(self, p), "TAGUCH1540:not_orthogonal")

    def test_single_factor_orthogonal_vacuous_true_if_balanced(self):
        p = packet(factors=["A"], runs=[run_rec("a", [1], ["1"]), run_rec("b", [2], ["1"])])
        self.assertEqual(go(p)["array_status"], "pairwise_balanced")
        p = packet(factors=["A"], runs=[run_rec("a", [1], ["1"]), run_rec("b", [2], ["1"]), run_rec("c", [2], ["1"])])
        self.assertEqual(refusal(self, p), "TAGUCH1540:not_orthogonal")

    def test_level_means_bookkeeping_only(self):
        p = packet(factors=["A"], runs=[run_rec("a", [1], ["1"]), run_rec("b", [2], ["2"]), run_rec("c", [1], ["2"]),
                                                  run_rec("d", [2], ["2"])])
        f = go(p)["factor_summaries"][0]
        self.assertEqual(f["level_mean_sn"], {"1": "3.010300", "2": "6.020600"})   # level1 = (0 + 6.0206)/2; level2 = (6.0206 + 6.0206)/2
        self.assertEqual(set(f), {"factor", "observed_levels", "balanced", "level_mean_sn"})

    BANNED = ("best", "better", "optimal", "optimum", "recommend", "rank", "winner", "winning", "robust", "improve",
              "superior", "ideal", "preferred", "highest", "select", "choose")   # the 13 relayed words plus the three older ones, kept
    EXEMPT_KEYS = frozenset({"robustness_certified"})   # the one disclaimer key (value is a bool); listed in the contract

    @classmethod
    def banned_in(cls, out):
        """Banned tokens in generated keys and str values (caller ids and factor names excluded), case-folded."""
        import re as _re
        found = []
        def toks(text):
            return [x for x in _re.split(r"[^0-9a-z]+", text.casefold()) if x]
        def walk(node, caller=False):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k not in cls.EXEMPT_KEYS:
                        found.extend(x for x in toks(k) if x.startswith(cls.BANNED))
                    walk(v, k in ("id", "factor"))
            elif isinstance(node, list):
                for v in node:
                    walk(v, caller)
            elif isinstance(node, str) and not caller:
                found.extend(x for x in toks(node) if x.startswith(cls.BANNED))
        walk(out)
        return found

    def test_scanner_catches_keys_and_values(self):
        for key in ("best_level", "Optimal_Setting", "RANKING", "winner-1", "robust.x", "preferred", "Improvement"):
            self.assertTrue(self.banned_in({key: 1}), key)
        self.assertTrue(self.banned_in({"a": "This is the Best level"}))
        self.assertTrue(self.banned_in({"a": ["x", {"b": "ranking_of_levels"}]}))
        self.assertEqual(self.banned_in({"id": "best", "factor": "ranking", "a": "plain text"}), [])   # caller text excluded
        self.assertEqual(self.banned_in({"robustness_certified": False}), [])                           # the one exempt key

    def test_no_banned_word_in_generated_output(self):
        for out in (go(packet()), go(packet("smaller")), go(single("nominal", ["1", "3"]))):
            self.assertEqual(self.banned_in(out), [])
        r = go(packet())
        self.assertEqual({k for k in r if any(x.startswith(self.BANNED) for x in __import__("re").split(r"[^0-9a-z]+", k.casefold()))},
                         set(self.EXEMPT_KEYS))
        self.assertIs(r["robustness_certified"], False)

    def test_exempt_key_and_value_pinned_in_every_output_and_no_robust_string(self):
        self.assertEqual(self.EXEMPT_KEYS, {"robustness_certified"})
        outs = [go(packet()), go(packet("smaller")), go(single("nominal", ["1", "3"])), go(single("larger", ["2"]))]
        for out in outs:
            self.assertIn("robustness_certified", out)
            self.assertIs(out["robustness_certified"], False)                       # key and constant value
            self.assertEqual([k for k in out if "robust" in k.casefold()], ["robustness_certified"])   # only that key stem
            def strings(node):
                if isinstance(node, dict):
                    for k, v in node.items():
                        if k in ("id", "factor"):
                            continue
                        yield from strings(v)
                elif isinstance(node, list):
                    for v in node:
                        yield from strings(v)
                elif isinstance(node, str):
                    yield node
            for text in strings(out):
                self.assertNotIn("robust", text.casefold())

    def test_banned_list_keeps_the_older_words(self):
        for word in ("highest", "select", "choose"):
            self.assertIn(word, self.BANNED)
            self.assertTrue(self.banned_in({"a": "pick the " + word + " one"}))
            self.assertTrue(self.banned_in({word + "ion_x": 1}))

    def test_array_note_and_no_catalogue_claim(self):
        r = go(packet())
        self.assertIn("declared array, not matched to any catalogue", r["array_note"])
        self.assertIn("declared array, not matched to any catalogue", r["boundary"])
        low = repr(r).lower()
        for w in ("l4", "l8", "l9", "taguchi array"):
            self.assertNotIn(w, low)

    def test_runs_sorted_deterministic_no_mutation(self):
        p = packet(); p["runs"].reverse()
        before = copy.deepcopy(p)
        a, b = go(p), go(p)
        self.assertEqual(a, b)
        self.assertEqual(p, before)
        self.assertEqual([x["id"] for x in a["runs"]], ["r1", "r2", "r3", "r4"])
        self.assertEqual(a["runs"][0]["levels"], [1, 1, 1])
        a["runs"][0]["levels"].append(9)
        self.assertEqual(p, before)

    def test_run_fields(self):
        r = go(packet())["runs"][0]
        self.assertEqual(r, {"id": "r1", "levels": [1, 1, 1], "response_count": 2, "signal_to_noise_db": "2.041200"})

    def test_flags_no_robustness_claims(self):
        r = go(packet())
        self.assertEqual(r["goal"], "larger")
        self.assertIs(r["robustness_certified"], False)
        self.assertIs(r["requires_engineer_review"], True)
        self.assertEqual(r["scope"], "declared_runs_array_and_sn_bookkeeping_only")
        self.assertIn("rounded", r["rounding"])

    def test_survivor_pins(self):
        self.assertEqual(sn("larger", ["1.5"]), "3.521825")           # short fraction padded on the right
        self.assertEqual(go(single("smaller", ["1"]))["goal"], "smaller")
        self.assertEqual(go(single("nominal", ["1", "2"]))["goal"], "nominal")
        rows = [[1, 1], [1, 1], [1, 2], [2, 1], [2, 2], [2, 2]]   # factors balanced, pair counts 2,1,1,2
        p = packet(factors=["A", "B"], runs=[run_rec("r%d" % (k + 1), rows[k], ["1"]) for k in range(6)])
        self.assertEqual(refusal(self, p), "TAGUCH1540:not_orthogonal")
        p = packet(factors=["A"], runs=[run_rec("a", [2], ["1"]), run_rec("b", [1], ["1"])])
        self.assertEqual(go(p)["factor_summaries"][0]["observed_levels"], [1, 2])


class Refusals(unittest.TestCase):
    def test_not_orthogonal_is_never_an_output_value(self):
        self.assertNotIn("not_orthogonal", repr(go(packet())))

    def check(self, p, code):
        self.assertEqual(refusal(self, p), "TAGUCH1540:" + code)

    def test_packet(self):
        for bad in (None, [], "x", 3):
            self.check(bad, "invalid_packet")
        p = packet(); p["extra"] = 1
        self.check(p, "unknown_fields:packet")
        p = packet(); del p["goal"]
        self.check(p, "unknown_fields:packet")

    def test_goal(self):
        for bad in ("Larger", "", None, 1, "larger ", "target", "x"):
            self.check(packet(goal=bad), "invalid_goal")

    def test_factor_count_and_text(self):
        names = ["f%d" % i for i in range(8)]
        go(packet(factors=names, runs=[run_rec("r", [1] * 8, ["1"])]))
        self.check(packet(factors=names + ["f8"], runs=[run_rec("r", [1] * 9, ["1"])]), "invalid_count:factors")
        self.check(packet(factors=[], runs=[run_rec("r", [], ["1"])]), "invalid_count:factors")
        self.check(packet(factors="AB"), "invalid_count:factors")
        self.check(packet(factors=["A", "A", "C"]), "duplicate_factor")
        go(packet(factors=["A" * 128, "B", "C"]))
        for bad in ("", " ", "a" * 129, None, 3, "a\tb", "a\x7fb"):
            self.check(packet(factors=[bad, "B", "C"]), "invalid_text:factor")

    def test_run_count(self):
        go(packet(runs=[run_rec("r%d" % i, [1, 1, 1], ["1"]) for i in range(64)]))
        self.check(packet(runs=[run_rec("r%d" % i, [1, 1, 1], ["1"]) for i in range(65)]), "invalid_count:runs")
        self.check(packet(runs=[]), "invalid_count:runs")
        self.check(packet(runs=(run_rec("a", [1, 1, 1], ["1"]),)), "invalid_count:runs")

    def test_run_records(self):
        self.check(packet(runs=["x"]), "invalid_record:runs")
        r = run_rec("a", [1, 1, 1], ["1"]); r["extra"] = 1
        self.check(packet(runs=[r]), "invalid_fields:runs")
        self.check(packet(runs=[{"id": "a", "levels": [1, 1, 1]}]), "invalid_fields:runs")
        self.check(packet(runs=[run_rec("a", [1, 1, 1], ["1"]), run_rec("a", [1, 1, 2], ["1"])]), "duplicate_id")
        for bad in ("", " ", "a" * 129, None, 3, "a\nb"):
            self.check(packet(runs=[run_rec(bad, [1, 1, 1], ["1"])]), "invalid_text:id")

    def test_levels(self):
        go(packet(runs=[run_rec("a", [9, 9, 9], ["1"])]))
        for bad in ([1, 1], [1, 1, 1, 1], [0, 1, 1], [10, 1, 1], [1, 1, True], [1, 1, 1.0], [1, 1, "1"], "111", None, (1, 1, 1)):
            self.check(packet(runs=[run_rec("a", bad, ["1"])]), "invalid_levels")

    def test_responses(self):
        go(packet(runs=[run_rec("a", [1, 1, 1], ["1"] * 16)]))
        self.check(packet(runs=[run_rec("a", [1, 1, 1], ["1"] * 17)]), "invalid_count:responses")
        self.check(packet(runs=[run_rec("a", [1, 1, 1], [])]), "invalid_count:responses")
        self.check(packet(runs=[run_rec("a", [1, 1, 1], "12")]), "invalid_count:responses")
        for bad in ("+1", "1e3", "1.", ".5", "", " 1", "1 ", "\uff11", 1, 1.0, None, True, "nan", "Infinity", "--1", "1.2.3", "01", "00", "-", "-.5", "-01", "00.5", "0x1", "\n1", "1\n"):
            self.check(packet(runs=[run_rec("a", [1, 1, 1], [bad])]), "invalid_number")
        for bad in ("1" * 81, "0." + "0" * 79, "1" * 100):
            self.check(packet(runs=[run_rec("a", [1, 1, 1], [bad])]), "number_too_long")
        for bad in ("0." + "0" * 78, "11111111111.2" + "3" * 53, "0." + "1" * 65):
            self.check(packet(runs=[run_rec("a", [1, 1, 1], [bad])]), "number_precision")
        for bad in ("1" * 13, "1" * 64, "-" + "9" * 13):
            self.check(packet(runs=[run_rec("a", [1, 1, 1], [bad])]), "number_range")
        go(single("smaller", ["999999999999.999999", "-999999999999.999999"]))
        go(single("smaller", ["1" * 11 + "." + "1" * 53, "1." + "1" * 63]))   # 64 significant digits
        go(single("smaller", ["0." + "0" * 6 + "1" * 58, "2"]))          # 58 significant, 64 fraction digits
        self.assertEqual(sn("smaller", ["123456789012", "1.0000001"]), sn("smaller", ["123456789012", "1.0000001"]))

    def test_char_cap_80_n_and_n_plus_1(self):
        self.check(single("smaller", ["1" * 80, "2"]), "number_precision")   # 80 characters: past the cap check
        self.check(single("smaller", ["1" * 64, "2"]), "number_range")       # 64 significant digits, over 1e12
        self.check(single("smaller", ["1" * 65, "2"]), "number_precision")
        self.check(single("smaller", ["1" * 81, "2"]), "number_too_long")    # 81: refused by length first
        self.check(single("smaller", ["0." + "0" * 78, "2"]), "number_precision")
        self.check(single("smaller", ["0." + "0" * 79, "2"]), "number_too_long")
        self.check(single("smaller", ["0" * 81, "2"]), "number_too_long")    # length wins over shape

    def test_no_80_character_valid_shape_is_accepted(self):
        """Witness search: for every sign, whole-digit count and fraction-digit count, the least-significant candidate."""
        best, at80 = 0, set()
        for sign in ("", "-"):
            for w in range(1, 81):
                whole = "0" if w == 1 else "1" + "0" * (w - 1)
                for f in range(0, 81):
                    text = sign + whole + ("." + "0" * f if f else "")
                    if len(text) > 80:
                        continue
                    try:
                        m._value(text)
                        best = max(best, len(text))
                    except ValueError as exc:
                        if len(text) == 80:
                            at80.add(str(exc))
        self.assertEqual(best, 67)                       # "-0." plus 64 zeros: sign, 0, point, 64 fraction digits
        self.assertEqual(at80, {"TAGUCH1540:number_precision"})
        for bad in ("0" * 79 + "1", "0" * 80, "0001", "0" * 78 + ".1", "00.5"):
            with self.assertRaises(ValueError) as cm:
                m._value(bad)
            self.assertIn(str(cm.exception), ("TAGUCH1540:invalid_number", "TAGUCH1540:number_precision"))
        for bad in ("0001", "0" * 79 + "1", "0" * 80):
            with self.assertRaises(ValueError) as cm:
                m._value(bad)
            self.assertEqual(str(cm.exception), "TAGUCH1540:invalid_number")      # shape, no padding default

    WITNESSES = (
        ("-0." + "0" * 63 + "1", 67, "PASS"), ("999999999999." + "9" * 52, 65, "PASS"), ("1000000000000." + "0" * 51, 65, "PASS"),
        ("999999999999." + "9" * 53, 66, "number_precision"), ("0." + "0" * 64 + "1", 67, "number_precision"),
        ("1." + "0" * 78, 80, "number_precision"), ("1." + "0" * 79, 81, "number_too_long"), ("0" * 81, 81, "number_too_long"),
        ("0" * 80, 80, "invalid_number"), ("1000000000000.0000000001", 24, "number_range"),
    )

    def test_counted_witnesses(self):
        for text, length, want in self.WITNESSES:
            self.assertEqual(len(text), length)
            if want == "PASS":
                m._value(text)
                continue
            with self.assertRaises(ValueError) as cm:
                m._value(text)
            self.assertEqual(str(cm.exception), "TAGUCH1540:" + want, text[:16])

    def test_every_length_68_to_80_is_precision_and_81_up_is_too_long(self):
        seen = {}
        for sign in ("", "-"):
            for w in range(1, 81):
                for f in range(0, 81):
                    for whole in (("0" if w == 1 else "1" + "0" * (w - 1)), "9" * w, "1" * w):
                        for frac in ("0" * f, "9" * f):
                            text = sign + whole + ("." + frac if f else "")
                            if not 65 <= len(text) <= 85:
                                continue
                            try:
                                m._value(text)
                                code = "PASS"
                            except ValueError as exc:
                                code = str(exc).split(":", 1)[1]
                            seen.setdefault(len(text), set()).add(code)
        for length in range(68, 81):
            self.assertEqual(seen[length], {"number_precision"}, length)
        for length in range(81, 86):
            self.assertEqual(seen[length], {"number_too_long"}, length)
        self.assertIn("PASS", seen[67])
        self.assertNotIn("PASS", seen[68])

    def test_range_is_exact_and_independent_of_the_ambient_decimal_context(self):
        import decimal
        edge_ok, edge_bad = "1000000000000." + "0" * 51, "1000000000000.0000000001"
        for prec, rounding in ((1, decimal.ROUND_DOWN), (2, decimal.ROUND_UP), (100, decimal.ROUND_HALF_UP)):
            with decimal.localcontext() as ctx:
                ctx.prec, ctx.rounding = prec, rounding
                m._value(edge_ok)
                m._value("-1000000000000")
                with self.assertRaises(ValueError) as cm:
                    m._value(edge_bad)
                self.assertEqual(str(cm.exception), "TAGUCH1540:number_range")

    def test_contract_doc_has_no_stale_api_or_ban_lines(self):
        doc = (pathlib.Path(__file__).resolve().parents[2] / "docs/M20_TAGUCHI_METHODS1540_CONTRACT.md").read_text().split("\n")
        for line in doc:
            low = line.casefold()
            self.assertNotIn("highest-mean", low)
            self.assertNotIn("at most 12 integer", low)
            self.assertNotIn("dropped in the test", low)
            self.assertNotIn("orthogonal_pairwise` is true", low)
            if "highest" in low or "selection" in low:
                self.assertTrue("banned words" in low or "select` prefix" in low or "(a `select`" in low, line[:80])

    def test_range_exact_with_traps_cleared_and_all_ambient_contexts(self):
        import decimal
        for prec in (1, 2, 100):
            for rounding in (decimal.ROUND_DOWN, decimal.ROUND_UP, decimal.ROUND_HALF_UP):
                for clear in (False, True):
                    with decimal.localcontext() as ctx:
                        ctx.prec, ctx.rounding = prec, rounding
                        if clear:
                            ctx.clear_traps()
                            ctx.clear_flags()
                        self.assertEqual(m._value("1000000000000"), 10 ** 12)
                        self.assertEqual(m._value("-1000000000000.0"), -10 ** 12)
                        with self.assertRaises(ValueError) as cm:
                            m._value("1000000000000.0000000001")
                        self.assertEqual(str(cm.exception), "TAGUCH1540:number_range")
                        with self.assertRaises(ValueError) as cm:
                            m._value("-1000000000000.0000000001")
                        self.assertEqual(str(cm.exception), "TAGUCH1540:number_range")

    def test_range_doc_line_is_exact(self):
        doc = (pathlib.Path(__file__).resolve().parents[2] / "docs/M20_TAGUCHI_METHODS1540_CONTRACT.md").read_text()
        self.assertIn("range is an exact rational compare, independent of the decimal context", doc)

    def test_number_grammar_legal_and_illegal(self):
        from fractions import Fraction
        for text, want in (("0", 0), ("-0", 0), ("0.0", 0), ("0.5", Fraction(1, 2)), ("10", 10), ("-3.25", Fraction(-13, 4)),
                           ("100", 100), ("1.50", Fraction(3, 2))):
            self.assertEqual(m._value(text), want)
        for bad in ("01", "00", ".5", "5.", "-", "+1", "", "1e3", "1E3", "1_0", " 1", "1 ", "\uff11", "0 .5", "-.5", "1.2.3", "1\uff11", "0.\uff11", "\u0663", "1\u0663", "1.\u0663"):
            with self.assertRaises(ValueError) as cm:
                m._value(bad)
            self.assertEqual(str(cm.exception), "TAGUCH1540:invalid_number", repr(bad))
        for bad in (1, 1.0, None, True, b"1", ["1"]):
            with self.assertRaises(ValueError) as cm:
                m._value(bad)
            self.assertEqual(str(cm.exception), "TAGUCH1540:invalid_number")

    def test_bound_1e12_inclusive(self):
        self.assertEqual(m._value("1000000000000"), 10 ** 12)
        self.assertEqual(m._value("-1000000000000"), -10 ** 12)
        self.assertEqual(m._value("1000000000000.0"), 10 ** 12)
        self.assertEqual(m._value("999999999999.9999999999"), __import__("fractions").Fraction("999999999999.9999999999"))
        for bad in ("1000000000000.0000000001", "-1000000000000.0000000001", "1000000000001", "10000000000000"):
            with self.assertRaises(ValueError) as cm:
                m._value(bad)
            self.assertEqual(str(cm.exception), "TAGUCH1540:number_range")

    def test_check_order_long_then_shape_then_precision_then_range(self):
        for text, code in (("x" * 81, "number_too_long"), ("0" * 79 + "1", "invalid_number"),
                           ("1" * 79, "number_precision"), ("1" * 64, "number_range"), ("0." + "1" * 65, "number_precision"),
                           ("1" * 13 + "." + "0" * 65, "number_precision"), ("1" * 13, "number_range")):
            with self.assertRaises(ValueError) as cm:
                m._value(text)
            self.assertEqual(str(cm.exception), "TAGUCH1540:" + code, text[:20])

    def test_error_codes_are_flat_and_never_echo_the_value(self):
        for bad in ("SECRET1", "9" * 13, "0." + "7" * 70, "7" * 90):
            with self.assertRaises(ValueError) as cm:
                m._value(bad)
            self.assertNotIn("7", str(cm.exception).replace("TAGUCH1540", ""))
            self.assertNotIn("SECRET", str(cm.exception))
            self.assertNotIn("invalid_number:", str(cm.exception))

    def test_level_mean_decimal_signal_is_arithmetic_refusal(self):
        import decimal
        class Huge(decimal.Context):
            calls = 0
            def divide(self, a, b):
                Huge.calls += 1
                return decimal.Decimal("1E+80") if Huge.calls == 2 else super().divide(a, b)   # call 1: log ratio, call 2: level mean
        old = m._CTX
        m._CTX = Huge(prec=60, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
                      traps=[decimal.Overflow, decimal.Underflow, decimal.InvalidOperation, decimal.DivisionByZero])
        try:
            self.assertEqual(refusal(self, single("larger", ["2"])), "TAGUCH1540:arithmetic")
        finally:
            m._CTX = old
        self.assertEqual(go(single("larger", ["2"]))["runs"][0]["signal_to_noise_db"], "6.020600")

    def test_fraction_digits_cap_64(self):
        go(single("smaller", ["0." + "1" * 64, "2"]))
        for bad in ("0." + "0" * 64 + "1", "1." + "0" * 65):
            self.check(single("smaller", [bad, "2"]), "number_precision")
        go(single("smaller", ["1." + "0" * 63, "2"]))

    def test_level_mean_tie_rounds_half_even(self):
        p = packet(factors=["A"], runs=[run_rec("a", [1], ["1", "2"]), run_rec("b", [1], ["3"])])
        # (2.041200 + 9.542425) / 2 = 5.7918125 exactly: half-even gives 5.791812, half-up would give 5.791813
        self.assertEqual(go(p)["factor_summaries"][0]["level_mean_sn"], {"1": "5.791812"})

    def test_context_is_explicit_and_input_parsed_exactly(self):
        c = m._CTX
        self.assertEqual((c.prec, c.rounding, c.Emin, c.Emax), (60, "ROUND_HALF_EVEN", -999999, 999999))
        for flag in ("Overflow", "Underflow", "InvalidOperation", "DivisionByZero"):
            self.assertTrue(c.traps[getattr(__import__("decimal"), flag)])
        from fractions import Fraction
        for text in ("1" * 12 + "." + "1" * 52, "-" + "9" * 12 + "." + "9" * 52, "0." + "1234567890" * 6 + "1234", "123456789012.1234567890123456789012345678901234567890123456789012"):
            self.assertEqual(m._value(text), Fraction(text))                      # 64 significant digits parsed unchanged
            self.assertEqual(Fraction(m._value(text).numerator, m._value(text).denominator), Fraction(text))
        import decimal
        with decimal.localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(m._value("1" * 12 + "." + "1" * 52), Fraction("1" * 12 + "." + "1" * 52))

    def test_caps_checked_before_any_parse(self):
        junk = ["\x00"] * 17
        bad = packet(goal="larger", factors=["\x00", "\x00", "\x00"], runs=[run_rec("\x00", [99, 99, 99], junk)])
        self.check(bad, "invalid_count:responses")
        runs = [run_rec("\x00", [99], ["x"]) for _ in range(65)]
        self.check(packet(factors=["\x00"], runs=runs), "invalid_count:runs")
        self.check(packet(factors=["\x00"] * 9, runs=[run_rec("a", [1], ["1"])]), "invalid_count:factors")
        self.check(packet(runs=[run_rec("a", [1, 1, 1], [])]), "invalid_count:responses")

    def test_undefined_sn_cases(self):
        for g, r in (("larger", ["0"]), ("larger", ["-1"]), ("smaller", ["0"]), ("nominal", ["1"]), ("nominal", ["2", "2"]),
                     ("nominal", ["-1", "1"])):
            self.check(single(g, r), "undefined_sn")

    def test_ambient_decimal_context_does_not_change_results(self):
        import decimal
        base = go(packet())
        for prec, rounding in ((2, decimal.ROUND_DOWN), (100, decimal.ROUND_HALF_UP), (1, decimal.ROUND_UP)):
            with decimal.localcontext() as ctx:
                ctx.prec, ctx.rounding = prec, rounding
                self.assertEqual(go(packet()), base)
                self.assertEqual(sn("nominal", ["1", "2", "3"]), "7.781513")
                self.assertEqual(go(single("larger", ["1.5"]))["runs"][0]["signal_to_noise_db"], "3.521825")

    def test_reason_never_echoes_input(self):
        secret = "SECRET-VALUE-XYZ"
        for p in (packet(goal=secret), packet(factors=[secret * 20, "B", "C"]), packet(runs=[run_rec(secret * 20, [1, 1, 1], ["1"])]),
                  packet(runs=[run_rec("a", [1, 1, 1], [secret])])):
            self.assertNotIn(secret, refusal(self, p))

    def test_surface_and_offline(self):
        self.assertEqual([n for n in dir(m) if not n.startswith("_") and callable(getattr(m, n))
                          and getattr(getattr(m, n), "__module__", None) == "taguchi_methods1540"], ["analyze_taguchi_runs"])
        src = _P.read_text()
        for banned in ("import socket", "import requests", "urllib", "subprocess", "import os", "open(", "float(", "engineering_1510_1559", "math.log"):
            self.assertNotIn(banned, src)


class UnicodeText(unittest.TestCase):
    HIDDEN = ("\x85", "\u2028", "\u2029", "\u202e", "\u200b", "\ufeff", "\x7f", "\u200f", "\u202a", "\u2066", "\u2069", "\u200c", "\x00", "\x1f", "\u200e", "\u202d", "\u2067", "\u2068")
    ALLOWED = ("a b", "\u00e9", "\u00b5m", "\u4e2d\u6587", "\u00a0x", "\u2010x", "\u200a" + "x")

    def test_hidden_refused_on_factor_and_id(self):
        for ch in self.HIDDEN:
            self.assertEqual(refusal(self, packet(factors=["a%sb" % ch, "B", "C"])), "TAGUCH1540:invalid_text:factor")
            self.assertEqual(refusal(self, packet(runs=[run_rec("a%sb" % ch, [1, 1, 1], ["1"])])), "TAGUCH1540:invalid_text:id")
            self.assertNotIn(ch, refusal(self, packet(factors=[ch, "B", "C"])))

    def test_printable_non_ascii_and_spaces_allowed(self):
        for text in self.ALLOWED:
            r = go(packet(factors=[text, "B", "C"], runs=[run_rec(text, [1, 1, 1], ["1"])]))
            self.assertEqual(r["factor_summaries"][0]["factor"], text)



class CapFirst(unittest.TestCase):
    """The first operation after the isinstance check is the raw length check (no strip, regex or scan before it)."""
    BIG = 10 * 1024 * 1024

    def _peak(self, fn):
        import tracemalloc
        tracemalloc.start()
        try:
            fn()
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    def test_text_raw_cap_n_and_n_plus_1(self):
        self.assertEqual(m._text("a" * m.MAX_TEXT, "id"), "a" * m.MAX_TEXT)
        for bad in ("a" * (m.MAX_TEXT + 1), " " + "a" * m.MAX_TEXT, "a" * m.MAX_TEXT + " "):   # raw length, not stripped length
            with self.assertRaises(ValueError) as cm:
                m._text(bad, "id")
            self.assertEqual(str(cm.exception), "TAGUCH1540:invalid_text:id")

    def test_text_10mb_refused_without_strip_allocation(self):
        big = " a" + "b" * self.BIG       # strip() of this would allocate about 10 MB
        def call():
            with self.assertRaises(ValueError) as cm:
                m._text(big, "id")
            self.assertEqual(str(cm.exception), "TAGUCH1540:invalid_text:id")
        self.assertLess(self._peak(call), 100000)

    def test_text_oversize_refused_before_any_scan(self):
        def boom(char):
            raise AssertionError("scanned an oversize value")
        old = m._hidden
        m._hidden = boom
        try:
            with self.assertRaises(ValueError):
                m._text("a" * (m.MAX_TEXT + 1), "id")
        finally:
            m._hidden = old

    def test_text_oversize_through_public_entry(self):
        big = " a" + "b" * self.BIG
        self.assertEqual(refusal(self, packet(factors=[big, "B", "C"])), "TAGUCH1540:invalid_text:factor")
        p = packet()
        p["runs"][0]["id"] = big
        self.assertEqual(refusal(self, p), "TAGUCH1540:invalid_text:id")

    def test_number_cap_n_and_n_plus_1_and_10mb_before_regex(self):
        class Spy:
            def fullmatch(self, text):
                raise AssertionError("regex ran on an oversize value")
        old = m._NUMBER
        m._NUMBER = Spy()
        try:
            for bad in ("1" * (m.MAX_NUMBER_CHARS + 1), "1" * self.BIG, " " + "1" * m.MAX_NUMBER_CHARS):
                with self.assertRaises(ValueError) as cm:
                    m._value(bad)
                self.assertEqual(str(cm.exception), "TAGUCH1540:number_too_long")
        finally:
            m._NUMBER = old
        with self.assertRaises(ValueError) as cm:      # N characters pass the cap check and reach the regex and precision check
            m._value("1" * m.MAX_NUMBER_CHARS)
        self.assertEqual(str(cm.exception), "TAGUCH1540:number_precision")


if __name__ == "__main__":
    unittest.main()
