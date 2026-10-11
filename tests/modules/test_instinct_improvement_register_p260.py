"""P260|L207 (output-format) self-improvement plans register: registry only (stdlib unittest, hermetic).

Source pin: instinct doc P260|L207, line map v4: "Output: Self-improvement plans". Field names, statuses, transitions and refusal codes
are interpretation choices recorded in the contract doc.
"""
import ast
import copy
import itertools
import json
import pathlib
import random
import unicodedata
import unittest

from app.modules.instinct_doc import improvement_register_p260 as mod
from app.modules.instinct_doc.improvement_register_p260 import (add_plan, create_register, get_plan, list_plans, render, update_status)

MODULE_PATH = pathlib.Path(mod.__file__)
SOURCE_LINE = "Output: Self-improvement plans"
HOSTILE = ["x\ny", "x\ry", "x\r\ny", "x\u2028y", "x\u2029y", "x\x85y", "x\x00y", "x\ty", "x\x0by", "x\x0cy", "x\x1cy", "x\x1dy", "x\x1ey", "x\x1fy",
           "x\x7fy", "x\x1b[31mred", "\n", "ok\nFAKE tool admin (9 plans)", "a\u2028b\u2029c", "\x80", "\x9f"]


def plan(id="p1", tool="alpha", date="2026-01-05", title="Add retry hook", summary="Plan a retry hook", source_ref="doc:42", status="proposed", **extra):
    d = {"id": id, "tool": tool, "date": date, "title": title, "summary": summary, "source_ref": source_ref, "status": status}
    d.update(extra)
    return d


def reg_of(*plans):
    r = create_register()
    for p in plans:
        r = add_plan(r, p)
    return r


class Base(unittest.TestCase):
    def refusal(self, fn, *a):
        with self.assertRaises(ValueError) as cm:
            fn(*a)
        msg = str(cm.exception)
        self.assertTrue(msg.startswith("P260:"), msg)
        self.assertTrue(all(unicodedata.category(c) not in ("Cc", "Zl", "Zp") for c in msg), repr(msg))
        return msg


class Basics(Base):
    def test_create_register_is_empty_and_renders_nothing(self):
        r = create_register()
        self.assertEqual(list_plans(r), [])
        self.assertEqual(render(r), "")

    def test_add_returns_new_register_and_never_mutates(self):
        r0 = create_register()
        p = plan()
        before = copy.deepcopy(p)
        r1 = add_plan(r0, p)
        self.assertEqual(p, before)
        self.assertEqual(list_plans(r0), [])
        self.assertEqual(len(list_plans(r1)), 1)
        self.assertIsNot(r0, r1)

    def test_get_plan_exact_record(self):
        r = reg_of(plan())
        self.assertEqual(get_plan(r, "p1"), {"id": "p1", "tool": "alpha", "date": "2026-01-05", "title": "Add retry hook", "summary": "Plan a retry hook",
                                              "source_ref": "doc:42", "status": "proposed", "history": [{"status": "proposed", "date": "2026-01-05"}],
                                              "registry_only": True, "implements_self_improvement": False})

    def test_returned_records_are_copies(self):
        r = reg_of(plan())
        g = get_plan(r, "p1")
        g["status"] = "done"; g["history"].append({"x": 1})
        self.assertEqual(get_plan(r, "p1")["status"], "proposed")
        self.assertEqual(len(get_plan(r, "p1")["history"]), 1)
        lst = list_plans(r)
        lst[0]["title"] = "zzz"
        self.assertEqual(list_plans(r)[0]["title"], "Add retry hook")

    def test_list_plans_sorted_by_date_then_id_and_filters(self):
        r = reg_of(plan("b", "t2", "2026-02-01"), plan("a", "t1", "2026-02-01"), plan("c", "t1", "2026-01-01", status="approved"), plan("D", "t2", "2026-03-01"))
        self.assertEqual([p["id"] for p in list_plans(r)], ["c", "a", "b", "D"])
        self.assertEqual([p["id"] for p in list_plans(r, tool="t1")], ["c", "a"])
        self.assertEqual([p["id"] for p in list_plans(r, status="approved")], ["c"])
        self.assertEqual([p["id"] for p in list_plans(r, tool="t2", status="proposed")], ["b", "D"])
        self.assertEqual(list_plans(r, tool="nope"), [])
        self.assertEqual(list_plans(r, status="done"), [])

    def test_list_plans_filter_validation(self):
        r = reg_of(plan())
        self.assertEqual(self.refusal(list_plans, r, 5), "P260:bad_type:tool")
        self.assertEqual(self.refusal(list_plans, r, "t", 5), "P260:bad_type:status")
        self.assertEqual(self.refusal(list_plans, r, "t", "bogus"), "P260:bad_status:bogus")
        self.assertEqual(self.refusal(list_plans, None), "P260:bad_type:register")

    def test_order_of_adds_does_not_change_output(self):
        ps = [plan("a", "t1", "2026-01-02"), plan("b", "t2", "2026-01-01"), plan("c", "t1", "2026-01-02"), plan("d", "t3", "2025-12-31")]
        base = render(reg_of(*ps))
        for perm in itertools.permutations(ps):
            self.assertEqual(render(reg_of(*perm)), base)


