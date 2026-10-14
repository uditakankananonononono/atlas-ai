"""P235 concepts batch 91: systems and queueing exact computations.

Ten small, deterministic, pure functions with input validation,
declared resource caps, and coded refusals. No external deps.
Lists are capped at MAX_ITEMS entries and matrices at MAX_ITEMS
cells. The round-robin simulator refuses before simulating when
the quantum-slice count sum(ceil(duration / quantum)) would
exceed MAX_RR_SLICES; response-time analysis carries a declared
iteration guard MAX_RTA_STEPS so a pathological recurrence stays
finite. The buddy arena is a power of two up to MAX_ARENA.
Erlang-B, birth-death, stride, and RTT arithmetic use exact
Fractions.
"""

from bisect import insort
from collections import deque
from fractions import Fraction
from heapq import heapify, heappop, heappush

from app.modules.instinct_doc.p235_concepts_registry import (
    MAX_ITEMS, check_int, check_items, check_str, make_fail)

MAX_VAL = 1_000_000
MAX_CLOCK = 10 ** 12
MAX_ARENA = 2 ** 20
MAX_RR_SLICES = 1_000_000
MAX_RTA_STEPS = 1_000_000


def _int_list(fail, xs, name, lo, hi):
    check_items(fail, xs, name)
    if not xs:
        fail("empty:%s" % name)
    for i, v in enumerate(xs):
        check_int(fail, v, "%s[%d]" % (name, i))
        if v < lo or v > hi:
            fail("out_of_range:%s[%d]" % (name, i))
    return xs


def _pairs(fail, rows, name):
    check_items(fail, rows, name)
    if not rows:
        fail("empty:%s" % name)
    for i, row in enumerate(rows):
        if type(row) is not list or len(row) != 2:
            fail("bad_shape:%s[%d]" % (name, i))
    return rows


