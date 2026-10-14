"""Tests for P235 concepts batch 100.

Every pin was read off a live run of the module. The RC-4 pins
cross-check two external vector sets: the classic Key/Wiki/
Secret short-key vectors, and RFC 6229 vectors for the 40-bit
key 0102030405 at stream offsets 0 and 4096. Randomized checks
compare against independent oracles: a scaled-integer
simulation for the token bucket, connectivity, symmetry and
spanning-tree counts for the maze, brute-force permutation
search plus substitution verification for cryptarithmetic,
and the no-false-negatives property for the Bloom filter.
"""
import itertools
import random
import sys
import unittest

sys.path.insert(0, "backend")

from app.modules.instinct_doc import p235_concepts_batch100 as b100


class TestRc4Keystream(unittest.TestCase):
    def test_classic_vectors(self):
        # The classic well-known RC4 test vectors (keys "Key",
        # "Wiki", "Secret"), not RFC 6229 material.
        self.assertEqual(
            b100.rc4_keystream([0x4B, 0x65, 0x79], 8),
            [0xEB, 0x9F, 0x77, 0x81, 0xB7, 0x34, 0xCA, 0x72])
        self.assertEqual(
            b100.rc4_keystream([0x57, 0x69, 0x6B, 0x69], 8),
            [0x60, 0x44, 0xDB, 0x6D, 0x41, 0xB7, 0xE8, 0xE7])
        self.assertEqual(
            b100.rc4_keystream(
                [0x53, 0x65, 0x63, 0x72, 0x65, 0x74], 8),
            [0x04, 0xD4, 0x6B, 0x05, 0x3C, 0xA8, 0x7B, 0x59])

    def test_rfc6229_vectors(self):
        # RFC 6229, 40-bit key 0x0102030405: 16 bytes at stream
        # offsets 0 and 4096, transcribed from the RFC text.
        ks = b100.rc4_keystream([0x01, 0x02, 0x03, 0x04, 0x05],
                                4112)
        self.assertEqual(
            ks[:16],
            [0xB2, 0x39, 0x63, 0x05, 0xF0, 0x3D, 0xC0, 0x27,
             0xCC, 0xC3, 0x52, 0x4A, 0x0A, 0x11, 0x18, 0xA8])
        self.assertEqual(
            ks[4096:4112],
            [0xFF, 0x25, 0xB5, 0x89, 0x95, 0x99, 0x67, 0x07,
             0xE5, 0x1F, 0xBD, 0xF0, 0x8B, 0x34, 0xD8, 0x75])

    def test_edges(self):
        self.assertEqual(b100.rc4_keystream([0], 0), [])
        self.assertEqual(len(b100.rc4_keystream([7] * 256, 10)),
                         10)
        self.assertEqual(
            len(b100.rc4_keystream([255, 0, 128], 10000)), 10000)
        out = b100.rc4_keystream([42], 500)
        self.assertTrue(all(0 <= v <= 255 for v in out))
        self.assertEqual(out, b100.rc4_keystream([42], 500))

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b100.rc4_keystream(*args)
            self.assertIn("rc4_keystream:" + want,
                          str(ctx.exception))
        code("empty:key", [], 1)
        code("too_many:key", [0] * 257, 1)
        code("out_of_range:key[0]", [256], 1)
        code("out_of_range:key[1]", [0, -1], 1)
        code("out_of_range:n", [1], -1)
        code("out_of_range:n", [1], 10001)
        code("bad_type:key", None, 1)
        code("bad_type:key[0]", [True], 1)
        code("bad_type:n", [1], 2.5)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b100.rc4_keystream(bad, 1)
            with self.assertRaises(ValueError):
                b100.rc4_keystream([1], bad)