class RenderFormat(Base):
    def test_exact_render(self):
        r = reg_of(plan("p2", "beta", "2026-02-01", "Second", "s2", "r2"), plan("p1", "alpha", "2026-01-05"), plan("p3", "alpha", "2026-01-05", "Other", "s3", "r3", "approved"))
        self.assertEqual(render(r), "\n".join([
            "tool alpha (2 plans)",
            "2026-01-05 p1 proposed Add retry hook - Plan a retry hook [doc:42]",
            "2026-01-05 p3 approved Other - s3 [r3]",
            "tool beta (1 plan)",
            "2026-02-01 p2 proposed Second - s2 [r2]"]))

    def test_render_single_tool_and_unknown_tool(self):
        r = reg_of(plan("p1", "alpha"), plan("p2", "beta"))
        self.assertEqual(render(r, "beta").split("\n")[0], "tool beta (1 plan)")
        self.assertEqual(len(render(r, "beta").split("\n")), 2)
        self.assertEqual(self.refusal(render, r, "gamma"), "P260:unknown_tool:gamma")
        self.assertEqual(self.refusal(render, r, 5), "P260:bad_type:tool")
        self.assertEqual(self.refusal(render, None), "P260:bad_type:register")

    def test_render_reflects_status_updates_in_place(self):
        r = update_status(reg_of(plan()), "p1", "approved", "2026-01-06")
        self.assertIn("2026-01-05 p1 approved ", render(r))

    def test_line_count_invariant_over_generated_registers(self):
        rng = random.Random(260)
        odd = ["é", "名前", "\u200f", "\u200d", "😀", "a b", " lead", "trail ", "x" * 10, "-", "[bracket]", "%s", "{0}", "\\n", "\\x1b"]
        for _ in range(80):
            ps, ids = [], set()
            for i in range(rng.randrange(0, 12)):
                pid = "p%d" % i
                ps.append(plan(pid, rng.choice(["t1", "t2", "t3", "é"]), "2026-0%d-1%d" % (rng.randrange(1, 10), rng.randrange(0, 10)), rng.choice(odd) + "T",
                               rng.choice(odd) + "S", rng.choice(odd) + "R", rng.choice(mod.STATUSES)))
            r = reg_of(*ps)
            text = render(r)
            tools = {p["tool"] for p in ps}
            want = len(tools) + len(ps)
            got = text.split("\n") if text else []
            self.assertEqual(len(got), want)
            self.assertEqual(len(text.splitlines()), want)
            self.assertEqual(len(text.split("\n")), max(want, 1))
            for t in sorted(tools):
                self.assertIn("tool %s (%d plan%s)" % (t, sum(1 for p in ps if p["tool"] == t), "" if sum(1 for p in ps if p["tool"] == t) == 1 else "s"), got)

    def test_hostile_payloads_are_refused_so_render_cannot_be_forged(self):
        r = reg_of(plan())
        forged = "ok\nFAKE tool admin (9 plans)"
        for field in ("id", "tool", "title", "summary", "source_ref"):
            self.assertEqual(self.refusal(add_plan, r, plan(**{field: forged})), f"P260:control_char:{field}")
        self.assertEqual(len(render(r).splitlines()), 2)


