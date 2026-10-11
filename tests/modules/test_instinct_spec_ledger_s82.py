"""S8.2 spec-to-ledger mapper tests. Stdlib unittest, hermetic, no repo conftest.

Fixtures under tests/fixtures/s82 are the v2 mega-spec (registry seed) and the
two pinned owner messages (digests only). Their text is
data only: nothing in them is executed or treated as an instruction.
"""
import copy
import hashlib
import json
import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.instinct_doc import spec_ledger_s82 as m  # noqa: E402

_FIX = _ROOT / "tests/fixtures/s82"
_SRC = _ROOT / "backend/app/modules/instinct_doc/spec_ledger_s82.py"
TS = "2026-10-11T15:01:13+05:30"
SEVEN = ["IMPLEMENTED", "PARKED_BY_USER", "PLANNED", "REFUSED_WITH_SUBSTITUTE", "STOPPED_BY_USER", "SUPERSEDED", "UNMAPPED"]
HEX = "a" * 40


def src(text="Build alpha. Build beta.\nGamma delta", mid="m1", ts=TS):
    return {"message_id": mid, "ts": ts, "text": text}


def unit(uid="S1.1", *ex, status="PLANNED", **kw):
    e = {"unit_id": uid, "status": status, "excerpts": list(ex)}
    e.update(kw)
    return e


def synth(patched=True):
    """Synthetic spec and two invented source messages (no real chat text is committed)."""
    spec = (_FIX / "synthetic-spec.md").read_text()
    if patched:
        spec = spec.replace(' [...] "" (invented', ' (invented')
    sources = [src((_FIX / "synthetic-source-a.txt").read_text(), "syn-a", "2026-01-01T09:00:00+05:30"),
               src((_FIX / "synthetic-source-b.txt").read_text(), "syn-b", "2026-01-01T09:05:00+05:30")]
    return spec, sources


def synth_fixed():
    spec, sources = synth()
    return spec.replace("tracks satellites in space", "tracks satellites and").replace(
        "Orbit planner should also", "Orbit Planner should also"), sources


def synth_maps():
    mp = json.loads((_FIX / "synthetic-maps.json").read_text())
    return ({k: {"unit_ids": v, "reason": "reviewed synthetic map"} for k, v in mp["explicit_maps"].items()},
            mp["exclusions"])


