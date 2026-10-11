"""[1265] Due Process: tests for due_process1265. Hermetic, stdlib unittest, no network, no clock."""
import ast
import copy
import importlib.util
import json
import pathlib
import re
import sys
import unicodedata
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_P = _ROOT / "backend/app/modules/m20_general_cognitive_worker/due_process1265.py"
_DOC = _ROOT / "docs/M20_DUE_PROCESS1265_CONTRACT.md"
_spec = importlib.util.spec_from_file_location("due_process1265_mod", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["due_process1265_mod"] = m
_spec.loader.exec_module(m)

STANDING = ("Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, "
            "currency, citations, facts, duties, deadlines and strategy before use.")


def req(**over):
    r = {
        "jurisdiction": "Example Jurisdiction",
        "as_of": "2026-01-31",
        "sources": [{"source_id": "S1", "label": "Supplied record A"}, {"source_id": "S2", "label": "Supplied record B"}],
        "protected_interest": {"description": "Declared interest in a supplied benefit", "source_ids": ["S1"]},
        "deprivation": {"description": "Declared termination of the benefit", "date": "2026-01-10", "source_ids": ["S1"]},
        "notice": {"given": True, "date": "2026-01-05", "content_summary": "Declared written notice", "source_ids": ["S2"]},
        "hearing": {"held": True, "date": "2026-01-08", "decision_maker": "Declared reviewer role", "source_ids": ["S2"]},
        "balancing_factors": [
            {"label": "private side", "statement": "Declared private-side statement", "source_ids": ["S1"]},
            {"label": "public side", "statement": "Declared public-side statement", "source_ids": ["S2"]},
        ],
    }
    r.update(over)
    return r


def err(f, *a, **k):
    try:
        f(*a, **k)
    except m.DueProcessError as e:
        return str(e)
    raise AssertionError("no DueProcessError raised")


def codes(out, element=None):
    return sorted(g["code"] for g in out["gaps"] if element is None or g["element"] == element)


class Shape(unittest.TestCase):
    def test_exports_and_constants(self):
        self.assertTrue(issubclass(m.DueProcessError, ValueError))
        self.assertEqual(m.PREFIX, "DUEPRO1265:")
        self.assertEqual(m.STANDING_BOUNDARY, STANDING)

    def test_full_request_has_no_gaps_and_fixed_honesty_fields(self):
        o = m.analyze_due_process(req())
        self.assertEqual(o["gaps"], [])
        self.assertIs(o["adequacy_judged"], False)
        self.assertIsNone(o["legal_conclusion"])
        self.assertIs(o["requires_licensed_counsel"], True)
        self.assertIs(o["filing_or_external_effect"], False)
        self.assertIs(o["authority_independently_verified"], False)
        self.assertEqual(o["disclaimer"], STANDING)
        self.assertEqual(o["scope"], m.SCOPE)
        self.assertEqual(o["jurisdiction"], "Example Jurisdiction")
        self.assertEqual(o["as_of"], "2026-01-31")
        self.assertEqual(set(o["elements"]), {"protected_interest", "deprivation", "notice", "hearing", "balancing_factors"})
        for k, v in o["elements"].items():
            self.assertEqual(v["status"], "DECLARED_SOURCED", k)
        self.assertEqual(o["elements"]["balancing_factors"]["count"], 2)

    def test_sequence_is_mechanical_dates_only(self):
        s = m.analyze_due_process(req())["sequence"]
        self.assertEqual(s, {"notice_vs_deprivation": "before", "hearing_vs_deprivation": "before",
                             "notice_vs_hearing": "before"})

    def test_deterministic_and_input_not_mutated_or_aliased(self):
        r = req()
        snap = copy.deepcopy(r)
        a = m.analyze_due_process(r)
        self.assertEqual(r, snap)
        self.assertEqual(a, m.analyze_due_process(copy.deepcopy(r)))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(m.analyze_due_process(r), sort_keys=True))
        a["elements"]["notice"]["status"] = "X"
        a["gaps"].append(1)
        self.assertEqual(m.analyze_due_process(r)["elements"]["notice"]["status"], "DECLARED_SOURCED")
        self.assertEqual(m.analyze_due_process(r)["gaps"], [])

    def test_declared_text_passes_through_untouched(self):
        o = m.analyze_due_process(req())
        self.assertEqual(o["elements"]["protected_interest"]["description"], "Declared interest in a supplied benefit")
        self.assertEqual(o["elements"]["hearing"]["decision_maker"], "Declared reviewer role")
        self.assertEqual(o["elements"]["balancing_factors"]["items"][1]["statement"], "Declared public-side statement")