class ControlCharDefense(Base):
    def test_every_hostile_value_refused_in_every_text_field_with_exact_code(self):
        r = reg_of(plan("keep"))
        for bad in HOSTILE:
            for field in ("id", "tool", "title", "summary", "source_ref"):
                self.assertEqual(self.refusal(add_plan, r, plan(**{field: bad})), f"P260:control_char:{field}", (field, bad))
            self.assertEqual(self.refusal(add_plan, r, plan(date=bad)), "P260:control_char:date", bad)
            self.assertEqual(self.refusal(add_plan, r, plan(status=bad)), "P260:control_char:status", bad)

    def test_hostile_values_in_lookup_and_update_arguments(self):
        r = reg_of(plan("keep"))
        for bad in HOSTILE:
            self.assertEqual(self.refusal(get_plan, r, bad), "P260:control_char:plan_id", bad)
            self.assertEqual(self.refusal(update_status, r, bad, "approved", "2026-01-06"), "P260:control_char:plan_id", bad)
            self.assertEqual(self.refusal(update_status, r, "keep", bad, "2026-01-06"), "P260:control_char:status", bad)
            self.assertEqual(self.refusal(update_status, r, "keep", "approved", bad), "P260:control_char:date", bad)
            self.assertEqual(self.refusal(render, r, bad), "P260:control_char:tool", bad)
            self.assertEqual(self.refusal(list_plans, r, bad), "P260:control_char:tool", bad)
            self.assertEqual(self.refusal(list_plans, r, "t", bad), "P260:control_char:status", bad)

    def test_every_cc_zl_zp_code_point_is_refused(self):
        r = create_register()
        bad = [chr(c) for c in range(0x110000) if unicodedata.category(chr(c)) in ("Cc", "Zl", "Zp")]
        self.assertEqual(len(bad), 65 + 2)  # 32 C0 + DEL + 32 C1, plus U+2028 and U+2029
        for ch in bad:
            self.assertEqual(self.refusal(add_plan, r, plan(title="a" + ch + "b")), "P260:control_char:title", hex(ord(ch)))

    def test_other_unicode_is_accepted_and_does_not_add_lines(self):
        r = reg_of(plan(title="caf\u00e9 \u540d\u524d \U0001F600 \u200f\u200d \u00a0 end", summary="a\u2060b", id="\u00e9"))
        self.assertEqual(len(render(r).splitlines()), 2)

    def test_control_check_precedes_length_and_content_checks_without_echoing_payload(self):
        msg = self.refusal(add_plan, create_register(), plan(title="\n" * 500))
        self.assertEqual(msg, "P260:control_char:title")
        msg = self.refusal(add_plan, create_register(), plan(status="\n" + "x" * 500))
        self.assertEqual(msg, "P260:control_char:status")

    def test_errors_that_interpolate_values_only_carry_clean_validated_values(self):
        r = reg_of(plan("keep"))
        self.assertEqual(self.refusal(add_plan, r, plan(status="bogus")), "P260:bad_status:bogus")
        self.assertEqual(self.refusal(get_plan, r, "nope"), "P260:unknown_plan:nope")
        self.assertEqual(self.refusal(add_plan, r, plan("keep")), "P260:duplicate_id:keep")
        self.assertEqual(self.refusal(update_status, r, "keep", "done", "2026-01-06"), "P260:bad_transition:proposed>done")


