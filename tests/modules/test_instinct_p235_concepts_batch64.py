"""Tests for P235 concepts batch 64 (doc 631-640)."""
import random
import unittest
from collections import Counter

from app.modules.instinct_doc import p235_concepts_batch64 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch64Test(unittest.TestCase):
    def test_count_pairs_abs_diff_k(self):
        self.assertEqual(m.count_pairs_abs_diff_k([1, 2, 2, 1], 1), 4)
        self.assertEqual(m.count_pairs_abs_diff_k([1, 3], 3), 0)
        self.assertEqual(m.count_pairs_abs_diff_k([3, 2, 1, 5, 4], 2), 3)
        # oracle: Counter pairs c[v] * c[v - k]
        rng = random.Random(6401)
        for _ in range(80):
            items = [rng.randint(-9, 9) for _ in range(rng.randint(1, 12))]
            k = rng.randint(0, 6)
            c = Counter(items)
            if k == 0:
                want = sum(cnt * (cnt - 1) // 2 for cnt in c.values())
            else:
                want = sum(cnt * c[v - k] for v, cnt in c.items())
            self.assertEqual(m.count_pairs_abs_diff_k(items, k), want,
                             (items, k))
        with self.assertRaises(ValueError):
            m.count_pairs_abs_diff_k([1, 2], -1)
        with self.assertRaises(ValueError):
            m.count_pairs_abs_diff_k([1, True], 1)

    def test_koko_eating_bananas(self):
        self.assertEqual(m.koko_eating_bananas([3, 6, 7, 11], 8), 4)
        self.assertEqual(m.koko_eating_bananas([30, 11, 23, 4, 20], 5), 30)
        self.assertEqual(m.koko_eating_bananas([30, 11, 23, 4, 20], 6), 23)
        # oracle: linear scan of every speed
        rng = random.Random(6402)
        for _ in range(60):
            piles = [rng.randint(1, 60) for _ in range(rng.randint(1, 8))]
            h = rng.randint(len(piles), len(piles) + 12)

            def hours(s):
                return sum((p + s - 1) // s for p in piles)
            want = next(s for s in range(1, max(piles) + 1)
                        if hours(s) <= h)
            self.assertEqual(m.koko_eating_bananas(piles, h), want,
                             (piles, h))
        with self.assertRaises(ValueError):
            m.koko_eating_bananas([5, 5], 1)
        with self.assertRaises(ValueError):
            m.koko_eating_bananas([0], 3)

    def test_count_largest_groups(self):
        self.assertEqual(m.count_largest_groups(13), 4)
        self.assertEqual(m.count_largest_groups(2), 2)
        self.assertEqual(m.count_largest_groups(1), 1)
        # oracle: build the group lists, compare sizes
        rng = random.Random(6403)
        for _ in range(40):
            n = rng.randint(1, 400)
            groups = {}
            for v in range(1, n + 1):
                s = sum(int(d) for d in str(v))
                groups.setdefault(s, []).append(v)
            best = max(len(g) for g in groups.values())
            want = sum(1 for g in groups.values() if len(g) == best)
            self.assertEqual(m.count_largest_groups(n), want, n)
        with self.assertRaises(ValueError):
            m.count_largest_groups(0)

    def test_max_69_number(self):
        self.assertEqual(m.max_69_number(9669), 9969)
        self.assertEqual(m.max_69_number(9996), 9999)
        self.assertEqual(m.max_69_number(9999), 9999)
        # oracle: max over flipping any single 6, plus no flip
        rng = random.Random(6404)
        for _ in range(100):
            num = rng.randint(1, 99999)
            ds = str(num)
            cands = [num]
            for i, ch in enumerate(ds):
                if ch == "6":
                    cands.append(int(ds[:i] + "9" + ds[i + 1:]))
            self.assertEqual(m.max_69_number(num), max(cands), num)
        with self.assertRaises(ValueError):
            m.max_69_number(0)

    def test_defuse_bomb_circular(self):
        self.assertEqual(m.defuse_bomb_circular([5, 7, 1, 4], 3),
                         [12, 10, 16, 13])
        self.assertEqual(m.defuse_bomb_circular([5, 7, 1, 4], -2),
                         [5, 9, 12, 8])
        self.assertEqual(m.defuse_bomb_circular([5, 7, 1, 4], 0),
                         [0, 0, 0, 0])
        # oracle: doubled list slices
        rng = random.Random(6405)
        for _ in range(60):
            n = rng.randint(1, 9)
            code = [rng.randint(-9, 9) for _ in range(n)]
            k = rng.randint(-n, n)
            dbl = code + code
            want = []
            for i in range(n):
                if k > 0:
                    want.append(sum(dbl[i + 1:i + 1 + k]))
                elif k < 0:
                    want.append(sum(dbl[n + i + k:n + i]))
                else:
                    want.append(0)
            self.assertEqual(m.defuse_bomb_circular(code, k), want,
                             (code, k))
        with self.assertRaises(ValueError):
            m.defuse_bomb_circular([1, 2, 3], 4)

    def test_count_good_meals(self):
        self.assertEqual(m.count_good_meals([1, 3, 5, 7, 9]), 4)
        self.assertEqual(m.count_good_meals([1, 1, 1, 3, 3, 3]), 12)
        self.assertEqual(m.count_good_meals([1]), 0)
        # oracle: Counter pair counting against a power set
        rng = random.Random(6406)
        powers = {1 << b for b in range(0, 30)}
        for _ in range(80):
            vals = [rng.randint(0, 60) for _ in range(rng.randint(1, 15))]
            c = Counter(vals)
            want = 0
            seen = set()
            for v in sorted(c):
                for p in powers:
                    o = p - v
                    if o in c and (o, v) not in seen and o >= v:
                        seen.add((v, o))
                        if o == v:
                            want += c[v] * (c[v] - 1) // 2
                        else:
                            want += c[v] * c[o]
            self.assertEqual(m.count_good_meals(vals), want, vals)
        with self.assertRaises(ValueError):
            m.count_good_meals([-1, 2])

    def test_find_words_with_chars(self):
        self.assertEqual(m.find_words_with_chars(
            ["cat", "bt", "hat", "tree"], "atach"), 6)
        self.assertEqual(m.find_words_with_chars(
            ["hello", "world", "leetcode"], "welldonehoneyr"), 10)
        # oracle: per-word multiset subtraction
        rng = random.Random(6407)
        alpha = "abc"
        for _ in range(60):
            words = ["".join(rng.choice(alpha)
                             for _ in range(rng.randint(1, 5)))
                     for _ in range(rng.randint(1, 6))]
            chars = "".join(rng.choice(alpha)
                            for _ in range(rng.randint(1, 8)))
            have = Counter(chars)
            want = sum(len(w) for w in words
                       if not (Counter(w) - have))
            self.assertEqual(m.find_words_with_chars(words, chars),
                             want, (words, chars))
        with self.assertRaises(ValueError):
            m.find_words_with_chars([], "cat")
        with self.assertRaises(ValueError):
            m.find_words_with_chars(["Cat"], "cat")

    def test_min_operations_make_increasing(self):
        self.assertEqual(m.min_operations_make_increasing([1, 1, 1]), 3)
        self.assertEqual(m.min_operations_make_increasing(
            [1, 5, 2, 4, 1]), 14)
        self.assertEqual(m.min_operations_make_increasing([8]), 0)
        # oracle: simulate the increments cell by cell
        rng = random.Random(6408)
        for _ in range(80):
            items = [rng.randint(1, 30) for _ in range(rng.randint(1, 12))]
            sim = list(items)
            ops = 0
            for i in range(1, len(sim)):
                if sim[i] <= sim[i - 1]:
                    ops += sim[i - 1] + 1 - sim[i]
                    sim[i] = sim[i - 1] + 1
            self.assertEqual(m.min_operations_make_increasing(items),
                             ops, items)
        with self.assertRaises(ValueError):
            m.min_operations_make_increasing([1, "a"])

    def test_min_cost_travel_days(self):
        self.assertEqual(m.min_cost_travel_days(
            [1, 4, 6, 7, 8, 20], [2, 7, 15]), 11)
        self.assertEqual(m.min_cost_travel_days(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 30, 31], [2, 7, 15]), 17)
        self.assertEqual(m.min_cost_travel_days([1], [100, 200, 300]),
                         100)
        # oracle: exhaustive pass assignment per travel day
        rng = random.Random(6409)
        for _ in range(40):
            k = rng.randint(1, 8)
            days = sorted(rng.sample(range(1, 61), k))
            costs = [rng.randint(1, 30) for _ in range(3)]
            best = [None]

            def rec(i, spent):
                if i == len(days):
                    if best[0] is None or spent < best[0]:
                        best[0] = spent
                    return
                if best[0] is not None and spent >= best[0]:
                    return
                for dur, price in ((1, costs[0]), (7, costs[1]),
                                   (30, costs[2])):
                    j = i
                    while (j < len(days)
                           and days[j] <= days[i] + dur - 1):
                        j += 1
                    rec(j, spent + price)
            rec(0, 0)
            self.assertEqual(m.min_cost_travel_days(days, costs),
                             best[0], (days, costs))
        with self.assertRaises(ValueError):
            m.min_cost_travel_days([3, 2], [2, 7, 15])
        with self.assertRaises(ValueError):
            m.min_cost_travel_days([366], [2, 7, 15])
        with self.assertRaises(ValueError):
            m.min_cost_travel_days([1], [2, 7])

    def test_deck_partition_gcd(self):
        self.assertTrue(m.deck_partition_gcd([1, 2, 3, 4, 4, 3, 2, 1]))
        self.assertFalse(m.deck_partition_gcd([1, 1, 1, 2, 2, 2, 3]))
        self.assertTrue(m.deck_partition_gcd([1, 1]))
        self.assertFalse(m.deck_partition_gcd([1]))
        # oracle: try every group size d >= 2 dividing the deck
        rng = random.Random(6410)
        for _ in range(60):
            n = rng.randint(1, 20)
            deck = [rng.randint(1, 6) for _ in range(n)]
            c = Counter(deck)
            want = any(n % d == 0 and all(v % d == 0
                                          for v in c.values())
                       for d in range(2, n + 1))
            self.assertEqual(m.deck_partition_gcd(deck), want, deck)
        with self.assertRaises(ValueError):
            m.deck_partition_gcd([1, True])

    def test_registry_knows_batch64(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("count_pairs_abs_diff_k", "koko_eating_bananas",
                     "count_largest_groups", "max_69_number",
                     "defuse_bomb_circular", "count_good_meals",
                     "find_words_with_chars",
                     "min_operations_make_increasing",
                     "min_cost_travel_days", "deck_partition_gcd"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
