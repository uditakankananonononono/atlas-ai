"""P235 batch 92: replacement concepts from auditor screens."""
import random
import unittest
from fractions import Fraction
from itertools import accumulate, permutations

from app.modules.instinct_doc import p235_concepts_batch92 as m
from app.modules.instinct_doc.p235_concepts_registry import MAX_ITEMS


def refusal(code):
    return "P235:" + code


class TestSkylineOutline(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.skyline_outline(
            [[2, 9, 10], [3, 7, 15], [5, 12, 12], [15, 20, 10],
             [19, 24, 8]]),
            [[2, 10], [3, 15], [7, 12], [12, 0], [15, 10], [20, 8],
             [24, 0]])
        self.assertEqual(m.skyline_outline([[1, 2, 1]]),
                         [[1, 1], [2, 0]])
        self.assertEqual(m.skyline_outline([[0, 2, 3], [2, 5, 3]]),
                         [[0, 3], [5, 0]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.skyline_outline([])
        self.assertEqual(str(ctx.exception), refusal(
            "skyline_outline:empty:buildings"))
        with self.assertRaises(ValueError) as ctx:
            m.skyline_outline([[1, 2]])
        self.assertEqual(str(ctx.exception), refusal(
            "skyline_outline:bad_shape:buildings[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.skyline_outline([[2, 2, 5]])
        self.assertEqual(str(ctx.exception), refusal(
            "skyline_outline:out_of_range:buildings[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.skyline_outline([[0, 1, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "skyline_outline:out_of_range:buildings[0][2]"))
        with self.assertRaises(ValueError) as ctx:
            m.skyline_outline([[-1, 1, 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "skyline_outline:out_of_range:buildings[0][0]"))

    def test_oracle(self):
        rng = random.Random(9201)
        for _ in range(60):
            buildings = []
            for _ in range(rng.randint(1, 8)):
                left = rng.randint(0, 20)
                right = left + rng.randint(1, 8)
                buildings.append([left, right, rng.randint(1, 10)])
            # brute oracle: sample the max height just right of every
            # edge coordinate by scanning every building
            xs = sorted({v for b in buildings for v in b[:2]})
            want = []
            prev = 0
            for x in xs:
                top = 0
                for left, right, height in buildings:
                    if left <= x < right:
                        top = max(top, height)
                if top != prev:
                    want.append([x, top])
                    prev = top
            self.assertEqual(m.skyline_outline(buildings), want)


class TestCarFleetArrivals(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(
            m.car_fleet_arrivals(12, [10, 8, 0, 5, 3], [2, 4, 1, 1, 3]),
            3)
        self.assertEqual(m.car_fleet_arrivals(10, [3], [3]), 1)
        self.assertEqual(m.car_fleet_arrivals(10, [0, 5], [2, 1]), 1)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.car_fleet_arrivals(0, [1], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "car_fleet_arrivals:out_of_range:target"))
        with self.assertRaises(ValueError) as ctx:
            m.car_fleet_arrivals(10, [10], [1])
        self.assertEqual(str(ctx.exception), refusal(
            "car_fleet_arrivals:out_of_range:positions[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.car_fleet_arrivals(10, [1, 1], [1, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "car_fleet_arrivals:duplicate:positions[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.car_fleet_arrivals(10, [1], [1, 2])
        self.assertEqual(str(ctx.exception), refusal(
            "car_fleet_arrivals:bad_shape:speeds"))
        with self.assertRaises(ValueError) as ctx:
            m.car_fleet_arrivals(10, [1], [0])
        self.assertEqual(str(ctx.exception), refusal(
            "car_fleet_arrivals:out_of_range:speeds[0]"))

    def test_oracle(self):
        rng = random.Random(9202)
        for _ in range(60):
            n = rng.randint(1, 8)
            target = rng.randint(10, 20)
            positions = rng.sample(range(target), n)
            speeds = [rng.randint(1, 5) for _ in range(n)]
            # record-high formulation over descending positions
            order = sorted(range(n), key=lambda i: -positions[i])
            times = [Fraction(target - positions[i], speeds[i])
                     for i in order]
            want = sum(1 for i, hi in enumerate(accumulate(
                times, max)) if i == 0 or times[i] == hi
                and times[i] > max(times[:i]))
            self.assertEqual(
                m.car_fleet_arrivals(target, positions, speeds), want)


class TestChampagneTowerFill(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.champagne_tower_fill(1, 1, 1), Fraction(0))
        self.assertEqual(m.champagne_tower_fill(2, 1, 1), Fraction(1, 2))
        self.assertEqual(m.champagne_tower_fill(4, 2, 0), Fraction(1, 4))
        self.assertEqual(m.champagne_tower_fill(4, 2, 1), Fraction(1, 2))
        self.assertEqual(m.champagne_tower_fill(100, 3, 1), Fraction(1))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.champagne_tower_fill(-1, 0, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "champagne_tower_fill:out_of_range:poured"))
        with self.assertRaises(ValueError) as ctx:
            m.champagne_tower_fill(1, 2001, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "champagne_tower_fill:out_of_range:row"))
        with self.assertRaises(ValueError) as ctx:
            m.champagne_tower_fill(1, 2, 3)
        self.assertEqual(str(ctx.exception), refusal(
            "champagne_tower_fill:out_of_range:glass"))

    def test_row_cap(self):
        self.assertEqual(m.champagne_tower_fill(1, 2000, 1000),
                         Fraction(0))

    def test_oracle(self):
        rng = random.Random(9203)
        for _ in range(40):
            poured = rng.randint(0, 12)
            row = rng.randint(0, 6)
            glass = rng.randint(0, row)
            # full triangular simulation, every glass tracked
            tri = [[Fraction(poured)]]
            for r in range(1, row + 2):
                level = [Fraction(0)] * (r + 1)
                for i, v in enumerate(tri[r - 1]):
                    if v > 1:
                        level[i] += (v - 1) / 2
                        level[i + 1] += (v - 1) / 2
                tri.append(level)
            want = min(tri[row][glass], Fraction(1))
            self.assertEqual(m.champagne_tower_fill(poured, row, glass),
                             want)


class TestExclusiveTimeFunctions(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.exclusive_time_functions(
            ["0:start:0", "1:start:2", "1:end:5", "0:end:6"], 2), [3, 4])
        self.assertEqual(m.exclusive_time_functions(
            ["0:start:0", "1:start:1", "1:end:2", "0:end:5"], 2), [4, 2])
        self.assertEqual(m.exclusive_time_functions(
            ["0:start:0", "0:end:0"], 1), [1])
        self.assertEqual(m.exclusive_time_functions(
            ["0:start:0", "1:start:1", "1:end:1", "0:end:2"], 2), [2, 1])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:end:0"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:unbalanced:logs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:0"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:unbalanced:logs"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:0", "1:start:1",
                                        "0:end:2", "1:end:3"], 2)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:unbalanced:logs[2]"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:x"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:bad_time:logs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:pause:0"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:bad_op:logs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["2:start:0", "2:end:0"], 2)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:out_of_range:logs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions([], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:empty:logs"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:0", "0:end:1"], True)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:bad_type:n"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(None, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:bad_type:logs"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:1", "0:end:0"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:out_of_order:logs[1]"))

    def test_cap_pins(self):
        self.assertEqual(m.exclusive_time_functions(
            ["0:start:0", "0:end:0"], 10000)[0], 1)
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:0", "0:end:0"], 10001)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:out_of_range:n"))
        # entry-length cap at 64, pinned n and n+1
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:" + "9" * 57], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:too_long:logs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:" + "9" * 56], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:too_long:logs[0]"))
        # id digit cap at 5, pinned n and n+1
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["99999:start:0"], 5)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:out_of_range:logs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["999999:start:0"], 5)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:too_long:logs[0]"))
        # timestamp digit cap at 10, pinned n and n+1
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:9999999999"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:out_of_range:logs[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["0:start:99999999999"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:too_long:logs[0]"))
        # digit caps refuse before int(): a 5000-digit id never
        # reaches raw conversion
        with self.assertRaises(ValueError) as ctx:
            m.exclusive_time_functions(["9" * 5000 + ":start:0"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "exclusive_time_functions:too_long:logs[0]"))

    def test_oracle(self):
        rng = random.Random(9210)
        for _ in range(60):
            n = rng.randint(1, 6)
            # build a random well-formed nested call tree with gaps
            logs = []
            intervals = {}
            children = {f: [] for f in range(n)}
            counter = [0]
            def emit(fid, depth, lo, hi):
                counter[0] += 1
                start = counter[0]
                stack_top = depth[-1] if depth else None
                logs.append("%d:start:%d" % (fid, start))
                kids = []
                for _ in range(rng.randint(0, 2)):
                    if counter[0] > 25:
                        break
                    kid = rng.randrange(n)
                    counter[0] += rng.randint(0, 2)
                    kids.append(emit(kid, depth + [fid], lo, hi))
                counter[0] += rng.randint(0, 2)
                end = counter[0]
                logs.append("%d:end:%d" % (fid, end))
                intervals.setdefault(fid, []).append((start, end))
                if depth:
                    children[depth[-1]].append((start, end))
                return (start, end)
            for _ in range(rng.randint(1, 2)):
                emit(rng.randrange(n), [], 0, 0)
                counter[0] += rng.randint(0, 2)
            # independent oracle: total span minus direct child spans,
            # children found by re-scanning the log with a fresh stack
            totals = {}
            kid_spans = {f: [] for f in range(n)}
            stack = []
            for entry in logs:
                fid_s, op, ts_s = entry.split(":")
                fid, ts = int(fid_s), int(ts_s)
                if op == "start":
                    stack.append((fid, ts))
                else:
                    fid0, start = stack.pop()
                    span = ts - start + 1
                    totals[fid0] = totals.get(fid0, 0) + span
                    if stack:
                        kid_spans[stack[-1][0]].append(span)
            want = [totals.get(f, 0) - sum(kid_spans[f]) for f in range(n)]
            self.assertEqual(m.exclusive_time_functions(logs, n), want)