class Sequence(unittest.TestCase):
    def seq(self, nd, hd, dd):
        r = req()
        r["notice"]["date"] = nd
        r["hearing"]["date"] = hd
        r["deprivation"]["date"] = dd
        return m.analyze_due_process(r)["sequence"]

    def test_all_orderings(self):
        s = self.seq("2026-01-12", "2026-01-15", "2026-01-10")
        self.assertEqual((s["notice_vs_deprivation"], s["hearing_vs_deprivation"], s["notice_vs_hearing"]),
                         ("after", "after", "before"))
        s = self.seq("2026-01-10", "2026-01-10", "2026-01-10")
        self.assertEqual((s["notice_vs_deprivation"], s["hearing_vs_deprivation"], s["notice_vs_hearing"]),
                         ("same_day", "same_day", "same_day"))
        s = self.seq("2026-01-20", "2026-01-11", "2026-01-15")
        self.assertEqual((s["notice_vs_deprivation"], s["hearing_vs_deprivation"], s["notice_vs_hearing"]),
                         ("after", "before", "after"))

    def test_hearing_before_notice_is_reported_not_judged(self):
        o = m.analyze_due_process(req(notice={"given": True, "date": "2026-01-09", "source_ids": ["S2"]},
                                      hearing={"held": True, "date": "2026-01-02", "source_ids": ["S2"]}))
        self.assertEqual(o["sequence"]["notice_vs_hearing"], "after")
        self.assertEqual(o["gaps"], [])

    def test_not_comparable_when_a_date_is_missing_or_not_given(self):
        r = req()
        del r["notice"]["date"]
        o = m.analyze_due_process(r)
        self.assertEqual(o["sequence"]["notice_vs_deprivation"], "not_comparable")
        self.assertEqual(o["sequence"]["notice_vs_hearing"], "not_comparable")
        self.assertEqual(o["sequence"]["hearing_vs_deprivation"], "before")
        self.assertEqual(codes(o, "notice"), ["DATE_UNDECLARED"])
        r = req(notice={"given": False, "source_ids": ["S2"]})
        o = m.analyze_due_process(r)
        self.assertEqual(o["sequence"]["notice_vs_deprivation"], "not_comparable")
        self.assertEqual(codes(o, "notice"), ["NOTICE_DECLARED_NOT_GIVEN"])

    def test_hearing_not_held_and_deprivation_without_date(self):
        o = m.analyze_due_process(req(hearing={"held": False, "source_ids": ["S2"]}))
        self.assertEqual(codes(o, "hearing"), ["HEARING_DECLARED_NOT_HELD"])
        self.assertEqual(o["sequence"]["hearing_vs_deprivation"], "not_comparable")
        r = req()
        del r["deprivation"]["date"]
        o = m.analyze_due_process(r)
        self.assertEqual(codes(o, "deprivation"), ["DATE_UNDECLARED"])
        self.assertEqual(o["sequence"], {"notice_vs_deprivation": "not_comparable",
                                         "hearing_vs_deprivation": "not_comparable", "notice_vs_hearing": "before"})


class Gaps(unittest.TestCase):
    def test_each_element_not_declared(self):
        for k in ("protected_interest", "deprivation", "notice", "hearing", "balancing_factors"):
            r = req()
            del r[k]
            o = m.analyze_due_process(r)
            self.assertEqual(o["elements"][k]["status"], "NOT_DECLARED", k)
            self.assertEqual(codes(o, k), ["ELEMENT_NOT_DECLARED"], k)
            self.assertEqual([g["element"] for g in o["gaps"]], [k])

    def test_empty_balancing_list_is_not_declared(self):
        o = m.analyze_due_process(req(balancing_factors=[]))
        self.assertEqual(o["elements"]["balancing_factors"]["status"], "NOT_DECLARED")
        self.assertEqual(o["elements"]["balancing_factors"]["count"], 0)
        self.assertEqual(codes(o, "balancing_factors"), ["ELEMENT_NOT_DECLARED"])

    def test_unsourced_element_and_factor(self):
        r = req()
        r["protected_interest"]["source_ids"] = []
        del r["hearing"]["source_ids"]
        r["balancing_factors"][1]["source_ids"] = []
        o = m.analyze_due_process(r)
        self.assertEqual(o["elements"]["protected_interest"]["status"], "DECLARED_UNSOURCED")
        self.assertEqual(o["elements"]["hearing"]["status"], "DECLARED_UNSOURCED")
        self.assertEqual(o["elements"]["balancing_factors"]["status"], "DECLARED_UNSOURCED")
        self.assertEqual(o["elements"]["balancing_factors"]["items"][0]["status"], "DECLARED_SOURCED")
        self.assertEqual(o["elements"]["balancing_factors"]["items"][1]["status"], "DECLARED_UNSOURCED")
        got = [(g["element"], g["code"], g.get("index")) for g in o["gaps"]]
        self.assertEqual(got, [("protected_interest", "UNSOURCED", None), ("hearing", "UNSOURCED", None),
                               ("balancing_factors", "UNSOURCED", 1)])

    def test_unknown_source_id_is_a_gap_not_a_refusal(self):
        r = req()
        r["notice"]["source_ids"] = ["S2", "S9"]
        o = m.analyze_due_process(r)
        self.assertEqual(o["elements"]["notice"]["status"], "DECLARED_UNSOURCED")
        g = [g for g in o["gaps"] if g["code"] == "UNKNOWN_SOURCE_ID"]
        self.assertEqual(len(g), 1)
        self.assertEqual((g[0]["element"], g[0]["source_id"]), ("notice", "S9"))

    def test_date_after_as_of(self):
        r = req()
        r["deprivation"]["date"] = "2026-02-01"
        o = m.analyze_due_process(r)
        self.assertEqual(codes(o, "deprivation"), ["DATE_AFTER_AS_OF"])
        r["deprivation"]["date"] = "2026-01-31"           # equal is fine
        self.assertEqual(m.analyze_due_process(r)["gaps"], [])
        r = req()
        r["hearing"]["date"] = "2027-01-01"
        self.assertEqual(codes(m.analyze_due_process(r), "hearing"), ["DATE_AFTER_AS_OF"])
        r = req()
        r["notice"]["date"] = "2026-03-01"
        self.assertEqual(codes(m.analyze_due_process(r), "notice"), ["DATE_AFTER_AS_OF"])

    def test_gap_order_is_element_order(self):
        o = m.analyze_due_process({k: v for k, v in req().items() if k not in ("hearing", "protected_interest")})
        self.assertEqual([g["element"] for g in o["gaps"]], ["protected_interest", "hearing"])


    def test_hearing_held_without_date_is_a_gap(self):
        r = req()
        del r["hearing"]["date"]
        o = m.analyze_due_process(r)
        self.assertEqual(codes(o, "hearing"), ["DATE_UNDECLARED"])
        self.assertEqual(codes(o, "notice"), [])
        self.assertEqual(o["sequence"]["hearing_vs_deprivation"], "not_comparable")
        self.assertEqual(o["sequence"]["notice_vs_hearing"], "not_comparable")

    def test_summary_counts(self):
        o = m.analyze_due_process(req())
        self.assertEqual(o["summary"], {"elements_declared": 5, "gap_count": 0})
        o = m.analyze_due_process({k: v for k, v in req().items() if k not in ("hearing", "notice")})
        self.assertEqual(o["summary"], {"elements_declared": 3, "gap_count": 2})
        o = m.analyze_due_process({k: v for k, v in req().items() if k in ("jurisdiction", "as_of", "sources")})
        self.assertEqual(o["summary"], {"elements_declared": 0, "gap_count": 5})


