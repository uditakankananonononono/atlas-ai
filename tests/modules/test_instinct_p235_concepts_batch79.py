"""Tests for P235 concepts batch 79 (doc 781-790)."""
import random
import unittest
from collections import deque
from itertools import combinations

from app.modules.instinct_doc import p235_concepts_batch79 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch70Test(unittest.TestCase):
    def test_stock_max_profit_twice(self):
        self.assertEqual(m.stock_max_profit_twice(
            [3, 3, 5, 0, 0, 3, 1, 4]), 6)
        self.assertEqual(m.stock_max_profit_twice([1, 2, 3, 4, 5]),
                         4)
        self.assertEqual(m.stock_max_profit_twice([7, 6, 4, 3, 1]),
                         0)
        # oracle: best pair of non-overlapping buy/sell intervals
        rng = random.Random(7001)
        for _ in range(40):
            prices = [rng.randint(0, 9)
                      for _ in range(rng.randint(1, 9))]
            n = len(prices)
            best = 0
            for b1 in range(n):
                for s1 in range(b1, n):
                    for b2 in range(s1, n):
                        for s2 in range(b2, n):
                            gain = (prices[s1] - prices[b1]
                                    + prices[s2] - prices[b2])
                            if gain > best:
                                best = gain
            self.assertEqual(m.stock_max_profit_twice(prices),
                             best, prices)
        with self.assertRaises(ValueError):
            m.stock_max_profit_twice([-1, 2])

    def test_min_cost_climbing_stairs(self):
        self.assertEqual(m.min_cost_climbing_stairs([10, 15, 20]),
                         15)
        self.assertEqual(m.min_cost_climbing_stairs(
            [1, 100, 1, 1, 1, 100, 1, 1, 100, 1]), 6)
        # oracle: plain recursion from the top
        rng = random.Random(7002)
        for _ in range(50):
            cost = [rng.randint(0, 20)
                    for _ in range(rng.randint(2, 12))]
            memo = {}

            def rec(i):
                if i < 2:
                    return 0
                if i not in memo:
                    memo[i] = min(rec(i - 1) + cost[i - 1],
                                  rec(i - 2) + cost[i - 2])
                return memo[i]
            self.assertEqual(m.min_cost_climbing_stairs(cost),
                             rec(len(cost)), cost)
        with self.assertRaises(ValueError):
            m.min_cost_climbing_stairs([5])

    def test_delete_and_earn(self):
        self.assertEqual(m.delete_and_earn([3, 4, 2]), 6)
        self.assertEqual(m.delete_and_earn([2, 2, 3, 3, 3, 4]), 9)
        # oracle: best subset of distinct values, no two adjacent
        rng = random.Random(7003)
        for _ in range(40):
            items = [rng.randint(1, 9)
                     for _ in range(rng.randint(1, 12))]
            sums = {}
            for v in items:
                sums[v] = sums.get(v, 0) + v
            vals = sorted(sums)
            best = 0
            for r in range(len(vals) + 1):
                for combo in combinations(vals, r):
                    if all(combo[i + 1] - combo[i] > 1
                           for i in range(len(combo) - 1)):
                        best = max(best, sum(sums[v]
                                             for v in combo))
            self.assertEqual(m.delete_and_earn(items), best, items)
        with self.assertRaises(ValueError):
            m.delete_and_earn([0, 1])

    def test_minimum_swaps_sort(self):
        self.assertEqual(m.minimum_swaps_sort([2, 8, 5, 4]), 1)
        self.assertEqual(m.minimum_swaps_sort([1, 2, 3]), 0)
        self.assertEqual(m.minimum_swaps_sort([4, 3, 2, 1]), 2)
        # oracle: BFS over the swap space
        rng = random.Random(7004)
        for _ in range(30):
            n = rng.randint(2, 6)
            items = list(range(1, n + 1))
            rng.shuffle(items)
            goal = tuple(sorted(items))
            dist = {tuple(items): 0}
            q = deque([tuple(items)])
            while q:
                cur = q.popleft()
                if cur == goal:
                    break
                for i in range(n):
                    for j in range(i + 1, n):
                        nxt = list(cur)
                        nxt[i], nxt[j] = nxt[j], nxt[i]
                        nxt = tuple(nxt)
                        if nxt not in dist:
                            dist[nxt] = dist[cur] + 1
                            q.append(nxt)
            self.assertEqual(m.minimum_swaps_sort(items),
                             dist[goal], items)
        with self.assertRaises(ValueError):
            m.minimum_swaps_sort([2, 2, 1])

    def test_reorganize_string_arrange(self):
        self.assertEqual(m.reorganize_string_arrange("aab"), "aba")
        self.assertEqual(m.reorganize_string_arrange("aaab"), "")
        self.assertEqual(m.reorganize_string_arrange("aaabbc"),
                         "ababac")
        self.assertEqual(m.reorganize_string_arrange(""), "")
        # property oracle: permutation, no equal neighbors,
        # empty exactly when a majority exists
        rng = random.Random(7005)
        for _ in range(80):
            text = "".join(rng.choice("abc")
                           for _ in range(rng.randint(0, 10)))
            got = m.reorganize_string_arrange(text)
            counts = {}
            for ch in text:
                counts[ch] = counts.get(ch, 0) + 1
            possible = (not counts
                        or max(counts.values())
                        <= (len(text) + 1) // 2)
            if not possible:
                self.assertEqual(got, "", text)
            else:
                self.assertEqual(sorted(got), sorted(text), text)
                self.assertTrue(all(got[i] != got[i + 1]
                                    for i in range(len(got) - 1)),
                                (text, got))
        with self.assertRaises(ValueError):
            m.reorganize_string_arrange("aB")

    def test_min_swaps_parens_balance(self):
        self.assertEqual(m.min_swaps_parens_balance(")()("), 1)
        self.assertEqual(m.min_swaps_parens_balance(")))((("), 2)
        self.assertEqual(m.min_swaps_parens_balance(""), 0)
        self.assertEqual(m.min_swaps_parens_balance("()()"), 0)
        # oracle: BFS over swaps of any two positions
        rng = random.Random(7006)
        for _ in range(25):
            half = rng.randint(1, 4)
            chars = ["("] * half + [")"] * half
            rng.shuffle(chars)
            text = "".join(chars)

            def balanced(s):
                bal = 0
                for ch in s:
                    bal += 1 if ch == "(" else -1
                    if bal < 0:
                        return False
                return bal == 0
            n = len(text)
            dist = {text: 0}
            q = deque([text])
            want = None
            while q:
                cur = q.popleft()
                if balanced(cur):
                    want = dist[cur]
                    break
                for i in range(n):
                    for j in range(i + 1, n):
                        if cur[i] == cur[j]:
                            continue
                        nxt = (cur[:i] + cur[j] + cur[i + 1:j]
                               + cur[i] + cur[j + 1:])
                        if nxt not in dist:
                            dist[nxt] = dist[cur] + 1
                            q.append(nxt)
            self.assertEqual(m.min_swaps_parens_balance(text),
                             want, text)
        with self.assertRaises(ValueError):
            m.min_swaps_parens_balance("(((")
        with self.assertRaises(ValueError):
            m.min_swaps_parens_balance("(())x")

    def test_min_taps_garden(self):
        self.assertEqual(m.min_taps_garden(5, [3, 4, 1, 1, 0, 0]),
                         1)
        self.assertEqual(m.min_taps_garden(3, [0, 0, 0, 0]), -1)
        self.assertEqual(m.min_taps_garden(
            7, [1, 2, 1, 0, 2, 1, 0, 1]), 3)
        # oracle: smallest tap subset covering [0, n]
        rng = random.Random(7007)
        for _ in range(40):
            n = rng.randint(1, 7)
            ranges = [rng.randint(0, n) for _ in range(n + 1)]
            want = -1
            for r in range(1, n + 2):
                ok = False
                for combo in combinations(range(n + 1), r):
                    # continuous interval coverage of [0, n]
                    ivs = sorted((max(0, i - ranges[i]),
                                  min(n, i + ranges[i]))
                                 for i in combo)
                    end = 0
                    good = True
                    for lo, hi in ivs:
                        if lo > end:
                            good = False
                            break
                        end = max(end, hi)
                    if good and end >= n:
                        ok = True
                        break
                if ok:
                    want = r
                    break
            self.assertEqual(m.min_taps_garden(n, ranges), want,
                             (n, ranges))
        with self.assertRaises(ValueError):
            m.min_taps_garden(3, [1, 1, 1])

    def test_min_refuel_stops(self):
        self.assertEqual(m.min_refuel_stops(
            100, 10, [[10, 60], [20, 30], [30, 30], [60, 40]]), 2)
        self.assertEqual(m.min_refuel_stops(100, 1, []), -1)
        self.assertEqual(m.min_refuel_stops(1, 1, []), 0)
        # oracle: Dijkstra over (station index, tank) minimizing
        # stops
        rng = random.Random(7008)
        for _ in range(40):
            k = rng.randint(0, 6)
            target = rng.randint(5, 30)
            stations = []
            prev = 0
            for _ in range(k):
                prev += rng.randint(1, max(1, (target - prev)))
                if prev >= target:
                    break
                stations.append([prev, rng.randint(1, 15)])
            start = rng.randint(0, 10)
            import heapq
            dist = {(0, start): 0}
            heap = [(0, 0, start)]
            want = -1
            while heap:
                stops, i, tank = heapq.heappop(heap)
                if tank >= target:
                    want = stops
                    break
                if dist.get((i, tank), -1) != stops:
                    continue
                if i < len(stations) and tank >= stations[i][0]:
                    nt = tank + stations[i][1]
                    key = (i + 1, nt)
                    if stops + 1 < dist.get(key, 1 << 30):
                        dist[key] = stops + 1
                        heapq.heappush(heap, (stops + 1, i + 1,
                                              nt))
                    key = (i + 1, tank)
                    if stops < dist.get(key, 1 << 30):
                        dist[key] = stops
                        heapq.heappush(heap, (stops, i + 1, tank))
            self.assertEqual(m.min_refuel_stops(target, start,
                                                stations), want,
                             (target, start, stations))
        with self.assertRaises(ValueError):
            m.min_refuel_stops(10, 5, [[12, 3]])
        with self.assertRaises(ValueError):
            m.min_refuel_stops(10, 5, [[3, 3], [3, 3]])

    def test_max_erasure_value(self):
        self.assertEqual(m.max_erasure_value([4, 2, 4, 5, 6]), 17)
        self.assertEqual(m.max_erasure_value(
            [5, 2, 1, 2, 5, 2, 1, 2, 5]), 8)
        # oracle: best sum over windows of distinct values
        rng = random.Random(7009)
        for _ in range(60):
            items = [rng.randint(1, 9)
                     for _ in range(rng.randint(1, 12))]
            best = 0
            for i in range(len(items)):
                seen = set()
                total = 0
                for j in range(i, len(items)):
                    if items[j] in seen:
                        break
                    seen.add(items[j])
                    total += items[j]
                    best = max(best, total)
            self.assertEqual(m.max_erasure_value(items), best,
                             items)
        with self.assertRaises(ValueError):
            m.max_erasure_value([0, 1])

    def test_longest_unique_substring_length(self):
        self.assertEqual(m.longest_unique_substring_length(
            "abcabcbb"), 3)
        self.assertEqual(m.longest_unique_substring_length(
            "pwwkew"), 3)
        self.assertEqual(m.longest_unique_substring_length(""), 0)
        # oracle: longest window whose characters are all distinct
        rng = random.Random(7010)
        for _ in range(60):
            text = "".join(rng.choice("abc")
                           for _ in range(rng.randint(0, 12)))
            best = 0
            for i in range(len(text)):
                for j in range(i + 1, len(text) + 1):
                    if len(set(text[i:j])) == j - i:
                        best = max(best, j - i)
            self.assertEqual(m.longest_unique_substring_length(
                text), best, text)
        with self.assertRaises(ValueError):
            m.longest_unique_substring_length("ab\u00e9")

    def test_registry_knows_batch79(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("stock_max_profit_twice",
                     "min_cost_climbing_stairs", "delete_and_earn",
                     "minimum_swaps_sort", "reorganize_string_arrange",
                     "min_swaps_parens_balance", "min_taps_garden",
                     "min_refuel_stops", "max_erasure_value",
                     "longest_unique_substring_length"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