class Refusals(Base):
    def test_plan_shape(self):
        r = create_register()
        for bad in (None, [], "x", 5):
            self.assertEqual(self.refusal(add_plan, r, bad), "P260:bad_type:plan")
        self.assertEqual(self.refusal(add_plan, r, plan(extra=1)), "P260:unknown_fields:plan")
        for k in ("id", "tool", "date", "title", "summary", "source_ref", "status"):
            d = plan(); del d[k]
            self.assertEqual(self.refusal(add_plan, r, d), f"P260:empty_field:{k}")
        self.assertEqual(self.refusal(add_plan, None, plan()), "P260:bad_type:register")

    def test_types_and_blank(self):
        r = create_register()
        for k in ("id", "tool", "date", "title", "summary", "source_ref", "status"):
            for bad in (5, None, ["a"], True, 1.5):
                self.assertEqual(self.refusal(add_plan, r, plan(**{k: bad})), f"P260:bad_type:{k}")
            for blank in ("", "   "):
                self.assertEqual(self.refusal(add_plan, r, plan(**{k: blank})), f"P260:empty_field:{k}")

    def test_length_bounds_n_and_n_plus_1(self):
        r = create_register()
        for field, n in (("id", 64), ("tool", 64), ("title", 128), ("summary", 256), ("source_ref", 128)):
            add_plan(r, plan(**{field: "a" * n}))
            self.assertEqual(self.refusal(add_plan, r, plan(**{field: "a" * (n + 1)})), f"P260:text_too_long:{field}")
        add_plan(r, plan(id="é" * 64))
        self.assertEqual(self.refusal(add_plan, r, plan(id="é" * 65)), "P260:text_too_long:id")

    def test_dates(self):
        r = create_register()
        for ok in ("2026-01-05", "2024-02-29", "0001-01-01", "9999-12-31"):
            add_plan(r, plan(date=ok))
        for bad in ("2026-1-5", "2026/01/05", "26-01-05", "2026-13-01", "2026-00-10", "2026-02-30", "2025-02-29", "2026-01-05T00:00:00", "2026-01-05 ", " 2026-01-05",
                    "20260105", "2026-01-005", "\u0662026-01-05", "2026-\u0660\u0661-05", "0000-01-01", "abcd-ef-gh"):
            self.assertEqual(self.refusal(add_plan, r, plan(date=bad)), "P260:bad_date", bad)

    def test_status_values(self):
        r = create_register()
        for s in mod.STATUSES:
            add_plan(r, plan(status=s))
        for bad in ("Proposed", "DONE", "complete", "completed", "x", "proposed ", " proposed"):
            self.assertEqual(self.refusal(add_plan, r, plan(status=bad)), f"P260:bad_status:{bad}")
        self.assertEqual(self.refusal(add_plan, r, plan(status="x" * 17)), "P260:text_too_long:status")
        self.assertEqual(mod.STATUSES, ("proposed", "approved", "in_progress", "done", "dropped"))

    def test_duplicate_ids_global_across_tools(self):
        r = reg_of(plan("d", "t1"))
        self.assertEqual(self.refusal(add_plan, r, plan("d", "t2")), "P260:duplicate_id:d")
        self.assertEqual(self.refusal(add_plan, r, plan("d", "t1")), "P260:duplicate_id:d")
        add_plan(r, plan("D", "t1"))

    def test_strict_types_subclasses_refused(self):
        class S(str):
            pass

        class D(dict):
            pass
        r = create_register()
        self.assertEqual(self.refusal(add_plan, r, D(plan())), "P260:bad_type:plan")
        self.assertEqual(self.refusal(add_plan, r, plan(title=S("x"))), "P260:bad_type:title")
        self.assertEqual(self.refusal(get_plan, reg_of(plan()), S("p1")), "P260:bad_type:plan_id")

    def test_check_order_in_one_plan(self):
        r = create_register()
        bad = {"id": "", "tool": 5, "date": "bad", "title": "t\n", "summary": "s", "source_ref": "r", "status": "zzz", "x": 1}
        self.assertEqual(self.refusal(add_plan, r, bad), "P260:unknown_fields:plan")
        del bad["x"]
        self.assertEqual(self.refusal(add_plan, r, bad), "P260:bad_type:tool")
        bad["tool"] = "t"
        self.assertEqual(self.refusal(add_plan, r, bad), "P260:control_char:title")
        bad["title"] = "t"
        self.assertEqual(self.refusal(add_plan, r, bad), "P260:empty_field:id")
        bad["id"] = "i"
        self.assertEqual(self.refusal(add_plan, r, bad), "P260:bad_date")
        bad["date"] = "2026-01-01"
        self.assertEqual(self.refusal(add_plan, r, bad), "P260:bad_status:zzz")

    def test_register_bounds(self):
        r = create_register()
        for i in range(mod.MAX_TOOLS):
            r = add_plan(r, plan("p%d" % i, "t%d" % i))
        self.assertEqual(self.refusal(add_plan, r, plan("extra", "newtool")), "P260:limit_exceeded:tools")
        r = add_plan(r, plan("extra", "t0"))  # existing tool is fine
        r = create_register()
        for i in range(mod.MAX_PLANS):
            r = add_plan(r, plan("p%d" % i, "t%d" % (i % 8)))
        self.assertEqual(len(list_plans(r)), mod.MAX_PLANS)
        self.assertEqual(self.refusal(add_plan, r, plan("overflow", "t0")), "P260:limit_exceeded:plans")
        self.assertEqual((mod.MAX_PLANS, mod.MAX_TOOLS), (1024, 128))