class Refusals(unittest.TestCase):
    def run_(self, r):
        return m.analyze_due_process(r)

    def test_request_shape(self):
        self.assertEqual(err(self.run_, []), "DUEPRO1265:BAD_TYPE:request")
        self.assertEqual(err(self.run_, None), "DUEPRO1265:BAD_TYPE:request")
        r = req(); r["extra"] = 1
        self.assertEqual(err(self.run_, r), "DUEPRO1265:UNKNOWN_KEY:request")
        for k in ("jurisdiction", "as_of", "sources"):
            r = req(); del r[k]
            self.assertEqual(err(self.run_, r), "DUEPRO1265:MISSING:" + k)

    def test_text_rules(self):
        for bad in ("", "   ", 5, None, True, "a\nb", "a\x00b", "a\u202eb", "a\u200bb", "x" * 501):
            self.assertEqual(err(self.run_, req(jurisdiction=bad)), "DUEPRO1265:BAD_TEXT:jurisdiction", repr(bad)[:20])
        self.assertEqual(m.analyze_due_process(req(jurisdiction="x" * 500))["jurisdiction"], "x" * 500)
        r = req(); r["protected_interest"]["description"] = "a\nb"
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TEXT:protected_interest.description")
        r = req(); r["notice"]["content_summary"] = ""
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TEXT:notice.content_summary")
        r = req(); r["hearing"]["decision_maker"] = 3
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TEXT:hearing.decision_maker")
        r = req(); r["balancing_factors"][1]["label"] = " "
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TEXT:balancing_factors[1].label")
        r = req(); r["balancing_factors"][0]["statement"] = None
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TEXT:balancing_factors[0].statement")

    def test_dates(self):
        for bad in ("2026-1-31", "20260131", "2026-02-30", "2026-13-01", "2026-01-31T00:00", 20260131, None, True, "٢٠٢٦-٠١-٣١"):
            self.assertEqual(err(self.run_, req(as_of=bad)), "DUEPRO1265:BAD_DATE:as_of", repr(bad))
        r = req(); r["deprivation"]["date"] = "tomorrow"
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_DATE:deprivation.date")
        r = req(); r["notice"]["date"] = "2026-02-30"
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_DATE:notice.date")
        r = req(); r["hearing"]["date"] = 5
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_DATE:hearing.date")

    def test_sources(self):
        self.assertEqual(err(self.run_, req(sources="x")), "DUEPRO1265:BAD_TYPE:sources")
        self.assertEqual(err(self.run_, req(sources=[1])), "DUEPRO1265:BAD_TYPE:sources[0]")
        self.assertEqual(err(self.run_, req(sources=[{"source_id": "A"}])), "DUEPRO1265:MISSING:sources[0].label")
        self.assertEqual(err(self.run_, req(sources=[{"label": "A"}])), "DUEPRO1265:MISSING:sources[0].source_id")
        self.assertEqual(err(self.run_, req(sources=[{"source_id": "A", "label": "x", "url": "u"}])),
                         "DUEPRO1265:UNKNOWN_KEY:sources[0]")
        self.assertEqual(err(self.run_, req(sources=[{"source_id": "", "label": "x"}])), "DUEPRO1265:BAD_TEXT:sources[0].source_id")
        self.assertEqual(err(self.run_, req(sources=[{"source_id": "A", "label": "x"}, {"source_id": "A", "label": "y"}])),
                         "DUEPRO1265:DUPLICATE_SOURCE:sources[1].source_id")
        self.assertEqual(err(self.run_, req(sources=[{"source_id": "S%d" % i, "label": "x"} for i in range(65)])),
                         "DUEPRO1265:TOO_MANY:sources")
        ok = m.analyze_due_process(req(sources=[{"source_id": "S%d" % i, "label": "x"} for i in range(64)]))
        self.assertEqual(len(ok["elements"]), 5)

    def test_source_ids_field(self):
        r = req(); r["notice"]["source_ids"] = "S1"
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TYPE:notice.source_ids")
        r = req(); r["notice"]["source_ids"] = [1]
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TEXT:notice.source_ids[0]")
        r = req(); r["notice"]["source_ids"] = ["S1"] * 21
        self.assertEqual(err(self.run_, r), "DUEPRO1265:TOO_MANY:notice.source_ids")
        r = req(); r["notice"]["source_ids"] = ["S1"] * 20
        self.assertEqual(codes(m.analyze_due_process(r)), [])

    def test_element_shapes_and_unknown_keys(self):
        for k in ("protected_interest", "deprivation", "notice", "hearing"):
            self.assertEqual(err(self.run_, req(**{k: []})), "DUEPRO1265:BAD_TYPE:" + k)
            self.assertEqual(err(self.run_, req(**{k: None})), "DUEPRO1265:BAD_TYPE:" + k)
            r = req(); r[k]["zzz"] = 1
            self.assertEqual(err(self.run_, r), "DUEPRO1265:UNKNOWN_KEY:" + k)
        r = req(); del r["protected_interest"]["description"]
        self.assertEqual(err(self.run_, r), "DUEPRO1265:MISSING:protected_interest.description")
        r = req(); del r["deprivation"]["description"]
        self.assertEqual(err(self.run_, r), "DUEPRO1265:MISSING:deprivation.description")
        r = req(); del r["notice"]["given"]
        self.assertEqual(err(self.run_, r), "DUEPRO1265:MISSING:notice.given")
        r = req(); del r["hearing"]["held"]
        self.assertEqual(err(self.run_, r), "DUEPRO1265:MISSING:hearing.held")

    def test_bools_are_strict(self):
        for bad in (1, 0, "true", None):
            r = req(); r["notice"]["given"] = bad
            self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TYPE:notice.given", repr(bad))
            r = req(); r["hearing"]["held"] = bad
            self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TYPE:hearing.held", repr(bad))

    def test_date_with_negative_declaration_is_inconsistent(self):
        r = req(notice={"given": False, "date": "2026-01-05"})
        self.assertEqual(err(self.run_, r), "DUEPRO1265:INCONSISTENT:notice.date")
        r = req(hearing={"held": False, "date": "2026-01-05"})
        self.assertEqual(err(self.run_, r), "DUEPRO1265:INCONSISTENT:hearing.date")

    def test_balancing_list(self):
        self.assertEqual(err(self.run_, req(balancing_factors="x")), "DUEPRO1265:BAD_TYPE:balancing_factors")
        self.assertEqual(err(self.run_, req(balancing_factors=None)), "DUEPRO1265:BAD_TYPE:balancing_factors")
        self.assertEqual(err(self.run_, req(balancing_factors=[3])), "DUEPRO1265:BAD_TYPE:balancing_factors[0]")
        self.assertEqual(err(self.run_, req(balancing_factors=[{"label": "a"}])), "DUEPRO1265:MISSING:balancing_factors[0].statement")
        self.assertEqual(err(self.run_, req(balancing_factors=[{"statement": "a"}])), "DUEPRO1265:MISSING:balancing_factors[0].label")
        self.assertEqual(err(self.run_, req(balancing_factors=[{"label": "a", "statement": "b", "q": 1}])),
                         "DUEPRO1265:UNKNOWN_KEY:balancing_factors[0]")
        many = [{"label": "f%d" % i, "statement": "s"} for i in range(51)]
        self.assertEqual(err(self.run_, req(balancing_factors=many)), "DUEPRO1265:TOO_MANY:balancing_factors")
        ok = m.analyze_due_process(req(balancing_factors=many[:50]))
        self.assertEqual(ok["elements"]["balancing_factors"]["count"], 50)
        self.assertEqual(ok["elements"]["balancing_factors"]["status"], "DECLARED_UNSOURCED")

    def test_all_messages_row_tagged(self):
        for r in ([], req(as_of="x"), req(sources=3)):
            self.assertTrue(err(self.run_, r).startswith("DUEPRO1265:"))

    def test_no_non_row_exception_escapes(self):
        for bad in (object(), 5, "s", b"b", {"jurisdiction": object()}, req(sources=[object()]),
                    req(notice={"given": object()})):
            try:
                m.analyze_due_process(bad)
            except m.DueProcessError:
                pass