class TestTokenBucketTrace(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(
            b100.token_bucket_trace(
                4, 1, 2, [[0, 3], [1, 3], [2, 3], [10, 4],
                          [10, 1]]),
            [1, 0, 0, 1, 0])

    def test_oracle_scaled_ints(self):
        # Independent simulation: bucket and capacity scaled by
        # refill_den stay integral, so no Fractions are used.
        rng = random.Random(1001)
        for _ in range(200):
            cap = rng.randint(1, 12)
            num = rng.randint(0, 6)
            den = rng.randint(1, 6)
            events = []
            tick = 0
            for _ in range(rng.randint(0, 10)):
                tick += rng.randint(0, 4)
                events.append([tick, rng.randint(1, cap)])
            want = []
            bucket = cap * den
            cap_s = cap * den
            prev = 0
            for t, cost in events:
                bucket = min(cap_s, bucket + (t - prev) * num)
                prev = t
                if bucket >= cost * den:
                    bucket -= cost * den
                    want.append(1)
                else:
                    want.append(0)
            self.assertEqual(
                b100.token_bucket_trace(cap, num, den, events),
                want)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b100.token_bucket_trace(*args)
            self.assertIn("token_bucket_trace:" + want,
                          str(ctx.exception))
        code("out_of_range:capacity", 0, 1, 1, [])
        code("out_of_range:capacity", 10**9 + 1, 1, 1, [])
        code("out_of_range:refill_num", 1, -1, 1, [])
        code("out_of_range:refill_num", 1, 10**9 + 1, 1, [])
        code("out_of_range:refill_den", 1, 1, 0, [])
        code("out_of_range:refill_den", 1, 1, 10**9 + 1, [])
        code("bad_shape:events[0]", 1, 1, 1, [[0]])
        code("bad_type:events[0][0]", 1, 1, 1, [[True, 1]])
        code("bad_type:events[0][1]", 1, 1, 1, [[0, 1.5]])
        code("out_of_range:events[0][0]", 1, 1, 1, [[-1, 1]])
        code("out_of_range:events[0][0]", 1, 1, 1,
             [[10**9 + 1, 1]])
        code("unordered:events[1]", 2, 1, 1, [[5, 1], [4, 1]])
        code("out_of_range:events[0][1]", 2, 1, 1, [[0, 0]])
        code("out_of_range:events[0][1]", 2, 1, 1, [[0, 3]])

    def test_cap(self):
        events = [[i, 1] for i in range(10000)]
        self.assertEqual(
            len(b100.token_bucket_trace(10**9, 10**9, 1, events)),
            10000)
        with self.assertRaises(ValueError):
            b100.token_bucket_trace(1, 1, 1, [0] * 10001)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b100.token_bucket_trace(bad, 1, 1, [])
            with self.assertRaises(ValueError):
                b100.token_bucket_trace(1, bad, 1, [])
            with self.assertRaises(ValueError):
                b100.token_bucket_trace(1, 1, bad, [])
            with self.assertRaises(ValueError):
                b100.token_bucket_trace(1, 1, 1, bad)


class TestMazeGenBacktracker(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b100.maze_gen_backtracker(1, 1, 7),
                         [[0]])
        self.assertEqual(b100.maze_gen_backtracker(2, 3, 42),
                         [[4, 6, 12], [3, 9, 1]])
        self.assertEqual(b100.maze_gen_backtracker(3, 3, 0),
                         [[4, 2, 12], [3, 10, 13],
                          [2, 10, 9]])

    def test_oracle_tree_and_connected(self):
        rng = random.Random(77)
        for _ in range(40):
            rows = rng.randint(1, 8)
            cols = rng.randint(1, 8)
            seed = rng.randint(0, 2**64 - 1)
            grid = b100.maze_gen_backtracker(rows, cols, seed)
            # passage symmetry and count
            bits = 0
            for r in range(rows):
                for c in range(cols):
                    v = grid[r][c]
                    bits += bin(v).count("1")
                    if v & 1:
                        self.assertTrue(grid[r - 1][c] & 4)
                    if v & 2:
                        self.assertTrue(grid[r][c + 1] & 8)
                    if v & 4:
                        self.assertTrue(grid[r + 1][c] & 1)
                    if v & 8:
                        self.assertTrue(grid[r][c - 1] & 2)
            self.assertEqual(bits // 2, rows * cols - 1)
            # connectivity from (0, 0)
            seen = {(0, 0)}
            stack = [(0, 0)]
            while stack:
                r, c = stack.pop()
                for bit, dr, dc in ((1, -1, 0), (2, 0, 1),
                                    (4, 1, 0), (8, 0, -1)):
                    if grid[r][c] & bit:
                        nxt = (r + dr, c + dc)
                        if nxt not in seen:
                            seen.add(nxt)
                            stack.append(nxt)
            self.assertEqual(len(seen), rows * cols)
            # determinism
            self.assertEqual(
                grid, b100.maze_gen_backtracker(rows, cols, seed))

    def test_seeds_differ(self):
        self.assertNotEqual(b100.maze_gen_backtracker(5, 5, 1),
                            b100.maze_gen_backtracker(5, 5, 2))

    def test_refusals_and_caps(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b100.maze_gen_backtracker(*args)
            self.assertIn("maze_gen_backtracker:" + want,
                          str(ctx.exception))
        code("out_of_range:rows", 0, 1, 0)
        code("out_of_range:rows", 4097, 1, 0)
        code("out_of_range:cols", 1, 0, 0)
        code("out_of_range:cols", 1, 4097, 0)
        code("too_many:rows,cols", 65, 64, 0)
        code("out_of_range:seed", 1, 1, -1)
        code("out_of_range:seed", 1, 1, 2**64)
        code("bad_type:rows", True, 1, 0)
        code("bad_type:seed", 1, 1, 1.5)
        # boundary accepted: exactly MAX_MAZE_CELLS cells
        grid = b100.maze_gen_backtracker(64, 64, 3)
        self.assertEqual(len(grid), 64)
        self.assertEqual(len(grid[0]), 64)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b100.maze_gen_backtracker(bad, 1, 0)
            with self.assertRaises(ValueError):
                b100.maze_gen_backtracker(1, bad, 0)
            with self.assertRaises(ValueError):
                b100.maze_gen_backtracker(1, 1, bad)


class TestCryptarithmeticSolve(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b100.cryptarithmetic_solve(["SEND", "MORE"], "MONEY"),
            [["D", 7], ["E", 5], ["M", 1], ["N", 6], ["O", 0],
             ["R", 8], ["S", 9], ["Y", 2]])
        self.assertEqual(b100.cryptarithmetic_solve(["I", "BB"],
                                                    "ILL"),
                         [["B", 9], ["I", 1], ["L", 0]])
        self.assertEqual(b100.cryptarithmetic_solve(["A", "A"],
                                                    "B"),
                         [["A", 1], ["B", 2]])
        self.assertIsNone(
            b100.cryptarithmetic_solve(["AB", "CDE"], "FGHIJ"))

    def _verify(self, terms, result, sol):
        mapping = dict(sol)
        self.assertEqual(len(mapping), len(set(mapping.values())))
        for w in terms + [result]:
            self.assertNotEqual(mapping[w[0]], 0)

        def val(w):
            out = 0
            for ch in w:
                out = out * 10 + mapping[ch]
            return out
        self.assertEqual(sum(val(w) for w in terms), val(result))

    def test_oracle_brute_force(self):
        rng = random.Random(4242)
        letters = "ABCDEFGH"
        for _ in range(60):
            distinct = rng.sample(letters, rng.randint(2, 6))

            def word(maxlen):
                return "".join(rng.choice(distinct)
                               for _ in range(rng.randint(1, 3)))

            terms = [word(3) for _ in range(2)]
            result = word(4)
            got = b100.cryptarithmetic_solve(terms, result)
            # independent existence check by raw permutations
            pool = sorted(set("".join(terms) + result))
            found = None
            for digs in itertools.permutations(range(10),
                                               len(pool)):
                m = dict(zip(pool, digs))
                if any(m[w[0]] == 0 for w in terms + [result]):
                    continue

                def val(w):
                    out = 0
                    for ch in w:
                        out = out * 10 + m[ch]
                    return out
                if sum(val(w) for w in terms) == val(result):
                    found = m
                    break
            if found is None:
                self.assertIsNone(got)
            else:
                self.assertIsNotNone(got)
                self._verify(terms, result, got)

    def test_refusals_and_caps(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b100.cryptarithmetic_solve(*args)
            self.assertIn("cryptarithmetic_solve:" + want,
                          str(ctx.exception))
        code("too_few:terms", ["A"], "B")
        code("too_many:terms", ["A"] * 9, "B")
        code("empty:terms[0]", ["", "A"], "B")
        code("empty:result", ["A", "B"], "")
        code("too_long:terms[0]", ["A" * 13, "B"], "C")
        code("too_long:result", ["A", "B"], "C" * 13)
        code("bad_char:terms[0][1]", ["Aa", "B"], "C")
        code("bad_char:terms[0][1]", ["A\ud800", "B"], "C")
        code("bad_char:result[0]", ["A", "B"], "c")
        # 11 distinct letters refuse; exactly 10 accepted
        code("too_many:letters", ["ABC", "DEF"], "GHIJK")
        self.assertIsNone(
            b100.cryptarithmetic_solve(["AB", "CDE"], "FGHIJ"))

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b100.cryptarithmetic_solve(bad, "B")
            with self.assertRaises(ValueError):
                b100.cryptarithmetic_solve([bad, "B"], "C")
            with self.assertRaises(ValueError):
                b100.cryptarithmetic_solve(["A", "B"], bad)


class TestBloomFilterCheck(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b100.bloom_filter_check(
                ["apple", "banana", "cherry"],
                ["apple", "grape", "cherry", "durian"], 64, 3),
            [1, 0, 1, 0])
        self.assertEqual(
            b100.bloom_filter_check(["a"], ["a", "b"], 8, 1),
            [1, 0])

    def test_no_false_negatives(self):
        rng = random.Random(31337)
        items = ["item-%d-%d" % (rng.randint(0, 10**6), i)
                 for i in range(300)]
        verdicts = b100.bloom_filter_check(items, items, 4096, 4)
        self.assertTrue(all(v == 1 for v in verdicts))

    def test_absent_mostly_rejected(self):
        rng = random.Random(999)
        items = ["k%d" % i for i in range(100)]
        queries = ["q%d" % i for i in range(2000)]
        verdicts = b100.bloom_filter_check(items, queries,
                                           4096, 3)
        hits = sum(verdicts)
        # read off the run; far below the 2000 queries
        self.assertEqual(hits, 2)

    def test_deterministic(self):
        args = (["x", "yz"], ["x", "w"], 128, 5)
        self.assertEqual(b100.bloom_filter_check(*args),
                         b100.bloom_filter_check(*args))

    def test_refusals_and_caps(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b100.bloom_filter_check(*args)
            self.assertIn("bloom_filter_check:" + want,
                          str(ctx.exception))
        code("out_of_range:size", [], [], 0, 1)
        code("out_of_range:size", [], [], 4097, 1)
        code("out_of_range:hashes", [], [], 8, 0)
        code("out_of_range:hashes", [], [], 8, 65)
        code("too_long:items[0]", ["a" * 1025], [], 8, 1)
        code("too_long:queries[0]", [], ["b" * 1025], 8, 1)
        code("bad_type:items[0]", [7], [], 8, 1)
        code("bad_type:queries[0]", [], [None], 8, 1)
        code("bad_char:items[0]", ["\ud800"], [], 8, 1)
        code("bad_char:queries[0]", [], ["ok\udfff"], 8, 1)
        code("bad_char:items[0]", ["\udfff" * 3], [], 8, 1)
        # boundaries accepted
        self.assertEqual(
            len(b100.bloom_filter_check(["a"], ["a"], 4096,
                                        64)), 1)
        self.assertEqual(
            b100.bloom_filter_check(["a" * 1024], ["a" * 1024],
                                    8, 1), [1])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b100.bloom_filter_check(bad, [], 8, 1)
            with self.assertRaises(ValueError):
                b100.bloom_filter_check([], bad, 8, 1)
            with self.assertRaises(ValueError):
                b100.bloom_filter_check([], [], bad, 1)
            with self.assertRaises(ValueError):
                b100.bloom_filter_check([], [], 8, bad)


if __name__ == "__main__":
    unittest.main()