class StatusUpdates(Base):
    def test_transition_table(self):
        allowed = {("proposed", "approved"), ("proposed", "dropped"), ("approved", "in_progress"), ("approved", "dropped"), ("in_progress", "done"),
                   ("in_progress", "dropped")}
        for a, b in itertools.product(mod.STATUSES, repeat=2):
            r = reg_of(plan(status=a))
            if (a, b) in allowed:
                n = update_status(r, "p1", b, "2026-01-06")
                self.assertEqual(get_plan(n, "p1")["status"], b)
            else:
                self.assertEqual(self.refusal(update_status, r, "p1", b, "2026-01-06"), f"P260:bad_transition:{a}>{b}", (a, b))

    def test_full_lifecycle_history_and_immutability(self):
        r0 = reg_of(plan())
        r1 = update_status(r0, "p1", "approved", "2026-01-06")
        r2 = update_status(r1, "p1", "in_progress", "2026-01-06")
        r3 = update_status(r2, "p1", "done", "2026-02-01")
        self.assertEqual(get_plan(r0, "p1")["status"], "proposed")
        self.assertEqual(get_plan(r2, "p1")["status"], "in_progress")
        g = get_plan(r3, "p1")
        self.assertEqual(g["status"], "done")
        self.assertEqual(g["history"], [{"status": "proposed", "date": "2026-01-05"}, {"status": "approved", "date": "2026-01-06"},
                                        {"status": "in_progress", "date": "2026-01-06"}, {"status": "done", "date": "2026-02-01"}])
        self.assertEqual(g["date"], "2026-01-05")  # plan date never changes
        self.assertEqual(self.refusal(update_status, r3, "p1", "dropped", "2026-02-02"), "P260:bad_transition:done>dropped")

    def test_date_rules(self):
        r = reg_of(plan(date="2026-01-05"))
        self.assertEqual(self.refusal(update_status, r, "p1", "approved", "2026-01-04"), "P260:date_regression:p1")
        update_status(r, "p1", "approved", "2026-01-05")  # same day allowed
        r2 = update_status(r, "p1", "approved", "2026-03-01")
        self.assertEqual(self.refusal(update_status, r2, "p1", "in_progress", "2026-02-28"), "P260:date_regression:p1")
        update_status(r2, "p1", "in_progress", "2026-03-01")
        self.assertEqual(self.refusal(update_status, r, "p1", "approved", "2026-13-01"), "P260:bad_date")
        self.assertEqual(self.refusal(update_status, r, "p1", "approved", 5), "P260:bad_type:date")

    def test_update_argument_checks_and_order(self):
        r = reg_of(plan())
        self.assertEqual(self.refusal(update_status, None, "p1", "approved", "2026-01-06"), "P260:bad_type:register")
        self.assertEqual(self.refusal(update_status, r, 5, "approved", "2026-01-06"), "P260:bad_type:plan_id")
        self.assertEqual(self.refusal(update_status, r, "", "approved", "2026-01-06"), "P260:empty_field:plan_id")
        self.assertEqual(self.refusal(update_status, r, "zz", "approved", "2026-01-06"), "P260:unknown_plan:zz")
        self.assertEqual(self.refusal(update_status, r, "p1", "bogus", "2026-01-06"), "P260:bad_status:bogus")
        self.assertEqual(self.refusal(update_status, r, "p1", 5, "2026-01-06"), "P260:bad_type:status")
        self.assertEqual(self.refusal(update_status, r, "zz", "bogus", "bad"), "P260:bad_status:bogus")  # value checks precede lookup
        self.assertEqual(self.refusal(update_status, r, "p1", "dropped", "bad"), "P260:bad_date")

    def test_failed_update_changes_nothing(self):
        r = reg_of(plan())
        before = render(r)
        with self.assertRaises(ValueError):
            update_status(r, "p1", "done", "2026-01-06")
        self.assertEqual(render(r), before)
        self.assertEqual(get_plan(r, "p1")["status"], "proposed")

    def test_update_changes_only_target_plan(self):
        r = reg_of(plan("a", "t1"), plan("b", "t1"), plan("c", "t2"))
        n = update_status(r, "b", "dropped", "2026-01-09")
        self.assertEqual([(p["id"], p["status"]) for p in list_plans(n)], [("a", "proposed"), ("b", "dropped"), ("c", "proposed")])

    def test_register_subclass_and_update_plan_id_length(self):
        class R(mod.Register):
            pass
        r = reg_of(plan())
        self.assertEqual(self.refusal(add_plan, R(), plan()), "P260:bad_type:register")
        self.assertEqual(self.refusal(update_status, r, "x" * 65, "approved", "2026-01-06"), "P260:text_too_long:plan_id")
        self.assertEqual(self.refusal(update_status, r, "x" * 64, "approved", "2026-01-06"), "P260:unknown_plan:" + "x" * 64)

    def test_get_plan_errors(self):
        r = reg_of(plan())
        self.assertEqual(self.refusal(get_plan, r, 5), "P260:bad_type:plan_id")
        self.assertEqual(self.refusal(get_plan, r, "  "), "P260:empty_field:plan_id")
        self.assertEqual(self.refusal(get_plan, None, "p1"), "P260:bad_type:register")
        self.assertEqual(self.refusal(get_plan, r, "x" * 65), "P260:text_too_long:plan_id")