class PolicyPins(unittest.TestCase):
    """Count first, raw cap first, full Cc/Cf/Zl/Zp refusal, Zs accepted, fixed unknown-key reason."""

    def run_(self, r):
        return m.analyze_due_process(r)

    # --- count before iteration -------------------------------------------------------------------
    def test_dict_key_count_before_any_key_is_examined(self):
        # 65 keys whose first key is junk: iterating first would give UNKNOWN_KEY, counting first gives TOO_MANY
        def big(base):
            d = {"zz-junk": 1}
            d.update(base)
            for i in range(65 - len(d)):
                d["k%d" % i] = 1
            self.assertEqual(len(d), 65)
            return d
        self.assertEqual(err(self.run_, big(req())), "DUEPRO1265:TOO_MANY:request")
        for path in ("protected_interest", "deprivation", "notice", "hearing"):
            r = req()
            r[path] = big(r[path])
            self.assertEqual(err(self.run_, r), "DUEPRO1265:TOO_MANY:" + path)
        r = req()
        r["sources"][0] = big(r["sources"][0])
        self.assertEqual(err(self.run_, r), "DUEPRO1265:TOO_MANY:sources[0]")
        r = req()
        r["balancing_factors"][1] = big(r["balancing_factors"][1])
        self.assertEqual(err(self.run_, r), "DUEPRO1265:TOO_MANY:balancing_factors[1]")
        d = dict(req())                                            # exactly at the cap: unknown key, not TOO_MANY
        for i in range(64 - len(d)):
            d["k%d" % i] = 1
        self.assertEqual(len(d), 64)
        self.assertEqual(err(self.run_, d), "DUEPRO1265:UNKNOWN_KEY:request")

    def test_list_length_before_any_item_is_examined(self):
        self.assertEqual(err(self.run_, req(sources=[3] * 65)), "DUEPRO1265:TOO_MANY:sources")
        self.assertEqual(err(self.run_, req(sources=[3])), "DUEPRO1265:BAD_TYPE:sources[0]")
        self.assertEqual(err(self.run_, req(balancing_factors=[3] * 51)), "DUEPRO1265:TOO_MANY:balancing_factors")
        r = req()
        r["notice"]["source_ids"] = [3] * 21
        self.assertEqual(err(self.run_, r), "DUEPRO1265:TOO_MANY:notice.source_ids")
        r["notice"]["source_ids"] = [3]
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TEXT:notice.source_ids[0]")

    def test_containers_must_be_exact_builtins(self):
        class D(dict):
            pass

        class L(list):
            pass
        self.assertEqual(err(self.run_, D(req())), "DUEPRO1265:BAD_TYPE:request")
        for path in ("protected_interest", "deprivation", "notice", "hearing"):
            r = req()
            r[path] = D(r[path])
            self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TYPE:" + path)
        r = req(); r["sources"][0] = D(r["sources"][0])
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TYPE:sources[0]")
        r = req(); r["balancing_factors"][0] = D(r["balancing_factors"][0])
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TYPE:balancing_factors[0]")
        self.assertEqual(err(self.run_, req(sources=L(req()["sources"]))), "DUEPRO1265:BAD_TYPE:sources")
        self.assertEqual(err(self.run_, req(balancing_factors=L(req()["balancing_factors"]))),
                         "DUEPRO1265:BAD_TYPE:balancing_factors")
        r = req(); r["notice"]["source_ids"] = L(["S1"])
        self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TYPE:notice.source_ids")
        self.assertEqual(err(self.run_, req(sources=tuple(req()["sources"]))), "DUEPRO1265:BAD_TYPE:sources")

    def test_keys_must_be_exact_str_before_the_allowlist_lookup(self):
        calls = []

        class K(str):
            def __eq__(self, o):
                calls.append(1)
                return str.__eq__(self, o)
            __hash__ = str.__hash__
        r = req()
        r[K("notice")] = r.pop("notice")           # same text and hash as an allowed key, wrong type
        del calls[:]
        self.assertEqual(err(self.run_, r), "DUEPRO1265:UNKNOWN_KEY:request")
        self.assertEqual(calls, [])
        r = req()
        r["notice"][K("given")] = r["notice"].pop("given")
        del calls[:]
        self.assertEqual(err(self.run_, r), "DUEPRO1265:UNKNOWN_KEY:notice")
        self.assertEqual(calls, [])
        for bad in (1, None, (1,), b"given"):
            r = req(); r["notice"][bad] = 1
            self.assertEqual(err(self.run_, r), "DUEPRO1265:UNKNOWN_KEY:notice", repr(bad))
        r = req(); r[3] = 1
        self.assertEqual(err(self.run_, r), "DUEPRO1265:UNKNOWN_KEY:request")

    def test_unknown_key_reason_is_fixed_and_does_not_echo_the_key(self):
        secret = "caller-key-xyz"
        for path, mk in (("request", lambda r: r.update({secret: 1})),
                         ("notice", lambda r: r["notice"].update({secret: 1})),
                         ("sources[0]", lambda r: r["sources"][0].update({secret: 1})),
                         ("balancing_factors[0]", lambda r: r["balancing_factors"][0].update({secret: 1}))):
            r = req()
            mk(r)
            e = err(self.run_, r)
            self.assertEqual(e, "DUEPRO1265:UNKNOWN_KEY:" + path)
            self.assertNotIn(secret, e)

    # --- raw cap before strip / Unicode check -------------------------------------------------------
    def test_text_raw_cap_before_any_unicode_check(self):
        calls = []
        real = unicodedata.category
        m.unicodedata.category = lambda c: calls.append(c) or real(c)
        try:
            for bad in ("x" * 501, " " * 501, "\u200b" * 501, "a" * 100000):
                del calls[:]
                self.assertEqual(err(self.run_, req(jurisdiction=bad)), "DUEPRO1265:BAD_TEXT:jurisdiction")
                self.assertEqual(calls, [], repr(bad)[:12])
            del calls[:]
            self.run_(req(jurisdiction="ok"))
            self.assertTrue(calls)                                  # the spy does see in-cap text
        finally:
            m.unicodedata.category = real

    def test_text_requires_exact_str_type(self):
        class S(str):
            pass
        for bad in (S("abc"), b"abc", bytearray(b"abc"), ["a"]):
            self.assertEqual(err(self.run_, req(jurisdiction=bad)), "DUEPRO1265:BAD_TEXT:jurisdiction", repr(bad))
        self.assertEqual(err(self.run_, req(sources=[{"source_id": S("A"), "label": "x"}])),
                         "DUEPRO1265:BAD_TEXT:sources[0].source_id")

    def test_date_raw_length_cap_before_pattern(self):
        class Rx:
            n = 0

            def fullmatch(self, s):
                Rx.n += 1
                return real.fullmatch(s)
        real = m._DATE_RE
        m._DATE_RE = Rx()
        try:
            for bad in ("2" * 11, "2026-01-31" + " " * 5000, "x" * 100000, ""):
                Rx.n = 0
                self.assertEqual(err(self.run_, req(as_of=bad)), "DUEPRO1265:BAD_DATE:as_of")
                self.assertEqual(Rx.n, 0, repr(bad)[:12])
            Rx.n = 0
            self.run_(req())
            self.assertGreater(Rx.n, 0)
        finally:
            m._DATE_RE = real

    def test_date_requires_exact_str_type(self):
        class S(str):
            pass
        self.assertEqual(err(self.run_, req(as_of=S("2026-01-31"))), "DUEPRO1265:BAD_DATE:as_of")

    # --- Unicode categories ----------------------------------------------------------------------
    def _accepts(self, ch):
        return m.analyze_due_process(req(jurisdiction="a%sb" % ch))["jurisdiction"] == "a%sb" % ch

    def test_every_cc_cf_zl_zp_code_point_is_refused_in_echoed_text(self):
        n = 0
        for cp in range(0x110000):
            ch = chr(cp)
            if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp"):
                n += 1
                for text in ("a%sb" % ch, ch + "a", "a" + ch):
                    self.assertEqual(err(self.run_, req(jurisdiction=text)), "DUEPRO1265:BAD_TEXT:jurisdiction", hex(cp))
        self.assertGreater(n, 150)

    def test_explicit_soft_hyphen_and_word_joiner_pins(self):
        for ch, cat in (("\u00ad", "Cf"), ("\u2060", "Cf"), ("\u2028", "Zl"), ("\u2029", "Zp"), ("\x00", "Cc"),
                        ("\x7f", "Cc"), ("\ufeff", "Cf"), ("\u200d", "Cf")):
            self.assertEqual(unicodedata.category(ch), cat)
            self.assertEqual(err(self.run_, req(jurisdiction="a" + ch + "b")), "DUEPRO1265:BAD_TEXT:jurisdiction")
        for where, mk in (("protected_interest.description", lambda r, c: r["protected_interest"].update(description="a%sb" % c)),
                          ("balancing_factors[0].label", lambda r, c: r["balancing_factors"][0].update(label="a%sb" % c)),
                          ("sources[1].label", lambda r, c: r["sources"][1].update(label="a%sb" % c)),
                          ("notice.source_ids[0]", lambda r, c: r["notice"].update(source_ids=["a%sb" % c]))):
            for ch in ("\u00ad", "\u2060"):
                r = req()
                mk(r, ch)
                self.assertEqual(err(self.run_, r), "DUEPRO1265:BAD_TEXT:" + where)

    def test_every_zs_code_point_is_accepted_inside_text(self):
        n = 0
        for cp in range(0x110000):
            ch = chr(cp)
            if unicodedata.category(ch) == "Zs":
                n += 1
                self.assertTrue(self._accepts(ch), hex(cp))
        self.assertGreaterEqual(n, 17)
        self.assertEqual(err(self.run_, req(jurisdiction=" \u00a0\u3000 ")), "DUEPRO1265:BAD_TEXT:jurisdiction")   # blank

    def test_surrogates_are_not_newly_refused_disclosed_residual(self):
        self.assertEqual(unicodedata.category("\ud800"), "Cs")
        self.assertTrue(self._accepts("\ud800"))


