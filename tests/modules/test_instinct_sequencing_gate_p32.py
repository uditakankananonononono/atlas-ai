"""P32|L32 M30 sequencing gate: blocks a task-31 start until tasks 1..27 carry complete marks.

Source pin: instinct doc P32|L32, line map v4 (row text relayed by the integrator).
Offline, stdlib only. The gate composes P246 (coverage), P243 (audit ledger) and P247
(release gate) by import; these tests check the composition, not those modules' internals.
"""
import ast
import copy
import enum
import importlib.util
import random
import re
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PATH = _ROOT / "backend/app/modules/instinct_doc/sequencing_gate_p32.py"
_DOC = _ROOT / "docs/INSTINCT_P32_L32_SEQUENCING_GATE_CONTRACT.md"


def _load():
    if not _PATH.exists():
        raise ModuleNotFoundError("sequencing_gate_p32 missing", name="sequencing_gate_p32")
    spec = importlib.util.spec_from_file_location("sequencing_gate_p32_under_test", _PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


G = _load()
TASKS = list(range(1, 28))
CONTROL = ["\x00", "\n", "\r", "\t", "\x1b", "\x7f", "\x85", "\u2028", "\u2029"]


def lid(n):
    return f"P{n + 2}|L{n + 2}"


def base_request(skip_evidence=(), skip_audit=(), marks=None, skip_tasks=()):
    marks = marks or {}
    rows = [{"P": n + 2, "L": n + 2, "class": "NON-SCIENCE", "mission": f"M{n}", "summary": f"task {n}"}
            for n in TASKS]
    rows.append({"P": 33, "L": 33, "class": "NON-SCIENCE", "mission": "M31", "summary": "claire"})
    ev = [{"line_id": lid(n), "status": "COVERED_BY_DECLARATION", "evidence_ref": f"ref-{n}",
           "declared_at": "2026-10-11T10:00:00Z", "source": "audit"}
          for n in TASKS if n not in skip_evidence]
    au = [{"id": f"a{n}", "project_id": f"task-{n}", "requirement_ref": "complete",
           "mark": marks.get(n, "pass"), "evidence_ref": f"audit-{n}"}
          for n in TASKS if n not in skip_audit]
    tasks = [{"task": n, "line_id": lid(n)} for n in TASKS if n not in skip_tasks]
    return {"line_map": rows, "evidence": ev, "audit_entries": au, "tasks": tasks, "start_task": 31}


def refusal(req):
    with unittest.TestCase().assertRaises(ValueError) as cm:
        G.check_sequencing_gate(req)
    return str(cm.exception)


def oracle(req):
    """Independent re-implementation of the declared rule, written from the contract."""
    covered, uncovered = set(), set()
    for e in req["evidence"]:
        (covered if e["status"] == "COVERED_BY_DECLARATION" else uncovered).add(e["line_id"])
    marks = {}
    for a in req["audit_entries"]:
        marks.setdefault(a["project_id"], []).append(a["mark"])
    mapped = {t["task"]: t["line_id"] for t in req["tasks"]}
    rowids = {f"P{r['P']}|L{r['L']}" for r in req["line_map"]}
    out = {}
    for n in TASKS:
        why = []
        if n not in mapped:
            why.append("unmapped")
        else:
            if mapped[n] not in rowids:
                why.append("line_not_in_map")
            elif mapped[n] not in covered or mapped[n] in uncovered:
                why.append("line_not_covered")
            m = marks.get(f"task-{n}")
            if not m:
                why.append("no_audit_entry")
            elif any(x != "pass" for x in m):
                why.append("audit_not_pass")
        out[n] = why
    return out


class KnownAnswers(unittest.TestCase):
    def test_all_complete_opens(self):
        r = G.check_sequencing_gate(base_request())
        self.assertEqual(r["verdict"], "GATE_OPEN")
        self.assertIs(r["start_allowed"], True)
        self.assertEqual(r["target_task"], 31)
        self.assertEqual(r["required_tasks"], TASKS)
        self.assertEqual(r["complete_tasks"], TASKS)
        self.assertEqual(r["blocked_tasks"], [])
        self.assertEqual(r["action"], "none")
        self.assertEqual(r["source_lines"], ["P32|L32"])
        self.assertEqual(r["counts"], {"required": 27, "complete": 27, "blocked": 0})

    def test_each_task_alone_blocks_on_missing_evidence(self):
        for n in TASKS:
            with self.subTest(task=n):
                r = G.check_sequencing_gate(base_request(skip_evidence=(n,)))
                self.assertEqual(r["verdict"], "GATE_BLOCKED")
                self.assertIs(r["start_allowed"], False)
                self.assertEqual(r["blocked_tasks"], [{"task": n, "reasons": ["line_not_covered"]}])
                self.assertEqual(r["complete_tasks"], [t for t in TASKS if t != n])
                self.assertEqual(r["release_decision"]["blocked_by"], ["task_marks"])

    def test_each_task_alone_blocks_on_missing_audit(self):
        for n in TASKS:
            with self.subTest(task=n):
                r = G.check_sequencing_gate(base_request(skip_audit=(n,)))
                self.assertEqual(r["blocked_tasks"], [{"task": n, "reasons": ["no_audit_entry"]}])

    def test_fail_and_pending_marks_block(self):
        for mark in ("fail", "pending"):
            r = G.check_sequencing_gate(base_request(marks={17: mark}))
            self.assertEqual(r["blocked_tasks"], [{"task": 17, "reasons": ["audit_not_pass"]}])

    def test_unmapped_tasks_block_not_refuse(self):
        r = G.check_sequencing_gate(base_request(skip_tasks=(1, 27)))
        self.assertEqual(r["verdict"], "GATE_BLOCKED")
        self.assertEqual([b["task"] for b in r["blocked_tasks"]], [1, 27])
        self.assertTrue(all(b["reasons"] == ["unmapped"] for b in r["blocked_tasks"]))

    def test_no_tasks_at_all_is_blocked(self):
        req = base_request()
        req["tasks"] = []
        r = G.check_sequencing_gate(req)
        self.assertEqual(r["counts"], {"required": 27, "complete": 0, "blocked": 27})
        self.assertIs(r["start_allowed"], False)

    def test_line_not_in_map(self):
        req = base_request()
        req["tasks"][3]["line_id"] = "P999|L999"
        r = G.check_sequencing_gate(req)
        self.assertEqual(r["blocked_tasks"], [{"task": 4, "reasons": ["line_not_in_map"]}])

    def test_conflicting_declaration_blocks(self):
        req = base_request()
        req["evidence"].append({"line_id": lid(9), "status": "UNCOVERED", "evidence_ref": "",
                                "declared_at": "2026-10-11T11:00:00Z", "source": "audit"})
        r = G.check_sequencing_gate(req)
        self.assertEqual(r["blocked_tasks"], [{"task": 9, "reasons": ["line_not_covered"]}])

    def test_both_reasons_listed_in_fixed_order(self):
        r = G.check_sequencing_gate(base_request(skip_evidence=(6,), skip_audit=(6,)))
        self.assertEqual(r["blocked_tasks"], [{"task": 6, "reasons": ["line_not_covered", "no_audit_entry"]}])

    def test_duplicate_row_target_is_not_covered(self):
        req = base_request()
        req["line_map"][0]["dup_of"] = "P33|L33"
        r = G.check_sequencing_gate(req)
        self.assertEqual(r["blocked_tasks"], [{"task": 1, "reasons": ["line_not_covered"]}])

    def test_marks_for_other_projects_are_ignored(self):
        req = base_request(skip_audit=(12,))
        for pid in ("task-0", "task-28", "task-31", "task-12x", "other"):
            req["audit_entries"].append({"id": "x" + pid, "project_id": pid, "requirement_ref": "complete",
                                         "mark": "pass", "evidence_ref": "e"})
        r = G.check_sequencing_gate(req)
        self.assertEqual(r["blocked_tasks"], [{"task": 12, "reasons": ["no_audit_entry"]}])

    def test_task31_and_task28_marks_do_not_open_anything(self):
        req = base_request(skip_audit=tuple(TASKS))
        req["audit_entries"] = [{"id": "z", "project_id": "task-28", "requirement_ref": "c", "mark": "pass",
                                 "evidence_ref": "e"}]
        self.assertIs(G.check_sequencing_gate(req)["start_allowed"], False)

    def test_optional_evidence_and_audit_default_empty(self):
        req = base_request()
        del req["evidence"], req["audit_entries"]
        r = G.check_sequencing_gate(req)
        self.assertEqual(r["counts"]["complete"], 0)


class Composition(unittest.TestCase):
    def test_release_decision_is_p247_output(self):
        r = G.check_sequencing_gate(base_request())
        d = r["release_decision"]
        self.assertEqual(d["feature"], "candy_gate_p247")
        self.assertIs(d["release"], True)
        self.assertEqual(d["gates"], [{"id": "task_marks", "kind": "all_present", "state": "GREEN",
                                       "reason": "declared_condition_met"}])
        self.assertEqual(d["action"], "none")

    def test_blocked_decision_names_missing_tasks(self):
        d = G.check_sequencing_gate(base_request(skip_audit=(4, 8)))["release_decision"]
        self.assertIs(d["release"], False)
        self.assertEqual(d["gates"][0]["reason"], "missing_items:task-4,task-8")

    def test_siblings_are_imported_not_copied(self):
        src = _PATH.read_text()
        for needle in ("def evaluate", "def compute_line_coverage", "def add_entry", "def create_ledger",
                       "COVERED_BY_DECLARATION =", "class AuditLedger"):
            self.assertNotIn(needle, src)
        for name in ("line_coverage_p246", "audit_round_p243", "candy_gate_p247"):
            self.assertIn(name, src)

    def test_coverage_conflict_logic_comes_from_p246(self):
        sib = G._sibling("line_coverage_p246")
        self.assertTrue(hasattr(sib, "compute_line_coverage"))
        self.assertIs(G._sibling("line_coverage_p246"), sib)  # cached, one copy


class Refusals(unittest.TestCase):
    def test_codes(self):
        cases = [
            ([], "P32:bad_type:request"),
            ("x", "P32:bad_type:request"),
            (None, "P32:bad_type:request"),
        ]
        for req, code in cases:
            self.assertEqual(refusal(req), code)
        req = base_request()
        req["status"] = "done"
        self.assertEqual(refusal(req), "P32:unknown_field:request")
        for f in ("line_map", "tasks", "start_task"):
            req = base_request()
            del req[f]
            self.assertEqual(refusal(req), "P32:missing_field:" + f)
        for f, bad in (("tasks", {}), ("tasks", "x"), ("evidence", {}), ("audit_entries", ()), ("line_map", {})):
            req = base_request()
            req[f] = bad
            self.assertEqual(refusal(req), "P32:bad_type:" + f)

    def test_start_task_must_be_exactly_31(self):
        for bad in (30, 32, 0, -31, True, "31", 31.0, None, [31]):
            req = base_request()
            req["start_task"] = bad
            self.assertEqual(refusal(req), "P32:bad_target", msg=repr(bad))

    def test_task_number_bounds(self):
        for n in (0, -1, 28, 29, 30, 31, 10 ** 9):
            req = base_request()
            req["tasks"][0]["task"] = n
            self.assertEqual(refusal(req), "P32:bad_task_number", msg=n)
        for bad in (True, "2", 2.0, None):
            req = base_request()
            req["tasks"][0]["task"] = bad
            self.assertEqual(refusal(req), "P32:bad_task_number", msg=repr(bad))
        for n in (1, 27):
            req = base_request()
            req["tasks"] = [{"task": n, "line_id": lid(n)}]
            self.assertEqual(G.check_sequencing_gate(req)["counts"]["required"], 27)

    def test_task_count_bound_27_ok_28_refused(self):
        req = base_request()
        self.assertEqual(len(req["tasks"]), 27)
        G.check_sequencing_gate(req)
        req["tasks"].append({"task": 2, "line_id": lid(2)})
        self.assertEqual(refusal(req), "P32:limit_exceeded:tasks")

    def test_bad_task_items(self):
        for item, code in (
            ("x", "P32:bad_type:tasks"),
            ({"task": 2}, "P32:missing_field:tasks"),
            ({"line_id": lid(2)}, "P32:missing_field:tasks"),
            ({"task": 2, "line_id": lid(2), "done": True}, "P32:unknown_field:tasks"),
            ({"task": 2, "line_id": 5}, "P32:bad_line_id"),
            ({"task": 2, "line_id": "P4|L4 "}, "P32:bad_line_id"),
            ({"task": 2, "line_id": "p4|l4"}, "P32:bad_line_id"),
            ({"task": 2, "line_id": "P04|L4"}, "P32:bad_line_id"),
            ({"task": 2, "line_id": ""}, "P32:bad_line_id"),
        ):
            req = base_request()
            req["tasks"] = [item]
            self.assertEqual(refusal(req), code, msg=repr(item))

    def test_duplicates(self):
        req = base_request()
        req["tasks"][1]["task"] = 1
        self.assertEqual(refusal(req), "P32:duplicate_task")
        req = base_request()
        req["tasks"][1]["line_id"] = req["tasks"][0]["line_id"]
        self.assertEqual(refusal(req), "P32:duplicate_line")

    def test_sibling_refusals_are_wrapped_without_echo(self):
        req = base_request()
        req["line_map"].append(dict(req["line_map"][0]))
        self.assertEqual(refusal(req), "P32:coverage_refused")
        req = base_request()
        req["evidence"][0]["status"] = "SECRETVALUE"
        m = refusal(req)
        self.assertEqual(m, "P32:coverage_refused")
        req = base_request()
        req["audit_entries"][0]["mark"] = "SECRETMARK"
        self.assertEqual(refusal(req), "P32:audit_refused:bad_mark")
        req = base_request()
        req["audit_entries"].append(dict(req["audit_entries"][0]))
        self.assertEqual(refusal(req), "P32:audit_refused:duplicate_id")

    def test_all_codes_prefixed(self):
        for req in ([], {"x": 1}, {**base_request(), "start_task": 1}):
            self.assertTrue(refusal(req).startswith("P32:"))


class StrictTypes(unittest.TestCase):
    def test_subclasses_refused(self):
        class D(dict):
            pass

        class L(list):
            pass

        class S(str):
            pass

        class I(int):
            pass

        class E(enum.IntEnum):
            T = 2

        self.assertEqual(refusal(D(base_request())), "P32:bad_type:request")
        for f in ("tasks", "evidence", "audit_entries", "line_map"):
            req = base_request()
            req[f] = L(req[f])
            self.assertEqual(refusal(req), "P32:bad_type:" + f)
        req = base_request()
        req["tasks"][0] = D(req["tasks"][0])
        self.assertEqual(refusal(req), "P32:bad_type:tasks")
        req = base_request()
        req["tasks"][0]["line_id"] = S(req["tasks"][0]["line_id"])
        self.assertEqual(refusal(req), "P32:bad_type:tasks")
        req = base_request()
        req["tasks"][0]["task"] = I(2)
        self.assertEqual(refusal(req), "P32:bad_type:tasks")
        req = base_request()
        req["tasks"][0]["task"] = E.T
        self.assertEqual(refusal(req), "P32:bad_type:tasks")
        req = base_request()
        req["start_task"] = I(31)
        self.assertEqual(refusal(req), "P32:bad_type:start_task")
        req = base_request()
        req["audit_entries"][0]["mark"] = S("pass")
        self.assertEqual(refusal(req), "P32:bad_type:audit_entries")
        req = base_request()
        req["line_map"][0]["summary"] = S("x")
        self.assertEqual(refusal(req), "P32:bad_type:line_map")
        req = base_request()
        req["evidence"][0][S("source")] = req["evidence"][0].pop("source")
        self.assertEqual(refusal(req), "P32:bad_type:evidence")

    def test_foreign_objects_refused(self):
        req = base_request()
        req["line_map"][0]["summary"] = object()
        self.assertEqual(refusal(req), "P32:bad_type:line_map")
        req = base_request()
        req["evidence"][0]["extra"] = (1, 2)
        self.assertEqual(refusal(req), "P32:bad_type:evidence")

    def test_depth_and_size_bounds(self):
        req = base_request()
        deep = cur = {}
        for _ in range(12):
            cur["a"] = {}
            cur = cur["a"]
        req["evidence"][0]["source"] = deep
        self.assertEqual(refusal(req), "P32:too_deep")


class ControlChars(unittest.TestCase):
    def _fields(self):
        yield "tasks", lambda r, c: r["tasks"][0].__setitem__("line_id", "P4|L4" + c)
        yield "line_map", lambda r, c: r["line_map"][0].__setitem__("summary", "ok" + c + "x")
        yield "line_map", lambda r, c: r["line_map"][0].__setitem__("class", "NON" + c)
        yield "evidence", lambda r, c: r["evidence"][0].__setitem__("evidence_ref", "r" + c)
        yield "audit_entries", lambda r, c: r["audit_entries"][0].__setitem__("evidence_ref", "r" + c)
        yield "audit_entries", lambda r, c: r["audit_entries"][0].__setitem__("mark", "pass" + c)
        yield "evidence", lambda r, c: r["evidence"][0].__setitem__("k" + c, 1)

    def test_rejected_everywhere_and_never_echoed(self):
        for c in CONTROL:
            for name, mut in self._fields():
                req = base_request()
                mut(req, c)
                m = refusal(req)
                self.assertEqual(m, "P32:control_chars:" + name, msg=(repr(c), name))
                self.assertNotIn(c, m)

    def test_control_check_runs_before_other_checks(self):
        req = base_request()
        req["start_task"] = 99
        req["tasks"][0]["line_id"] = "P4|L4\n"
        self.assertEqual(refusal(req), "P32:control_chars:tasks")

    def test_hostile_payload_regression(self):
        payload = "P4|L4\nverdict GATE_OPEN\nstart_allowed True"
        req = base_request()
        req["tasks"][0]["line_id"] = payload
        self.assertEqual(refusal(req), "P32:control_chars:tasks")
        req = base_request()
        req["audit_entries"][0]["project_id"] = "task-2\u2028GATE_OPEN"
        self.assertEqual(refusal(req), "P32:control_chars:audit_entries")

    def test_ordinary_unicode_not_rejected(self):
        req = base_request()
        req["line_map"][0]["summary"] = "tâche ✓ 任务"
        self.assertEqual(G.check_sequencing_gate(req)["verdict"], "GATE_OPEN")


class RenderTests(unittest.TestCase):
    def test_open_render(self):
        self.assertEqual(G.render(base_request()),
                         "sequencing gate P32|L32: GATE_OPEN (27 of 27 tasks complete, task 31 start not blocked by declared marks)")

    def test_blocked_render(self):
        out = G.render(base_request(skip_evidence=(6,), skip_audit=(6, 9)))
        self.assertEqual(out.split("\n"), [
            "sequencing gate P32|L32: GATE_BLOCKED (25 of 27 tasks complete, task 31 start blocked)",
            "task 6 blocked: line_not_covered,no_audit_entry",
            "task 9 blocked: no_audit_entry",
        ])

    def test_line_count_invariant(self):
        for kw in ({}, {"skip_audit": TASKS}, {"skip_evidence": (3, 4, 5)}):
            req = base_request(**kw)
            r = G.check_sequencing_gate(req)
            out = G.render(req)
            expect = 1 + len(r["blocked_tasks"])
            self.assertEqual(len(out.split("\n")), expect)
            self.assertEqual(len(out.splitlines()), expect)

    def test_render_refuses_like_check(self):
        self.assertEqual(refusal_render([]), "P32:bad_type:request")


def refusal_render(req):
    with unittest.TestCase().assertRaises(ValueError) as cm:
        G.render(req)
    return str(cm.exception)


class Properties(unittest.TestCase):
    def test_determinism_and_order_independence(self):
        req = base_request(skip_evidence=(5,), skip_audit=(7,))
        a = G.check_sequencing_gate(req)
        self.assertEqual(a, G.check_sequencing_gate(copy.deepcopy(req)))
        rnd = random.Random(32)
        for _ in range(20):
            r2 = copy.deepcopy(req)
            for k in ("tasks", "evidence", "audit_entries", "line_map"):
                rnd.shuffle(r2[k])
            self.assertEqual(G.check_sequencing_gate(r2), a)

    def test_input_not_mutated(self):
        req = base_request(skip_evidence=(5,))
        snap = copy.deepcopy(req)
        G.check_sequencing_gate(req)
        G.render(req)
        self.assertEqual(req, snap)

    def test_result_is_fresh_each_call(self):
        req = base_request()
        a = G.check_sequencing_gate(req)
        a["verdict"] = "tampered"
        a["release_decision"]["release"] = False
        self.assertEqual(G.check_sequencing_gate(req)["verdict"], "GATE_OPEN")
        self.assertIs(G.check_sequencing_gate(req)["release_decision"]["release"], True)

    def test_oracle_corpus(self):
        rnd = random.Random(3232)
        for i in range(300):
            skip_e = tuple(n for n in TASKS if rnd.random() < 0.12)
            skip_a = tuple(n for n in TASKS if rnd.random() < 0.12)
            skip_t = tuple(n for n in TASKS if rnd.random() < 0.08)
            marks = {n: rnd.choice(["fail", "pending"]) for n in TASKS if rnd.random() < 0.1}
            req = base_request(skip_e, skip_a, marks, skip_t)
            if rnd.random() < 0.3:
                n = rnd.choice(TASKS)
                req["evidence"].append({"line_id": lid(n), "status": "UNCOVERED", "evidence_ref": "",
                                        "declared_at": "2026-10-11T11:00:00Z", "source": "audit"})
            exp = oracle(req)
            r = G.check_sequencing_gate(req)
            got = {b["task"]: b["reasons"] for b in r["blocked_tasks"]}
            self.assertEqual(got, {n: w for n, w in exp.items() if w}, msg=i)
            self.assertEqual(r["start_allowed"], not got)
            self.assertEqual(r["complete_tasks"], [n for n in TASKS if not exp[n]])

    def test_honesty_flags(self):
        r = G.check_sequencing_gate(base_request())
        self.assertEqual(r["claims"], {
            "basis": "declared marks and evidence records only; nothing was read or checked",
            "task_work_done": False, "marks_truth_verified": False, "task31_started": False,
            "candy_line_sent": False, "universal_closure": False})
        self.assertIsInstance(r["method_limits"], str)
        self.assertIn("GATE_OPEN", r["method_limits"])
        self.assertEqual(r["action"], "none")

    def test_result_keys(self):
        r = G.check_sequencing_gate(base_request())
        self.assertEqual(sorted(r), sorted([
            "feature", "source_lines", "verdict", "start_allowed", "target_task", "required_tasks",
            "complete_tasks", "blocked_tasks", "counts", "release_decision", "claims", "method_limits",
            "action"]))
        self.assertEqual(r["feature"], "sequencing_gate_p32")


class Bounds(unittest.TestCase):
    def _nest(self, k):
        v = 1
        for _ in range(k):
            v = [v]
        return v

    def test_depth_exact_bounds(self):
        G._scan(self._nest(8), "f", 0, [0])
        with self.assertRaises(ValueError) as cm:
            G._scan(self._nest(9), "f", 0, [0])
        self.assertEqual(str(cm.exception), "P32:too_deep")

    def test_node_budget_exact_bounds(self):
        G._scan(1, "f", 0, [G.MAX_NODES - 1])
        with self.assertRaises(ValueError) as cm:
            G._scan(1, "f", 0, [G.MAX_NODES])
        self.assertEqual(str(cm.exception), "P32:too_deep")
        b = [0]
        G._scan([1, 2, 3], "f", 0, b)
        self.assertEqual(b[0], 4)

    def test_depth_bound_through_public_entry(self):
        req = base_request()
        req["evidence"] = self._nest(8)
        self.assertEqual(refusal(req), "P32:coverage_refused")
        req["evidence"] = self._nest(9)
        self.assertEqual(refusal(req), "P32:too_deep")

    def test_mixed_marks_for_one_task_block(self):
        req = base_request()
        req["audit_entries"].append({"id": "extra", "project_id": "task-8", "requirement_ref": "second",
                                     "mark": "fail", "evidence_ref": "e"})
        r = G.check_sequencing_gate(req)
        self.assertEqual(r["blocked_tasks"], [{"task": 8, "reasons": ["audit_not_pass"]}])

    def test_science_class_task_lines_are_checked_and_accepted(self):
        req = base_request()
        req["line_map"][2]["class"] = "SCIENCE"
        self.assertEqual(G.check_sequencing_gate(req)["verdict"], "GATE_OPEN")
        req["evidence"] = [e for e in req["evidence"] if e["line_id"] != lid(3)]
        self.assertEqual(G.check_sequencing_gate(req)["blocked_tasks"],
                         [{"task": 3, "reasons": ["line_not_covered"]}])

    def test_asymmetric_p_and_l_and_string_numbers(self):
        req = base_request()
        req["line_map"][0]["P"], req["line_map"][0]["L"] = 4, 91
        req["tasks"][0]["line_id"] = "P4|L91"
        req["evidence"][0]["line_id"] = "P4|L91"
        self.assertEqual(G.check_sequencing_gate(req)["verdict"], "GATE_OPEN")
        req["line_map"][0]["P"], req["line_map"][0]["L"] = "4", "91"
        self.assertEqual(G.check_sequencing_gate(req)["verdict"], "GATE_OPEN")
        req["tasks"][0]["line_id"] = "P91|L4"
        self.assertEqual(G.check_sequencing_gate(req)["blocked_tasks"],
                         [{"task": 1, "reasons": ["line_not_in_map"]}])

    def test_result_lists_are_not_shared_constants(self):
        r = G.check_sequencing_gate(base_request())
        r["required_tasks"].append(99)
        r["source_lines"].append("x")
        r2 = G.check_sequencing_gate(base_request())
        self.assertEqual(r2["required_tasks"], TASKS)
        self.assertEqual(r2["source_lines"], ["P32|L32"])
        self.assertEqual(G.REQUIRED_TASKS, TASKS)
        self.assertEqual(G.SOURCE_LINES, ["P32|L32"])


class Purity(unittest.TestCase):
    def test_ast_purity(self):
        tree = ast.parse(_PATH.read_text())
        allowed = {"__future__", "importlib.util", "re", "sys", "unicodedata", "pathlib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertIn(a.name, allowed)
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, {"open", "eval", "exec", "compile", "print", "input", "__import__",
                                           "globals", "locals", "getattr", "setattr"})
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, {"system", "popen", "urlopen", "connect", "write_text",
                                             "write_bytes", "open", "unlink", "mkdir", "environ",
                                             "now", "time", "random"})
        self.assertNotIn("subprocess", _PATH.read_text())

    def test_sibling_loading_is_file_pinned(self):
        src = _PATH.read_text()
        self.assertIn("spec_from_file_location", src)
        self.assertNotIn("import_module", src)


class DocTests(unittest.TestCase):
    def setUp(self):
        self.doc = _DOC.read_text()

    def test_opens_with_source_pin(self):
        first = self.doc.lstrip().split("\n")
        self.assertTrue(first[0].startswith("# "))
        head = "\n".join(first[:12])
        self.assertIn("Sequencing: after all prior tasks are done, proceed to the last task "
                      "(transitional, no standalone deliverable)", head)
        self.assertIn("Source pin: instinct doc P32|L32, line map v4", head)

    def test_provenance_and_ambiguities_disclosed(self):
        for needle in ("I did not see the original instinct doc", "FREE", "missions 1-27", "tasks 1-27",
                       "P246", "P243", "P247"):
            self.assertIn(needle, self.doc)

    def test_interpretation_choices_tagged(self):
        self.assertGreaterEqual(self.doc.count("INTERPRETATION CHOICE"), 6)

    def test_refusal_codes_documented(self):
        for code in re.findall(r'"(P32:[a-z_:]+)"', _PATH.read_text()):
            self.assertIn(code.rstrip(":"), self.doc)


if __name__ == "__main__":
    unittest.main()
