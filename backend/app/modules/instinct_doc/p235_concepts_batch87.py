"""P235 concepts batch 87: operation-log simulations.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps. Each
replays a validated operation log and returns the per-step results
in order; every contract is distinct (page navigation, stack
minimums, note dispensing, account transfers, timestamped lookups,
rate limiting, sliding-window counts, cursor editing, bounded
deque state, and price extremes). Logs stay within MAX_ITEMS
operations. Per-op costs are not constant: browser-history visits
copy the truncated tail, the timestamped store builds per-key
lists, the price log shifts a sorted list on insert and removal,
and the editor walks the cursor per step, so a full replay is
O(n^2) in the worst case under the op cap.
"""

from bisect import bisect_left, bisect_right, insort

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_VAL = 10_000
MAX_TS = 10 ** 9
MAX_TEXT = 200
_DENOMS = (20, 50, 100, 200, 500)


def _ops(fail, ops, name="ops"):
    """Validate a nonempty operation log; return it."""
    check_items(fail, ops, name)
    if not ops:
        fail("empty:%s" % name)
    for i, op in enumerate(ops):
        if type(op) is not list or not op:
            fail("bad_shape:%s[%d]" % (name, i))
        if type(op[0]) is not str:
            fail("bad_type:%s[%d]" % (name, i))
    return ops


def _text(fail, value, name):
    check_str(fail, value, name)
    if not value:
        fail("empty:%s" % name)
    if len(value) > MAX_TEXT:
        fail("too_long:%s" % name)
    return value


def _count(fail, v, name, lo=1, hi=MAX_VAL):
    check_int(fail, v, name)
    if v < lo or v > hi:
        fail("out_of_range:%s" % name)
    return v


def _ts(fail, v, name, lo=0):
    check_int(fail, v, name)
    if v < lo or v > MAX_TS:
        fail("out_of_range:%s" % name)
    return v


def browser_history_log(homepage, ops):
    """Current page after every navigation op.

    ops holds ["visit", url], ["back", k], or ["forward", k]; a
    visit drops every forward page. Back and forward stop at the
    ends of history."""
    fail = make_fail("browser_history_log")
    _text(fail, homepage, "homepage")
    _ops(fail, ops)
    history = [homepage]
    at = 0
    out = []
    for i, op in enumerate(ops):
        if op[0] == "visit":
            if len(op) != 2:
                fail("bad_shape:ops[%d]" % i)
            _text(fail, op[1], "ops[%d][1]" % i)
            history = history[:at + 1]
            history.append(op[1])
            at += 1
        elif op[0] in ("back", "forward"):
            if len(op) != 2:
                fail("bad_shape:ops[%d]" % i)
            _count(fail, op[1], "ops[%d][1]" % i)
            if op[0] == "back":
                at = max(0, at - op[1])
            else:
                at = min(len(history) - 1, at + op[1])
        else:
            fail("bad_value:ops[%d]" % i)
        out.append(history[at])
    return out


def min_stack_ops(ops):
    """Every get_min result over a push/pop log.

    ops holds ["push", value], ["pop"], or ["get_min"]. Popping or
    reading an empty stack refuses. A push also refuses past the
    depth cap, but that refusal is unreachable in practice: the
    stack can never outgrow the op log, which is itself capped at
    MAX_ITEMS, so the depth cap exists only as a guard."""
    fail = make_fail("min_stack_ops")
    _ops(fail, ops)
    stack = []
    mins = []
    out = []
    for i, op in enumerate(ops):
        if op[0] == "push":
            if len(op) != 2:
                fail("bad_shape:ops[%d]" % i)
            _count(fail, op[1], "ops[%d][1]" % i, lo=-MAX_VAL)
            if len(stack) >= MAX_ITEMS:
                fail("too_deep:stack")
            stack.append(op[1])
            mins.append(op[1] if not mins else min(mins[-1], op[1]))
        elif op[0] in ("pop", "get_min"):
            if len(op) != 1:
                fail("bad_shape:ops[%d]" % i)
            if not stack:
                fail("bad_state:ops[%d]" % i)
            if op[0] == "pop":
                stack.pop()
                mins.pop()
            else:
                out.append(mins[-1])
        else:
            fail("bad_value:ops[%d]" % i)
    return out