class Hygiene(unittest.TestCase):
    def test_module_is_stdlib_only_and_does_not_call_the_template_engine(self):
        tree = ast.parse(_P.read_text())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        self.assertLessEqual(mods, {"__future__", "datetime", "re", "unicodedata"})

    def test_no_io_or_clock_calls(self):
        src = _P.read_text()
        for bad in ("open(", "urllib", "socket", "subprocess", "datetime.now", "date.today", "random", "os."):
            self.assertNotIn(bad, src, bad)

    def test_contract_doc_shape(self):
        d = _DOC.read_text()
        lines = [x for x in d.splitlines() if x.strip()]
        self.assertTrue(lines[0].startswith("# "))
        self.assertIn("Source pin", d.split("\n## ")[1][:40])
        self.assertIn("audits/coverage-register.json", d)
        self.assertNotIn("source_document_id", d)
        self.assertIn(STANDING, d)
        heads = re.findall(r"^## (.+)$", d, re.M)
        self.assertEqual(heads[0], "Source pin")
        self.assertEqual(heads[-1], "Limits and residual disclosures")
        self.assertIn("legal_support_1260_1309.py:22", d)
        self.assertIn("legal_support_1260_1309.py:96", d)
        self.assertIn("a294723b7a8f7bbe6067804ee4d7d325e1a8bde9", d)
        self.assertIn("DUEPRO1265:", d)
        for code in m.REFUSAL_CODES + m.GAP_CODES:
            self.assertIn(code, d, code)
        self.assertIn("5bb48316ab5beca30ae050c61913f07d71e6f7a3", d)
        self.assertIn("patch-only", d)
        self.assertIn("no individual RED", d)
        self.assertIn("raw per-mutant output", d)
        self.assertIn("surrogate", d)
        self.assertIn("exact built-in", d)
        self.assertIn("U+00AD", d)
        self.assertIn("U+2060", d)
        self.assertNotRegex(d, r"[\w.+-]+@[\w-]+\.[\w.]+")
        self.assertNotRegex(d, r"(?i)wamid|whatsapp|authuser|\bsecret\b|password")

    def test_code_tables_match_behavior(self):
        self.assertEqual(set(m.GAP_CODES), {"ELEMENT_NOT_DECLARED", "UNSOURCED", "UNKNOWN_SOURCE_ID", "DATE_AFTER_AS_OF",
                                            "DATE_UNDECLARED", "NOTICE_DECLARED_NOT_GIVEN", "HEARING_DECLARED_NOT_HELD"})
        self.assertEqual(set(m.REFUSAL_CODES), {"BAD_TYPE", "MISSING", "UNKNOWN_KEY", "BAD_TEXT", "BAD_DATE", "TOO_MANY",
                                                "DUPLICATE_SOURCE", "INCONSISTENT"})


