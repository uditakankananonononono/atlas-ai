"""Tests for P235 concepts batch 101.

Every pin was read off a live run of the module. Randomized
and exhaustive checks compare against independent oracles:
Vandermonde Gaussian elimination for interpolation,
known-answer Brainfuck programs, step invariants for the ant,
brute-force residue sets plus root verification for
Tonelli-Shanks, and a from-spec encoder exercised over every
codeword and every single-bit flip for Hamming(7,4).
"""
import random
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, "backend")

from app.modules.instinct_doc import p235_concepts_batch101 as b101


class TestLagrangeInterpolate(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(
            b101.lagrange_interpolate([[0, 0], [1, 1], [2, 4]],
                                      3),
            Fraction(9))
        self.assertEqual(b101.lagrange_interpolate([[1, 3]], 99),
                         Fraction(3))
        self.assertEqual(
            b101.lagrange_interpolate([[0, 1], [1, 5]], -2),
            Fraction(-7))

    def _vandermonde_value(self, points, x):
        # Independent oracle: solve for the coefficients by
        # exact Gaussian elimination, then evaluate by Horner.
        n = len(points)
        mat = []
        for xi, yi in points:
            row = [Fraction(xi)**k for k in range(n)]
            mat.append(row + [Fraction(yi)])
        for col in range(n):
            piv = next(r for r in range(col, n)
                       if mat[r][col] != 0)
            mat[col], mat[piv] = mat[piv], mat[col]
            inv = 1 / mat[col][col]
            mat[col] = [v * inv for v in mat[col]]
            for r in range(n):
                if r != col and mat[r][col] != 0:
                    f = mat[r][col]
                    mat[r] = [a - f * b for a, b in
                              zip(mat[r], mat[col])]
        coeffs = [mat[r][n] for r in range(n)]
        out = Fraction(0)
        for c in reversed(coeffs):
            out = out * x + c
        return out

    def test_oracle_vandermonde(self):
        rng = random.Random(744)
        for _ in range(120):
            n = rng.randint(1, 7)
            xs = rng.sample(range(-20, 21), n)
            points = [[xi, rng.randint(-30, 30)] for xi in xs]
            x = rng.randint(-10, 10)
            self.assertEqual(
                b101.lagrange_interpolate(points, x),
                self._vandermonde_value(points, x))
            # the interpolant hits every given point
            for xi, yi in points:
                self.assertEqual(
                    b101.lagrange_interpolate(points, xi),
                    Fraction(yi))

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b101.lagrange_interpolate(*args)
            self.assertIn("lagrange_interpolate:" + want,
                          str(ctx.exception))
        code("empty:points", [], 0)
        code("too_many:points", [[i, i] for i in range(17)], 0)
        code("bad_shape:points[0]", [[1]], 0)
        code("bad_type:points[0][0]", [[True, 1]], 0)
        code("bad_type:points[0][1]", [[1, 1.5]], 0)
        code("out_of_range:points[0][0]",
             [[10**9 + 1, 0]], 0)
        code("out_of_range:points[0][1]",
             [[0, -(10**9 + 1)]], 0)
        code("duplicate:points[1]", [[1, 2], [1, 3]], 0)
        code("out_of_range:x", [[1, 2]], 10**9 + 1)
        code("out_of_range:x", [[1, 2]], -(10**9 + 1))
        # boundaries accepted
        self.assertEqual(
            len(str(b101.lagrange_interpolate(
                [[i, i] for i in range(16)], 5))) > 0, True)
        self.assertEqual(
            b101.lagrange_interpolate([[10**9, 7]], 10**9),
            Fraction(7))

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b101.lagrange_interpolate(bad, 0)
            with self.assertRaises(ValueError):
                b101.lagrange_interpolate([[1, 2]], bad)


class TestBrainfuckInterpret(unittest.TestCase):
    def test_known_programs(self):
        # 4 * 4 = 16 printed as one byte
        self.assertEqual(b101.brainfuck_interpret(
            "++++[>++++<-]>.", ""), [16])
        # echo the two input bytes
        self.assertEqual(b101.brainfuck_interpret(",[.,]", "hi"),
                         [104, 105])
        # non-command characters are ignored
        self.assertEqual(b101.brainfuck_interpret(
            "++ plus two more ++ .", ""), [4])
        # reads past the end of input yield 0
        self.assertEqual(b101.brainfuck_interpret(",,.", "A"),
                         [0])
        # wrapping cells
        self.assertEqual(b101.brainfuck_interpret("-.+++.", ""),
                         [255, 2])

    def test_hello_world(self):
        prog = ("++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]"
                ">>.>---.+++++++..+++.>>.<-.<.+++.------.--------."
                ">>+.>++.")
        self.assertEqual(
            bytes(b101.brainfuck_interpret(prog, "")),
            b"Hello World!\n")

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b101.brainfuck_interpret(*args)
            self.assertIn("brainfuck_interpret:" + want,
                          str(ctx.exception))
        code("unmatched:program", "]", "")
        code("unmatched:program", "[", "")
        code("unmatched:program", "[[]", "")
        code("unmatched:program", "[]]", "")
        code("out_of_tape:program", "<", "")
        code("out_of_tape:program", ">" * 4096, "")
        code("too_complex:program", "+[]", "")
        code("too_long:program", "+" * 10001, "")
        code("too_long:input_text", "", "x" * 1025)
        code("bad_char:input_text", "", "\ud800")
        code("bad_type:program", None, "")
        code("bad_type:input_text", "", 7)
        # boundaries accepted
        self.assertEqual(b101.brainfuck_interpret(">" * 4095,
                                                  ""), [])
        self.assertEqual(
            b101.brainfuck_interpret("+" * 10000, ""), [])
        self.assertEqual(
            b101.brainfuck_interpret(",.", "x" * 1024), [120])

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b101.brainfuck_interpret(bad, "")
            with self.assertRaises(ValueError):
                b101.brainfuck_interpret("", bad)


class TestLangtonsAnt(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b101.langtons_ant(0), [0, 0, 0, 0])
        self.assertEqual(b101.langtons_ant(4), [0, 0, 0, 4])
        self.assertEqual(b101.langtons_ant(11), [-2, -1, 3, 7])
        self.assertEqual(b101.langtons_ant(100), [0, 2, 0, 20])
        self.assertEqual(b101.langtons_ant(1000),
                         [8, 6, 2, 118])

    def test_invariants(self):
        # independent re-simulation with a different data shape
        for steps in (1, 7, 50, 250):
            black = set()
            x = y = d = 0
            for _ in range(steps):
                if (x, y) in black:
                    black.remove((x, y))
                    d = (d + 3) % 4
                else:
                    black.add((x, y))
                    d = (d + 1) % 4
                x, y = (x + (0, 1, 0, -1)[d],
                        y + (1, 0, -1, 0)[d])
            self.assertEqual(b101.langtons_ant(steps),
                             [x, y, d, len(black)])
            self.assertLessEqual(b101.langtons_ant(steps)[3],
                                 steps)

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b101.langtons_ant(*args)
            self.assertIn("langtons_ant:" + want,
                          str(ctx.exception))
        code("out_of_range:steps", -1)
        code("out_of_range:steps", 20001)
        code("bad_type:steps", True)
        code("bad_type:steps", 2.5)
        # boundary accepted
        out = b101.langtons_ant(20000)
        self.assertEqual(len(out), 4)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b101.langtons_ant(bad)


class TestTonelliShanks(unittest.TestCase):
    def test_pins(self):
        self.assertEqual(b101.tonelli_shanks(4, 7), 2)
        self.assertEqual(b101.tonelli_shanks(2, 7), 3)
        self.assertIsNone(b101.tonelli_shanks(3, 7))
        self.assertEqual(b101.tonelli_shanks(0, 7), 0)
        self.assertIsNone(b101.tonelli_shanks(-1, 7))
        self.assertEqual(b101.tonelli_shanks(10, 13), 6)

    def test_oracle_exhaustive_small_primes(self):
        primes = [p for p in range(3, 200)
                  if all(p % d for d in range(2, p))]
        for p in primes:
            residues = {(x * x) % p for x in range(p)}
            for n in range(p):
                got = b101.tonelli_shanks(n, p)
                if n in residues:
                    self.assertIsNotNone(got, (n, p))
                    self.assertEqual((got * got) % p, n)
                    self.assertLessEqual(got, p // 2)
                else:
                    self.assertIsNone(got, (n, p))

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b101.tonelli_shanks(*args)
            self.assertIn("tonelli_shanks:" + want,
                          str(ctx.exception))
        # signature is (n, p)
        code("out_of_range:p", 1, 0)
        code("out_of_range:p", 1, 2)
        code("out_of_range:p", 1, 10**6 + 1)
        code("not_prime:p", 1, 9)
        code("not_prime:p", 2, 15)
        code("out_of_range:n", 10**9 + 1, 3)
        code("out_of_range:n", -(10**9 + 1), 3)
        code("bad_type:p", 1, True)
        code("bad_type:n", 1.5, 3)
        # boundaries accepted (both are non-residues there)
        self.assertIsNone(b101.tonelli_shanks(10**9, 999983))
        self.assertIsNone(b101.tonelli_shanks(-10**9, 3))
        self.assertEqual(b101.tonelli_shanks(4, 999983), 2)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b101.tonelli_shanks(bad, 3)
            with self.assertRaises(ValueError):
                b101.tonelli_shanks(1, bad)


class TestHamming74Decode(unittest.TestCase):
    @staticmethod
    def _encode(nibble):
        # Independent from-spec encoder: data bits to positions
        # 3, 5, 6, 7, then even parity at positions 1, 2, 4.
        bits = [0] * 8
        for i, pos in enumerate((3, 5, 6, 7)):
            bits[pos] = (nibble >> i) & 1
        for par in (1, 2, 4):
            total = 0
            for pos in range(1, 8):
                if pos & par:
                    total ^= bits[pos]
            bits[par] = total
        return sum(bits[pos] << (pos - 1) for pos in range(1, 8))

    def test_pins(self):
        self.assertEqual(b101.hamming74_decode(0), [0, 0])
        self.assertEqual(b101.hamming74_decode(4), [0, 3])
        self.assertEqual(b101.hamming74_decode(127), [127, 0])
        self.assertEqual(b101.hamming74_decode(126), [127, 1])

    def test_oracle_all_codewords_all_flips(self):
        for nibble in range(16):
            cw = self._encode(nibble)
            # no error
            self.assertEqual(b101.hamming74_decode(cw), [cw, 0])
            # every single-bit error corrects back
            for pos in range(1, 8):
                flipped = cw ^ (1 << (pos - 1))
                self.assertEqual(b101.hamming74_decode(flipped),
                                 [cw, pos])

    def test_refusals(self):
        def code(want, *args):
            with self.assertRaises(ValueError) as ctx:
                b101.hamming74_decode(*args)
            self.assertIn("hamming74_decode:" + want,
                          str(ctx.exception))
        code("out_of_range:code", -1)
        code("out_of_range:code", 128)
        code("bad_type:code", True)
        code("bad_type:code", 3.5)

    def test_nonbool(self):
        for bad in (True, 3.5, None):
            with self.assertRaises(ValueError):
                b101.hamming74_decode(bad)


if __name__ == "__main__":
    unittest.main()
