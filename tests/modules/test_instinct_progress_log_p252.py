"""P252|L199 progress log tests. Stdlib unittest, hermetic, no repo conftest."""
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / "backend/app/modules/instinct_doc/progress_log_p252.py"
_spec = importlib.util.spec_from_file_location("progress_log_p252", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["progress_log_p252"] = m
_spec.loader.exec_module(m)


def E(id="e1", task_id="t1", seq=0, status="started", message="m", source_ref="r"):
    return {"id": id, "task_id": task_id, "seq": seq, "status": status,
            "message": message, "source_ref": source_ref}


def build(*entries):
    log = m.create_log()
    for e in entries:
        log = m.append(log, e)
    return log


class Base(unittest.TestCase):
    def refuses(self, code, fn, *a):
        with self.assertRaises(ValueError) as cm:
            fn(*a)
        self.assertEqual(str(cm.exception), "P252:" + code)


class RoundTrip(Base):
    def test_round_trip_exact_text(self):
        log = build(E("a", "t1", 0, "started", "go", "ref1"),
                    E("b", "t1", 2, "progress", "half", "ref2"))
        self.assertEqual(m.render(log),
                         "task t1 (2 entries, open)\n0 started go [ref1]\n2 progress half [ref2]")
        self.assertEqual(m.render(log, "t1"), m.render(log))

    def test_empty_log_renders_empty_and_unknown_status(self):
        log = m.create_log()
        self.assertEqual(m.render(log), "")
        self.assertEqual(m.task_status(log, "x"), "unknown")

    def test_multi_task_isolation_and_sorting(self):
        log = build(E("a", "tb", 5), E("b", "ta", 0), E("c", "tb", 6, "note", "n", "r"))
        self.assertEqual(m.render(log),
                         "task ta (1 entries, open)\n0 started m [r]\n"
                         "task tb (2 entries, open)\n5 started m [r]\n6 note n [r]")
        self.assertEqual(m.render(log, "ta"), "task ta (1 entries, open)\n0 started m [r]")

    def test_entry_order_follows_seq_not_id(self):
        log = build(E("z", "t1", 0), E("a", "t1", 1, "note", "n", "r"))
        self.assertEqual(m.render(log), "task t1 (2 entries, open)\n0 started m [r]\n1 note n [r]")

    def test_seq_per_task_independent(self):
        log = build(E("a", "t1", 5), E("b", "t2", 0))
        self.assertEqual(m.task_status(log, "t2"), "open")

    def test_seq_strictly_increasing(self):
        log = build(E("a", "t1", 3))
        self.refuses("non_monotonic_seq:t1", m.append, log, E("b", "t1", 3))
        self.refuses("non_monotonic_seq:t1", m.append, log, E("b", "t1", 2))
        m.append(log, E("b", "t1", 4))

    def test_negative_seq_refused(self):
        self.refuses("non_monotonic_seq:t1", m.append, m.create_log(), E(seq=-1))
        m.append(m.create_log(), E(seq=0))

    def test_terminal_closure_completed_and_failed(self):
        for st in ("completed", "failed"):
            log = build(E("a", "t1", 0, st))
            self.assertEqual(m.task_status(log, "t1"), st)
            self.refuses("task_closed:t1", m.append, log, E("b", "t1", 1))
            m.append(log, E("b", "t2", 0))
            self.assertIn("(1 entries, %s)" % st, m.render(log))

    def test_non_terminal_statuses_stay_open(self):
        for st in ("started", "progress", "blocked", "note"):
            self.assertEqual(m.task_status(build(E(status=st)), "t1"), "open")

    def test_no_auto_completed(self):
        log = build(E("a", "t1", 0, "progress"))
        self.assertNotIn("completed", m.render(log))
        self.assertEqual(m.task_status(log, "t1"), "open")

    def test_duplicate_id_across_tasks(self):
        log = build(E("x", "t1", 0))
        self.refuses("duplicate_id:x", m.append, log, E("x", "t2", 0))

    def test_unknown_fields_and_missing(self):
        e = E(); e["extra"] = 1
        self.refuses("unknown_fields:entry", m.append, m.create_log(), e)
        e = E(); del e["source_ref"]
        self.refuses("empty_field:source_ref", m.append, m.create_log(), e)
        self.refuses("bad_type:entry", m.append, m.create_log(), [E()])

    def test_empty_fields(self):
        for name in ("id", "task_id", "message", "source_ref"):
            for blank in ("", "   "):
                self.refuses("empty_field:" + name, m.append, m.create_log(), E(**{name: blank}))

    def test_bad_status(self):
        self.refuses("bad_status:done", m.append, m.create_log(), E(status="done"))
        self.refuses("bad_status:Started", m.append, m.create_log(), E(status="Started"))

    def test_bad_types(self):
        mk = m.create_log()
        self.refuses("bad_type:seq", m.append, mk, E(seq=True))
        self.refuses("bad_type:seq", m.append, mk, E(seq=1.0))
        self.refuses("bad_type:seq", m.append, mk, E(seq="1"))
        self.refuses("bad_type:message", m.append, mk, E(message=None))
        for name in ("id", "task_id", "status", "message", "source_ref"):
            self.refuses("bad_type:" + name, m.append, mk, E(**{name: False}))
            self.refuses("bad_type:" + name, m.append, mk, E(**{name: 5}))

    def test_text_boundaries(self):
        for name, n in (("id", 64), ("task_id", 64), ("message", 256), ("source_ref", 128)):
            m.append(m.create_log(), E(**{name: "x" * n}))
            self.refuses("text_too_long:" + name, m.append, m.create_log(), E(**{name: "x" * (n + 1)}))

    def test_entries_per_task_boundary(self):
        log = m.create_log()
        for i in range(4096):
            log = m.append(log, E("e%d" % i, "t1", i, "progress"))
        self.assertIn("(4096 entries, open)", m.render(log))
        self.refuses("limit_exceeded:entries_per_task", m.append, log, E("z", "t1", 4096))
        m.append(log, E("z", "t2", 0))

    def test_tasks_boundary(self):
        log = m.create_log()
        for i in range(1024):
            log = m.append(log, E("e%d" % i, "t%d" % i, 0))
        self.refuses("limit_exceeded:tasks", m.append, log, E("z", "new", 0))
        m.append(log, E("z", "t0", 1))

    def test_render_unknown_task_refused(self):
        log = build(E())
        self.refuses("unknown_task:nope", m.render, log, "nope")
        self.refuses("unknown_task:nope", m.render, m.create_log(), "nope")
        self.refuses("bad_type:task_id", m.render, log, 5)
        self.refuses("bad_type:task_id", m.render, log, True)

    def test_mutation_free_append(self):
        log = build(E("a"))
        before = m.render(log)
        e = E("b", "t1", 1)
        snap = dict(e)
        new = m.append(log, e)
        self.assertEqual(e, snap)
        self.assertEqual(m.render(log), before)
        self.assertIsNot(new, log)
        self.assertEqual(len(new.entries), 2)
        self.assertEqual(len(log.entries), 1)

    def test_failed_append_leaves_log_unchanged(self):
        log = build(E("a"))
        self.refuses("duplicate_id:a", m.append, log, E("a", "t1", 1))
        self.assertEqual(len(log.entries), 1)

    def test_render_determinism(self):
        seq = [E("a", "t2", 1, "blocked", "w", "r"), E("b", "t1", 0), E("c", "t2", 4, "failed", "x", "y")]
        self.assertEqual(m.render(build(*seq)).encode(), m.render(build(*seq)).encode())

    def test_constants_pinned(self):
        self.assertEqual(m.STATUSES, ("started", "progress", "blocked", "completed", "failed", "note"))
        self.assertEqual(m.FIELDS, ("id", "task_id", "seq", "status", "message", "source_ref"))


if __name__ == "__main__":
    unittest.main()