if __name__ == "__main__":
    unittest.main()


class LiteralHonestyOracles(unittest.TestCase):
    def test_scope_full_literal_not_self_comparison(self):
        expected = 'DUEPRO1265 declared-element completeness and date ordering only'
        self.assertEqual(m.SCOPE, expected)
        self.assertEqual(m.analyze_due_process(req())['scope'], expected)

    def test_boundary_full_literal_not_substring(self):
        expected = (
            'Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, '
            'currency, citations, facts, duties, deadlines and strategy before use. '
            'Mechanical bookkeeping over caller-declared statements: it does not decide '
            'whether notice or a hearing was adequate, timely or required, does not weigh any factor, and does '
            'not verify any declared fact, date or source.'
        )
        self.assertEqual(m.BOUNDARY, expected)
        self.assertEqual(m.analyze_due_process(req())['boundary'], expected)


class OutputErrorLiteralOracles(unittest.TestCase):
    def test_exact_top_level_keys(self):
        self.assertEqual(set(m.analyze_due_process(req())), {
            'scope', 'boundary', 'jurisdiction', 'as_of', 'elements', 'sequence',
            'gaps', 'summary', 'adequacy_judged', 'legal_conclusion',
            'requires_licensed_counsel', 'filing_or_external_effect',
            'authority_independently_verified', 'disclaimer',
        })

    def test_unsourced_exact_gap_shape_and_detail(self):
        data = req()
        del data['protected_interest']['source_ids']
        self.assertEqual(m.analyze_due_process(data)['gaps'], [{
            'code': 'UNSOURCED', 'element': 'protected_interest',
            'detail': 'no source ids declared',
        }])

    def test_unknown_source_exact_gap_shape_and_detail(self):
        data = req()
        data['protected_interest']['source_ids'] = ['unknown']
        self.assertEqual(m.analyze_due_process(data)['gaps'], [{
            'code': 'UNKNOWN_SOURCE_ID', 'element': 'protected_interest',
            'detail': 'source id is not in the supplied sources', 'source_id': 'unknown',
        }])

    def test_protected_interest_ids_exact_wrong_type_refusal(self):
        data = req()
        data['protected_interest']['source_ids'] = 'S1'
        self.assertEqual(err(m.analyze_due_process, data),
                         'DUEPRO1265:BAD_TYPE:protected_interest.source_ids')