def atm_withdraw_log(notes, ops):
    """Per-op ATM results over 20/50/100/200/500 notes.

    notes holds the starting counts per denomination. A deposit op
    adds five counts and logs True; a withdraw op logs the greedy
    largest-first note counts, or -1 when the amount cannot be
    dispensed (the machine then keeps its notes)."""
    fail = make_fail("atm_withdraw_log")
    check_items(fail, notes, "notes")
    if len(notes) != 5:
        fail("bad_shape:notes")
    held = []
    for j, v in enumerate(notes):
        _count(fail, v, "notes[%d]" % j, lo=0)
        held.append(v)
    _ops(fail, ops)
    out = []
    for i, op in enumerate(ops):
        if op[0] == "deposit":
            if len(op) != 2 or type(op[1]) is not list or len(op[1]) != 5:
                fail("bad_shape:ops[%d]" % i)
            for j, v in enumerate(op[1]):
                _count(fail, v, "ops[%d][1][%d]" % (i, j), lo=0)
            for j in range(5):
                held[j] += op[1][j]
            out.append(True)
        elif op[0] == "withdraw":
            if len(op) != 2:
                fail("bad_shape:ops[%d]" % i)
            _count(fail, op[1], "ops[%d][1]" % i, hi=MAX_TS)
            remaining = op[1]
            used = [0] * 5
            for j in (4, 3, 2, 1, 0):
                take = min(held[j], remaining // _DENOMS[j])
                used[j] = take
                remaining -= take * _DENOMS[j]
            if remaining:
                out.append(-1)
            else:
                for j in range(5):
                    held[j] -= used[j]
                out.append(used)
        else:
            fail("bad_value:ops[%d]" % i)
    return out


def bank_transfer_log(balances, ops):
    """True/False per banking op against 1-based accounts.

    ops holds ["transfer", a, b, amount], ["deposit", a, amount],
    or ["withdraw", a, amount]. An op is False when an account is
    out of range or the funds do not cover it; False ops change
    nothing. Check order differs by op: a transfer with an invalid
    account logs False before the amount's domain check runs, so
    an invalid account paired with an out-of-range amount yields
    False, while deposit and withdraw validate the amount first
    and so refuse on the same combination."""
    fail = make_fail("bank_transfer_log")
    check_items(fail, balances, "balances")
    if not balances:
        fail("empty:balances")
    if len(balances) > 1000:
        fail("too_many:balances")
    held = []
    for j, v in enumerate(balances):
        _count(fail, v, "balances[%d]" % j, lo=0, hi=MAX_TS)
        held.append(v)
    _ops(fail, ops)
    n = len(held)
    out = []
    for i, op in enumerate(ops):
        if op[0] == "transfer":
            if len(op) != 4:
                fail("bad_shape:ops[%d]" % i)
            _, a, b, amount = op
            for j, v in enumerate((a, b, amount)):
                check_int(fail, v, "ops[%d][%d]" % (i, j + 1))
            if not (1 <= a <= n) or not (1 <= b <= n):
                out.append(False)
            elif amount < 1 or amount > MAX_TS:
                fail("out_of_range:ops[%d]" % i)
            elif held[a - 1] < amount:
                out.append(False)
            else:
                held[a - 1] -= amount
                held[b - 1] += amount
                out.append(True)
        elif op[0] in ("deposit", "withdraw"):
            if len(op) != 3:
                fail("bad_shape:ops[%d]" % i)
            _, a, amount = op
            check_int(fail, a, "ops[%d][1]" % i)
            check_int(fail, amount, "ops[%d][2]" % i)
            if amount < 1 or amount > MAX_TS:
                fail("out_of_range:ops[%d]" % i)
            if not (1 <= a <= n):
                out.append(False)
            elif op[0] == "withdraw" and held[a - 1] < amount:
                out.append(False)
            else:
                held[a - 1] += amount if op[0] == "deposit" else -amount
                out.append(True)
        else:
            fail("bad_value:ops[%d]" % i)
    return out


def time_map_get_log(ops):
    """Every get result against a timestamped key-value store.

    ops holds ["set", key, value, ts] or ["get", key, ts]. Set
    timestamps must strictly increase per key; a get returns the
    value with the largest set timestamp at or below its own, or
    the empty string."""
    fail = make_fail("time_map_get_log")
    _ops(fail, ops)
    store = {}
    out = []
    for i, op in enumerate(ops):
        if op[0] == "set":
            if len(op) != 4:
                fail("bad_shape:ops[%d]" % i)
            _text(fail, op[1], "ops[%d][1]" % i)
            _text(fail, op[2], "ops[%d][2]" % i)
            _ts(fail, op[3], "ops[%d][3]" % i, lo=1)
            series = store.setdefault(op[1], [])
            if series and series[-1][0] >= op[3]:
                fail("bad_value:ops[%d]" % i)
            series.append((op[3], op[2]))
        elif op[0] == "get":
            if len(op) != 3:
                fail("bad_shape:ops[%d]" % i)
            _text(fail, op[1], "ops[%d][1]" % i)
            _ts(fail, op[3 - 1], "ops[%d][2]" % i, lo=1)
            series = store.get(op[1])
            if not series:
                out.append("")
                continue
            times = [t for t, _ in series]
            pos = bisect_right(times, op[2]) - 1
            out.append(series[pos][1] if pos >= 0 else "")
        else:
            fail("bad_value:ops[%d]" % i)
    return out


def logger_rate_limit_log(ops):
    """True when each message may print, False when the same text
    already printed inside the previous ten ticks.

    ops holds [timestamp, message] pairs with non-decreasing
    timestamps."""
    fail = make_fail("logger_rate_limit_log")
    check_items(fail, ops, "ops")
    if not ops:
        fail("empty:ops")
    last = {}
    prev = -1
    out = []
    for i, op in enumerate(ops):
        if type(op) is not list or len(op) != 2:
            fail("bad_shape:ops[%d]" % i)
        _ts(fail, op[0], "ops[%d][0]" % i)
        _text(fail, op[1], "ops[%d][1]" % i)
        if op[0] < prev:
            fail("out_of_order:ops[%d]" % i)
        prev = op[0]
        seen = last.get(op[1])
        if seen is None or op[0] - seen >= 10:
            last[op[1]] = op[0]
            out.append(True)
        else:
            out.append(False)
    return out


def hit_counter_log(ops):
    """Every get_hits result: hits inside (ts - 300, ts].

    ops holds ["hit", ts] or ["get_hits", ts] with non-decreasing
    timestamps."""
    fail = make_fail("hit_counter_log")
    _ops(fail, ops)
    hits = []
    prev = 0
    out = []
    for i, op in enumerate(ops):
        if len(op) != 2:
            fail("bad_shape:ops[%d]" % i)
        _ts(fail, op[1], "ops[%d][1]" % i, lo=1)
        if op[1] < prev:
            fail("out_of_order:ops[%d]" % i)
        prev = op[1]
        if op[0] == "hit":
            hits.append(op[1])
        elif op[0] == "get_hits":
            lo = bisect_right(hits, op[1] - 300)
            hi = bisect_right(hits, op[1])
            out.append(hi - lo)
        else:
            fail("bad_value:ops[%d]" % i)
    return out


def text_editor_log(ops):
    """The last ten characters left of the cursor after every op.

    ops holds ["insert", text], ["delete", k], ["left", k], or
    ["right", k]. Deletes and cursor moves stop at the buffer
    ends. The buffer never exceeds the text cap."""
    fail = make_fail("text_editor_log")
    _ops(fail, ops)
    left = []
    right = []
    out = []
    for i, op in enumerate(ops):
        if op[0] == "insert":
            if len(op) != 2:
                fail("bad_shape:ops[%d]" % i)
            _text(fail, op[1], "ops[%d][1]" % i)
            if len(left) + len(right) + len(op[1]) > MAX_ITEMS:
                fail("too_long:text")
            left.extend(op[1])
        elif op[0] in ("delete", "left", "right"):
            if len(op) != 2:
                fail("bad_shape:ops[%d]" % i)
            _count(fail, op[1], "ops[%d][1]" % i)
            if op[0] == "delete":
                del left[max(0, len(left) - op[1]):]
            elif op[0] == "left":
                move = min(op[1], len(left))
                for _ in range(move):
                    right.append(left.pop())
            else:
                move = min(op[1], len(right))
                for _ in range(move):
                    left.append(right.pop())
        else:
            fail("bad_value:ops[%d]" % i)
        out.append("".join(left[-10:]))
    return out


def circular_deque_log(k, ops):
    """Per-op results for a bounded circular deque.

    Insert and delete ops log True or False; get_front and
    get_rear log the value or -1; is_empty and is_full log the
    predicate."""
    fail = make_fail("circular_deque_log")
    _count(fail, k, "k", hi=1000)
    _ops(fail, ops)
    ring = [0] * k
    head = count = 0
    out = []
    for i, op in enumerate(ops):
        cmd = op[0]
        if cmd in ("insert_front", "insert_rear"):
            if len(op) != 2:
                fail("bad_shape:ops[%d]" % i)
            _count(fail, op[1], "ops[%d][1]" % i, lo=0)
            if count == k:
                out.append(False)
                continue
            if cmd == "insert_front":
                head = (head - 1) % k
                ring[head] = op[1]
            else:
                ring[(head + count) % k] = op[1]
            count += 1
            out.append(True)
        elif cmd in ("delete_front", "delete_rear"):
            if len(op) != 1:
                fail("bad_shape:ops[%d]" % i)
            if count == 0:
                out.append(False)
                continue
            if cmd == "delete_front":
                head = (head + 1) % k
            count -= 1
            out.append(True)
        elif cmd in ("get_front", "get_rear"):
            if len(op) != 1:
                fail("bad_shape:ops[%d]" % i)
            if count == 0:
                out.append(-1)
            elif cmd == "get_front":
                out.append(ring[head])
            else:
                out.append(ring[(head + count - 1) % k])
        elif cmd in ("is_empty", "is_full"):
            if len(op) != 1:
                fail("bad_shape:ops[%d]" % i)
            out.append(count == 0 if cmd == "is_empty" else count == k)
        else:
            fail("bad_value:ops[%d]" % i)
    return out


def stock_price_log(ops):
    """Per-op current, maximum, or minimum of live prices.

    ops holds ["update", ts, price] (restamping a timestamp
    corrects it) or the parameterless "current", "maximum", and
    "minimum". Reading before any update refuses. A new timestamp
    must be at least the latest one seen; restamping an existing
    (older) timestamp is the correction case and stays allowed."""
    fail = make_fail("stock_price_log")
    _ops(fail, ops)
    prices = {}
    ordered = []
    latest = -1
    out = []
    for i, op in enumerate(ops):
        if op[0] == "update":
            if len(op) != 3:
                fail("bad_shape:ops[%d]" % i)
            _ts(fail, op[1], "ops[%d][1]" % i, lo=1)
            _count(fail, op[2], "ops[%d][2]" % i, hi=MAX_TS)
            if op[1] < latest and op[1] not in prices:
                fail("out_of_order:ops[%d]" % i)
            if op[1] > latest:
                latest = op[1]
            old = prices.get(op[1])
            if old is not None:
                ordered.pop(bisect_left(ordered, old))
            prices[op[1]] = op[2]
            insort(ordered, op[2])
        elif op[0] in ("current", "maximum", "minimum"):
            if len(op) != 1:
                fail("bad_shape:ops[%d]" % i)
            if not prices:
                fail("bad_state:ops[%d]" % i)
            if op[0] == "current":
                out.append(prices[latest])
            elif op[0] == "maximum":
                out.append(ordered[-1])
            else:
                out.append(ordered[0])
        else:
            fail("bad_value:ops[%d]" % i)
    return out
