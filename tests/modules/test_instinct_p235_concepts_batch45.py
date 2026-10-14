"""Tests for P235 concepts batch 45 (441-450)."""
import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch45 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch45Test(unittest.TestCase):
    def test_monotonic_array_check(self):
        self.assertTrue(m.monotonic_array_check([1, 2, 2, 3]))
        self.assertTrue(m.monotonic_array_check([6, 5, 4, 4]))
        self.assertFalse(m.monotonic_array_check([1, 3, 2]))
        self.assertTrue(m.monotonic_array_check([7]))
        # oracle: sign scan of consecutive deltas
        rng = random.Random(4501)
        for _ in range(60):
            vals = [rng.randint(0, 6)
                    for _ in range(rng.randint(1, 12))]
            signs = {(vals[i] > vals[i - 1]) - (vals[i] < vals[i - 1])
                     for i in range(1, len(vals))}
            want = not ({1, -1} <= signs)
            self.assertEqual(m.monotonic_array_check(vals), want, vals)
        with self.assertRaises(ValueError):
            m.monotonic_array_check([])

    def test_rank_transform_values(self):
        self.assertEqual(m.rank_transform_values([40, 10, 20, 30]),
                         [4, 1, 2, 3])
        self.assertEqual(m.rank_transform_values([7, 7, 7]), [1, 1, 1])
        # oracle: bisect on the sorted distinct values
        import bisect
        rng = random.Random(4502)
        for _ in range(50):
            vals = [rng.randint(-9, 9)
                    for _ in range(rng.randint(1, 15))]
            keys = sorted(set(vals))
            want = [bisect.bisect_left(keys, v) + 1 for v in vals]
            self.assertEqual(m.rank_transform_values(vals), want, vals)
        with self.assertRaises(ValueError):
            m.rank_transform_values([])

    def test_relative_sort_order(self):
        self.assertEqual(m.relative_sort_order(
            [2, 3, 1, 3, 2, 4, 6, 7, 9, 2, 19], [2, 1, 4, 3, 9, 6]),
            [2, 2, 2, 1, 4, 3, 3, 9, 6, 7, 19])
        # oracle: counting-sort over order positions + sorted rest
        rng = random.Random(4503)
        for _ in range(50):
            order = rng.sample(range(10), rng.randint(1, 6))
            vals = [rng.randint(0, 9)
                    for _ in range(rng.randint(1, 15))]
            want = []
            for o in order:
                want.extend([o] * vals.count(o))
            want.extend(sorted(v for v in vals if v not in order))
            self.assertEqual(m.relative_sort_order(vals, order), want,
                             (vals, order))
        with self.assertRaises(ValueError):
            m.relative_sort_order([1], [1, 1])

    def test_alien_dictionary_verify(self):
        self.assertTrue(m.alien_dictionary_verify(
            ["hello", "leetcode"],
            "hlabcdefgijkmnopqrstuvwxyz"))
        self.assertFalse(m.alien_dictionary_verify(
            ["word", "world", "row"],
            "worldabcefghijkmnpqstuvxyz"))
        self.assertFalse(m.alien_dictionary_verify(
            ["apple", "app"], "abcdefghijklmnopqrstuvwxyz"))
        # oracle: pairwise translated comparison
        rng = random.Random(4504)
        alpha = "qwertyuiop"
        for _ in range(50):
            words = ["".join(rng.choice(alpha)
                             for _ in range(rng.randint(1, 5)))
                     for _ in range(rng.randint(1, 5))]
            rank = {ch: i for i, ch in enumerate(alpha)}
            keyed = [[rank[c] for c in w] for w in words]
            want = all(keyed[i] <= keyed[i + 1]
                       for i in range(len(keyed) - 1))
            self.assertEqual(m.alien_dictionary_verify(words, alpha),
                             want, words)
        with self.assertRaises(ValueError):
            m.alien_dictionary_verify(["ab"], "aab")
        with self.assertRaises(ValueError):
            m.alien_dictionary_verify(["az"], "qwertyuiop")

    def test_arithmetic_progression_check(self):
        self.assertTrue(m.arithmetic_progression_check([3, 5, 1]))
        self.assertFalse(m.arithmetic_progression_check([1, 2, 4]))
        self.assertTrue(m.arithmetic_progression_check([5, 5]))
        # oracle: min + constant-step reconstruction
        rng = random.Random(4505)
        for _ in range(50):
            n = rng.randint(2, 10)
            vals = [rng.randint(-9, 9) for _ in range(n)]
            s = sorted(vals)
            want = all(s[i] - s[i - 1] == s[1] - s[0]
                       for i in range(2, n))
            self.assertEqual(m.arithmetic_progression_check(vals),
                             want, vals)
        with self.assertRaises(ValueError):
            m.arithmetic_progression_check([1])

    def test_teemo_attack_duration(self):
        self.assertEqual(m.teemo_attack_duration([1, 4], 2), 4)
        self.assertEqual(m.teemo_attack_duration([1, 2], 2), 3)
        self.assertEqual(m.teemo_attack_duration([5], 10), 10)
        # oracle: union of poison intervals
        rng = random.Random(4506)
        for _ in range(50):
            n = rng.randint(1, 8)
            attacks = sorted(rng.randint(0, 30) for _ in range(n))
            dur = rng.randint(1, 6)
            poisoned = set()
            for a in attacks:
                poisoned.update(range(a, a + dur))
            self.assertEqual(m.teemo_attack_duration(attacks, dur),
                             len(poisoned), (attacks, dur))
        with self.assertRaises(ValueError):
            m.teemo_attack_duration([3, 1], 2)
        with self.assertRaises(ValueError):
            m.teemo_attack_duration([1], 0)

    def test_num_rescue_boats(self):
        self.assertEqual(m.num_rescue_boats([3, 2, 2, 1], 3), 3)
        self.assertEqual(m.num_rescue_boats([3, 5, 3, 4], 5), 4)
        self.assertEqual(m.num_rescue_boats([1, 2], 3), 1)
        # oracle: exhaustive pairing search on tiny inputs
        rng = random.Random(4507)
        for _ in range(30):
            n = rng.randint(1, 8)
            limit = rng.randint(2, 6)
            weights = [rng.randint(1, limit) for _ in range(n)]
            best = [n]

            def match(i, used, boats):
                if i == n:
                    best[0] = min(best[0], boats)
                    return
                if used[i]:
                    match(i + 1, used, boats)
                    return
                used[i] = True
                for j in range(i + 1, n):
                    if (not used[j]
                            and weights[i] + weights[j] <= limit):
                        used[j] = True
                        match(i + 1, used, boats + 1)
                        used[j] = False
                match(i + 1, used, boats + 1)
                used[i] = False

            match(0, [False] * n, 0)
            self.assertEqual(m.num_rescue_boats(weights, limit),
                             best[0], (weights, limit))
        with self.assertRaises(ValueError):
            m.num_rescue_boats([0], 3)
        with self.assertRaises(ValueError):
            m.num_rescue_boats([4], 3)

    def test_advantage_shuffle_pairs(self):
        out = m.advantage_shuffle_pairs([2, 7, 11, 15], [1, 10, 4, 11])
        self.assertEqual(sorted(out), [2, 7, 11, 15])
        self.assertEqual(
            sum(1 for a, b in zip(out, [1, 10, 4, 11]) if a > b), 4)
        # oracle: brute force the best permutation on tiny inputs
        from itertools import permutations
        rng = random.Random(4508)
        for _ in range(25):
            n = rng.randint(1, 6)
            a = [rng.randint(0, 9) for _ in range(n)]
            b = [rng.randint(0, 9) for _ in range(n)]
            best = max(sum(1 for x, y in zip(p, b) if x > y)
                       for p in permutations(a))
            got = m.advantage_shuffle_pairs(a, b)
            self.assertEqual(sorted(got), sorted(a), (a, b))
            self.assertEqual(
                sum(1 for x, y in zip(got, b) if x > y), best, (a, b))
        with self.assertRaises(ValueError):
            m.advantage_shuffle_pairs([1], [1, 2])

    def test_array_pair_sum_max(self):
        self.assertEqual(m.array_pair_sum_max([1, 4, 3, 2]), 4)
        self.assertEqual(m.array_pair_sum_max([6, 2, 6, 5, 1, 2]), 9)
        # oracle: exhaustive pairing on tiny inputs
        rng = random.Random(4509)
        for _ in range(30):
            n = rng.randint(1, 4) * 2
            vals = [rng.randint(0, 9) for _ in range(n)]
            best = [0]

            def pair(i, used, total):
                if i == n:
                    best[0] = max(best[0], total)
                    return
                if used[i]:
                    pair(i + 1, used, total)
                    return
                used[i] = True
                for j in range(i + 1, n):
                    if not used[j]:
                        used[j] = True
                        pair(i + 1, used,
                             total + min(vals[i], vals[j]))
                        used[j] = False
                used[i] = False

            pair(0, [False] * n, 0)
            self.assertEqual(m.array_pair_sum_max(vals), best[0], vals)
        with self.assertRaises(ValueError):
            m.array_pair_sum_max([1, 2, 3])

    def test_partition_labels_lengths(self):
        self.assertEqual(
            m.partition_labels_lengths("ababcbacadefegdehijhklij"),
            [9, 7, 8])
        self.assertEqual(m.partition_labels_lengths("aaa"), [3])
        self.assertEqual(m.partition_labels_lengths("abc"), [1, 1, 1])
        # oracle: merge intervals of first/last occurrence
        rng = random.Random(4510)
        for _ in range(50):
            text = "".join(rng.choice("abcd")
                           for _ in range(rng.randint(1, 15)))
            spans = {}
            for i, ch in enumerate(text):
                if ch in spans:
                    spans[ch][1] = i
                else:
                    spans[ch] = [i, i]
            ivs = sorted(spans.values())
            merged = []
            for lo, hi in ivs:
                if merged and lo <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])
            want = [hi - lo + 1 for lo, hi in merged]
            self.assertEqual(m.partition_labels_lengths(text), want,
                             text)
        with self.assertRaises(ValueError):
            m.partition_labels_lengths("ab1")

    def test_registry_knows_batch45(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 45]
        self.assertEqual(len(names), 10)
        for name in ("monotonic_array_check", "rank_transform_values",
                     "relative_sort_order", "alien_dictionary_verify",
                     "arithmetic_progression_check",
                     "teemo_attack_duration", "num_rescue_boats",
                     "advantage_shuffle_pairs", "array_pair_sum_max",
                     "partition_labels_lengths"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