class CompleteElementOracles(unittest.TestCase):
    def test_four_complete_sourced_element_dicts(self):
        out = m.analyze_due_process(req())['elements']
        self.assertEqual(out['protected_interest'], {
            'status': 'DECLARED_SOURCED', 'description': 'Declared interest in a supplied benefit',
            'source_ids': ['S1'],
        })
        self.assertEqual(out['deprivation'], {
            'status': 'DECLARED_SOURCED', 'description': 'Declared termination of the benefit',
            'date': '2026-01-10', 'source_ids': ['S1'],
        })
        self.assertEqual(out['notice'], {
            'status': 'DECLARED_SOURCED', 'given': True, 'date': '2026-01-05',
            'content_summary': 'Declared written notice', 'source_ids': ['S2'],
        })
        self.assertEqual(out['hearing'], {
            'status': 'DECLARED_SOURCED', 'held': True, 'date': '2026-01-08',
            'decision_maker': 'Declared reviewer role', 'source_ids': ['S2'],
        })

    def test_source_ids_wrong_list_types_exact_fields(self):
        for element in ('protected_interest', 'deprivation', 'notice', 'hearing'):
            with self.subTest(element=element):
                data = req()
                data[element]['source_ids'] = 'S1'
                self.assertEqual(err(m.analyze_due_process, data),
                                 'DUEPRO1265:BAD_TYPE:' + element + '.source_ids')

    def test_deprivation_description_exact_bad_text_field(self):
        data = req()
        data['deprivation']['description'] = 1
        self.assertEqual(err(m.analyze_due_process, data),
                         'DUEPRO1265:BAD_TEXT:deprivation.description')

    def test_deprivation_unknown_source_exact_gap(self):
        data = req()
        data['deprivation']['source_ids'] = ['unknown']
        self.assertEqual(m.analyze_due_process(data)['gaps'], [{
            'code': 'UNKNOWN_SOURCE_ID', 'element': 'deprivation',
            'detail': 'source id is not in the supplied sources', 'source_id': 'unknown',
        }])


