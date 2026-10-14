"""Tests for P235 concepts batch 83 (binary search on the answer)."""

import itertools
import random
import unittest
from math import isqrt

from app.modules.instinct_doc import p235_concepts_batch83 as m
from app.modules.instinct_doc import p235_concepts_registry as reg

MAX_ITEMS = reg.MAX_ITEMS
MAX_VAL = 10_000


def refusal(code):
    return "P235:" + code


class TestMaxAverageSubarrayK(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.max_average_subarray_k(
            [1, 12, 5, 6, 50, 3], 3), 20.333333)
        self.assertEqual(m.max_average_subarray_k([1, 2, 3, 4, 5], 2), 4.5)
        self.assertEqual(m.max_average_subarray_k([5], 1), 5.0)
        self.assertEqual(m.max_average_subarray_k([3, 3, 3], 1), 3.0)
        self.assertEqual(m.max_average_subarray_k([9, 1, 1, 1, 9], 2), 5.0)
        self.assertEqual(m.max_average_subarray_k([4, 2, 8, 1], 2), 5.0)

    def test_value_boundary(self):
        # MAX_VAL accepted exactly
        self.assertEqual(m.max_average_subarray_k([10000], 1), 10000.0)
        self.assertEqual(m.max_average_subarray_k([1, 10000], 1), 10000.0)

    def test_k_boundaries(self):
        # k == len forces the whole-array average
        self.assertEqual(m.max_average_subarray_k([2, 4, 6], 3), 4.0)
        # k == 1 picks the largest single value
        self.assertEqual(m.max_average_subarray_k([3, 9, 4], 1), 9.0)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.max_average_subarray_k("123", 2)
        self.assertEqual(str(ctx.exception), refusal(
            "max_average_subarray_k:bad_type:nums"))
        with self.assertRaises(ValueError) as ctx:
            m.max_average_subarray_k([], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_average_subarray_k:empty:nums"))
        with self.assertRaises(ValueError) as ctx:
            m.max_average_subarray_k([0, 1], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_average_subarray_k:out_of_range:nums[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.max_average_subarray_k([MAX_ITEMS + 1], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_average_subarray_k:out_of_range:nums[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.max_average_subarray_k([1, 2], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "max_average_subarray_k:out_of_range:k"))
        with self.assertRaises(ValueError) as ctx:
            m.max_average_subarray_k([1, 2], 3)
        self.assertEqual(str(ctx.exception), refusal(
            "max_average_subarray_k:out_of_range:k"))
        with self.assertRaises(ValueError) as ctx:
            m.max_average_subarray_k([1] * (MAX_ITEMS + 1), 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_average_subarray_k:too_many:nums"))

    def test_cap(self):
        self.assertEqual(m.max_average_subarray_k(
            [1] * MAX_ITEMS, 2), 1.0)
        self.assertEqual(m.max_average_subarray_k(
            [MAX_VAL] * MAX_ITEMS, MAX_ITEMS), float(MAX_VAL))

    def test_oracle(self):
        from fractions import Fraction

        def exact(nums, k):
            prefix = [Fraction(0)]
            for v in nums:
                prefix.append(prefix[-1] + v)
            best = None
            for j in range(k, len(nums) + 1):
                for i in range(0, j - k + 1):
                    avg = (prefix[j] - prefix[i]) / (j - i)
                    if best is None or avg > best:
                        best = avg
            return best
        def rounded(fr):
            scaled = fr * 1_000_000
            base, rem = divmod(scaled.numerator, scaled.denominator)
            if 2 * rem > scaled.denominator or (
                    2 * rem == scaled.denominator and base % 2 == 1):
                base += 1
            return base / 1_000_000
        rng = random.Random(8301)
        for _ in range(60):
            n = rng.randint(1, 14)
            nums = [rng.randint(1, 50) for _ in range(n)]
            k = rng.randint(1, n)
            want = rounded(exact(nums, k))
            self.assertEqual(m.max_average_subarray_k(nums, k), want)

    def test_exact_tie_rounding(self):
        # exact average 131/128 = 1.0234375 ties at the sixth
        # decimal and must round half-even up, not stop just below
        # the tie at a search lower bound
        self.assertEqual(m.max_average_subarray_k(
            [1] * 127 + [4], 128), 1.023438)
        self.assertEqual(m.max_average_subarray_k(
            [1] * 255 + [7], 256), 1.023438)

class TestShipCapacityMinDays(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.ship_capacity_min_days(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5), 15)
        self.assertEqual(m.ship_capacity_min_days([3, 2, 2, 4, 1, 4], 3), 6)
        self.assertEqual(m.ship_capacity_min_days([1, 2, 3, 1, 1], 4), 3)
        self.assertEqual(m.ship_capacity_min_days([7], 1), 7)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.ship_capacity_min_days([], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "ship_capacity_min_days:empty:weights"))
        with self.assertRaises(ValueError) as ctx:
            m.ship_capacity_min_days([4, 0], 2)
        self.assertEqual(str(ctx.exception), refusal(
            "ship_capacity_min_days:out_of_range:weights[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.ship_capacity_min_days([4], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "ship_capacity_min_days:out_of_range:days"))
        with self.assertRaises(ValueError) as ctx:
            m.ship_capacity_min_days([4], True)
        self.assertEqual(str(ctx.exception), refusal(
            "ship_capacity_min_days:bad_type:days"))

    def test_oracle(self):
        def oracle(weights, days):
            def needed(cap):
                used, run = 1, 0
                for w in weights:
                    if run + w > cap:
                        used += 1
                        run = w
                    else:
                        run += w
                return used
            for cap in range(max(weights), sum(weights) + 1):
                if needed(cap) <= days:
                    return cap
            return sum(weights)
        rng = random.Random(8302)
        for _ in range(60):
            n = rng.randint(1, 8)
            weights = [rng.randint(1, 9) for _ in range(n)]
            days = rng.randint(1, n + 2)
            self.assertEqual(m.ship_capacity_min_days(weights, days),
                             oracle(weights, days))


class TestMagneticForceMaxMin(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.magnetic_force_max_min([1, 2, 3, 4, 7], 3), 3)
        self.assertEqual(m.magnetic_force_max_min([5, 4, 3, 2, 1, 100], 2), 99)
        self.assertEqual(m.magnetic_force_max_min([1, 2, 4, 8, 16], 5), 1)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.magnetic_force_max_min([0, 5], 2)
        self.assertEqual(str(ctx.exception), refusal(
            "magnetic_force_max_min:out_of_range:positions[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.magnetic_force_max_min([1, 1, 5], 2)
        self.assertEqual(str(ctx.exception), refusal(
            "magnetic_force_max_min:bad_value:positions"))
        with self.assertRaises(ValueError) as ctx:
            m.magnetic_force_max_min([1, 5], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "magnetic_force_max_min:out_of_range:balls"))
        with self.assertRaises(ValueError) as ctx:
            m.magnetic_force_max_min([1, 5], 3)
        self.assertEqual(str(ctx.exception), refusal(
            "magnetic_force_max_min:out_of_range:balls"))

    def test_oracle(self):
        def oracle(positions, balls):
            best = 0
            for combo in itertools.combinations(sorted(positions), balls):
                gap = min(b - a for a, b in zip(combo, combo[1:]))
                best = max(best, gap)
            return best
        rng = random.Random(8303)
        for _ in range(60):
            n = rng.randint(2, 8)
            positions = rng.sample(range(1, 40), n)
            balls = rng.randint(2, n)
            self.assertEqual(m.magnetic_force_max_min(positions, balls),
                             oracle(positions, balls))


class TestMinLimitBallsInBag(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.min_limit_balls_in_bag([9], 2), 3)
        self.assertEqual(m.min_limit_balls_in_bag([2, 4, 8, 2], 4), 2)
        self.assertEqual(m.min_limit_balls_in_bag([7, 17], 2), 7)
        self.assertEqual(m.min_limit_balls_in_bag([6], 0), 6)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.min_limit_balls_in_bag([1, -2], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "min_limit_balls_in_bag:out_of_range:nums[1]"))
        with self.assertRaises(ValueError) as ctx:
            m.min_limit_balls_in_bag([1], -1)
        self.assertEqual(str(ctx.exception), refusal(
            "min_limit_balls_in_bag:out_of_range:max_ops"))
        with self.assertRaises(ValueError) as ctx:
            m.min_limit_balls_in_bag([], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "min_limit_balls_in_bag:empty:nums"))

    def test_oracle(self):
        def oracle(nums, max_ops):
            for k in range(1, max(nums) + 1):
                if sum((v - 1) // k for v in nums) <= max_ops:
                    return k
            return max(nums)
        rng = random.Random(8304)
        for _ in range(60):
            nums = [rng.randint(1, 20) for _ in range(rng.randint(1, 6))]
            ops = rng.randint(0, 12)
            self.assertEqual(m.min_limit_balls_in_bag(nums, ops),
                             oracle(nums, ops))


class TestMinDaysMakeBouquets(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.min_days_make_bouquets([1, 10, 3, 10, 2], 3, 1), 3)
        self.assertEqual(m.min_days_make_bouquets([1, 10, 3, 10, 2], 3, 2), -1)
        self.assertEqual(m.min_days_make_bouquets([7, 7, 7, 7, 12, 7, 7], 2, 3), 12)
        self.assertEqual(m.min_days_make_bouquets([5, 5], 2, 1), 5)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.min_days_make_bouquets([1], 0, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "min_days_make_bouquets:out_of_range:bouquets"))
        with self.assertRaises(ValueError) as ctx:
            m.min_days_make_bouquets([1], 1, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "min_days_make_bouquets:out_of_range:flowers"))
        with self.assertRaises(ValueError) as ctx:
            m.min_days_make_bouquets([], 1, 1)
        self.assertEqual(str(ctx.exception), refusal(
            "min_days_make_bouquets:empty:bloom_days"))

    def test_oracle(self):
        def oracle(bloom_days, bouquets, flowers):
            if bouquets * flowers > len(bloom_days):
                return -1

            def ready(day):
                made = run = 0
                for d in bloom_days:
                    run = run + 1 if d <= day else 0
                    if run == flowers:
                        made += 1
                        run = 0
                return made
            for day in range(min(bloom_days), max(bloom_days) + 1):
                if ready(day) >= bouquets:
                    return day
            return -1
        rng = random.Random(8305)
        for _ in range(60):
            n = rng.randint(1, 9)
            days = [rng.randint(1, 12) for _ in range(n)]
            bouquets = rng.randint(1, 4)
            flowers = rng.randint(1, 3)
            self.assertEqual(m.min_days_make_bouquets(days, bouquets, flowers),
                             oracle(days, bouquets, flowers))


class TestMinTimeRepairCars(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.min_time_repair_cars([4, 2, 3, 1], 10), 16)
        self.assertEqual(m.min_time_repair_cars([5, 1, 8], 6), 16)
        self.assertEqual(m.min_time_repair_cars([1], 1), 1)
        self.assertEqual(m.min_time_repair_cars([3], 3), 27)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.min_time_repair_cars([], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "min_time_repair_cars:empty:ranks"))
        with self.assertRaises(ValueError) as ctx:
            m.min_time_repair_cars([0], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "min_time_repair_cars:out_of_range:ranks[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.min_time_repair_cars([1], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "min_time_repair_cars:out_of_range:cars"))
        with self.assertRaises(ValueError) as ctx:
            m.min_time_repair_cars([1] * (MAX_ITEMS + 1), 1)
        self.assertEqual(str(ctx.exception), refusal(
            "min_time_repair_cars:too_many:ranks"))

    def test_oracle(self):
        def oracle(ranks, cars):
            t = 1
            while sum(isqrt(t // r) for r in ranks) < cars:
                t += 1
            return t
        rng = random.Random(8306)
        for _ in range(60):
            ranks = [rng.randint(1, 6) for _ in range(rng.randint(1, 5))]
            cars = rng.randint(1, 8)
            self.assertEqual(m.min_time_repair_cars(ranks, cars),
                             oracle(ranks, cars))


class TestMaxRunningTimeComputers(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.max_running_time_computers(2, [3, 3, 3]), 4)
        self.assertEqual(m.max_running_time_computers(2, [1, 1, 1, 1]), 2)
        self.assertEqual(m.max_running_time_computers(3, [2, 2, 2]), 2)
        self.assertEqual(m.max_running_time_computers(5, [1, 2]), 0)
        self.assertEqual(m.max_running_time_computers(1, [9]), 9)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.max_running_time_computers(0, [1])
        self.assertEqual(str(ctx.exception), refusal(
            "max_running_time_computers:out_of_range:n_computers"))
        with self.assertRaises(ValueError) as ctx:
            m.max_running_time_computers(1, [])
        self.assertEqual(str(ctx.exception), refusal(
            "max_running_time_computers:empty:batteries"))
        with self.assertRaises(ValueError) as ctx:
            m.max_running_time_computers(1, [2, 0])
        self.assertEqual(str(ctx.exception), refusal(
            "max_running_time_computers:out_of_range:batteries[1]"))

    def test_oracle(self):
        def oracle(n_computers, batteries):
            t = sum(batteries) // n_computers
            while t > 0 and sum(min(b, t) for b in batteries) < n_computers * t:
                t -= 1
            return t
        rng = random.Random(8307)
        for _ in range(60):
            n_computers = rng.randint(1, 6)
            batteries = [rng.randint(1, 12) for _ in range(rng.randint(1, 6))]
            self.assertEqual(m.max_running_time_computers(n_computers, batteries),
                             oracle(n_computers, batteries))


class TestMinCapabilityRobHouses(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.min_capability_rob_houses([2, 3, 5, 9], 2), 5)
        self.assertEqual(m.min_capability_rob_houses([2, 7, 9, 3, 1], 2), 2)
        self.assertEqual(m.min_capability_rob_houses([4, 4, 4], 2), 4)
        self.assertEqual(m.min_capability_rob_houses([8], 1), 8)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.min_capability_rob_houses([1, 2, 3, 4], 3)
        self.assertEqual(str(ctx.exception), refusal(
            "min_capability_rob_houses:out_of_range:picks"))
        with self.assertRaises(ValueError) as ctx:
            m.min_capability_rob_houses([1, 2], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "min_capability_rob_houses:out_of_range:picks"))
        with self.assertRaises(ValueError) as ctx:
            m.min_capability_rob_houses([], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "min_capability_rob_houses:empty:values"))

    def test_oracle(self):
        def oracle(values, picks):
            best = None
            n = len(values)
            for combo in itertools.combinations(range(n), picks):
                if all(combo[i + 1] - combo[i] > 1
                       for i in range(picks - 1)):
                    cost = max(values[c] for c in combo)
                    if best is None or cost < best:
                        best = cost
            return best
        rng = random.Random(8308)
        for _ in range(60):
            n = rng.randint(1, 9)
            values = [rng.randint(1, 9) for _ in range(n)]
            picks = rng.randint(1, (n + 1) // 2)
            self.assertEqual(m.min_capability_rob_houses(values, picks),
                             oracle(values, picks))


class TestMaxCandiesPerChild(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.max_candies_per_child([5, 8, 6], 3), 5)
        self.assertEqual(m.max_candies_per_child([2, 5], 11), 0)
        self.assertEqual(m.max_candies_per_child([4, 7, 5], 4), 3)
        self.assertEqual(m.max_candies_per_child([10], 1), 10)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.max_candies_per_child([0], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_candies_per_child:out_of_range:piles[0]"))
        with self.assertRaises(ValueError) as ctx:
            m.max_candies_per_child([5], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "max_candies_per_child:out_of_range:children"))
        with self.assertRaises(ValueError) as ctx:
            m.max_candies_per_child([], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_candies_per_child:empty:piles"))
        with self.assertRaises(ValueError) as ctx:
            m.max_candies_per_child([3], 0)
        self.assertEqual(str(ctx.exception), refusal(
            "max_candies_per_child:out_of_range:children"))
        with self.assertRaises(ValueError) as ctx:
            m.max_candies_per_child([3, "4"], 1)
        self.assertEqual(str(ctx.exception), refusal(
            "max_candies_per_child:bad_type:piles[1]"))

    def test_oracle(self):
        def oracle(piles, children):
            for k in range(max(piles), 0, -1):
                if sum(p // k for p in piles) >= children:
                    return k
            return 0
        rng = random.Random(8309)
        for _ in range(60):
            piles = [rng.randint(1, 15) for _ in range(rng.randint(1, 6))]
            children = rng.randint(1, 20)
            self.assertEqual(m.max_candies_per_child(piles, children),
                             oracle(piles, children))


class TestNthMagicalNumber(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.nth_magical_number(4, 2, 3), 6)
        self.assertEqual(m.nth_magical_number(1, 1, 1), 1)
        self.assertEqual(m.nth_magical_number(5, 2, 4), 10)
        self.assertEqual(m.nth_magical_number(10, 2, 5), 16)
        self.assertEqual(m.nth_magical_number(3, 6, 4), 8)

    def test_refusals(self):
        with self.assertRaises(ValueError) as ctx:
            m.nth_magical_number(1, 1, 0)
        self.assertEqual(str(ctx.exception), refusal(
            "nth_magical_number:out_of_range:b"))
        with self.assertRaises(ValueError) as ctx:
            m.nth_magical_number(0, 2, 3)
        self.assertEqual(str(ctx.exception), refusal(
            "nth_magical_number:out_of_range:n"))
        with self.assertRaises(ValueError) as ctx:
            m.nth_magical_number(1, 0, 3)
        self.assertEqual(str(ctx.exception), refusal(
            "nth_magical_number:out_of_range:a"))
        with self.assertRaises(ValueError) as ctx:
            m.nth_magical_number(1, 2, MAX_ITEMS + 2)
        self.assertEqual(str(ctx.exception), refusal(
            "nth_magical_number:out_of_range:b"))

    def test_oracle(self):
        def oracle(n, a, b):
            found = seen = 0
            x = 1
            while True:
                if x % a == 0 or x % b == 0:
                    seen += 1
                    if seen == n:
                        return x
                x += 1
                found += 1
                if found > n * min(a, b):
                    raise AssertionError("oracle overshot")
        rng = random.Random(8310)
        for _ in range(60):
            n = rng.randint(1, 20)
            a = rng.randint(1, 9)
            b = rng.randint(1, 9)
            self.assertEqual(m.nth_magical_number(n, a, b), oracle(n, a, b))


class TestRegistryKnowsBatch83(unittest.TestCase):
    def test_registry_knows_batch83(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("max_average_subarray_k", "ship_capacity_min_days",
                     "magnetic_force_max_min", "min_limit_balls_in_bag",
                     "min_days_make_bouquets", "min_time_repair_cars",
                     "max_running_time_computers", "min_capability_rob_houses",
                     "max_candies_per_child", "nth_magical_number"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
