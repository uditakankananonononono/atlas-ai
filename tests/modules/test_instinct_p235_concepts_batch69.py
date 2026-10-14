"""Tests for P235 concepts batch 69 (doc 681-690)."""
import random
import unittest
from itertools import combinations

from app.modules.instinct_doc import p235_concepts_batch69 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch69Test(unittest.TestCase):
    def test_max_chunks_to_sorted(self):
        self.assertEqual(m.max_chunks_to_sorted([1, 0, 2, 3, 4]), 4)
        self.assertEqual(m.max_chunks_to_sorted([2, 1, 3, 4, 0]), 1)
        self.assertEqual(m.max_chunks_to_sorted([0]), 1)
        # oracle: try every chunking, keep the largest valid count
        rng = random.Random(6901)
        for _ in range(40):
            n = rng.randint(1, 8)
            items = list(range(n))
            rng.shuffle(items)
            ordered = sorted(items)
            best = 1
            for mask in range(1 << (n - 1)):
                parts = []
                prev = 0
                for i in range(n - 1):
                    if mask & (1 << i):
                        parts.append(items[prev:i + 1])
                        prev = i + 1
                parts.append(items[prev:])
                joined = []
                for p in parts:
                    joined.extend(sorted(p))
                if joined == ordered:
                    best = max(best, len(parts))
            self.assertEqual(m.max_chunks_to_sorted(items), best,
                             items)
        with self.assertRaises(ValueError):
            m.max_chunks_to_sorted([0, 0])
        with self.assertRaises(ValueError):
            m.max_chunks_to_sorted([0, 2])

    def test_partition_disjoint_max(self):
        self.assertEqual(m.partition_disjoint_max([5, 0, 3, 8, 6]),
                         3)
        self.assertEqual(m.partition_disjoint_max([1, 1, 1, 0, 6]),
                         4)
        self.assertEqual(m.partition_disjoint_max([1, 2]), 1)
        # oracle: first split whose left max stays under right min
        rng = random.Random(6902)
        for _ in range(60):
            items = [rng.randint(0, 9)
                     for _ in range(rng.randint(2, 10))]
            want = len(items)
            for cut in range(1, len(items)):
                if max(items[:cut]) <= min(items[cut:]):
                    want = cut
                    break
            self.assertEqual(m.partition_disjoint_max(items), want,
                             items)
        with self.assertRaises(ValueError):
            m.partition_disjoint_max([1])

    def test_majority_candidates_n3(self):
        self.assertEqual(m.majority_candidates_n3([3, 2, 3]), [3])
        self.assertEqual(m.majority_candidates_n3(
            [1, 1, 1, 3, 3, 2, 2, 2]), [1, 2])
        self.assertEqual(m.majority_candidates_n3([1, 2]), [1, 2])
        # oracle: direct membership count per distinct value
        rng = random.Random(6903)
        for _ in range(60):
            items = [rng.randint(1, 5)
                     for _ in range(rng.randint(1, 15))]
            want = sorted({v for v in items
                           if items.count(v) * 3 > len(items)})
            self.assertEqual(m.majority_candidates_n3(items), want,
                             items)
        with self.assertRaises(ValueError):
            m.majority_candidates_n3([])

    def test_subarray_sum_k_count(self):
        self.assertEqual(m.subarray_sum_k_count([1, 1, 1], 2), 2)
        self.assertEqual(m.subarray_sum_k_count([1, 2, 3], 3), 2)
        self.assertEqual(m.subarray_sum_k_count([1], 0), 0)
        # oracle: brute force over every slice
        rng = random.Random(6904)
        for _ in range(60):
            items = [rng.randint(-4, 4)
                     for _ in range(rng.randint(1, 10))]
            k = rng.randint(-5, 5)
            want = sum(1 for i in range(len(items))
                       for j in range(i + 1, len(items) + 1)
                       if sum(items[i:j]) == k)
            self.assertEqual(m.subarray_sum_k_count(items, k),
                             want, (items, k))
        with self.assertRaises(ValueError):
            m.subarray_sum_k_count([1, True], 1)

    def test_min_size_subarray_sum(self):
        self.assertEqual(m.min_size_subarray_sum(
            [2, 3, 1, 2, 4, 3], 7), 2)
        self.assertEqual(m.min_size_subarray_sum([1, 1, 1], 50), 0)
        self.assertEqual(m.min_size_subarray_sum([10], 5), 1)
        # oracle: shortest qualifying window by brute force
        rng = random.Random(6905)
        for _ in range(60):
            items = [rng.randint(1, 9)
                     for _ in range(rng.randint(1, 10))]
            target = rng.randint(1, 30)
            best = 0
            for i in range(len(items)):
                total = 0
                for j in range(i, len(items)):
                    total += items[j]
                    if total >= target:
                        if best == 0 or j - i + 1 < best:
                            best = j - i + 1
                        break
            self.assertEqual(m.min_size_subarray_sum(items, target),
                             best, (items, target))
        with self.assertRaises(ValueError):
            m.min_size_subarray_sum([0, 1], 1)

    def test_shortest_unsorted_subarray(self):
        self.assertEqual(m.shortest_unsorted_subarray(
            [2, 6, 4, 8, 10, 9, 15]), 5)
        self.assertEqual(m.shortest_unsorted_subarray([1, 2, 3]), 0)
        self.assertEqual(m.shortest_unsorted_subarray([3, 1]), 2)
        # oracle: first and last index differing from the sorted copy
        rng = random.Random(6906)
        for _ in range(60):
            items = [rng.randint(0, 9)
                     for _ in range(rng.randint(1, 12))]
            ordered = sorted(items)
            diff = [i for i in range(len(items))
                    if items[i] != ordered[i]]
            want = 0 if not diff else diff[-1] - diff[0] + 1
            self.assertEqual(m.shortest_unsorted_subarray(items),
                             want, items)
        with self.assertRaises(ValueError):
            m.shortest_unsorted_subarray([])

    def test_max_consecutive_ones_flips(self):
        self.assertEqual(m.max_consecutive_ones_flips(
            [1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0], 2), 6)
        self.assertEqual(m.max_consecutive_ones_flips(
            [0, 0, 0], 1), 1)
        self.assertEqual(m.max_consecutive_ones_flips([1, 1], 0), 2)
        # oracle: longest window holding at most k zeros
        rng = random.Random(6907)
        for _ in range(60):
            items = [rng.randint(0, 1)
                     for _ in range(rng.randint(1, 12))]
            k = rng.randint(0, 4)
            best = 0
            for i in range(len(items)):
                for j in range(i, len(items)):
                    if items[i:j + 1].count(0) <= k:
                        best = max(best, j - i + 1)
            self.assertEqual(m.max_consecutive_ones_flips(items, k),
                             best, (items, k))
        with self.assertRaises(ValueError):
            m.max_consecutive_ones_flips([1, 2], 1)

    def test_sum_subarray_minimums(self):
        self.assertEqual(m.sum_subarray_minimums([3, 1, 2, 4]), 17)
        self.assertEqual(m.sum_subarray_minimums([11, 81, 94, 43,
                                                  3]), 444)
        self.assertEqual(m.sum_subarray_minimums([5]), 5)
        # oracle: minimum of every slice, summed directly
        rng = random.Random(6908)
        for _ in range(50):
            items = [rng.randint(0, 9)
                     for _ in range(rng.randint(1, 9))]
            want = sum(min(items[i:j])
                       for i in range(len(items))
                       for j in range(i + 1, len(items) + 1))
            self.assertEqual(m.sum_subarray_minimums(items), want,
                             items)
        with self.assertRaises(ValueError):
            m.sum_subarray_minimums([])

    def test_online_median_list(self):
        self.assertEqual(m.online_median_list([2, 1, 5, 7, 2, 0,
                                               5]),
                         [2, 1, 2, 2, 2, 2, 2])
        self.assertEqual(m.online_median_list([9]), [9])
        # oracle: sorted copy each step, take the lower middle
        rng = random.Random(6909)
        for _ in range(60):
            items = [rng.randint(0, 20)
                     for _ in range(rng.randint(1, 12))]
            held = []
            want = []
            for v in items:
                held.append(v)
                want.append(sorted(held)[(len(held) - 1) // 2])
            self.assertEqual(m.online_median_list(items), want,
                             items)
        with self.assertRaises(ValueError):
            m.online_median_list([1, "a"])

    def test_remove_k_digits(self):
        self.assertEqual(m.remove_k_digits("1432219", 3), "1219")
        self.assertEqual(m.remove_k_digits("10200", 1), "200")
        self.assertEqual(m.remove_k_digits("10", 2), "0")
        self.assertEqual(m.remove_k_digits("9", 0), "9")
        # oracle: smallest kept subsequence over every drop set
        rng = random.Random(6910)
        for _ in range(50):
            n = rng.randint(1, 8)
            text = "".join(rng.choice("0123456789")
                           for _ in range(n))
            k = rng.randint(0, n)
            best = None
            for keep in combinations(range(n), n - k):
                cand = "".join(text[i] for i in keep).lstrip("0")
                cand = cand if cand else "0"
                if best is None or (len(cand), cand) < (len(best),
                                                        best):
                    best = cand
            self.assertEqual(m.remove_k_digits(text, k), best,
                             (text, k))
        with self.assertRaises(ValueError):
            m.remove_k_digits("12a", 1)
        with self.assertRaises(ValueError):
            m.remove_k_digits("12", 3)

    def test_registry_knows_batch69(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("max_chunks_to_sorted", "partition_disjoint_max",
                     "majority_candidates_n3", "subarray_sum_k_count",
                     "min_size_subarray_sum",
                     "shortest_unsorted_subarray",
                     "max_consecutive_ones_flips",
                     "sum_subarray_minimums", "online_median_list",
                     "remove_k_digits"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