class MissingUndatedGapOracles(unittest.TestCase):
    def test_minimal_request_exact_missing_gaps(self):
        data = {'jurisdiction': 'Example Jurisdiction', 'as_of': '2026-01-31', 'sources': []}
        self.assertEqual(m.analyze_due_process(data)['gaps'], [
            {'code': 'ELEMENT_NOT_DECLARED', 'element': 'protected_interest', 'detail': 'element was not declared'},
            {'code': 'ELEMENT_NOT_DECLARED', 'element': 'deprivation', 'detail': 'element was not declared'},
            {'code': 'ELEMENT_NOT_DECLARED', 'element': 'notice', 'detail': 'element was not declared'},
            {'code': 'ELEMENT_NOT_DECLARED', 'element': 'hearing', 'detail': 'element was not declared'},
            {'code': 'ELEMENT_NOT_DECLARED', 'element': 'balancing_factors', 'detail': 'element was not declared'},
        ])

    def test_declared_undated_exact_gaps(self):
        data = req()
        for element in ('deprivation', 'notice', 'hearing'):
            del data[element]['date']
        self.assertEqual(m.analyze_due_process(data)['gaps'], [
            {'code': 'DATE_UNDECLARED', 'element': 'deprivation',
             'detail': 'no date declared; ordering not comparable'},
            {'code': 'DATE_UNDECLARED', 'element': 'notice',
             'detail': 'no date declared; ordering not comparable'},
            {'code': 'DATE_UNDECLARED', 'element': 'hearing',
             'detail': 'no date declared; ordering not comparable'},
        ])


class EmptyFactorsOracle(unittest.TestCase):
    def test_empty_factors_exact_record(self):
        out = m.analyze_due_process(req(balancing_factors=[]))
        self.assertEqual(out['elements']['balancing_factors'], {
            'status': 'NOT_DECLARED', 'count': 0, 'items': [],
        })


class FinalGapFactorOracles(unittest.TestCase):
    def test_future_date_exact_gap(self):
        data = req()
        data['deprivation']['date'] = '2026-02-01'
        self.assertEqual(m.analyze_due_process(data)['gaps'], [{
            'code': 'DATE_AFTER_AS_OF', 'element': 'deprivation',
            'detail': 'declared date is after as_of',
        }])

    def test_not_given_exact_gap(self):
        data = req(notice={'given': False, 'source_ids': ['S2']})
        self.assertEqual(m.analyze_due_process(data)['gaps'], [{
            'code': 'NOTICE_DECLARED_NOT_GIVEN', 'element': 'notice',
            'detail': 'caller declared that notice was not given',
        }])

    def test_not_held_exact_gap(self):
        data = req(hearing={'held': False, 'source_ids': ['S2']})
        self.assertEqual(m.analyze_due_process(data)['gaps'], [{
            'code': 'HEARING_DECLARED_NOT_HELD', 'element': 'hearing',
            'detail': 'caller declared that no hearing was held',
        }])

    def test_complete_balancing_record_literal(self):
        self.assertEqual(m.analyze_due_process(req())['elements']['balancing_factors'], {
            'status': 'DECLARED_SOURCED', 'count': 2, 'items': [
                {'label': 'private side', 'statement': 'Declared private-side statement',
                 'status': 'DECLARED_SOURCED', 'source_ids': ['S1']},
                {'label': 'public side', 'statement': 'Declared public-side statement',
                 'status': 'DECLARED_SOURCED', 'source_ids': ['S2']},
            ],
        })

    def test_factor_ids_wrong_type_exact_field(self):
        data = req()
        data['balancing_factors'][0]['source_ids'] = 'S1'
        self.assertEqual(err(m.analyze_due_process, data),
                         'DUEPRO1265:BAD_TYPE:balancing_factors[0].source_ids')