class Hygiene(Base):
    def test_deterministic_and_json_serialisable(self):
        ps = [plan("b", "t2", "2026-01-01"), plan("a", "t1", "2026-01-02")]
        a, b = reg_of(*ps), reg_of(*copy.deepcopy(ps))
        self.assertEqual(render(a), render(b))
        self.assertEqual(json.dumps(list_plans(a), sort_keys=True), json.dumps(list_plans(b), sort_keys=True))

    def test_generated_corpus_matches_independent_model(self):
        rng = random.Random(26007)
        trans = {"proposed": ["approved", "dropped"], "approved": ["in_progress", "dropped"], "in_progress": ["done", "dropped"], "done": [], "dropped": []}
        for _ in range(60):
            model, r = {}, create_register()
            for step in range(rng.randrange(1, 40)):
                if not model or rng.random() < 0.5:
                    pid = "p%d" % rng.randrange(0, 30)
                    p = plan(pid, rng.choice(["t1", "t2", "t3"]), "2026-01-%02d" % rng.randrange(1, 29), "T%d" % step, "S", "R")
                    try:
                        r = add_plan(r, p)
                        self.assertNotIn(pid, model)
                        model[pid] = {"p": p, "status": "proposed", "last": p["date"]}
                    except ValueError as e:
                        self.assertEqual(str(e), "P260:duplicate_id:" + pid)
                        self.assertIn(pid, model)
                else:
                    pid = rng.choice(sorted(model))
                    st = rng.choice(mod.STATUSES)
                    day = "2026-01-%02d" % rng.randrange(1, 29)
                    m = model[pid]
                    try:
                        r = update_status(r, pid, st, day)
                    except ValueError as e:
                        if st not in trans[m["status"]]:
                            self.assertEqual(str(e), "P260:bad_transition:%s>%s" % (m["status"], st))
                        else:
                            self.assertEqual(str(e), "P260:date_regression:" + pid)
                            self.assertLess(day, m["last"])
                    else:
                        self.assertIn(st, trans[m["status"]])
                        self.assertGreaterEqual(day, m["last"])
                        m["status"], m["last"] = st, day
            got = {p["id"]: p["status"] for p in list_plans(r)}
            self.assertEqual(got, {k: v["status"] for k, v in model.items()})
            lines = render(r).split("\n") if model else []
            self.assertEqual(len(lines), len({v["p"]["tool"] for v in model.values()}) + len(model))

    def test_source_line_and_pin_in_doc_and_ic_tags(self):
        doc = (MODULE_PATH.parents[4] / "docs" / "INSTINCT_P260_L207_IMPROVEMENT_REGISTER_CONTRACT.md").read_text(encoding="utf-8")
        first = doc.splitlines()[0:6]
        self.assertTrue(any(SOURCE_LINE in line for line in first), first)
        self.assertIn("Source pin: instinct doc P260|L207, line map v4", doc)
        self.assertIn("P61", doc)
        self.assertGreaterEqual(doc.count("INTERPRETATION CHOICE"), 6)
        self.assertIn("P260|L207", MODULE_PATH.read_text(encoding="utf-8")[:600])
        self.assertIn("P260|L207", pathlib.Path(__file__).read_text(encoding="utf-8")[:600])

    def test_module_is_pure_stdlib_no_io_no_clock(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imported.add((n.module or "").split(".")[0])
        self.assertLessEqual(imported, {"__future__", "dataclasses", "datetime", "re", "unicodedata", "typing"})
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for banned in ("open", "eval", "exec", "compile", "__import__", "input", "print", "time", "today", "now", "random", "os", "socket", "importlib", "subprocess", "getattr"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
