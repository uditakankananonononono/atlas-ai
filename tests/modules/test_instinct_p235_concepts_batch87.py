"""Tests for P235 concepts batch 87 (operation-log simulations)."""

import random
import unittest
from collections import deque

from app.modules.instinct_doc import p235_concepts_batch87 as m
from app.modules.instinct_doc import p235_concepts_registry as reg

MAX_ITEMS = reg.MAX_ITEMS


def refusal(code):
    return "P235:" + code


class TestBrowserHistoryLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.browser_history_log(
            "a.com",
            [["visit", "b.com"], ["visit", "c.com"], ["back", 1],
             ["visit", "d.com"], ["forward", 1], ["back", 2]]),
            ["b.com", "c.com", "b.com", "d.com", "d.com", "a.com"])
        self.assertEqual(m.browser_history_log(
            "h", [["back", 5]]), ["h"])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.browser_history_log("h", [["visit"]])
        self.assertEqual(str(ctx.exception),
                         refusal("browser_history_log:bad_shape:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.browser_history_log("h", [["jump", "x"]])
        self.assertEqual(str(ctx.exception),
                         refusal("browser_history_log:bad_value:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.browser_history_log("h", [["back", 0]])
        self.assertEqual(str(ctx.exception),
                         refusal("browser_history_log:out_of_range:ops[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.browser_history_log("", [["back", 1]])
        self.assertEqual(str(ctx.exception),
                         refusal("browser_history_log:empty:homepage"))

    def test_oracle(self):
        def oracle(homepage, ops):
            back_stack = []
            forward_stack = []
            current = homepage
            out = []
            for op in ops:
                if op[0] == "visit":
                    back_stack.append(current)
                    current = op[1]
                    forward_stack = []
                elif op[0] == "back":
                    for _ in range(min(op[1], len(back_stack))):
                        forward_stack.append(current)
                        current = back_stack.pop()
                else:
                    for _ in range(min(op[1], len(forward_stack))):
                        back_stack.append(current)
                        current = forward_stack.pop()
                out.append(current)
            return out
        rng = random.Random(8701)
        for _ in range(60):
            pages = ["p%d" % i for i in range(6)]
            ops = []
            for _ in range(rng.randint(1, 12)):
                cmd = rng.choice(["visit", "back", "forward"])
                if cmd == "visit":
                    ops.append(["visit", rng.choice(pages)])
                else:
                    ops.append([cmd, rng.randint(1, 5)])
            self.assertEqual(m.browser_history_log("home", ops),
                             oracle("home", ops))


class TestMinStackOps(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.min_stack_ops(
            [["push", 3], ["push", 1], ["get_min"], ["pop"],
             ["get_min"]]), [1, 3])
        self.assertEqual(m.min_stack_ops(
            [["push", -5], ["push", -2], ["get_min"]]), [-5])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.min_stack_ops([["pop"]])
        self.assertEqual(str(ctx.exception),
                         refusal("min_stack_ops:bad_state:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.min_stack_ops([["get_min"]])
        self.assertEqual(str(ctx.exception),
                         refusal("min_stack_ops:bad_state:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.min_stack_ops([["push", "x"]])
        self.assertEqual(str(ctx.exception),
                         refusal("min_stack_ops:bad_type:ops[0][1]"))

    def test_oracle(self):
        def oracle(ops):
            stack = []
            out = []
            for op in ops:
                if op[0] == "push":
                    stack.append(op[1])
                elif op[0] == "pop":
                    stack.pop()
                else:
                    out.append(min(stack))
            return out
        rng = random.Random(8702)
        for _ in range(60):
            ops = []
            depth = 0
            for _ in range(rng.randint(1, 15)):
                choices = ["push"] + (["pop", "get_min"] if depth else [])
                cmd = rng.choice(choices)
                if cmd == "push":
                    ops.append(["push", rng.randint(-99, 99)])
                    depth += 1
                elif cmd == "pop":
                    ops.append(["pop"])
                    depth -= 1
                else:
                    ops.append(["get_min"])
            self.assertEqual(m.min_stack_ops(ops), oracle(ops))


class TestAtmWithdrawLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.atm_withdraw_log(
            [0, 0, 1, 0, 0],
            [["deposit", [0, 0, 0, 0, 1]], ["withdraw", 600],
             ["withdraw", 550], ["withdraw", 70]]),
            [True, [0, 0, 1, 0, 1], -1, -1])
        self.assertEqual(m.atm_withdraw_log(
            [2, 0, 0, 0, 0], [["withdraw", 40]]), [[2, 0, 0, 0, 0]])
        self.assertEqual(m.atm_withdraw_log(
            [0, 0, 0, 0, 1], [["withdraw", 20]]), [-1])
        # failed withdraws roll back: notes survive for a later try
        self.assertEqual(m.atm_withdraw_log(
            [0, 0, 0, 0, 1], [["withdraw", 450], ["withdraw", 500]]),
            [-1, [0, 0, 0, 0, 1]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.atm_withdraw_log([1, 2], [])
        self.assertEqual(str(ctx.exception),
                         refusal("atm_withdraw_log:bad_shape:notes"))
        with self.assertRaises(ValueError) as ctx:
            m.atm_withdraw_log([0] * 5, [])
        self.assertEqual(str(ctx.exception),
                         refusal("atm_withdraw_log:empty:ops"))
        with self.assertRaises(ValueError) as ctx:
            m.atm_withdraw_log([0] * 5, [["deposit", [1, 2]]])
        self.assertEqual(str(ctx.exception),
                         refusal("atm_withdraw_log:bad_shape:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.atm_withdraw_log([0] * 5, [["withdraw", 0]])
        self.assertEqual(str(ctx.exception),
                         refusal("atm_withdraw_log:out_of_range:ops[0][1]"))

    def test_oracle(self):
        def oracle(notes, ops):
            denoms = (20, 50, 100, 200, 500)
            held = list(notes)
            out = []
            for op in ops:
                if op[0] == "deposit":
                    held = [h + d for h, d in zip(held, op[1])]
                    out.append(True)
                else:
                    remaining = op[1]
                    used = [0] * 5
                    for j in (4, 3, 2, 1, 0):
                        while remaining >= denoms[j] and used[j] < held[j]:
                            used[j] += 1
                            remaining -= denoms[j]
                    if remaining:
                        out.append(-1)
                    else:
                        held = [h - u for h, u in zip(held, used)]
                        out.append(used)
            return out
        rng = random.Random(8703)
        for _ in range(60):
            notes = [rng.randint(0, 4) for _ in range(5)]
            ops = []
            for _ in range(rng.randint(1, 10)):
                if rng.random() < 0.4:
                    ops.append(["deposit",
                                [rng.randint(0, 3) for _ in range(5)]])
                else:
                    amt = rng.choice([20, 50, 100, 200, 500])
                    ops.append(["withdraw",
                                amt * rng.randint(1, 8)])
            self.assertEqual(m.atm_withdraw_log(notes, ops),
                             oracle(notes, ops))


class TestBankTransferLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.bank_transfer_log(
            [100, 50],
            [["transfer", 1, 2, 50], ["withdraw", 2, 200],
             ["deposit", 3, 10], ["withdraw", 2, 50]]),
            [True, False, False, True])
        self.assertEqual(m.bank_transfer_log(
            [10], [["withdraw", 1, 10], ["withdraw", 1, 1]]),
            [True, False])
        self.assertEqual(m.bank_transfer_log(
            [5, 5], [["transfer", 0, 2, 1], ["transfer", 1, 2, 1]]),
            [False, True])

    def test_oracle(self):
        def oracle(balances, ops):
            held = dict(enumerate(balances, start=1))
            out = []
            for op in ops:
                if op[0] == "transfer":
                    _, a, b, amount = op
                    if a not in held or b not in held or held[a] < amount:
                        out.append(False)
                    else:
                        held[a] -= amount
                        held[b] += amount
                        out.append(True)
                elif op[0] == "deposit":
                    _, a, amount = op
                    if a not in held:
                        out.append(False)
                    else:
                        held[a] += amount
                        out.append(True)
                else:
                    _, a, amount = op
                    if a not in held or held[a] < amount:
                        out.append(False)
                    else:
                        held[a] -= amount
                        out.append(True)
            return out
        rng = random.Random(8704)
        for _ in range(60):
            n = rng.randint(1, 5)
            balances = [rng.randint(0, 100) for _ in range(n)]
            ops = []
            for _ in range(rng.randint(1, 12)):
                cmd = rng.choice(["transfer", "deposit", "withdraw"])
                if cmd == "transfer":
                    ops.append([cmd, rng.randint(1, n + 1),
                                rng.randint(1, n + 1),
                                rng.randint(1, 60)])
                else:
                    ops.append([cmd, rng.randint(1, n + 1),
                                rng.randint(1, 60)])
            self.assertEqual(m.bank_transfer_log(balances, ops),
                             oracle(balances, ops))


class TestTimeMapGetLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.time_map_get_log(
            [["set", "a", "x", 1], ["set", "a", "y", 5],
             ["get", "a", 3], ["get", "a", 6], ["get", "b", 1]]),
            ["x", "y", ""])
        self.assertEqual(m.time_map_get_log(
            [["set", "k", "v", 10], ["get", "k", 9]]), [""])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.time_map_get_log(
                [["set", "a", "x", 5], ["set", "a", "y", 5]])
        self.assertEqual(str(ctx.exception),
                         refusal("time_map_get_log:bad_value:ops[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.time_map_get_log([["get", "a"]])
        self.assertEqual(str(ctx.exception),
                         refusal("time_map_get_log:bad_shape:ops[0]"))

    def test_oracle(self):
        def oracle(ops):
            store = {}
            out = []
            for op in ops:
                if op[0] == "set":
                    store.setdefault(op[1], []).append((op[3], op[2]))
                else:
                    best = ""
                    for ts, value in store.get(op[1], []):
                        if ts <= op[2]:
                            best = value
                    out.append(best)
            return out
        rng = random.Random(8705)
        for _ in range(60):
            ops = []
            clocks = {}
            for _ in range(rng.randint(1, 12)):
                key = rng.choice(["a", "b", "c"])
                if rng.random() < 0.5:
                    ts = clocks.get(key, 0) + rng.randint(1, 5)
                    clocks[key] = ts
                    ops.append(["set", key, "v%d" % ts, ts])
                else:
                    ops.append(["get", key, rng.randint(1, 30)])
            self.assertEqual(m.time_map_get_log(ops), oracle(ops))


class TestLoggerRateLimitLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.logger_rate_limit_log(
            [[1, "foo"], [2, "bar"], [3, "foo"], [11, "foo"]]),
            [True, True, False, True])
        self.assertEqual(m.logger_rate_limit_log(
            [[0, "a"], [10, "a"], [20, "a"]]), [True, True, True])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.logger_rate_limit_log([[5, "a"], [4, "b"]])
        self.assertEqual(str(ctx.exception),
                         refusal("logger_rate_limit_log:out_of_order:ops[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.logger_rate_limit_log([[1, "a", "extra"]])
        self.assertEqual(str(ctx.exception),
                         refusal("logger_rate_limit_log:bad_shape:ops[0]"))

    def test_oracle(self):
        def oracle(ops):
            printed = {}
            out = []
            for ts, message in ops:
                prior = printed.get(message, [])
                ok = all(ts - t >= 10 for t in prior)
                if ok:
                    prior.append(ts)
                    printed[message] = prior
                out.append(ok)
            return out
        rng = random.Random(8706)
        for _ in range(60):
            ops = []
            ts = 0
            for _ in range(rng.randint(1, 12)):
                ts += rng.randint(0, 8)
                ops.append([ts, rng.choice(["a", "b", "c"])])
            self.assertEqual(m.logger_rate_limit_log(ops), oracle(ops))


class TestHitCounterLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.hit_counter_log(
            [["hit", 1], ["hit", 2], ["hit", 300],
             ["get_hits", 300], ["get_hits", 301]]), [3, 2])
        self.assertEqual(m.hit_counter_log(
            [["get_hits", 5]]), [0])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.hit_counter_log([["hit", 10], ["hit", 9]])
        self.assertEqual(str(ctx.exception),
                         refusal("hit_counter_log:out_of_order:ops[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.hit_counter_log([["peek", 1]])
        self.assertEqual(str(ctx.exception),
                         refusal("hit_counter_log:bad_value:ops[0]"))

    def test_oracle(self):
        def oracle(ops):
            hits = []
            out = []
            for op in ops:
                if op[0] == "hit":
                    hits.append(op[1])
                else:
                    ts = op[1]
                    out.append(sum(1 for h in hits
                                   if ts - 300 < h <= ts))
            return out
        rng = random.Random(8707)
        for _ in range(60):
            ops = []
            ts = 1
            for _ in range(rng.randint(1, 15)):
                ts += rng.randint(1, 100)
                cmd = rng.choice(["hit", "get_hits"])
                ops.append([cmd, ts])
            self.assertEqual(m.hit_counter_log(ops), oracle(ops))


class TestTextEditorLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.text_editor_log(
            [["insert", "hello"], ["left", 2], ["delete", 1],
             ["insert", "X"], ["right", 2]]),
            ["hello", "hel", "he", "heX", "heXlo"])
        self.assertEqual(m.text_editor_log(
            [["insert", "abcdefghijkl"], ["delete", 3]]),
            ["cdefghijkl", "abcdefghi"])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.text_editor_log([["insert", ""]])
        self.assertEqual(str(ctx.exception),
                         refusal("text_editor_log:empty:ops[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.text_editor_log([["undo", 1]])
        self.assertEqual(str(ctx.exception),
                         refusal("text_editor_log:bad_value:ops[0]"))

    def test_oracle(self):
        def oracle(ops):
            buffer = ""
            cursor = 0
            out = []
            for op in ops:
                if op[0] == "insert":
                    buffer = buffer[:cursor] + op[1] + buffer[cursor:]
                    cursor += len(op[1])
                elif op[0] == "delete":
                    start = max(0, cursor - op[1])
                    buffer = buffer[:start] + buffer[cursor:]
                    cursor = start
                elif op[0] == "left":
                    cursor = max(0, cursor - op[1])
                else:
                    cursor = min(len(buffer), cursor + op[1])
                out.append(buffer[max(0, cursor - 10):cursor])
            return out
        rng = random.Random(8708)
        for _ in range(60):
            ops = []
            for _ in range(rng.randint(1, 12)):
                cmd = rng.choice(["insert", "delete", "left", "right"])
                if cmd == "insert":
                    ops.append(["insert",
                                "".join(rng.choice("abc")
                                        for _ in range(rng.randint(1, 8)))])
                else:
                    ops.append([cmd, rng.randint(1, 6)])
            self.assertEqual(m.text_editor_log(ops), oracle(ops))


class TestCircularDequeLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.circular_deque_log(
            3,
            [["insert_rear", 1], ["insert_rear", 2], ["insert_front", 3],
             ["insert_rear", 4], ["is_full"], ["get_rear"],
             ["delete_front"], ["get_front"], ["get_rear"]]),
            [True, True, True, False, True, 2, True, 1, 2])
        self.assertEqual(m.circular_deque_log(
            1, [["get_front"], ["insert_front", 9], ["is_empty"],
                ["delete_rear"], ["is_empty"]]),
            [-1, True, False, True, True])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.circular_deque_log(0, [["is_empty"]])
        self.assertEqual(str(ctx.exception),
                         refusal("circular_deque_log:out_of_range:k"))
        with self.assertRaises(ValueError) as ctx:
            m.circular_deque_log(2, [["insert_front", -1]])
        self.assertEqual(str(ctx.exception),
                         refusal("circular_deque_log:out_of_range:ops[0][1]"))

    def test_oracle(self):
        def oracle(k, ops):
            dq = deque()
            out = []
            for op in ops:
                cmd = op[0]
                if cmd == "insert_front":
                    if len(dq) == k:
                        out.append(False)
                    else:
                        dq.appendleft(op[1])
                        out.append(True)
                elif cmd == "insert_rear":
                    if len(dq) == k:
                        out.append(False)
                    else:
                        dq.append(op[1])
                        out.append(True)
                elif cmd == "delete_front":
                    if dq:
                        dq.popleft()
                        out.append(True)
                    else:
                        out.append(False)
                elif cmd == "delete_rear":
                    if dq:
                        dq.pop()
                        out.append(True)
                    else:
                        out.append(False)
                elif cmd == "get_front":
                    out.append(dq[0] if dq else -1)
                elif cmd == "get_rear":
                    out.append(dq[-1] if dq else -1)
                elif cmd == "is_empty":
                    out.append(not dq)
                else:
                    out.append(len(dq) == k)
            return out
        rng = random.Random(8709)
        cmds = ["insert_front", "insert_rear", "delete_front",
                "delete_rear", "get_front", "get_rear",
                "is_empty", "is_full"]
        for _ in range(60):
            k = rng.randint(1, 5)
            ops = []
            for _ in range(rng.randint(1, 15)):
                cmd = rng.choice(cmds)
                if cmd.startswith("insert"):
                    ops.append([cmd, rng.randint(0, 99)])
                else:
                    ops.append([cmd])
            self.assertEqual(m.circular_deque_log(k, ops), oracle(k, ops))


class TestStockPriceLog(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.stock_price_log(
            [["update", 1, 10], ["update", 2, 5], ["current"],
             ["maximum"], ["minimum"], ["update", 1, 3], ["maximum"],
             ["current"]]), [5, 10, 5, 5, 5])
        self.assertEqual(m.stock_price_log(
            [["update", 4, 7], ["update", 4, 9], ["current"]]), [9])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.stock_price_log([["current"]])
        self.assertEqual(str(ctx.exception),
                         refusal("stock_price_log:bad_state:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.stock_price_log(
                [["update", 5, 10], ["update", 4, 10]])
        self.assertEqual(str(ctx.exception),
                         refusal("stock_price_log:out_of_order:ops[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.stock_price_log([["update", 1, 0]])
        self.assertEqual(str(ctx.exception),
                         refusal("stock_price_log:out_of_range:ops[0][2]"))

    def test_oracle(self):
        def oracle(ops):
            prices = {}
            latest = -1
            out = []
            for op in ops:
                if op[0] == "update":
                    prices[op[1]] = op[2]
                    latest = max(latest, op[1])
                elif op[0] == "current":
                    out.append(prices[latest])
                elif op[0] == "maximum":
                    out.append(max(prices.values()))
                else:
                    out.append(min(prices.values()))
            return out
        rng = random.Random(8710)
        for _ in range(60):
            ts = rng.randint(1, 5)
            ops = [["update", ts, rng.randint(1, 99)]]
            stamped = [ts]
            for _ in range(rng.randint(1, 15)):
                if rng.random() < 0.6:
                    if rng.random() < 0.3:
                        t = rng.choice(stamped)
                    else:
                        ts += rng.randint(1, 5)
                        t = ts
                        stamped.append(t)
                    ops.append(["update", t, rng.randint(1, 99)])
                else:
                    ops.append([rng.choice(
                        ["current", "maximum", "minimum"])])
            self.assertEqual(m.stock_price_log(ops), oracle(ops))


class TestRegistryKnowsBatch87(unittest.TestCase):
    def test_registry_knows_batch87(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("browser_history_log", "min_stack_ops",
                     "atm_withdraw_log", "bank_transfer_log",
                     "time_map_get_log", "logger_rate_limit_log",
                     "hit_counter_log", "text_editor_log",
                     "circular_deque_log", "stock_price_log"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