class T(unittest.TestCase):
    def refuses(self, code, fn, *a, **k):
        with self.assertRaises(ValueError) as cm:
            fn(*a, **k)
        self.assertEqual(str(cm.exception), code)
        self.assertNotIn("\n", str(cm.exception))

    # ---- constants
    def test_constants(self):
        self.assertEqual(sorted(m.STATES), SEVEN)
        self.assertEqual(m.B1_STATES, {"IMPLEMENTED", "PARKED_BY_USER", "STOPPED_BY_USER", "SUPERSEDED",
                                       "REFUSED_WITH_SUBSTITUTE", "UNMAPPED"})
        self.assertEqual(m.NON_B1_STATES, {"PLANNED"})
        self.assertEqual(m.UNIT, "S8.2")
        self.assertEqual(m.MIN_FRAGMENT, 8)

    # ---- spans
    def test_split_spans_lossless_partition(self):
        for t in ["Build alpha. Build beta.\nGamma delta", "", "a.b. c", "x\n\ny", "end.", " ", "Q? Yes! ok"]:
            sp = m.split_spans(t)
            self.assertEqual("".join(s["text"] for s in sp), t)
            pos = 0
            for s in sp:
                self.assertEqual(s["start"], pos)
                pos = s["end"]
            self.assertEqual(pos, len(t))

    def test_split_spans_known(self):
        sp = m.split_spans("Build alpha. Build beta.\nGamma delta")
        self.assertEqual([s["text"] for s in sp], ["Build alpha.", " Build beta.", "\n", "Gamma delta"])
        self.assertEqual([s["text"] for s in m.split_spans("a.b. c")], ["a.b.", " c"])

    # ---- mapping basics
    def test_excerpt_maps_overlapping_span_with_status_and_ids(self):
        led = m.map_ledger([src()], [unit("S1.1", "Build alpha"), unit("S1.2", "Build alpha")])
        r = led["rows"][0]
        self.assertEqual((r["source_msg"], r["line_no"], r["span_id"]), ("m1", 1, "m1:0"))
        self.assertEqual(r["verbatim"], "Build alpha.")
        self.assertEqual(r["unit_ids"], ["S1.1", "S1.2"])
        self.assertEqual((r["status"], r["basis"]), ("PLANNED", "excerpt"))
        self.assertEqual(r["verbatim"], "Build alpha.")

    def test_excerpt_spanning_two_spans_maps_both(self):
        led = m.map_ledger([src()], [unit("S1.1", "alpha. Build beta")])
        self.assertEqual([r["unit_ids"] for r in led["rows"][:3]], [["S1.1"], ["S1.1"], []])

    def test_ellipsis_fragments_each_map(self):
        led = m.map_ledger([src()], [unit("S1.1", "Build alpha... Gamma delta")])
        got = [r["unit_ids"] for r in led["rows"]]
        self.assertEqual(got, [["S1.1"], [], [], ["S1.1"]])

    def test_every_occurrence_maps(self):
        led = m.map_ledger([src("Do the thing. Do the thing. Other bit")], [unit("S1.1", "Do the thing")])
        self.assertEqual([r["unit_ids"] for r in led["rows"]], [["S1.1"], ["S1.1"], []])

    def test_unmapped_and_counts_and_gate(self):
        led = m.map_ledger([src()], [unit("S1.1", "Build alpha")])
        rep = led["report"]
        self.assertEqual(rep["counts"]["UNMAPPED"], 2)
        self.assertEqual(rep["counts"]["PLANNED"], 1)
        self.assertEqual(rep["nonrequests"], 1)
        self.assertEqual(rep["candidate_spans"], 4)
        self.assertIs(rep["passed"], False)
        self.assertEqual(rep["refusal"], "PLAN_REFUSED_UNMAPPED_LINE")
        self.assertEqual(sorted(rep["counts"]), SEVEN)
        self.refuses("PLAN_REFUSED_UNMAPPED_LINE:2", m.require_complete, led)

    def test_blank_spans_are_nonrequests_not_unmapped(self):
        led = m.map_ledger([src("Alpha beta gamma.\n\n  \nDelta epsilon zeta")], [unit("S1.1", "Alpha beta gamma", "Delta epsilon zeta")])
        rep = led["report"]
        self.assertEqual(rep["counts"]["UNMAPPED"], 0)
        self.assertEqual(rep["nonrequests"], 3)
        self.assertIs(rep["passed"], True)
        blank = [r for r in led["rows"] if r["basis"] == "blank"]
        self.assertEqual([(r["status"], r["nonrequest_reason"]) for r in blank], [(None, "structural_blank")] * 3)
        self.assertEqual(m.require_complete(led), led["report"])

    def test_dropping_a_unit_unmaps_its_lines_and_flips_gate(self):
        s = [src("Alpha beta gamma. Delta epsilon zeta.")]
        full = [unit("S1.1", "Alpha beta gamma"), unit("S1.2", "Delta epsilon zeta")]
        a = m.map_ledger(s, full)
        self.assertIs(a["report"]["passed"], True)
        b = m.map_ledger(s, full[:1])
        self.assertEqual(b["report"]["counts"]["UNMAPPED"], 1)
        self.assertIs(b["report"]["passed"], False)
        self.assertEqual([r["status"] for r in b["rows"]], ["PLANNED", "UNMAPPED"])
        c = m.map_ledger(s, full[1:])
        self.assertEqual([r["status"] for r in c["rows"]], ["UNMAPPED", "PLANNED"])

    def test_status_precedence(self):
        s = [src("Alpha beta gamma.")]
        order = ["STOPPED_BY_USER", "PARKED_BY_USER", "SUPERSEDED", "REFUSED_WITH_SUBSTITUTE", "IMPLEMENTED", "PLANNED"]
        ev = {
            "IMPLEMENTED": {"unit": "U", "tests": "t", "mutation": "m", "commit": HEX},
            "REFUSED_WITH_SUBSTITUTE": {"substitute": "X1", "unit": "S1.1", "reason": "r"},
            "PARKED_BY_USER": {"topic": "t", "pin_ref": "p"},
            "STOPPED_BY_USER": {"topic": "t", "pin_ref": "p"},
            "SUPERSEDED": {"topic": "t", "pin_ref": "p"},
            "PLANNED": None,
        }
        for i in range(len(order) - 1):
            hi, lo = order[i], order[i + 1]
            def mk(uid, st):
                kw = {} if ev[st] is None else {"evidence": ev[st]}
                return unit(uid, "Alpha beta gamma", status=st, **kw)
            led = m.map_ledger(s, [mk("S1.2", lo), mk("S1.1", hi)])
            self.assertEqual(led["rows"][0]["status"], hi)
            self.assertEqual(led["rows"][0]["unit_ids"], ["S1.1", "S1.2"])

    # ---- drift / unpinned / pins
    def test_paraphrase_drift_reported_and_fails_gate(self):
        led = m.map_ledger([src("Alpha beta gamma.")], [unit("S1.1", "Alpha beta gamma", "Alpha betta gamma")])
        rep = led["report"]
        self.assertEqual(rep["drift_units"], ["S1.1"])
        self.assertEqual(led["drift"], [{"unit_id": "S1.1", "fragment": "Alpha betta gamma"}])
        self.assertEqual(rep["counts"]["UNMAPPED"], 0)
        self.assertIs(rep["passed"], False)
        self.assertEqual(rep["refusal"], "PLAN_REFUSED_DRIFT")
        self.refuses("PLAN_REFUSED_DRIFT:1", m.require_complete, led)

    def test_unpinned_units_listed(self):
        led = m.map_ledger([src("Alpha beta gamma.")], [unit("S1.1", "Alpha beta gamma"), unit("S3.2")])
        self.assertEqual(led["report"]["unpinned_units"], ["S3.2"])
        self.assertIs(led["report"]["passed"], True)

    def test_pin_resolution_against_supplied_spans(self):
        ev = {"topic": "science", "pin_ref": "m1:1"}
        led = m.map_ledger([src("Alpha beta gamma. Stop that now.")],
                           [unit("V2-P1", "Alpha beta gamma", status="PARKED_BY_USER", evidence=ev),
                            unit("V2-P2", "Stop that now", status="PARKED_BY_USER", evidence={"topic": "t", "pin_ref": "14:59:56 not supplied"})])
        self.assertEqual(led["report"]["unresolved_pins"], ["V2-P2"])
        self.assertEqual(led["pins"], {"V2-P1": True, "V2-P2": False})

    # ---- explicit maps / exclusions
    def test_explicit_map_and_exclusion(self):
        s = [src("Alpha beta gamma. Delta epsilon zeta. Eta theta iota.")]
        reg = [unit("S1.1", "Alpha beta gamma")]
        led = m.map_ledger(s, reg,
                           explicit_maps={"m1:1": {"unit_ids": ["S1.1"], "reason": "continuation of the same request"}},
                           exclusions={"m1:2": "greeting, not a request"})
        self.assertEqual([r["basis"] for r in led["rows"]], ["excerpt", "explicit", "excluded"])
        self.assertEqual([r["status"] for r in led["rows"]], ["PLANNED", "PLANNED", None])
        self.assertEqual(led["rows"][2]["nonrequest_reason"], "greeting, not a request")
        self.assertEqual(led["report"]["nonrequests"], 1)
        self.assertIs(led["report"]["passed"], True)

    def test_explicit_map_plus_excerpt_unions(self):
        s = [src("Alpha beta gamma.")]
        led = m.map_ledger(s, [unit("S1.1", "Alpha beta gamma"), unit("S1.2")],
                           explicit_maps={"m1:0": {"unit_ids": ["S1.2"], "reason": "also"}})
        self.assertEqual(led["rows"][0]["unit_ids"], ["S1.1", "S1.2"])
        self.assertEqual(led["rows"][0]["basis"], "excerpt+explicit")

    def test_map_refusals(self):
        s = [src("Alpha beta gamma. Delta epsilon zeta.")]
        reg = [unit("S1.1", "Alpha beta gamma")]
        ok = {"unit_ids": ["S1.1"], "reason": "r"}
        self.refuses("PLAN_REFUSED_MAP:unknown_span", m.map_ledger, s, reg, explicit_maps={"m1:9": ok})
        self.refuses("PLAN_REFUSED_MAP:unknown_unit", m.map_ledger, s, reg, explicit_maps={"m1:1": {"unit_ids": ["S9.9"], "reason": "r"}})
        self.refuses("PLAN_REFUSED_MAP:empty_reason", m.map_ledger, s, reg, explicit_maps={"m1:1": {"unit_ids": ["S1.1"], "reason": "  "}})
        self.refuses("PLAN_REFUSED_MAP:empty_units", m.map_ledger, s, reg, explicit_maps={"m1:1": {"unit_ids": [], "reason": "r"}})
        self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, reg, explicit_maps={"m1:1": ["S1.1"]})
        self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, reg, explicit_maps=[])
        self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, reg, explicit_maps={"m1:1": {"unit_ids": ["S1.1"], "reason": "r", "x": 1}})
        self.refuses("PLAN_REFUSED_MAP:unknown_span", m.map_ledger, s, reg, exclusions={"nope": "r"})
        self.refuses("PLAN_REFUSED_MAP:empty_reason", m.map_ledger, s, reg, exclusions={"m1:1": " "})
        self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, reg, exclusions={"m1:1": 5})
        self.refuses("PLAN_REFUSED_MAP:conflict", m.map_ledger, s, reg, explicit_maps={"m1:1": ok}, exclusions={"m1:1": "r"})
        self.refuses("PLAN_REFUSED_MAP:conflict", m.map_ledger, s, reg, exclusions={"m1:0": "r"})

    # ---- source validation
    def test_source_refusals(self):
        reg = [unit("S1.1", "Alpha beta gamma")]
        for bad in ([], None, "x", {}):
            self.refuses("PLAN_REFUSED_NOSOURCE", m.map_ledger, bad, reg)
        self.refuses("PLAN_REFUSED_SOURCE:bad_shape", m.map_ledger, ["x"], reg)
        self.refuses("PLAN_REFUSED_SOURCE:bad_shape", m.map_ledger, [{**src(), "x": 1}], reg)
        self.refuses("PLAN_REFUSED_SOURCE:bad_shape", m.map_ledger, [{"message_id": "a", "ts": TS}], reg)
        for k, v in (("message_id", 5), ("message_id", True), ("message_id", ""), ("message_id", "a b"), ("message_id", "x" * 65),
                     ("text", 5), ("text", None), ("text", ""), ("ts", 5)):
            self.refuses("PLAN_REFUSED_SOURCE:bad_field:" + k, m.map_ledger, [{**src(), k: v}], reg)
        for ts in ("2026-10-11T15:01:13", "yesterday", "2026-13-01T00:00:00+05:30"):
            self.refuses("PLAN_REFUSED_SOURCE:bad_field:ts", m.map_ledger, [src(ts=ts)], reg)
        self.refuses("PLAN_REFUSED_SOURCE:duplicate_message_id", m.map_ledger, [src(), src()], reg)
        self.refuses("PLAN_REFUSED_SOURCE:too_long", m.map_ledger, [src("x" * 200001)], reg)
        m.map_ledger([src("x" * 200000)], [])
        self.refuses("PLAN_REFUSED_SOURCE:too_many", m.map_ledger, [src(mid="m%d" % i) for i in range(17)], reg)
        m.map_ledger([src(mid="m%d" % i) for i in range(16)], reg)

    def test_source_text_never_in_public_error(self):
        with self.assertRaises(ValueError) as cm:
            m.map_ledger([src("SECRET text\nUNMAPPED forged", ts="bad")], [])
        self.assertNotIn("SECRET", str(cm.exception))

    # ---- registry validation
    def test_registry_refusals(self):
        s = [src()]
        R = "PLAN_REFUSED_REGISTRY:"
        self.refuses(R + "bad_shape", m.map_ledger, s, "x")
        self.refuses(R + "bad_shape", m.map_ledger, s, ["x"])
        self.refuses(R + "bad_shape", m.map_ledger, s, [{"unit_id": "S1.1"}])
        self.refuses(R + "bad_shape", m.map_ledger, s, [{**unit("S1.1"), "z": 1}])
        for bad in ("s1.1", "S1.1 ", "S1.1\nX1", "", "Z", "S1.1.2", 5, None, "S" * 17, "X1;"):
            self.refuses(R + "bad_unit_id", m.map_ledger, s, [unit(bad)])
        self.refuses(R + "duplicate_unit:S1.1", m.map_ledger, s, [unit("S1.1"), unit("S1.1")])
        for bad in ("DONE", "IMPLEMENTED-BOUNDED", "planned", None, 5):
            self.refuses(R + "bad_status:S1.1", m.map_ledger, s, [unit("S1.1", status=bad)])
        for bad in ("x", None, ("a",)):
            self.refuses(R + "bad_excerpts:S1.1", m.map_ledger, s, [{"unit_id": "S1.1", "status": "PLANNED", "excerpts": bad}])
        self.refuses(R + "bad_excerpts:S1.1", m.map_ledger, s, [unit("S1.1", 5)])
        self.refuses(R + "bad_excerpts:S1.1", m.map_ledger, s, [unit("S1.1", "   ")])
        self.refuses(R + "bad_excerpts:S1.1", m.map_ledger, s, [unit("S1.1", "... ...")])
        self.refuses(R + "short_excerpt:S1.1", m.map_ledger, s, [unit("S1.1", "a" * 7)])
        m.map_ledger(s, [unit("S1.1", "a" * 8)])
        self.refuses(R + "bad_excerpts:S1.1", m.map_ledger, s, [unit("S1.1", "x" * 2001)])
        self.refuses(R + "bad_excerpts:S1.1", m.map_ledger, s, [unit("S1.1", *["abcdefgh%d" % i for i in range(65)])])
        m.map_ledger(s, [unit("S1.1", *["abcdefgh%d" % i for i in range(64)])])
        self.refuses(R + "too_many", m.map_ledger, s, [unit("S%d.1" % (i + 1)) for i in range(513)] if False else [{"unit_id": "T%d" % i, "status": "PLANNED", "excerpts": []} for i in range(513)])

    def test_boundaries_exact(self):
        s = [src()]
        R = "PLAN_REFUSED_REGISTRY:"
        m.map_ledger(s, [{"unit_id": "T%d" % i, "status": "PLANNED", "excerpts": []} for i in range(512)])
        m.map_ledger(s, [unit("S1.1", "x" * 2000)])
        m.map_ledger(s, [unit("S1.1", "abcdefgh")])
        m.map_ledger(s, [unit("S" + "1" * 15)])
        self.refuses(R + "bad_unit_id", m.map_ledger, s, [unit("S" + "1" * 16)])
        self.refuses(R + "bad_status:S1.1", m.map_ledger, s, [unit("S1.1", status="UNMAPPED")])
        self.refuses(R + "bad_excerpts:S1.1", m.map_ledger, s,
                     [{"unit_id": "S1.1", "status": "PLANNED", "excerpts": [], "unmatched": ["x" * 2001]}])
        m.map_ledger(s, [{"unit_id": "S1.1", "status": "PLANNED", "excerpts": [], "unmatched": ["x" * 2000]}])

    def test_as_of_is_latest_source_regardless_of_order(self):
        late, early = src("aaa", "m2", "2026-10-11T15:03:34+05:30"), src("bbb", "m1", "2026-10-11T15:01:13+05:30")
        for order in ([late, early], [early, late]):
            rep = m.map_ledger(order, [unit("S1.1")])["report"]
            self.assertEqual(rep["scope"]["as_of"], "2026-10-11T15:03:34+05:30")

    def test_parse_spec_odd_quotes_refused(self):
        self.refuses("PLAN_REFUSED_SPEC_LINE:3:odd_quotes", m.parse_spec,
                     '## 2. Units\n- **S1.1 a** | y\n  Source: "abc')

    def test_digest_covers_every_source(self):
        a, b = src("aaa", "m1"), src("bbb", "m2", "2026-10-11T15:03:34+05:30")
        self.assertNotEqual(m.map_ledger([a, b], [unit("S1.1")])["report"]["source_digest"],
                            m.map_ledger([a], [unit("S1.1")])["report"]["source_digest"])

    def test_whitespace_normalised_match_is_case_sensitive(self):
        s = [src("Build alpha  beta\ngamma delta. Other line.")]
        # runs of whitespace and newlines in the source match single spaces in an excerpt
        led = m.map_ledger(s, [unit("S1.1", "alpha beta gamma delta")])
        self.assertEqual(led["drift"], [])
        self.assertEqual([r["unit_ids"] for r in led["rows"]], [["S1.1"], ["S1.1"], []])
        # case differences are still drift
        led = m.map_ledger(s, [unit("S1.1", "ALPHA beta gamma delta")])
        self.assertEqual(led["drift"], [{"unit_id": "S1.1", "fragment": "ALPHA beta gamma delta"}])

    def test_parse_spec_accepts_add_headings(self):
        spec = "## ADD-1 New units\n- **C1 x** | y\n  Source: \"abcdefgh ijk\"\n## ADD-10 other\n- **C9 z** | y"
        reg = m.parse_spec(spec)
        self.assertEqual([e["unit_id"] for e in reg], ["C1"])
        reg = m.parse_spec("## ADD-2 X\n| # | a | b | c |\n|---|---|---|---|\n| X5 | \"abcdefgh\" | why | S1.1 |")
        self.assertEqual([e["unit_id"] for e in reg], ["X5"])

    def test_repair_battery_pins_2(self):
        s = [src("Build alpha beta gamma. Build beta.", "m" * 64)]  # 64-char message id accepted, 65 refused elsewhere
        good = {"unit": "u", "tests": "t", "mutation": "m", "commit": "0" * 40}
        m.map_ledger(s, [unit("S1.1", status="IMPLEMENTED", evidence=good)])
        reg = m.parse_spec("## V2-1 U\n- **C1 x** | y\n  Source: \"abcdefgh ijk\"\n## V2-2 X\n| # | a | b | c |\n|---|---|---|---|\n| X5 | \"abcdefgh\" | why | S1.1 |")
        self.assertEqual([e["unit_id"] for e in reg], ["C1", "X5"])
        self.refuses("PLAN_REFUSED_SPEC_LINE:1:no_registry_lines", m.parse_spec,
                     "## V2-2 U\n- **C1 x** | y\n## V2-3 X\n| # | a | b | c |\n|---|---|---|---|\n| X5 | \"abcdefgh\" | why | S1.1 |")
        # one short fragment among long ones: whole quote is unmatched, none usable
        reg = m.parse_spec('## ADD-1 U\n- **C1 x** | y\n  Source: "abcdefgh ijk ... ab"\n  Source: "abcdefgh ijk"')
        self.assertEqual(reg[0]["excerpts"], ["abcdefgh ijk"])
        self.assertEqual(reg[0]["unmatched"], ["abcdefgh ijk ... ab"])
        # one unknown id among a known one is refused
        self.refuses("PLAN_REFUSED_MAP:unknown_unit", m.map_ledger, [src()], [unit("S1.1")],
                     explicit_maps={"m1:1": {"unit_ids": ["S1.1", "S9.9"], "reason": "r"}})

    def test_id_grammar_pins(self):
        s = [src()]
        for ok in ("A1", "AB10", "S1.0", "V2-X9", "V2-9"):
            m.map_ledger(s, [unit(ok)])
        for bad in ("ABC1", "1", "A", "V2-"):
            self.refuses("PLAN_REFUSED_REGISTRY:bad_unit_id", m.map_ledger, s, [unit(bad)])
        hdr = '## ADD-1 U\n- **%s x** | y\n  Source: "abcdefgh ijk"'
        for ok in ("AB10", "B2.0"):
            self.assertEqual(m.parse_spec(hdr % ok)[0]["unit_id"], ok)
        for bad in ("ABC1", "1", "A10.", "A0"):
            if bad == "A0":
                self.assertEqual(m.parse_spec(hdr % bad)[0]["unit_id"], "A0")
            else:
                self.refuses("PLAN_REFUSED_SPEC_LINE:2:bad_unit_header", m.parse_spec, hdr % bad)
        x = '## ADD-2 X\n| # | a | b | c |\n|---|---|---|---|\n| - : |\n| X5 | "abcdefgh" | why | %s |'
        reg = m.parse_spec(x % "S1.0, T9.1, AB10")
        self.assertEqual(reg[0]["evidence"]["unit_refs"], ["S1.0", "T9.1", "AB10"])
        self.assertEqual(reg[0]["evidence"]["unit"], "S1.0")
        self.assertEqual(m.parse_spec(x % "ABC1")[0]["evidence"]["unit"], "UNSPECIFIED")

    def test_parked_pid_and_refs_pins(self):
        reg = m.parse_spec('## ADD-0 Notes\n- **Gate superseded.** "abcdefgh ijk"\n  - P0: "abcdefgh p0".\n  - P10: "abcdefgh p10".\n  - P19: "abcdefgh p19".')
        self.assertEqual([e["unit_id"] for e in reg], ["V2-GATE", "V2-P0", "V2-P10", "V2-P19"])
        x = '## ADD-2 X\n| # | a | b | c |\n|---|---|---|---|\n| X5 | "abcdefgh" | why | %s |'
        self.assertEqual(m.parse_spec(x % "see 10 then S1.9")[0]["evidence"]["unit_refs"], ["S1.9"])
        self.assertEqual(m.parse_spec(x % "S1.9")[0]["evidence"]["unit"], "S1.9")

    def test_split_spans_empty_contract(self):
        # Contract: empty text yields exactly one zero-width span, never [].
        self.assertEqual(m.split_spans(""), [{"start": 0, "end": 0, "text": ""}])
        self.assertEqual(m.split_spans("   "), [{"start": 0, "end": 3, "text": "   "}])
        self.assertEqual(m.split_spans("\n"), [{"start": 0, "end": 1, "text": "\n"}])

    def test_gate_heading_only_superseded_is_recorded(self):
        base = '## ADD-0 Notes\n- **Gate %s.** "abcdefgh ijk"\n  - P0: "abcdefgh p0".'
        reg = m.parse_spec(base % "superseded")
        self.assertEqual([(e["unit_id"], e["status"]) for e in reg], [("V2-GATE", "SUPERSEDED"), ("V2-P0", "PARKED_BY_USER")])
        for word in ("retained", "active", "Superseded", "supersededx", "supersede", ""):
            reg = m.parse_spec(base % word)
            self.assertEqual([e["unit_id"] for e in reg], ["V2-P0"], word)

    def test_normalised_match_edges(self):
        s = [src("Build alpha beta gamma\nDelta epsilon zeta", "m1")]
        # excerpt with its own double space still matches single-spaced source
        self.assertEqual(m.map_ledger([src("Build alpha beta gamma")], [unit("S1.1", "alpha   beta")])["drift"], [])
        # an excerpt ending on the first character of the next span maps that span too
        led = m.map_ledger(s, [unit("S1.1", "beta gamma\nD")])
        self.assertEqual([r["unit_ids"] for r in led["rows"]], [["S1.1"], ["S1.1"]])
        led = m.map_ledger(s, [unit("S1.1", "beta gamma")])
        self.assertEqual([r["unit_ids"] for r in led["rows"]], [["S1.1"], []])

    def test_evidence_rules(self):
        s = [src()]
        E = "PLAN_REFUSED_EVIDENCE:"
        good = {"unit": "u", "tests": "t", "mutation": "m", "commit": HEX}
        m.map_ledger(s, [unit("S1.1", status="IMPLEMENTED", evidence=good)])
        for k in good:
            self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status="IMPLEMENTED", evidence={**good, k: ""})])
        for bad in ("A" * 40, "a" * 39, "a" * 41, "g" * 40, HEX + "\n"):
            self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status="IMPLEMENTED", evidence={**good, "commit": bad})])
        self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status="IMPLEMENTED")])
        sub = {"substitute": "X30", "unit": "S1.1", "reason": "r"}
        m.map_ledger(s, [unit("X30", status="REFUSED_WITH_SUBSTITUTE", evidence=sub)])
        for bad in ("X0", "X31", "x1", "S1", ""):
            self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status="REFUSED_WITH_SUBSTITUTE", evidence={**sub, "substitute": bad})])
        for k in ("unit", "reason"):
            self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status="REFUSED_WITH_SUBSTITUTE", evidence={**sub, k: ""})])
        pin = {"topic": "t", "pin_ref": "p"}
        for st in ("PARKED_BY_USER", "STOPPED_BY_USER", "SUPERSEDED"):
            m.map_ledger(s, [unit("S1.1", status=st, evidence=pin)])
            for k in pin:
                self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status=st, evidence={**pin, k: ""})])
            self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status=st)])
        self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status="PLANNED", evidence="x")])
        self.refuses(E + "S1.1", m.map_ledger, s, [unit("S1.1", status="IMPLEMENTED", evidence=[])])

    # ---- parse_spec on small synthetic specs
    SPEC = "\n".join([
        "# T", "", "## 1. Register of refused lines", "",
        "| # | Quoted line | Reason | Replacement |", "|---|---|---|---|",
        '| X1 | "gather every fact" / "learn all topics" | Not finite. | Dataset ingest (S2.1, S2.2). |',
        "", "## 2. Units grouped by area", "", "### S1 Fleet", "",
        "- **S1.1 scanner** | `/c31/scan` | `ORBIT_DENIED_*`",
        '  Source: "Build alpha" and "Build beta".', "  Scope: stuff.",
        '- **C5 router** | `/c35/route` : "run any request" => router.',
        "- **S3.2 page-maker** | `/c34/pages` : static sites.",
        "", "## 4. Coverage notes", "- **S1.1 not a unit here** | x", "",
        "## V2-0 Retired", "",
        '- **Gate superseded.** Quote: "once the first batch is done". Ruling: "skip science" at 14:59:56.',
        "- **Shelved topic, PARKED**:",
        '  - P1: "per project 120+ datasets".',
        '- Also parked: "make a small quiz app" (her other message: "no need").',
    ])

    def test_parse_spec_synthetic(self):
        reg = m.parse_spec(self.SPEC)
        got = [(e["unit_id"], e["kind"], e["status"], e["excerpts"], e["spec_line"]) for e in reg]
        self.assertEqual(got, [
            ("X1", "x", "REFUSED_WITH_SUBSTITUTE", ["gather every fact", "learn all topics"], 7),
            ("S1.1", "unit", "PLANNED", ["Build alpha", "Build beta"], 13),
            ("C5", "unit", "PLANNED", ["run any request"], 16),
            ("S3.2", "unit", "PLANNED", [], 17),
            ("V2-GATE", "gate", "SUPERSEDED", ["once the first batch is done"], 24),
            ("V2-P1", "parked", "PARKED_BY_USER", ["per project 120+ datasets"], 26),
            ("V2-CBSE", "parked", "PARKED_BY_USER", ["make a small quiz app"], 27),
        ])
        x = reg[0]["evidence"]
        self.assertEqual(x, {"substitute": "X1", "unit": "S2.1", "reason": "Not finite.", "unit_refs": ["S2.1", "S2.2"]})
        self.assertEqual(reg[4]["evidence"]["topic"], "27-task gate")
        self.assertEqual(reg[5]["evidence"]["topic"], "science-scoped")
        self.assertTrue(reg[5]["evidence"]["pin_ref"])

    def test_parse_spec_refusals(self):
        def spec(*lines):
            return "\n".join(["## 2. Units", *lines])
        P = "PLAN_REFUSED_SPEC_LINE:"
        self.refuses(P + "0:empty", m.parse_spec, "")
        self.refuses(P + "0:empty", m.parse_spec, 5)
        self.refuses(P + "2:bad_unit_header", m.parse_spec, spec("- **s1.1 x** | y"))
        self.refuses(P + "2:bad_unit_header", m.parse_spec, spec("- not bold"))
        self.refuses(P + "2:bad_unit_header", m.parse_spec, spec("- **S1.1** | y"))
        self.refuses(P + "3:duplicate_unit", m.parse_spec, spec("- **S1.1 a** | y", "- **S1.1 b** | y"))
        self.refuses(P + "3:odd_quotes", m.parse_spec, spec("- **S1.1 a** | y", '  Source: "abc def'))
        self.refuses(P + "3:empty_excerpt", m.parse_spec, spec("- **S1.1 a** | y", '  Source: "  "'))
        self.refuses(P + "2:orphan_source", m.parse_spec, spec('  Source: "abc def ghi"'))
        self.refuses(P + "2:odd_quotes", m.parse_spec, spec('- **S1.1 a** | y : "x'))
        x = "## 1. X"
        self.refuses(P + "2:bad_x_row", m.parse_spec, "\n".join([x, "| X1 | only | two |"]))
        self.refuses(P + "3:duplicate_unit", m.parse_spec, "\n".join([x, '| X1 | "a b c" | w | s |', '| X1 | "a b c" | w | s |']))
        self.refuses(P + "2:bad_x_row", m.parse_spec, "\n".join([x, '| X31 | "a b c" | w | s |']))
        self.refuses(P + "2:bad_x_row", m.parse_spec, "\n".join([x, '| X0 | "a b c" | w | s |']))
        self.refuses(P + "2:odd_quotes", m.parse_spec, "\n".join([x, '| X1 | "a b c | w | s |']))
        self.refuses(P + "1:no_registry_lines", m.parse_spec, "# nothing here\ntext")

    def test_parse_spec_short_quote_is_unmatched_not_a_wildcard(self):
        reg = m.parse_spec("## 2. Units\n- **S1.1 a** | y\n  Source: \"AGI\" and \"long enough quote\" and \"x... AGI\".")
        self.assertEqual(reg[0]["excerpts"], ["long enough quote"])
        self.assertEqual(reg[0]["unmatched"], ["AGI", "x... AGI"])
        led = m.map_ledger([src("AGI is here. Nothing else mapped.")], reg)
        self.assertEqual(led["rows"][0]["status"], "UNMAPPED")
        self.assertEqual(led["report"]["unmatched_units"], ["S1.1"])
        self.assertEqual(led["report"]["unpinned_units"], [])
        self.refuses("PLAN_REFUSED_SPEC_LINE:3:empty_excerpt", m.parse_spec, "## 2. Units\n- **S1.1 a** | y\n  Source: \"...\"")
        self.refuses("PLAN_REFUSED_REGISTRY:bad_excerpts:S1.1", m.map_ledger, [src()], [{**unit("S1.1"), "unmatched": "x"}])
        self.refuses("PLAN_REFUSED_REGISTRY:bad_excerpts:S1.1", m.map_ledger, [src()], [{**unit("S1.1"), "unmatched": [" "]}])

    def test_parse_spec_unit_in_other_section_ignored(self):
        reg = m.parse_spec(self.SPEC)
        self.assertEqual([e["unit_id"] for e in reg].count("S1.1"), 1)

    # ---- the real v2 spec + real source messages
    def test_synthetic_registry_shape_and_roundtrip(self):
        spec, sources = synth()
        reg = m.parse_spec(spec)
        ids = [e["unit_id"] for e in reg]
        self.assertEqual(ids, ["X1", "X2", "X3", "S1.1", "S1.2", "S1.3", "S2.1", "S2.2", "S2.3", "S2.4", "S2.6",
                               "S2.5", "V2-GATE", "V2-P1", "V2-P2", "V2-CBSE"])
        self.assertTrue(all(e["status"] == "PLANNED" for e in reg if e["kind"] == "unit"))
        self.assertTrue(all(e["status"] == "REFUSED_WITH_SUBSTITUTE" for e in reg if e["kind"] == "x"))
        self.assertEqual([e["status"] for e in reg if e["kind"] == "gate"], ["SUPERSEDED"])
        self.assertTrue(all(e["status"] == "PARKED_BY_USER" for e in reg if e["kind"] == "parked"))
        self.assertNotIn("S9.9", ids)  # ADD-10 is not a units section
        back = json.loads(json.dumps(reg))
        self.assertEqual([(e["unit_id"], e["status"]) for e in back], [(e["unit_id"], e["status"]) for e in reg])
        led = m.map_ledger(sources, reg)
        self.assertEqual(led["unit_status"], {e["unit_id"]: e["status"] for e in reg})
        self.assertEqual(led["report"]["registry_units"], 16)

    def test_synthetic_golden_counts_and_findings(self):
        spec, sources = synth()
        led = m.map_ledger(sources, m.parse_spec(spec))
        rep = led["report"]
        self.assertEqual(rep["candidate_spans"], 25)
        self.assertEqual(rep["nonrequests"], 7)
        self.assertEqual(rep["counts"], {"IMPLEMENTED": 0, "PARKED_BY_USER": 3, "PLANNED": 7,
                                         "REFUSED_WITH_SUBSTITUTE": 1, "STOPPED_BY_USER": 0,
                                         "SUPERSEDED": 1, "UNMAPPED": 6})
        self.assertEqual(rep["drift_units"], ["S2.4", "S2.6"])
        self.assertEqual(rep["unmatched_units"], ["S2.5", "X3"])
        self.assertEqual(rep["unpinned_units"], ["S2.3"])
        self.assertEqual(rep["unresolved_pins"], ["V2-CBSE", "V2-GATE", "V2-P1", "V2-P2"])
        self.assertEqual([r["span_id"] for r in led["rows"] if r["status"] == "UNMAPPED"],
                         ["syn-a:0", "syn-a:5", "syn-a:10", "syn-b:6", "syn-b:9", "syn-b:10"])
        self.assertEqual(rep["source_digest"], "c63849a9dce098189b1e4e9fd604911c749b0763c225a1c695ec2babff9e5e85")
        self.assertIs(rep["passed"], False)
        self.assertEqual(rep["refusal"], "PLAN_REFUSED_UNMAPPED_LINE")
        self.assertEqual(len(led["drift"]), 2)

    def test_synthetic_whitespace_normalised_matches(self):
        spec, sources = synth()
        rows = {r["span_id"]: r for r in m.map_ledger(sources, m.parse_spec(spec))["rows"]}
        self.assertEqual(rows["syn-a:2"]["unit_ids"], ["S1.1"])   # double space in source
        self.assertEqual(rows["syn-a:3"]["unit_ids"], ["S1.1"])   # fragment on the next line
        self.assertEqual(rows["syn-b:3"]["unit_ids"], ["V2-GATE", "X2"])
        self.assertEqual(rows["syn-b:3"]["status"], "SUPERSEDED")

    def test_synthetic_empty_quote_line_is_refused(self):
        spec, _ = synth(patched=False)
        self.refuses("PLAN_REFUSED_SPEC_LINE:41:empty_excerpt", m.parse_spec, spec)

    def test_synthetic_green_with_reviewed_maps(self):
        spec, sources = synth_fixed()
        reg = m.parse_spec(spec)
        emap, excl = synth_maps()
        led = m.map_ledger(sources, reg, explicit_maps=emap, exclusions=excl)
        rep = led["report"]
        self.assertIs(rep["passed"], True)
        self.assertIsNone(rep["refusal"])
        self.assertEqual(led["drift"], [])
        self.assertEqual(rep["counts"]["UNMAPPED"], 0)
        self.assertEqual(rep["counts"], {"IMPLEMENTED": 0, "PARKED_BY_USER": 3, "PLANNED": 9,
                                         "REFUSED_WITH_SUBSTITUTE": 1, "STOPPED_BY_USER": 0,
                                         "SUPERSEDED": 1, "UNMAPPED": 0})
        self.assertEqual(rep["nonrequests"], 11)
        self.assertEqual(m.require_complete(led), rep)
        # drop a unit: its lines un-map and the gate refuses
        sub = [e for e in reg if e["unit_id"] != "S1.2"]
        led2 = m.map_ledger(sources, sub, explicit_maps=emap, exclusions=excl)
        self.assertEqual(led2["report"]["counts"]["UNMAPPED"], 1)
        self.refuses("PLAN_REFUSED_UNMAPPED_LINE:1", m.require_complete, led2)

    def test_synthetic_rows_are_lossless_and_ordered(self):
        spec, sources = synth()
        led = m.map_ledger(sources, m.parse_spec(spec))
        for s in sources:
            rows = [r for r in led["rows"] if r["source_msg"] == s["message_id"]]
            self.assertEqual("".join(r["verbatim"] for r in rows), s["text"])
            self.assertEqual([r["line_no"] for r in rows], list(range(1, len(rows) + 1)))

    def test_synthetic_dropping_each_mapped_unit_unmaps_its_lines(self):
        spec, sources = synth()
        reg = m.parse_spec(spec)
        base = m.map_ledger(sources, reg)
        base_un = base["report"]["counts"]["UNMAPPED"]
        grew = 0
        for drop in ("S1.1", "S1.2", "S1.3", "S2.1", "S2.2"):
            led = m.map_ledger(sources, [e for e in reg if e["unit_id"] != drop])
            only = [r["span_id"] for r in base["rows"] if r["unit_ids"] == [drop]]
            self.assertTrue(set(only) <= {r["span_id"] for r in led["rows"] if r["status"] == "UNMAPPED"})
            self.assertEqual(led["report"]["counts"]["UNMAPPED"], base_un + len(only))
            grew += len(only)
        self.assertGreater(grew, 0)

    # ---- repair pins (auditor battery)
    def test_parse_spec_min_fragment_is_eight_chars(self):
        head = "## 2. Units\n- **S1.1 a** | y\n  Source: "
        ok = m.parse_spec(head + '"abcdefgh"')[0]
        self.assertEqual((ok["excerpts"], ok["unmatched"]), (["abcdefgh"], []))
        short = m.parse_spec(head + '"abcdefg"')[0]
        self.assertEqual((short["excerpts"], short["unmatched"]), ([], ["abcdefg"]))

    def test_unmatched_list_limit_is_exactly_64(self):
        s = [src()]
        R = "PLAN_REFUSED_REGISTRY:bad_excerpts:S1.1"
        ok = {"unit_id": "S1.1", "status": "PLANNED", "excerpts": [], "unmatched": ["x"] * 64}
        m.map_ledger(s, [ok])
        self.refuses(R, m.map_ledger, s, [dict(ok, unmatched=["x"] * 65)])

    def test_sources_are_ordered_by_time_then_id(self):
        late = src("late line", "a-late", "2026-01-01T10:00:00+05:30")
        early = src("early line", "z-early", "2026-01-01T09:00:00+05:30")
        led = m.map_ledger([late, early], [unit("S1.1")])
        self.assertEqual([r["source_msg"] for r in led["rows"]], ["z-early", "a-late"])
        t1, t2 = src("one", "b", TS), src("two", "a", TS)
        led = m.map_ledger([t1, t2], [unit("S1.1")])
        self.assertEqual([r["source_msg"] for r in led["rows"]], ["a", "b"])
        # same instant in a different zone sorts by the instant, not the text
        east = src("east", "m1", "2026-01-01T09:00:00+05:30")
        west = src("west", "m2", "2026-01-01T03:30:01+00:00")
        led = m.map_ledger([west, east], [unit("S1.1")])
        self.assertEqual([r["source_msg"] for r in led["rows"]], ["m1", "m2"])

    def test_stopped_by_user_pin_is_tracked(self):
        ev = {"topic": "stopped", "pin_ref": "m1:0"}
        s = [src("Stop it. Next line", "m1")]
        rep = m.map_ledger(s, [unit("S1.1", "Stop it.", status="STOPPED_BY_USER", evidence=ev)])["report"]
        self.assertEqual(rep["unresolved_pins"], [])
        ev2 = {"topic": "stopped", "pin_ref": "nowhere:9"}
        rep = m.map_ledger(s, [unit("S1.1", "Stop it.", status="STOPPED_BY_USER", evidence=ev2)])["report"]
        self.assertEqual(rep["unresolved_pins"], ["S1.1"])
        self.assertEqual(rep["counts"]["STOPPED_BY_USER"], 1)

    def test_pin_and_evidence_texts_from_spec(self):
        spec, _ = synth()
        reg = {e["unit_id"]: e for e in m.parse_spec(spec)}
        pin = "ruling cited in spec, source message not supplied"
        self.assertEqual(reg["V2-GATE"]["evidence"], {"topic": "27-task gate", "pin_ref": "14:59:56 IST " + pin})
        self.assertEqual(reg["V2-P1"]["evidence"], {"topic": "science-scoped", "pin_ref": "14:59:56 IST " + pin})
        self.assertEqual(reg["V2-P2"]["evidence"], {"topic": "science-scoped", "pin_ref": "14:59:56 IST " + pin})
        self.assertEqual(reg["V2-CBSE"]["evidence"], {"topic": "class-11-cbse-app", "pin_ref": "15:03:20 IST " + pin})
        self.assertEqual(reg["X1"]["evidence"], {"substitute": "X1", "unit": "S1.1", "reason": "Outreach needs approval.",
                                                 "unit_refs": ["S1.1"]})
        self.assertEqual(reg["X2"]["evidence"], {"substitute": "X2", "unit": "UNSPECIFIED", "reason": "No unit.",
                                                 "unit_refs": []})
        self.assertEqual(reg["V2-GATE"]["spec_line"], 37)
        self.assertEqual(reg["X1"]["spec_line"], 7)

    def test_scope_and_row_strings_are_exact(self):
        spec, sources = synth()
        led = m.map_ledger(sources, m.parse_spec(spec))
        sc = led["report"]["scope"]
        self.assertEqual(sc["implemented"],
                         "deterministic mapping of source spans to registry units, with computed counts and drift check")
        self.assertEqual(sc["not_implemented"],
                         "proof that any unit is built, that an excerpt matches what was asked, or that a line is "
                         "fulfilled; not that pins cited by the spec were seen")
        self.assertEqual(sc["data_source"], "supplied spec registry and supplied pinned source messages")
        self.assertEqual(sc["provenance"], "spec_file_and_pinned_messages_not_owner_channel_rows")
        self.assertEqual(sc["as_of"], "2026-01-01T09:05:00+05:30")
        by = {r["span_id"]: r for r in led["rows"]}
        self.assertEqual(by["syn-a:0"]["basis"], "none")
        self.assertEqual(by["syn-a:0"]["status"], "UNMAPPED")
        self.assertEqual(by["syn-a:2"]["basis"], "excerpt")
        self.assertEqual(by["syn-a:1"]["basis"], "blank")
        self.assertEqual(by["syn-a:1"]["nonrequest_reason"], "structural_blank")
        emap, excl = synth_maps()
        led = m.map_ledger(sources, m.parse_spec(synth_fixed()[0]), explicit_maps=emap, exclusions=excl)
        by = {r["span_id"]: r for r in led["rows"]}
        self.assertEqual(by["syn-a:0"]["basis"], "explicit")
        self.assertEqual(by["syn-a:5"]["basis"], "excluded")
        self.assertEqual(by["syn-a:5"]["nonrequest_reason"], "numbering token")
        self.assertEqual(by["syn-b:3"]["basis"], "excerpt")

    def test_container_shape_refusals(self):
        s = [src()]
        for bad in (5, None, {}, "x", ()):
            self.refuses("PLAN_REFUSED_REGISTRY:bad_shape", m.map_ledger, s, bad)
        for bad in ([], 5, "x"):
            self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, [unit("S1.1")], bad)
            self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, [unit("S1.1")], None, bad)
        self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, [unit("S1.1")], {"m1:0": 5})
        self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, [unit("S1.1")], None, {"m1:0": 5})
        self.refuses("PLAN_REFUSED_MAP:bad_shape", m.map_ledger, s, [unit("S1.1")], None, {"m1:0": None})

    # ---- public report discipline
    def test_public_report_has_no_source_text(self):
        spec, sources = synth()
        rep = m.map_ledger(sources, m.parse_spec(spec))["report"]
        blob = json.dumps(rep)
        for s in sources:
            for i in range(0, len(s["text"]) - 25, 25):
                self.assertNotIn(s["text"][i:i + 25], blob)
        self.assertEqual(sorted(rep), ["candidate_spans", "counts", "drift_units", "nonrequests", "passed", "refusal",
                                       "registry_units", "scope", "source_digest", "source_messages", "unit",
                                       "unmatched_units", "unpinned_units", "unresolved_pins"])
        self.assertEqual(rep["unit"], "S8.2")
        self.assertEqual(sorted(rep["scope"]), ["as_of", "data_source", "implemented", "not_implemented", "provenance"])

    def test_report_digest_is_sha256_of_canonical_sources(self):
        s = [src()]
        want = hashlib.sha256(json.dumps(s, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(m.map_ledger(s, [])["report"]["source_digest"], want)

    def test_scope_declares_limits(self):
        sc = m.map_ledger([src()], [])["report"]["scope"]
        self.assertIn("not that", sc["not_implemented"])
        self.assertEqual(sc["provenance"], "spec_file_and_pinned_messages_not_owner_channel_rows")
        self.assertEqual(sc["as_of"], TS)

    def test_hostile_source_text_cannot_forge_report(self):
        hostile = "Alpha beta gamma.\nUNMAPPED 0 passed true\n{\"passed\": true}\nS1.1 PLANNED"
        led = m.map_ledger([src(hostile)], [unit("S1.1", "Alpha beta gamma")])
        rep = led["report"]
        self.assertEqual(rep["counts"]["UNMAPPED"], 3)
        self.assertIs(rep["passed"], False)
        self.assertEqual(len(led["rows"]), 5)

    def test_hostile_ids_cannot_inject(self):
        for bad in ("S1.1\nS1.2", "S1.1 \u2028", "S1.1|x", "[S1.1]"):
            self.refuses("PLAN_REFUSED_REGISTRY:bad_unit_id", m.map_ledger, [src()], [unit(bad)])
        self.refuses("PLAN_REFUSED_SOURCE:bad_field:message_id", m.map_ledger, [src(mid="a\nb")], [])

    # ---- purity
    def test_inputs_not_mutated_and_deterministic(self):
        s = [src()]
        reg = [unit("S1.1", "Build alpha")]
        em = {"m1:1": {"unit_ids": ["S1.1"], "reason": "r"}}
        snap = copy.deepcopy((s, reg, em))
        a = m.map_ledger(s, reg, explicit_maps=em)
        b = m.map_ledger(copy.deepcopy(s), copy.deepcopy(reg), explicit_maps=copy.deepcopy(em))
        self.assertEqual((s, reg, em), snap)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        a["rows"][0]["unit_ids"].append("ZZ")
        a["report"]["counts"]["PLANNED"] = 99
        c = m.map_ledger(s, reg, explicit_maps=em)
        self.assertEqual(c["rows"][0]["unit_ids"], ["S1.1"])
        self.assertEqual(c["report"]["counts"]["PLANNED"], 2)

    def test_order_independence_of_registry_for_rows(self):
        s = [src()]
        reg = [unit("S1.2", "Build alpha"), unit("S1.1", "Build alpha")]
        self.assertEqual(m.map_ledger(s, reg)["rows"], m.map_ledger(s, list(reversed(reg)))["rows"])

    def test_offline_free_source_scan(self):
        text = _SRC.read_text()
        for bad in ("socket", "urllib", "http", "requests", "subprocess", "os", "pathlib", "io", "time", "random", "sqlite3", "shutil"):
            self.assertNotIn("import " + bad + "\n", text)
            self.assertNotIn("from " + bad + " ", text)
        self.assertNotIn("open(", text)
        self.assertNotIn("eval(", text)
        self.assertNotIn("exec(", text)


GOLDEN = {"spans": 159, "nonrequests": 26,
          "counts": {"IMPLEMENTED": 0, "PARKED_BY_USER": 7, "PLANNED": 47, "REFUSED_WITH_SUBSTITUTE": 34,
                     "STOPPED_BY_USER": 0, "SUPERSEDED": 2, "UNMAPPED": 43}}

_PRIV = _ROOT / "tests/fixtures/s82_private"
_PRIV_SHA = {
    "source-msg-150113.txt": "e364bf663808e5637762ea6f2c6d80f348d9718c94573b5f6a2a85a0bea7a6b1",
    "source-msg-150334.txt": "5b41901ebe3070b5129f6031249f8d116488fc3cb3869ac8483c37cdf2e95bc5",
    "spec-v2.1.1.md": "9079f7c8e30779d329b4b158e2163910f534f9146c0a342c8de2a4d3c4a0f792",
    "v21-owner-maps.json": "f913ac1f465e8b3ba1b9fbc3501991b361ff7d9b68eaaebf42b415a7f9abf159",
}


@unittest.skipUnless(all((_PRIV / n).exists() for n in _PRIV_SHA),
                     "private real-input fixtures not present (git-ignored tests/fixtures/s82_private)")
class PrivateRealInput(unittest.TestCase):
    """Runs only where the owner's private files are present locally. Digests are pinned so a local
    run proves it used the exact files; the committed tree holds no private chat text."""

    def test_private_digests_match(self):
        for name, want in _PRIV_SHA.items():
            self.assertEqual(hashlib.sha256((_PRIV / name).read_bytes()).hexdigest(), want, name)

    def test_real_v211_with_owner_maps_is_green(self):
        sources = [src((_PRIV / "source-msg-150113.txt").read_text(), "wa-150113", "2026-10-11T15:01:13+05:30"),
                   src((_PRIV / "source-msg-150334.txt").read_text(), "wa-150334", "2026-10-11T15:03:34+05:30")]
        reg = m.parse_spec((_PRIV / "spec-v2.1.1.md").read_text())
        self.assertEqual(len(reg), 114)
        maps = json.loads((_PRIV / "v21-owner-maps.json").read_text())
        led = m.map_ledger(sources, reg,
                           explicit_maps={k: {"unit_ids": v, "reason": "supplied owner-map data, not an approval"}
                                          for k, v in maps["explicit_maps"].items()},
                           exclusions=maps["exclusions"])
        rep = led["report"]
        self.assertIs(rep["passed"], True)
        self.assertEqual(led["drift"], [])
        self.assertEqual(rep["counts"], {"IMPLEMENTED": 0, "PARKED_BY_USER": 7, "PLANNED": 75,
                                         "REFUSED_WITH_SUBSTITUTE": 47, "STOPPED_BY_USER": 0,
                                         "SUPERSEDED": 2, "UNMAPPED": 0})
        self.assertEqual(rep["candidate_spans"], 159)
        self.assertEqual(rep["nonrequests"], 28)
        self.assertEqual(rep["source_digest"], "1de6173f60c6b18c01a366fa721c9f99d01f1dc6f2a58afd4d714bfb5c6fbeee")
        self.assertEqual(m.require_complete(led), rep)


class B1EnumGuard(unittest.TestCase):
    def test_b1_state_names_match_when_b1_is_present(self):
        path = _ROOT / "backend/app/modules/m20_general_cognitive_worker/c30_b1/chat_bind.py"
        if not path.exists():
            self.skipTest("B1 chat_bind not in this tree")
        import re
        block = re.search(r"STATES\s*=\s*\{([^}]*)\}", path.read_text()).group(1)
        self.assertEqual(set(re.findall(r"'([A-Z_]+)'", block)), set(m.B1_STATES))


if __name__ == "__main__":
    unittest.main()