def round_robin_finish_times(arrivals, durations, quantum):
    """Finish time of every job under round-robin scheduling.

    Job i arrives at arrivals[i] holding durations[i] ticks of
    work. The ready queue is FIFO: a running job is preempted
    after at most quantum ticks and rejoins behind any jobs that
    arrived during its run. Ties on arrival break toward the
    lower input index; finish times come back in input index
    order. The slice count sum(ceil(duration / quantum)) is
    bounded by MAX_RR_SLICES, checked before any simulation."""
    fail = make_fail("round_robin_finish_times")
    _int_list(fail, arrivals, "arrivals", 0, MAX_VAL)
    _int_list(fail, durations, "durations", 1, MAX_VAL)
    if len(durations) != len(arrivals):
        fail("bad_shape:durations")
    check_int(fail, quantum, "quantum")
    if quantum < 1 or quantum > MAX_VAL:
        fail("out_of_range:quantum")
    slices = sum((d + quantum - 1) // quantum for d in durations)
    if slices > MAX_RR_SLICES:
        fail("too_much_work:slices")
    n = len(arrivals)
    order = sorted(range(n), key=lambda i: (arrivals[i], i))
    remaining = list(durations)
    finish = [0] * n
    queue = deque()
    t = 0
    pos = 0
    while True:
        while pos < n and arrivals[order[pos]] <= t:
            queue.append(order[pos])
            pos += 1
        if not queue:
            if pos == n:
                return finish
            t = arrivals[order[pos]]
            continue
        cur = queue.popleft()
        run = min(quantum, remaining[cur])
        t += run
        remaining[cur] -= run
        while pos < n and arrivals[order[pos]] <= t:
            queue.append(order[pos])
            pos += 1
        if remaining[cur]:
            queue.append(cur)
        else:
            finish[cur] = t


def stride_schedule_order(weights, steps):
    """Execution order of a deterministic stride scheduler.

    Task i starts with pass value 0 and stride 1 / weights[i];
    every step runs the task with the smallest pass (ties to the
    lowest index) and advances its pass by its stride. Pass
    values are exact Fractions, so the emitted order of task
    indices is exact. steps may be zero."""
    fail = make_fail("stride_schedule_order")
    weights = _int_list(fail, weights, "weights", 1, MAX_VAL)
    check_int(fail, steps, "steps")
    if steps < 0 or steps > MAX_ITEMS:
        fail("out_of_range:steps")
    heap = [(Fraction(0), i) for i in range(len(weights))]
    heapify(heap)
    out = []
    for _ in range(steps):
        value, i = heappop(heap)
        out.append(i)
        heappush(heap, (value + Fraction(1, weights[i]), i))
    return out


def banker_safe_sequence(available, allocation, maximum):
    """One safe process sequence for the banker's safety check, or
    [] when the state is unsafe.

    allocation and maximum are n by m matrices of non-negative
    ints with maximum >= allocation cellwise, and available is
    the m-vector of free units. The simulation repeatedly picks
    the lowest-index unfinished process whose remaining need fits
    the work vector, runs it, and reclaims its allocation; the
    lowest-index rule makes the reported sequence deterministic
    and unique. Each matrix is capped at MAX_ITEMS cells; the
    pair may hold twice that."""
    fail = make_fail("banker_safe_sequence")
    available = _int_list(fail, available, "available", 0, MAX_VAL)
    width = len(available)
    for name, matrix in (("allocation", allocation),
                         ("maximum", maximum)):
        check_items(fail, matrix, name)
        if not matrix:
            fail("empty:%s" % name)
        if len(matrix) * width > MAX_ITEMS:
            fail("too_many:%s" % name)
        for i, row in enumerate(matrix):
            if type(row) is not list or len(row) != width:
                fail("bad_shape:%s[%d]" % (name, i))
            for j, v in enumerate(row):
                check_int(fail, v, "%s[%d][%d]" % (name, i, j))
                if v < 0 or v > MAX_VAL:
                    fail("out_of_range:%s[%d][%d]" % (name, i, j))
    if len(maximum) != len(allocation):
        fail("bad_shape:maximum")
    need = []
    for i, (arow, mrow) in enumerate(zip(allocation, maximum)):
        row = []
        for j, (a, mx) in enumerate(zip(arow, mrow)):
            if mx < a:
                fail("bad_form:maximum[%d][%d]" % (i, j))
            row.append(mx - a)
        need.append(row)
    work = list(available)
    done = [False] * len(allocation)
    seq = []
    for _ in range(len(allocation)):
        pick = -1
        for i in range(len(allocation)):
            if not done[i] and all(
                    need[i][j] <= work[j] for j in range(width)):
                pick = i
                break
        if pick == -1:
            return []
        done[pick] = True
        for j in range(width):
            work[j] += allocation[pick][j]
        seq.append(pick)
    return seq


def response_time_worst_case(tasks):
    """Worst-case response time of every task under fixed-priority
    preemptive scheduling, or -1 when it would exceed its period.

    tasks is a priority-ordered list (highest first) of
    [period, cost] int pairs with 1 <= cost <= period. The
    response time of task i solves R = cost_i + sum over higher
    priority j of ceil(R / period_j) * cost_j, iterated from
    cost_i; the values climb monotonically, so the first R that
    repeats is the fixpoint and the first R past the period
    yields -1. Iterations across all tasks are counted and
    guarded by MAX_RTA_STEPS so a pathological case stays
    finite. The guard counts iterations, not total work: each
    iteration scans the higher-priority tasks."""
    fail = make_fail("response_time_worst_case")
    _pairs(fail, tasks, "tasks")
    for i, (period, cost) in enumerate(tasks):
        check_int(fail, period, "tasks[%d][0]" % i)
        check_int(fail, cost, "tasks[%d][1]" % i)
        if period < 1 or period > MAX_VAL:
            fail("out_of_range:tasks[%d][0]" % i)
        if cost < 1 or cost > period:
            fail("out_of_range:tasks[%d][1]" % i)
    steps = 0
    out = []
    for i, (period, cost) in enumerate(tasks):
        r = cost
        while True:
            interference = sum(
                -(-r // tasks[j][0]) * tasks[j][1] for j in range(i))
            new_r = cost + interference
            steps += 1
            if steps > MAX_RTA_STEPS:
                fail("too_much_work:response_time")
            if new_r > period:
                out.append(-1)
                break
            if new_r == r:
                out.append(r)
                break
            r = new_r
    return out


def erlang_b_blocking_exact(channels, traffic_num, traffic_den):
    """Exact Erlang-B blocking probability as a Fraction.

    The offered traffic in erlangs is traffic_num / traffic_den
    (non-negative numerator, positive denominator) and channels
    counts the servers, capped at MAX_ITEMS. The recursion
    B_0 = 1, B_c = a * B_{c-1} / (c + a * B_{c-1}) is evaluated
    in exact Fraction arithmetic; zero channels block every
    call."""
    fail = make_fail("erlang_b_blocking_exact")
    check_int(fail, channels, "channels")
    if channels < 0 or channels > MAX_ITEMS:
        fail("out_of_range:channels")
    check_int(fail, traffic_num, "traffic_num")
    if traffic_num < 0 or traffic_num > MAX_VAL:
        fail("out_of_range:traffic_num")
    check_int(fail, traffic_den, "traffic_den")
    if traffic_den < 1 or traffic_den > MAX_VAL:
        fail("out_of_range:traffic_den")
    a = Fraction(traffic_num, traffic_den)
    b = Fraction(1)
    for c in range(1, channels + 1):
        b = a * b / (c + a * b)
    return b


def birth_death_stationary_dist(birth_rates, death_rates):
    """Stationary distribution of a finite birth-death chain.

    States 0..n; birth_rates[i] is the rate from state i to
    state i + 1 and death_rates[i] the rate from i + 1 to i, so
    both lists share one length n. Rates are ints, births
    non-negative, deaths positive. Detailed balance gives
    unnormalized weights w_{k+1} = w_k * birth[k] / death[k],
    returned normalized as exact Fractions summing to one. A
    zero birth rate cuts the chain and zeroes every later
    weight."""
    fail = make_fail("birth_death_stationary_dist")
    birth = _int_list(fail, birth_rates, "birth_rates", 0, MAX_VAL)
    _int_list(fail, death_rates, "death_rates", 1, MAX_VAL)
    if len(death_rates) != len(birth):
        fail("bad_shape:death_rates")
    weights = [Fraction(1)]
    for k in range(len(birth)):
        weights.append(weights[-1] * Fraction(birth[k], death_rates[k]))
    total = sum(weights, Fraction(0))
    return [w / total for w in weights]


def lamport_clock_trace(events):
    """Logical clock value after every event on one process.

    Each event is a [kind, clock] pair: kind 0 is a local or
    send event and its clock field must be 0; kind 1 is a
    receive whose clock field carries the sender's timestamp,
    an int in 0..MAX_CLOCK. The process clock ticks by one on
    local events and jumps to max(local, message) + 1 on
    receives."""
    fail = make_fail("lamport_clock_trace")
    _pairs(fail, events, "events")
    for i, (kind, msg) in enumerate(events):
        check_int(fail, kind, "events[%d][0]" % i)
        if kind not in (0, 1):
            fail("out_of_range:events[%d][0]" % i)
        check_int(fail, msg, "events[%d][1]" % i)
        if msg < 0 or msg > MAX_CLOCK:
            fail("out_of_range:events[%d][1]" % i)
        if kind == 0 and msg != 0:
            fail("bad_form:events[%d]" % i)
    clock = 0
    out = []
    for kind, msg in events:
        if kind:
            clock = max(clock, msg) + 1
        else:
            clock += 1
        out.append(clock)
    return out


def rtt_estimator_trace(samples):
    """Retransmission timeout after every RTT sample, RFC 6298
    style, as exact Fractions.

    The first sample seeds srtt = r and rttvar = r / 2; every
    later sample updates rttvar = 3/4 rttvar + 1/4 |srtt - r|
    and then srtt = 7/8 srtt + 1/8 r. The reported timeout is
    srtt + 4 rttvar with no clock granularity, lower bound, or
    backoff applied. samples are ints in 1..MAX_VAL."""
    fail = make_fail("rtt_estimator_trace")
    _int_list(fail, samples, "samples", 1, MAX_VAL)
    out = []
    srtt = var = None
    for i, r in enumerate(samples):
        if i == 0:
            srtt = Fraction(r)
            var = Fraction(r, 2)
        else:
            var = Fraction(3, 4) * var + Fraction(1, 4) * abs(srtt - r)
            srtt = Fraction(7, 8) * srtt + Fraction(1, 8) * r
        out.append(srtt + 4 * var)
    return out


def cwnd_aimd_trace(rounds, ssthresh, losses):
    """Congestion window after every round under slow start and
    additive increase, with a timeout (reset-to-one) loss model.

    The window starts at 1; a round without loss doubles it
    while it is below ssthresh and otherwise adds 1; a round
    listed in losses sets ssthresh to max(window // 2, 1) and
    resets the window to 1 (reset-to-one slow start after loss,
    not generic AIMD halving of the window). losses must be
    sorted strictly
    increasing with values in 1..rounds; an empty loss list is
    allowed."""
    fail = make_fail("cwnd_aimd_trace")
    check_int(fail, rounds, "rounds")
    if rounds < 1 or rounds > MAX_ITEMS:
        fail("out_of_range:rounds")
    check_int(fail, ssthresh, "ssthresh")
    if ssthresh < 1 or ssthresh > MAX_VAL:
        fail("out_of_range:ssthresh")
    check_items(fail, losses, "losses")
    prev = 0
    for i, v in enumerate(losses):
        check_int(fail, v, "losses[%d]" % i)
        if v < 1 or v > rounds:
            fail("out_of_range:losses[%d]" % i)
        if v <= prev:
            fail("bad_form:losses[%d]" % i)
        prev = v
    loss_set = set(losses)
    cwnd = 1
    out = []
    for r in range(1, rounds + 1):
        if r in loss_set:
            ssthresh = max(cwnd // 2, 1)
            cwnd = 1
        elif cwnd < ssthresh:
            cwnd *= 2
        else:
            cwnd += 1
        out.append(cwnd)
    return out


def buddy_allocation_addresses(total_size, ops):
    """Per-operation results of a binary buddy allocator.

    total_size is a power of two up to MAX_ARENA. Each op is
    ["alloc", size] with 1 <= size <= total_size, or ["free",
    k] where k is the op index of a live allocation. An
    allocation takes the lowest-address block of the smallest
    available class at least next_pow2(size), splitting larger
    blocks, and returns the block's start address, or -1 when
    nothing fits. A free coalesces with its buddy while the
    buddy is free and returns None. Freeing a dead, failed, or
    repeated handle refuses."""
    fail = make_fail("buddy_allocation_addresses")
    check_int(fail, total_size, "total_size")
    if total_size < 1 or total_size > MAX_ARENA:
        fail("out_of_range:total_size")
    if total_size & (total_size - 1):
        fail("bad_form:total_size")
    check_items(fail, ops, "ops")
    for i, row in enumerate(ops):
        if type(row) is not list or len(row) != 2:
            fail("bad_shape:ops[%d]" % i)
        check_str(fail, row[0], "ops[%d][0]" % i)
        if row[0] not in ("alloc", "free"):
            fail("bad_form:ops[%d][0]" % i)
        check_int(fail, row[1], "ops[%d][1]" % i)
        if row[0] == "alloc" and (row[1] < 1 or row[1] > total_size):
            fail("out_of_range:ops[%d][1]" % i)
        if row[0] == "free" and (row[1] < 0 or row[1] >= i):
            fail("bad_form:ops[%d]" % i)
    blocks = {total_size: [0]}
    live = {}
    out = []
    for i, (verb, arg) in enumerate(ops):
        if verb == "alloc":
            cls = 1
            while cls < arg:
                cls *= 2
            c = cls
            while c <= total_size and not blocks.get(c):
                c *= 2
            if c > total_size:
                out.append(-1)
                continue
            addr = blocks[c].pop(0)
            while c > cls:
                c //= 2
                blocks.setdefault(c, []).append(addr + c)
            live[i] = (addr, cls)
            out.append(addr)
        else:
            if arg not in live:
                fail("bad_form:ops[%d]" % i)
            addr, cls = live.pop(arg)
            c = cls
            while c < total_size:
                buddy = addr ^ c
                if buddy in blocks.get(c, []):
                    blocks[c].remove(buddy)
                    addr = min(addr, buddy)
                    c *= 2
                else:
                    break
            blocks.setdefault(c, [])
            insort(blocks[c], addr)
            out.append(None)
    return out