class TestBeautifulArrangementCount(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.beautiful_arrangement_count(1), 1)
        self.assertEqual(m.beautiful_arrangement_count(2), 2)
        self.assertEqual(m.beautiful_arrangement_count(5), 10)
        self.assertEqual(m.beautiful_arrangement_count(15), 24679)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.beautiful_arrangement_count(0)
        self.assertEqual(str(ctx.exception), refusal(
            "beautiful_arrangement_count:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.beautiful_arrangement_count(16)
        self.assertEqual(str(ctx.exception), refusal(
            "beautiful_arrangement_count:out_of_range:n"))

    def test_oracle(self):
        for n in range(1, 8):
            want = sum(
                1 for perm in permutations(range(1, n + 1))
                if all(perm[i] % (i + 1) == 0 or (i + 1) % perm[i] == 0
                       for i in range(n)))
            self.assertEqual(m.beautiful_arrangement_count(n), want)


class TestQueueReconstructionHeight(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.queue_reconstruction_height(
            [[7, 0], [4, 4], [7, 1], [5, 0], [6, 1], [5, 2]]),
            [[5, 0], [7, 0], [5, 2], [6, 1], [4, 4], [7, 1]])
        self.assertEqual(m.queue_reconstruction_height([[1, 0]]),
                         [[1, 0]])
        self.assertEqual(m.queue_reconstruction_height(
            [[6, 0], [5, 0], [4, 0]]),
            [[4, 0], [5, 0], [6, 0]])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.queue_reconstruction_height([])
        self.assertEqual(str(ctx.exception), refusal(
            "queue_reconstruction_height:empty:people"))
        with self.assertRaises(ValueError) as ctx:
            m.queue_reconstruction_height([[5]])
        self.assertEqual(str(ctx.exception), refusal(
            "queue_reconstruction_height:bad_shape:people[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.queue_reconstruction_height([[0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "queue_reconstruction_height:out_of_range:people[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.queue_reconstruction_height([[5, -1]])
        self.assertEqual(str(ctx.exception), refusal(
            "queue_reconstruction_height:out_of_range:people[0][1]"))
        with self.assertRaises(ValueError) as ctx:
            m.queue_reconstruction_height([[5, 1]])
        self.assertEqual(str(ctx.exception), refusal(
            "queue_reconstruction_height:bad_form:people"))

    def test_oracle(self):
        rng = random.Random(9205)
        for _ in range(60):
            n = rng.randint(1, 6)
            heights = [rng.randint(1, 9) for _ in range(n)]
            # build a valid instance: shuffle an order, then read the
            # ahead counts off it
            order = list(range(n))
            rng.shuffle(order)
            people = []
            for pos, i in enumerate(order):
                ahead = sum(1 for j in order[:pos]
                            if heights[j] >= heights[i])
                people.append([heights[i], ahead])
            shuffled = [list(p) for p in people]
            rng.shuffle(shuffled)
            got = m.queue_reconstruction_height(shuffled)

            def valid(seq):
                for i, (h, k) in enumerate(seq):
                    if sum(1 for p in seq[:i] if p[0] >= h) != k:
                        return False
                return True

            self.assertTrue(valid(got))
            # uniqueness: brute force all permutations
            found = set()
            for perm in permutations(range(n)):
                seq = [shuffled[i] for i in perm]
                if valid(seq):
                    found.add(tuple(tuple(p) for p in seq))
            self.assertEqual(len(found), 1)
            self.assertEqual(
                tuple(tuple(p) for p in got), next(iter(found)))


class TestPalindromePairsList(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.palindrome_pairs_list(
            ["abcd", "dcba", "lls", "s", "sssll"]),
            [[0, 1], [1, 0], [2, 4], [3, 2]])
        self.assertEqual(m.palindrome_pairs_list(["a", "b", "aa"]),
                         [[0, 2], [2, 0]])
        self.assertEqual(m.palindrome_pairs_list(["bat", "tab", "cat"]),
                         [[0, 1], [1, 0]])
        self.assertEqual(m.palindrome_pairs_list(["ab", "cd"]), [])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.palindrome_pairs_list(["ab", "ab"])
        self.assertEqual(str(ctx.exception), refusal(
            "palindrome_pairs_list:duplicate:words[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.palindrome_pairs_list(["ab", ""])
        self.assertEqual(str(ctx.exception), refusal(
            "palindrome_pairs_list:empty:words[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.palindrome_pairs_list(["ab", 3.5])
        self.assertEqual(str(ctx.exception), refusal(
            "palindrome_pairs_list:bad_type:words[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.palindrome_pairs_list(["ab", True])
        self.assertEqual(str(ctx.exception), refusal(
            "palindrome_pairs_list:bad_type:words[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.palindrome_pairs_list("ab")
        self.assertEqual(str(ctx.exception), refusal(
            "palindrome_pairs_list:bad_type:words"))
        with self.assertRaises(ValueError) as ctx:
            m.palindrome_pairs_list(["a" * 51])
        self.assertEqual(str(ctx.exception), refusal(
            "palindrome_pairs_list:too_long:words[0]"))

    def test_cap_pins(self):
        words = ["w%d" % i for i in range(300)]
        self.assertEqual(m.palindrome_pairs_list(words), [])
        with self.assertRaises(ValueError) as ctx:
            m.palindrome_pairs_list(["w%d" % i for i in range(301)])
        self.assertEqual(str(ctx.exception), refusal(
            "palindrome_pairs_list:too_many:words"))
        self.assertEqual(m.palindrome_pairs_list(["a" * 50, "b"]), [])
        with self.assertRaises(ValueError) as ctx:
            m.palindrome_pairs_list(["a" * 51])
        self.assertEqual(str(ctx.exception), refusal(
            "palindrome_pairs_list:too_long:words[0]"))

    def test_oracle(self):
        rng = random.Random(9211)
        for _ in range(100):
            k = rng.randint(1, 8)
            words = set()
            while len(words) < k:
                words.add("".join(rng.choice("ab")
                                  for _ in range(rng.randint(1, 4))))
            words = sorted(words)
            want = []  # independent oracle: test every ordered pair
            for i in range(len(words)):
                for j in range(len(words)):
                    if i != j:
                        cat = words[i] + words[j]
                        if cat == cat[::-1]:
                            want.append([i, j])
            self.assertEqual(m.palindrome_pairs_list(words), want)


class TestKCoreNumbers(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.k_core_numbers([[]]), [0])
        self.assertEqual(m.k_core_numbers([[1], [0, 2], [1]]),
                         [1, 1, 1])
        self.assertEqual(m.k_core_numbers([[1, 2], [0, 2], [0, 1]]),
                         [2, 2, 2])
        self.assertEqual(
            m.k_core_numbers([[1, 2, 3], [0, 2, 3], [0, 1, 3],
                              [0, 1, 2]]),
            [3, 3, 3, 3])
        self.assertEqual(m.k_core_numbers([[1, 2, 3], [0], [0], [0]]),
                         [1, 1, 1, 1])

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers([])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:empty:adj"))
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers([[0]])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:self_loop:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers([[1, 1], [0, 0]])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:duplicate:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers([[1], []])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:asymmetric:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers([[2]])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:out_of_range:adj[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers(["01"])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:bad_type:adj[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers([[True], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:bad_type:adj[0][0]"))
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers([[1.5], [0]])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:bad_type:adj[0][0]"))

    def test_cap_pins(self):
        self.assertEqual(m.k_core_numbers([[] for _ in range(10000)]),
                         [0] * 10000)
        with self.assertRaises(ValueError) as ctx:
            m.k_core_numbers([[] for _ in range(10001)])
        self.assertEqual(str(ctx.exception), refusal(
            "k_core_numbers:too_many:adj"))

    def test_oracle(self):
        rng = random.Random(9210)
        for _ in range(60):
            n = rng.randint(1, 12)
            adj = [set() for _ in range(n)]
            for a in range(n):
                for b in range(a + 1, n):
                    if rng.random() < 0.3:
                        adj[a].add(b)
                        adj[b].add(a)
            arg = [sorted(s) for s in adj]
            # independent oracle: naive peeling that recomputes
            # degrees from scratch after every removal
            live = {i: set(s) for i, s in enumerate(adj)}
            want = {}
            best = 0
            while live:
                u = min(live, key=lambda x: (len(live[x]), x))
                best = max(best, len(live[u]))
                want[u] = best
                del live[u]
                for s in live.values():
                    s.discard(u)
            self.assertEqual(m.k_core_numbers(arg),
                             [want[i] for i in range(n)])


class TestBurstBalloonsMax(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.burst_balloons_max([3, 1, 5, 8]), 167)
        self.assertEqual(m.burst_balloons_max([9, 1]), 18)
        self.assertEqual(m.burst_balloons_max([]), 0)
        self.assertEqual(m.burst_balloons_max([5]), 5)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.burst_balloons_max([1] * 151)
        self.assertEqual(str(ctx.exception), refusal(
            "burst_balloons_max:too_many:values"))
        with self.assertRaises(ValueError) as ctx:
            m.burst_balloons_max([0])
        self.assertEqual(str(ctx.exception), refusal(
            "burst_balloons_max:out_of_range:values[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.burst_balloons_max([1000001])
        self.assertEqual(str(ctx.exception), refusal(
            "burst_balloons_max:out_of_range:values[0]"))

    def test_cap(self):
        self.assertGreater(m.burst_balloons_max([1] * 150), 0)

    def test_oracle(self):
        rng = random.Random(9208)
        for _ in range(40):
            values = [rng.randint(1, 9) for _ in range(rng.randint(0, 7))]
            memo = {}

            def walk(left, right):
                # choose the FIRST burst inside the open span instead
                if right - left <= 1:
                    return 0
                if (left, right) in memo:
                    return memo[(left, right)]
                nums = [1] + values + [1]
                best = 0
                for mid in range(left + 1, right):
                    gain = (nums[left] * nums[mid] * nums[right]
                            + walk(left, mid) + walk(mid, right))
                    best = max(best, gain)
                memo[(left, right)] = best
                return best

            self.assertEqual(m.burst_balloons_max(values),
                             walk(0, len(values) + 1))


class TestScrambleStringCheck(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.scramble_string_check("great", "rgeat"))
        self.assertFalse(m.scramble_string_check("abcde", "caebd"))
        self.assertTrue(m.scramble_string_check("a", "a"))
        self.assertTrue(m.scramble_string_check("ab", "ba"))
        self.assertFalse(m.scramble_string_check("abc", "abcd"))

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.scramble_string_check("a" * 31, "a" * 31)
        self.assertEqual(str(ctx.exception), refusal(
            "scramble_string_check:too_many:s1"))
        with self.assertRaises(ValueError) as ctx:
            m.scramble_string_check("a", 5)
        self.assertEqual(str(ctx.exception), refusal(
            "scramble_string_check:bad_type:s2"))

    def test_oracle(self):
        rng = random.Random(9209)
        alphabet = "ab"
        memo = {}

        def walk(a, b):
            # index-free recursive definition over both split orders,
            # written independently of the module's slicing
            if (a, b) in memo:
                return memo[(a, b)]
            if a == b:
                memo[(a, b)] = True
                return True
            from collections import Counter
            if Counter(a) != Counter(b):
                memo[(a, b)] = False
                return False
            n = len(a)
            for k in range(1, n):
                same = walk(a[:k], b[:k]) and walk(a[k:], b[k:])
                swap = walk(a[:k], b[n - k:]) and walk(a[k:], b[:n - k])
                if same or swap:
                    memo[(a, b)] = True
                    return True
            memo[(a, b)] = False
            return False

        for _ in range(60):
            n = rng.randint(1, 8)
            a = "".join(rng.choice(alphabet) for _ in range(n))
            b = "".join(rng.choice(alphabet) for _ in range(n))
            memo.clear()
            self.assertEqual(m.scramble_string_check(a, b), walk(a, b))
        # constructive True cases: scramble a random string
        for _ in range(20):
            n = rng.randint(2, 8)
            a = "".join(rng.choice("xyz") for _ in range(n))
            chars = list(a)
            rng.shuffle(chars)
            b = "".join(chars)
            memo.clear()
            self.assertEqual(
                m.scramble_string_check(a, b), walk(a, b))


class TestRegistryKnowsBatch92(unittest.TestCase):
    def test_names(self):
        from app.modules.instinct_doc.p235_concepts_registry import (
            ENTRIES)
        names = [e["name"] for e in ENTRIES]
        for name in ("skyline_outline", "car_fleet_arrivals",
                     "champagne_tower_fill", "exclusive_time_functions",
                     "beautiful_arrangement_count",
                     "queue_reconstruction_height",
                     "palindrome_pairs_list", "k_core_numbers",
                     "burst_balloons_max", "scramble_string_check"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
