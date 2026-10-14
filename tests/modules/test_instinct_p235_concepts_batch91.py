"""P235 batch 91: systems and queueing exact computations."""
import random
import unittest
from collections import deque
from fractions import Fraction
from math import factorial

from app.modules.instinct_doc import p235_concepts_batch91 as m
from app.modules.instinct_doc.p235_concepts_registry import MAX_ITEMS


def refusal(code):
    return "P235:" + code


class TestRoundRobinFinishTimes(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.round_robin_finish_times(
            [0, 0, 0], [24, 3, 3], 4), [30, 7, 10])
        self.assertEqual(m.round_robin_finish_times([0, 0], [2, 2], 1),
                         [3, 4])
        self.assertEqual(m.round_robin_finish_times([0], [5], 2), [5])
        self.assertEqual(m.round_robin_finish_times([2], [4], 10), [6])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.round_robin_finish_times([], [1], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "round_robin_finish_times:empty:arrivals"))
        with self.assertRaises(ValueError) as ctx:
            m.round_robin_finish_times([0], [1, 2], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "round_robin_finish_times:bad_shape:durations"))
        with self.assertRaises(ValueError) as ctx:
            m.round_robin_finish_times([-1], [1], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "round_robin_finish_times:out_of_range:arrivals[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.round_robin_finish_times([0], [0], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "round_robin_finish_times:out_of_range:durations[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.round_robin_finish_times([0], [1], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "round_robin_finish_times:out_of_range:quantum"))
        with self.assertRaises(ValueError) as ctx:
            m.round_robin_finish_times([True], [1], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "round_robin_finish_times:bad_type:arrivals[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.round_robin_finish_times([0] * 101, [10000] * 100 + [1], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "round_robin_finish_times:too_much_work:slices"))

    def test_slice_cap(self):
        got = m.round_robin_finish_times([0] * 100, [10000] * 100, 1)
        self.assertEqual(got[0], 999901)
        self.assertEqual(got[-1], 1000000)

    def test_oracle(self):
        rng = random.Random(9101)
        for _ in range(60):
            n = rng.randint(1, 6)
            arrivals = [rng.randint(0, 8) for _ in range(n)]
            durations = [rng.randint(1, 9) for _ in range(n)]
            quantum = rng.randint(1, 4)
            # tick-by-tick oracle: one tick of work per loop pass
            remaining = list(durations)
            finish = [0] * n
            queue = deque()
            t = 0
            pos = 0
            order = sorted(range(n), key=lambda i: (arrivals[i], i))
            served = 0
            slice_used = 0
            while served < n:
                while pos < n and arrivals[order[pos]] <= t:
                    queue.append(order[pos])
                    pos += 1
                if not queue:
                    t = arrivals[order[pos]]
                    continue
                cur = queue[0]
                remaining[cur] -= 1
                t += 1
                slice_used += 1
                while pos < n and arrivals[order[pos]] <= t:
                    queue.append(order[pos])
                    pos += 1
                if remaining[cur] == 0:
                    finish[cur] = t
                    queue.popleft()
                    slice_used = 0
                    served += 1
                elif slice_used == quantum:
                    queue.popleft()
                    queue.append(cur)
                    slice_used = 0
            self.assertEqual(
                m.round_robin_finish_times(arrivals, durations, quantum),
                finish)


class TestStrideScheduleOrder(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.stride_schedule_order([1, 2, 3], 8),
                         [0, 1, 2, 2, 1, 2, 0, 1])
        self.assertEqual(m.stride_schedule_order([1, 2], 3), [0, 1, 1])
        self.assertEqual(m.stride_schedule_order([5], 0), [])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.stride_schedule_order([], 3)
        self.assertEqual(str(ctx.exception), refusal(
            "stride_schedule_order:empty:weights"))
        with self.assertRaises(ValueError) as ctx:
            m.stride_schedule_order([0], 3)
        self.assertEqual(str(ctx.exception), refusal(
            "stride_schedule_order:out_of_range:weights[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.stride_schedule_order([1], -1)
        self.assertEqual(str(ctx.exception), refusal(
            "stride_schedule_order:out_of_range:steps"))
        with self.assertRaises(ValueError) as ctx:
            m.stride_schedule_order([1], MAX_ITEMS + 1)
        self.assertEqual(str(ctx.exception), refusal(
            "stride_schedule_order:out_of_range:steps"))

    def test_steps_cap(self):
        self.assertEqual(len(m.stride_schedule_order([1, 2], MAX_ITEMS)),
                         MAX_ITEMS)

    def test_oracle(self):
        rng = random.Random(9102)
        for _ in range(60):
            n = rng.randint(1, 6)
            weights = [rng.randint(1, 7) for _ in range(n)]
            steps = rng.randint(0, 30)
            passes = [Fraction(0) for _ in range(n)]
            want = []
            for _ in range(steps):
                i = min(range(n), key=lambda j: (passes[j], j))
                want.append(i)
                passes[i] += Fraction(1, weights[i])
            self.assertEqual(m.stride_schedule_order(weights, steps), want)


class TestBankerSafeSequence(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.banker_safe_sequence(
            [3, 3, 2],
            [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
            [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]),
            [1, 3, 0, 2, 4])
        self.assertEqual(m.banker_safe_sequence([0], [[1]], [[2]]), [])
        self.assertEqual(m.banker_safe_sequence([1, 1], [[0, 0], [0, 0]],
                                                [[1, 1], [1, 1]]), [0, 1])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.banker_safe_sequence([], [[0]], [[0]])
        self.assertEqual(str(ctx.exception), refusal(
            "banker_safe_sequence:empty:available"))
        with self.assertRaises(ValueError) as ctx:
            m.banker_safe_sequence([0], [], [[0]])
        self.assertEqual(str(ctx.exception), refusal(
            "banker_safe_sequence:empty:allocation"))
        with self.assertRaises(ValueError) as ctx:
            m.banker_safe_sequence([0, 0], [[0]], [[0]])
        self.assertEqual(str(ctx.exception), refusal(
            "banker_safe_sequence:bad_shape:allocation[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.banker_safe_sequence([0], [[0]], [[0], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "banker_safe_sequence:bad_shape:maximum"))
        with self.assertRaises(ValueError) as ctx:
            m.banker_safe_sequence([0], [[1]], [[0]])
        self.assertEqual(str(ctx.exception), refusal(
            "banker_safe_sequence:bad_form:maximum[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.banker_safe_sequence([0], [[-1]], [[0]])
        self.assertEqual(str(ctx.exception), refusal(
            "banker_safe_sequence:out_of_range:allocation[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.banker_safe_sequence([0] * 100, [[0] * 100] * 101,
                                   [[0] * 100] * 101)
        self.assertEqual(str(ctx.exception), refusal(
            "banker_safe_sequence:too_many:allocation"))

    def test_cells_cap(self):
        got = m.banker_safe_sequence([0] * 100, [[0] * 100] * 100,
                                     [[0] * 100] * 100)
        self.assertEqual(got, list(range(100)))

    def test_oracle(self):
        from itertools import permutations
        rng = random.Random(9103)
        for _ in range(60):
            n = rng.randint(1, 5)
            w = rng.randint(1, 3)
            allocation = [[rng.randint(0, 3) for _ in range(w)]
                          for _ in range(n)]
            maximum = [[a + rng.randint(0, 3) for a in row]
                       for row in allocation]
            available = [rng.randint(0, 4) for _ in range(w)]

            def replay(seq):
                work = list(available)
                seen = set()
                for p in seq:
                    if p in seen:
                        return False
                    seen.add(p)
                    need = [maximum[p][j] - allocation[p][j]
                            for j in range(w)]
                    if any(need[j] > work[j] for j in range(w)):
                        return False
                    for j in range(w):
                        work[j] += allocation[p][j]
                return len(seen) == n

            def any_safe():
                for perm in permutations(range(n)):
                    if replay(perm):
                        return True
                return False

            got = m.banker_safe_sequence(available, allocation, maximum)
            if any_safe():
                self.assertEqual(len(got), n)
                self.assertTrue(replay(got))
                # lowest-index rule determinism
                self.assertEqual(got, m.banker_safe_sequence(
                    available, allocation, maximum))
            else:
                self.assertEqual(got, [])


class TestResponseTimeWorstCase(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.response_time_worst_case(
            [[10, 3], [20, 5], [100, 2]]), [3, 8, 10])
        self.assertEqual(m.response_time_worst_case([[10, 9], [10, 2]]),
                         [9, -1])
        self.assertEqual(m.response_time_worst_case([[7, 3]]), [3])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.response_time_worst_case([])
        self.assertEqual(str(ctx.exception), refusal(
            "response_time_worst_case:empty:tasks"))
        with self.assertRaises(ValueError) as ctx:
            m.response_time_worst_case([[10]])
        self.assertEqual(str(ctx.exception), refusal(
            "response_time_worst_case:bad_shape:tasks[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.response_time_worst_case([[0, 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "response_time_worst_case:out_of_range:tasks[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.response_time_worst_case([[10, 11]])
        self.assertEqual(str(ctx.exception), refusal(
            "response_time_worst_case:out_of_range:tasks[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.response_time_worst_case([[10, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "response_time_worst_case:out_of_range:tasks[0][1]"))

    def test_heavy_accepted(self):
        self.assertEqual(m.response_time_worst_case([[1000000, 1]]), [1])

    def test_oracle(self):
        rng = random.Random(9104)
        for _ in range(60):
            n = rng.randint(1, 4)
            tasks = []
            for _ in range(n):
                period = rng.randint(2, 12)
                cost = rng.randint(1, period)
                tasks.append([period, cost])

            def simulate(i):
                # critical instant: every task releases at t=0, then at
                # multiples of its period; highest priority runs first
                period, cost = tasks[i]
                remaining = [0] * (i + 1)
                next_rel = [0] * (i + 1)
                t = 0
                while t < period:
                    for j in range(i + 1):
                        if next_rel[j] == t:
                            remaining[j] += tasks[j][1]
                            next_rel[j] += tasks[j][0]
                    run = None
                    for j in range(i + 1):
                        if remaining[j] > 0:
                            run = j
                            break
                    if run is not None:
                        remaining[run] -= 1
                        if run == i and remaining[i] == 0:
                            return t + 1
                    t += 1
                return -1

            want = [simulate(i) for i in range(n)]
            self.assertEqual(m.response_time_worst_case(tasks), want)


class TestErlangBBlockingExact(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.erlang_b_blocking_exact(2, 1, 1), Fraction(1, 5))
        self.assertEqual(m.erlang_b_blocking_exact(1, 1, 1), Fraction(1, 2))
        self.assertEqual(m.erlang_b_blocking_exact(0, 5, 1), Fraction(1))
        self.assertEqual(m.erlang_b_blocking_exact(3, 2, 1), Fraction(4, 19))
        self.assertEqual(m.erlang_b_blocking_exact(1, 0, 5), Fraction(0))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.erlang_b_blocking_exact(-1, 1, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "erlang_b_blocking_exact:out_of_range:channels"))
        with self.assertRaises(ValueError) as ctx:
            m.erlang_b_blocking_exact(MAX_ITEMS + 1, 1, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "erlang_b_blocking_exact:out_of_range:channels"))
        with self.assertRaises(ValueError) as ctx:
            m.erlang_b_blocking_exact(1, -1, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "erlang_b_blocking_exact:out_of_range:traffic_num"))
        with self.assertRaises(ValueError) as ctx:
            m.erlang_b_blocking_exact(1, 1, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "erlang_b_blocking_exact:out_of_range:traffic_den"))
        with self.assertRaises(ValueError) as ctx:
            m.erlang_b_blocking_exact(1.5, 1, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "erlang_b_blocking_exact:bad_type:channels"))

    def test_channels_cap(self):
        got = m.erlang_b_blocking_exact(MAX_ITEMS, 1, 1)
        self.assertTrue(got < 1)
        self.assertTrue(got > 0)

    def test_oracle(self):
        rng = random.Random(9105)
        for _ in range(40):
            c = rng.randint(0, 12)
            num = rng.randint(0, 8)
            den = rng.randint(1, 5)
            a = Fraction(num, den)
            terms = [a ** k / factorial(k) for k in range(c + 1)]
            want = terms[c] / sum(terms, Fraction(0)) if c else Fraction(1)
            self.assertEqual(m.erlang_b_blocking_exact(c, num, den), want)


class TestBirthDeathStationaryDist(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.birth_death_stationary_dist([1, 1], [1, 1]),
                         [Fraction(1, 3)] * 3)
        self.assertEqual(m.birth_death_stationary_dist([2, 1], [1, 2]),
                         [Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)])
        self.assertEqual(m.birth_death_stationary_dist([0, 5], [1, 1]),
                         [Fraction(1), Fraction(0), Fraction(0)])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.birth_death_stationary_dist([], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "birth_death_stationary_dist:empty:birth_rates"))
        with self.assertRaises(ValueError) as ctx:
            m.birth_death_stationary_dist([1, 1], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "birth_death_stationary_dist:bad_shape:death_rates"))
        with self.assertRaises(ValueError) as ctx:
            m.birth_death_stationary_dist([1], [0])
        self.assertEqual(str(ctx.exception), refusal(
            "birth_death_stationary_dist:out_of_range:death_rates[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.birth_death_stationary_dist([-1], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "birth_death_stationary_dist:out_of_range:birth_rates[0]"))

    def test_oracle(self):
        rng = random.Random(9106)
        for _ in range(40):
            n = rng.randint(1, 5)
            birth = [rng.randint(0, 4) for _ in range(n)]
            death = [rng.randint(1, 4) for _ in range(n)]
            got = m.birth_death_stationary_dist(birth, death)
            # global balance equations per state, plus normalization,
            # checked directly instead of via detailed balance
            states = n + 1
            for i in range(states):
                out_flow = Fraction(0)
                in_flow = Fraction(0)
                if i < n:
                    out_flow += got[i] * birth[i]
                if i > 0:
                    out_flow += got[i] * death[i - 1]
                if i > 0:
                    in_flow += got[i - 1] * birth[i - 1]
                if i < n:
                    in_flow += got[i + 1] * death[i]
                self.assertEqual(out_flow, in_flow)
            self.assertEqual(sum(got, Fraction(0)), 1)


class TestLamportClockTrace(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.lamport_clock_trace(
            [[0, 0], [0, 0], [1, 5], [0, 0]]), [1, 2, 6, 7])
        self.assertEqual(m.lamport_clock_trace([[1, 10]]), [11])
        self.assertEqual(m.lamport_clock_trace([[1, 0]]), [1])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.lamport_clock_trace([])
        self.assertEqual(str(ctx.exception), refusal(
            "lamport_clock_trace:empty:events"))
        with self.assertRaises(ValueError) as ctx:
            m.lamport_clock_trace([[2, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "lamport_clock_trace:out_of_range:events[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.lamport_clock_trace([[1, 10 ** 12 + 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "lamport_clock_trace:out_of_range:events[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.lamport_clock_trace([[0, 3]])
        self.assertEqual(str(ctx.exception), refusal(
            "lamport_clock_trace:bad_form:events[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.lamport_clock_trace([[1]])
        self.assertEqual(str(ctx.exception), refusal(
            "lamport_clock_trace:bad_shape:events[0]"))

    def test_clock_cap_accepted(self):
        self.assertEqual(m.lamport_clock_trace([[1, 10 ** 12]]),
                         [10 ** 12 + 1])

    def test_oracle(self):
        rng = random.Random(9107)
        for _ in range(60):
            n = rng.randint(1, 10)
            events = []
            for _ in range(n):
                if rng.random() < 0.5:
                    events.append([0, 0])
                else:
                    events.append([1, rng.randint(0, 30)])
            got = m.lamport_clock_trace(events)
            clock = 0
            want = []
            for kind, msg in events:
                clock = max(clock, msg) + 1 if kind else clock + 1
                want.append(clock)
            self.assertEqual(got, want)
            for i in range(1, len(got)):
                self.assertGreater(got[i], got[i - 1])
            for (kind, msg), value in zip(events, got):
                if kind:
                    self.assertGreater(value, msg)


class TestRttEstimatorTrace(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.rtt_estimator_trace([100, 200]),
                         [Fraction(300), Fraction(725, 2)])
        self.assertEqual(m.rtt_estimator_trace([100]), [Fraction(300)])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.rtt_estimator_trace([])
        self.assertEqual(str(ctx.exception), refusal(
            "rtt_estimator_trace:empty:samples"))
        with self.assertRaises(ValueError) as ctx:
            m.rtt_estimator_trace([0])
        self.assertEqual(str(ctx.exception), refusal(
            "rtt_estimator_trace:out_of_range:samples[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.rtt_estimator_trace([1000001])
        self.assertEqual(str(ctx.exception), refusal(
            "rtt_estimator_trace:out_of_range:samples[0]"))

    def test_oracle(self):
        rng = random.Random(9108)
        for _ in range(60):
            samples = [rng.randint(1, 500)
                       for _ in range(rng.randint(1, 10))]
            srtt = Fraction(samples[0])
            var = Fraction(samples[0]) / 2
            want = [srtt + 4 * var]
            for r in samples[1:]:
                var = (3 * var + abs(srtt - r)) / 4
                srtt = (7 * srtt + r) / 8
                want.append(srtt + 4 * var)
            got = m.rtt_estimator_trace(samples)
            self.assertEqual(got, want)
            for v in got:
                self.assertGreater(v, 0)


class TestCwndAimdTrace(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.cwnd_aimd_trace(6, 8, [4]), [2, 4, 8, 1, 2, 4])
        self.assertEqual(m.cwnd_aimd_trace(4, 1, []), [2, 3, 4, 5])
        self.assertEqual(m.cwnd_aimd_trace(5, 3, []), [2, 4, 5, 6, 7])
        self.assertEqual(m.cwnd_aimd_trace(3, 16, [1, 2, 3]), [1, 1, 1])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.cwnd_aimd_trace(0, 8, [])
        self.assertEqual(str(ctx.exception), refusal(
            "cwnd_aimd_trace:out_of_range:rounds"))
        with self.assertRaises(ValueError) as ctx:
            m.cwnd_aimd_trace(MAX_ITEMS + 1, 8, [])
        self.assertEqual(str(ctx.exception), refusal(
            "cwnd_aimd_trace:out_of_range:rounds"))
        with self.assertRaises(ValueError) as ctx:
            m.cwnd_aimd_trace(3, 0, [])
        self.assertEqual(str(ctx.exception), refusal(
            "cwnd_aimd_trace:out_of_range:ssthresh"))
        with self.assertRaises(ValueError) as ctx:
            m.cwnd_aimd_trace(3, 8, [4])
        self.assertEqual(str(ctx.exception), refusal(
            "cwnd_aimd_trace:out_of_range:losses[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.cwnd_aimd_trace(5, 8, [3, 3])
        self.assertEqual(str(ctx.exception), refusal(
            "cwnd_aimd_trace:bad_form:losses[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.cwnd_aimd_trace(5, 8, [4, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "cwnd_aimd_trace:bad_form:losses[1]"))

    def test_rounds_cap(self):
        self.assertEqual(len(m.cwnd_aimd_trace(MAX_ITEMS, 10 ** 6, [])),
                         MAX_ITEMS)

    def test_oracle(self):
        rng = random.Random(9109)
        for _ in range(60):
            rounds = rng.randint(1, 12)
            ssthresh = rng.randint(1, 10)
            losses = sorted(rng.sample(range(1, rounds + 1),
                                       rng.randint(0, rounds)))
            thresh = ssthresh
            cwnd = 1
            want = []
            li = 0
            for r in range(1, rounds + 1):
                if li < len(losses) and losses[li] == r:
                    li += 1
                    thresh = max(cwnd // 2, 1)
                    cwnd = 1
                elif cwnd < thresh:
                    cwnd *= 2
                else:
                    cwnd += 1
                want.append(cwnd)
            self.assertEqual(m.cwnd_aimd_trace(rounds, ssthresh, losses),
                             want)


class TestBuddyAllocationAddresses(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.buddy_allocation_addresses(
            8, [["alloc", 1], ["alloc", 1], ["free", 0], ["alloc", 2]]),
            [0, 1, None, 2])
        self.assertEqual(m.buddy_allocation_addresses(
            4, [["alloc", 4], ["alloc", 1]]), [0, -1])
        self.assertEqual(m.buddy_allocation_addresses(
            4, [["alloc", 2], ["alloc", 2], ["free", 0], ["alloc", 4]]),
            [0, 2, None, -1])
        self.assertEqual(m.buddy_allocation_addresses(
            4, [["alloc", 2], ["alloc", 2], ["free", 0], ["free", 1],
                ["alloc", 4]]),
            [0, 2, None, None, 0])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(0, [])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:out_of_range:total_size"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(2 ** 21, [])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:out_of_range:total_size"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(3, [])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:bad_form:total_size"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(4, [["alloc", 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:out_of_range:ops[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(4, [["alloc", 8]])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:out_of_range:ops[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(4, [["steal", 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:bad_form:ops[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(4, [["alloc", 1], ["free", 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:bad_form:ops[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(4, [["free", 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:bad_form:ops[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(4, [["alloc", 1], ["free", 0],
                                             ["free", 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:bad_form:ops[2]"))
        with self.assertRaises(ValueError) as ctx:
            m.buddy_allocation_addresses(4, [["alloc"]])
        self.assertEqual(str(ctx.exception), refusal(
            "buddy_allocation_addresses:bad_shape:ops[0]"))

    def test_arena_cap(self):
        self.assertEqual(
            m.buddy_allocation_addresses(2 ** 20, [["alloc", 1]]), [0])

    def test_oracle(self):
        rng = random.Random(9110)
        for _ in range(60):
            total = 2 ** rng.randint(1, 5)
            # independent oracle: free blocks kept as a set of
            # (address, size); candidates picked by smallest class
            # then lowest address. Op generation uses the same
            # oracle state so frees only reference live handles.
            free = {(0, total)}
            allocated = {}
            ops = []
            want = []
            for _ in range(rng.randint(1, 10)):
                if allocated and rng.random() < 0.4:
                    arg = rng.choice(sorted(allocated))
                    addr, cls = allocated.pop(arg)
                    free.add((addr, cls))
                    merged = True
                    while merged:
                        merged = False
                        for (a1, s1) in list(free):
                            buddy = a1 ^ s1
                            if (buddy, s1) in free:
                                free.discard((a1, s1))
                                free.discard((buddy, s1))
                                free.add((min(a1, buddy), s1 * 2))
                                merged = True
                                break
                    ops.append(["free", arg])
                    want.append(None)
                else:
                    size = rng.randint(1, total)
                    cls = 1
                    while cls < size:
                        cls *= 2
                    candidates = sorted(
                        (bsize, addr) for addr, bsize in free
                        if bsize >= cls)
                    if not candidates:
                        addr = -1
                    else:
                        bsize, addr = candidates[0]
                        free.discard((addr, bsize))
                        while bsize > cls:
                            bsize //= 2
                            free.add((addr + bsize, bsize))
                        allocated[len(ops)] = (addr, cls)
                    ops.append(["alloc", size])
                    want.append(addr)
            self.assertEqual(m.buddy_allocation_addresses(total, ops),
                             want)

    def test_invariants(self):
        rng = random.Random(9111)
        for _ in range(40):
            total = 2 ** rng.randint(1, 6)
            ops = []
            live = []
            for _ in range(rng.randint(1, 12)):
                # size-1 allocs with fewer live blocks than total
                # cells can never fail: some free block always fits
                if live and (rng.random() < 0.4 or len(live) == total):
                    pick = rng.choice(live)
                    ops.append(["free", pick])
                    live.remove(pick)
                else:
                    ops.append(["alloc", 1])
                    live.append(len(ops) - 1)
            got = m.buddy_allocation_addresses(total, ops)
            spans = {}
            for i, ((verb, arg), res) in enumerate(zip(ops, got)):
                if verb == "alloc":
                    self.assertNotEqual(res, -1)
                    self.assertTrue(0 <= res < total)
                    spans[i] = (res, res + 1)
                else:
                    spans.pop(arg)
            live_spans = sorted(spans.values())
            for (a1, b1), (a2, b2) in zip(live_spans, live_spans[1:]):
                self.assertLessEqual(b1, a2)


class TestRegistryKnowsBatch91(unittest.TestCase):
    def test_names(self):
        from app.modules.instinct_doc.p235_concepts_registry import ENTRIES
        names = [e["name"] for e in ENTRIES]
        for name in ("round_robin_finish_times", "stride_schedule_order",
                     "banker_safe_sequence", "response_time_worst_case",
                     "erlang_b_blocking_exact",
                     "birth_death_stationary_dist", "lamport_clock_trace",
                     "rtt_estimator_trace", "cwnd_aimd_trace",
                     "buddy_allocation_addresses"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
