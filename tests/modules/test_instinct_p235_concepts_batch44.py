"""Tests for P235 concepts batch 44 (431-440)."""
import random
import unittest

from app.modules.instinct_doc import p235_concepts_batch44 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class Batch44Test(unittest.TestCase):
    def test_score_of_parentheses(self):
        self.assertEqual(m.score_of_parentheses("()"), 1)
        self.assertEqual(m.score_of_parentheses("(())"), 2)
        self.assertEqual(m.score_of_parentheses("()()"), 2)
        self.assertEqual(m.score_of_parentheses("(()(()))"), 6)
        # oracle: stack of sub-scores, independently coded
        rng = random.Random(4401)
        def gen(depth):
            out = []
            for _ in range(rng.randint(1, 3)):
                if depth and rng.random() < 0.5:
                    out.append("(" + gen(depth - 1) + ")")
                else:
                    out.append("()")
            return "".join(out)

        for _ in range(60):
            text = gen(5)
            stack = [0]
            for ch in text:
                if ch == "(":
                    stack.append(0)
                else:
                    inner = stack.pop()
                    stack[-1] += max(2 * inner, 1)
            self.assertEqual(m.score_of_parentheses(text), stack[0],
                             text)
        for bad in ("(", ")", "())", "(a)"):
            with self.assertRaises(ValueError, msg=bad):
                m.score_of_parentheses(bad)

    def test_shortest_completing_word(self):
        self.assertEqual(m.shortest_completing_word(
            "1s3 PSt", ["step", "steps", "stripe", "pole"]), "steps")
        self.assertEqual(m.shortest_completing_word(
            "a", ["x", "a", "ab"]), "a")
        # oracle: multiset coverage scan, same tie rule
        rng = random.Random(4402)
        pool = ["abc", "bca", "ab", "bc", "xyz", "abbc"]
        for _ in range(40):
            words = [rng.choice(pool)
                     for _ in range(rng.randint(1, 6))]
            plate = "".join(rng.choice("ab1 ") for _ in range(3))
            if not any(c.isalpha() for c in plate):
                continue
            need = {}
            for ch in plate.lower():
                if ch.isalpha():
                    need[ch] = need.get(ch, 0) + 1
            want = None
            for w in words:
                have = {}
                for ch in w:
                    have[ch] = have.get(ch, 0) + 1
                if all(have.get(c, 0) >= n for c, n in need.items()):
                    if want is None or len(w) < len(want):
                        want = w
            if want is None:
                with self.assertRaises(ValueError, msg=(plate, words)):
                    m.shortest_completing_word(plate, words)
            else:
                self.assertEqual(
                    m.shortest_completing_word(plate, words), want,
                    (plate, words))
        with self.assertRaises(ValueError):
            m.shortest_completing_word("123", ["abc"])

    def test_palindrome_one_delete(self):
        self.assertTrue(m.palindrome_one_delete("abca"))
        self.assertFalse(m.palindrome_one_delete("abc"))
        self.assertTrue(m.palindrome_one_delete("racecar"))
        # oracle: try deleting each position
        rng = random.Random(4403)
        for _ in range(60):
            text = "".join(rng.choice("abc")
                           for _ in range(rng.randint(1, 10)))
            want = any(text[:i] + text[i + 1:] ==
                       (text[:i] + text[i + 1:])[::-1]
                       for i in range(len(text) + 1))
            self.assertEqual(m.palindrome_one_delete(text), want, text)
        with self.assertRaises(ValueError):
            m.palindrome_one_delete("")

    def test_backspace_string_compare(self):
        self.assertTrue(m.backspace_string_compare("ab#c", "ad#c"))
        self.assertFalse(m.backspace_string_compare("a#c", "b"))
        self.assertTrue(m.backspace_string_compare("##a", "a"))
        self.assertTrue(m.backspace_string_compare("bxj##tw",
                                                   "bxo#j##tw"))
        # oracle: regex-free reduction with explicit list
        rng = random.Random(4404)
        for _ in range(60):
            a = "".join(rng.choice("ab#")
                        for _ in range(rng.randint(0, 8)))
            b = "".join(rng.choice("ab#")
                        for _ in range(rng.randint(0, 8)))

            def red(t):
                out = []
                for ch in t:
                    if ch == "#":
                        out = out[:-1]
                    else:
                        out.append(ch)
                return "".join(out)

            self.assertEqual(m.backspace_string_compare(a, b),
                             red(a) == red(b), (a, b))

    def test_buddy_strings_check(self):
        self.assertTrue(m.buddy_strings_check("ab", "ba"))
        self.assertTrue(m.buddy_strings_check("aa", "aa"))
        self.assertFalse(m.buddy_strings_check("ab", "ab"))
        self.assertFalse(m.buddy_strings_check("abc", "abd"))
        # oracle: try every swap
        rng = random.Random(4405)
        for _ in range(60):
            a = "".join(rng.choice("abc")
                        for _ in range(rng.randint(0, 8)))
            b = "".join(rng.choice("abc") for _ in range(len(a)))
            want = False
            for i in range(len(a)):
                for j in range(i + 1, len(a)):
                    t = list(a)
                    t[i], t[j] = t[j], t[i]
                    if "".join(t) == b:
                        want = True
            self.assertEqual(m.buddy_strings_check(a, b), want, (a, b))
        self.assertFalse(m.buddy_strings_check("ab", "abc"))

    def test_reverse_only_letters(self):
        self.assertEqual(m.reverse_only_letters("ab-cd"), "dc-ba")
        self.assertEqual(m.reverse_only_letters("a-bC-dEf-ghIj"),
                         "j-Ih-gfE-dCba")
        self.assertEqual(m.reverse_only_letters("123"), "123")
        # oracle: collect letters, re-place in reverse
        rng = random.Random(4406)
        pool = "aZ-1 "
        for _ in range(60):
            text = "".join(rng.choice(pool)
                           for _ in range(rng.randint(0, 12)))
            letters = [c for c in text if c.isascii() and c.isalpha()]
            out = []
            for ch in text:
                if ch.isascii() and ch.isalpha():
                    out.append(letters.pop())
                else:
                    out.append(ch)
            self.assertEqual(m.reverse_only_letters(text),
                             "".join(out), text)

    def test_shortest_completing_word_cap(self):
        # per-word length cap: at the cap accepted, cap + 1 refused
        cap = m.MAX_WORD
        good = "a" * (cap - 1) + "z"
        self.assertEqual(m.shortest_completing_word("z", [good]), good)
        too_long = "a" * cap + "z"
        with self.assertRaises(ValueError) as ctx:
            m.shortest_completing_word("z", [too_long])
        self.assertIn("too_long:words[0]", str(ctx.exception))
        # refusal lands before any matching work: a covering word
        # that is one over the cap is refused, not returned
        cover = "z" * (cap + 1)
        with self.assertRaises(ValueError) as ctx:
            m.shortest_completing_word("z", [cover])
        self.assertIn("too_long:words[0]", str(ctx.exception))

    def test_lemonade_change_possible(self):
        self.assertTrue(m.lemonade_change_possible([5, 5, 5, 10, 20]))
        self.assertFalse(m.lemonade_change_possible([5, 5, 10, 10, 20]))
        self.assertTrue(m.lemonade_change_possible([5]))
        # oracle: brute try both change strategies per 20
        rng = random.Random(4407)
        for _ in range(60):
            bills = [rng.choice([5, 10, 20])
                     for _ in range(rng.randint(1, 10))]

            def possible():
                f = t = 0
                for b in bills:
                    if b == 5:
                        f += 1
                    elif b == 10:
                        if f < 1:
                            return False
                        f -= 1
                        t += 1
                    else:
                        if t >= 1 and f >= 1:
                            t -= 1
                            f -= 1
                        elif f >= 3:
                            f -= 3
                        else:
                            return False
                return True

            self.assertEqual(m.lemonade_change_possible(bills),
                             possible(), bills)
        with self.assertRaises(ValueError):
            m.lemonade_change_possible([7])

    def test_lemonade_change_validates_all_first(self):
        # bad bills refuse even when the queue would fail first
        for bad in ([10, True], [5, True], [True], [10, "x"],
                    [20, 20, 20, 5, "oops"], [7], [5, 0]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                m.lemonade_change_possible(list(bad))
        # refusal code names the bad position, not a False result
        with self.assertRaises(ValueError) as ctx:
            m.lemonade_change_possible([10, True])
        self.assertIn("bills[1]", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.lemonade_change_possible([True])
        self.assertIn("bills[0]", str(ctx.exception))
        # honest False still works when every bill is valid
        self.assertFalse(m.lemonade_change_possible([10]))
        self.assertTrue(m.lemonade_change_possible(
            [5, 5, 5, 10, 20]))

    def test_fair_candy_swap_sizes(self):
        self.assertEqual(m.fair_candy_swap_sizes([1, 1], [2, 2]), [1, 2])
        self.assertEqual(m.fair_candy_swap_sizes([1, 2], [2, 3]), [1, 2])
        # oracle: exhaustive pair search, same tie rule
        rng = random.Random(4408)
        for _ in range(40):
            a = [rng.randint(1, 9) for _ in range(rng.randint(1, 6))]
            b = [rng.randint(1, 9) for _ in range(rng.randint(1, 6))]
            diff = sum(a) - sum(b)
            want = None
            if diff % 2 == 0:
                half = diff // 2
                for x in sorted(set(a)):
                    if x - half in set(b):
                        cand = [x, x - half]
                        if (want is None
                                or (abs(x), x) < (abs(want[0]),
                                                  want[0])):
                            want = cand
            if want is None:
                with self.assertRaises(ValueError, msg=(a, b)):
                    m.fair_candy_swap_sizes(a, b)
            else:
                self.assertEqual(m.fair_candy_swap_sizes(a, b), want,
                                 (a, b))
        with self.assertRaises(ValueError):
            m.fair_candy_swap_sizes([1], [2])

    def test_projection_area_3d(self):
        self.assertEqual(m.projection_area_3d([[1, 2], [3, 4]]), 17)
        self.assertEqual(m.projection_area_3d([[2]]), 5)
        self.assertEqual(m.projection_area_3d([[1, 0], [0, 2]]), 8)
        # oracle: definition from row/col maxima and nonzero count
        rng = random.Random(4409)
        for _ in range(40):
            h = rng.randint(1, 5)
            w = rng.randint(1, 5)
            g = [[rng.randint(0, 6) for _ in range(w)] for _ in range(h)]
            want = (sum(1 for row in g for v in row if v > 0)
                    + sum(max(g[r][c] for r in range(h))
                          for c in range(w))
                    + sum(max(row) for row in g))
            self.assertEqual(m.projection_area_3d(g), want, g)
        with self.assertRaises(ValueError):
            m.projection_area_3d([[1], [1, -1]])

    def test_smallest_range_cover(self):
        self.assertEqual(m.smallest_range_cover(
            [[4, 10, 15, 24, 26], [0, 9, 12, 20], [5, 18, 22, 30]]),
            [20, 24])
        self.assertEqual(m.smallest_range_cover([[1], [1]]), [1, 1])
        # oracle: brute force over the Cartesian product, tiny inputs
        from itertools import product
        rng = random.Random(4410)
        for _ in range(30):
            k = rng.randint(2, 3)
            lists = [sorted(rng.sample(range(20),
                                       rng.randint(1, 3)))
                     for _ in range(k)]
            best = None
            for combo in product(*lists):
                span = max(combo) - min(combo)
                cand = [min(combo), max(combo)]
                if best is None or span < best[1] - best[0]:
                    best = cand
            self.assertEqual(m.smallest_range_cover(lists), best,
                             lists)
        with self.assertRaises(ValueError):
            m.smallest_range_cover([[3, 1]])
        with self.assertRaises(ValueError):
            m.smallest_range_cover([[]])

    def test_registry_knows_batch44(self):
        names = [e["name"] for e in reg.ENTRIES if e["batch"] == 44]
        self.assertEqual(len(names), 10)
        for name in ("score_of_parentheses", "shortest_completing_word",
                     "palindrome_one_delete", "backspace_string_compare",
                     "buddy_strings_check", "reverse_only_letters",
                     "lemonade_change_possible", "fair_candy_swap_sizes",
                     "projection_area_3d", "smallest_range_cover"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
