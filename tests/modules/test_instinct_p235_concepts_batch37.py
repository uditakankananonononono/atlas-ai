"""P235 concepts, batch 37 (checksums, encodings, DP II, 361-370)."""
from __future__ import annotations

import base64
import json
import random
import unittest
import zlib

from app.modules.instinct_doc import p235_concepts_batch37 as m


class Batch37Test(unittest.TestCase):
    def test_adler32_sum(self):
        self.assertEqual(m.adler32_sum(""), 1)
        self.assertEqual(m.adler32_sum("Wikipedia"), 0x11E60398)
        with self.assertRaises(ValueError):
            m.adler32_sum(b"bytes-refused")
        with self.assertRaises(ValueError) as ctx:
            m.adler32_sum("héllo")
        self.assertIn("non_ascii", str(ctx.exception))

    def test_adler32_zlib_oracle(self):
        rng = random.Random(37)
        for _ in range(80):
            n = rng.randint(0, 300)
            s = "".join(chr(rng.randint(32, 126)) for _ in range(n))
            self.assertEqual(m.adler32_sum(s),
                             zlib.adler32(s.encode("utf-8")), s)

    def test_crc16_ccitt_value(self):
        self.assertEqual(m.crc16_ccitt_value("123456789"), 0x29B1)
        self.assertEqual(m.crc16_ccitt_value(""), 0xFFFF)
        with self.assertRaises(ValueError):
            m.crc16_ccitt_value(123)

    def test_crc16_table_oracle(self):
        # independent route: table-driven implementation of the same
        # CRC-16/CCITT-FALSE spec, built differently from the module's
        # shift loop
        table = []
        for b in range(256):
            crc = b << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF \
                    if crc & 0x8000 else (crc << 1) & 0xFFFF
            table.append(crc)

        def oracle(data):
            crc = 0xFFFF
            for byte in data:
                crc = ((crc << 8) ^ table[(crc >> 8) ^ byte]) & 0xFFFF
            return crc

        rng = random.Random(3)
        for _ in range(80):
            n = rng.randint(0, 200)
            s = "".join(chr(rng.randint(32, 126)) for _ in range(n))
            self.assertEqual(m.crc16_ccitt_value(s),
                             oracle(s.encode("utf-8")), s)

    def test_base32_encode_text(self):
        vectors = {"": "", "f": "MY======", "fo": "MZXQ====",
                   "foo": "MZXW6===", "foob": "MZXW6YQ=",
                   "fooba": "MZXW6YTB", "foobar": "MZXW6YTBOI======"}
        for raw, want in vectors.items():
            self.assertEqual(m.base32_encode_text(raw), want)
        with self.assertRaises(ValueError):
            m.base32_encode_text(5)

    def test_base32_stdlib_oracle(self):
        rng = random.Random(11)
        for _ in range(80):
            n = rng.randint(0, 40)
            s = "".join(chr(rng.randint(32, 126)) for _ in range(n))
            self.assertEqual(m.base32_encode_text(s),
                             base64.b32encode(s.encode()).decode(), s)

    def test_base32_decode_text(self):
        self.assertEqual(m.base32_decode_text("MZXW6YTBOI======"),
                         "foobar")
        self.assertEqual(m.base32_decode_text(""), "")
        with self.assertRaises(ValueError) as ctx:
            m.base32_decode_text("MZX")  # length not multiple of 8
        self.assertIn("length", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.base32_decode_text("mzxw6yq=")  # lowercase refused
        self.assertIn("bad_value", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            m.base32_decode_text("MZXW6Y==")  # impossible padding
        self.assertIn("padding", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.base32_decode_text("MZXW6YQ1")  # 1 not in alphabet

    def test_base32_roundtrip_oracle(self):
        rng = random.Random(17)
        for _ in range(80):
            n = rng.randint(0, 40)
            s = "".join(chr(rng.randint(32, 126)) for _ in range(n))
            enc = m.base32_encode_text(s)
            self.assertEqual(base64.b32decode(enc).decode(), s)
            self.assertEqual(m.base32_decode_text(enc), s)

    def test_json_number_check(self):
        for good in ("0", "-0", "1", "-12.5e+3", "10", "0.5", "6e-2",
                     "12345678901234567890"):
            self.assertTrue(m.json_number_check(good), good)
        for bad in ("", "01", ".5", "1.", "+1", "1e", "0x10", "NaN",
                    "Infinity", "1 2", "--1", "1.2.3", "e5"):
            self.assertFalse(m.json_number_check(bad), bad)
        with self.assertRaises(ValueError):
            m.json_number_check(5)

    def test_json_number_vs_json_loads(self):
        # independent oracle: Python's json parser acceptance, over a
        # candidate space that avoids its non-strict NaN/Infinity
        rng = random.Random(23)
        alphabet = "0123456789-+eE."
        for _ in range(400):
            n = rng.randint(0, 10)
            s = "".join(rng.choice(alphabet) for _ in range(n))
            try:
                json.loads(s)
                want = True
            except (json.JSONDecodeError, ValueError):
                want = False
            self.assertEqual(m.json_number_check(s), want, s)

    def test_json_string_escape(self):
        self.assertEqual(m.json_string_escape('a"b'), 'a\\"b')
        self.assertEqual(m.json_string_escape("back\\slash"),
                         "back\\\\slash")
        self.assertEqual(m.json_string_escape("tab\there"),
                         "tab\\there")
        self.assertEqual(m.json_string_escape("bell\x07"),
                         "bell\\u0007")
        self.assertEqual(m.json_string_escape("unicode-é"), "unicode-é")
        with self.assertRaises(ValueError):
            m.json_string_escape(5)

    def test_json_string_unescape(self):
        self.assertEqual(m.json_string_unescape('a\\"b'), 'a"b')
        self.assertEqual(m.json_string_unescape("\\u0041\\n"), "A\n")
        self.assertEqual(m.json_string_unescape("plain"), "plain")
        for bad in ("trailing\\", "bad\\xescape", "\\u12",
                    "\\u12zz", "raw\x01control"):
            with self.assertRaises(ValueError, msg=bad):
                m.json_string_unescape(bad)

    def test_json_escape_roundtrip_oracle(self):
        rng = random.Random(29)
        pool = 'ab"\\\n\t\x00\x1féz'
        for _ in range(200):
            s = "".join(rng.choice(pool) for _ in range(rng.randint(0, 12)))
            # stdlib reference: json.dumps with ensure_ascii=False uses
            # the same escapes for quote/backslash/control
            ref = json.dumps(s, ensure_ascii=False)[1:-1]
            got = m.json_string_escape(s)
            self.assertEqual(json.loads('"' + got + '"'), s, (s, got))
            self.assertEqual(got, ref, s)
            self.assertEqual(m.json_string_unescape(got), s)

    def test_json_unescape_surrogates_and_raw_quote(self):
        # valid surrogate pair combines into the astral code point
        self.assertEqual(m.json_string_unescape("\\uD83D\\uDE00"),
                         "\U0001F600")
        # lone surrogates and an unescaped raw quote are refused
        for bad in ("\\uD83D", "\\uDE00", "\\uD83D\\u0041",
                    "\\uD83Dx", 'raw"quote'):
            with self.assertRaises(ValueError, msg=bad):
                m.json_string_unescape(bad)

    def test_json_unescape_loads_oracle(self):
        rng = random.Random(83)
        pool = ("ab\"\\\n\t\x00\x1f\u00e9\u20ac"
                "\U0001F600\U0001F4A9\u4e2d")
        for _ in range(200):
            s = "".join(rng.choice(pool)
                        for _ in range(rng.randint(0, 10)))
            for ascii_only in (True, False):
                inner = json.dumps(s, ensure_ascii=ascii_only)[1:-1]
                # stdlib reference for the wrapped literal
                self.assertEqual(json.loads('"' + inner + '"'), s)
                self.assertEqual(m.json_string_unescape(inner), s,
                                 (s, ascii_only, inner))

    def test_matrix_chain_cost(self):
        self.assertEqual(m.matrix_chain_cost([10, 30, 5, 60]), 4500)
        self.assertEqual(m.matrix_chain_cost([5, 10]), 0)
        self.assertEqual(m.matrix_chain_cost([40, 20, 30, 10, 30]), 26000)
        with self.assertRaises(ValueError) as ctx:
            m.matrix_chain_cost([5])
        self.assertIn("too_few", str(ctx.exception))
        with self.assertRaises(ValueError):
            m.matrix_chain_cost([5, 0])

    def test_matrix_chain_bruteforce_oracle(self):
        def oracle(dims, i, j):
            if i == j:
                return 0
            return min(oracle(dims, i, k) + oracle(dims, k + 1, j)
                       + dims[i] * dims[k + 1] * dims[j + 1]
                       for k in range(i, j))

        rng = random.Random(7)
        for _ in range(40):
            n = rng.randint(2, 7)
            dims = [rng.randint(1, 20) for _ in range(n)]
            self.assertEqual(m.matrix_chain_cost(dims),
                             oracle(dims, 0, n - 2), dims)

    def test_knapsack_01_max(self):
        self.assertEqual(m.knapsack_01_max([2, 3, 4, 5], [3, 4, 5, 6], 5),
                         7)
        self.assertEqual(m.knapsack_01_max([], [], 10), 0)
        self.assertEqual(m.knapsack_01_max([1], [10], 0), 0)
        self.assertEqual(m.knapsack_01_max([0, 5], [7, 3], 5), 10)
        with self.assertRaises(ValueError):
            m.knapsack_01_max([1], [1, 2], 5)
        with self.assertRaises(ValueError):
            m.knapsack_01_max([-1], [1], 5)

    def test_knapsack_bruteforce_oracle(self):
        from itertools import combinations
        rng = random.Random(13)
        for _ in range(60):
            n = rng.randint(0, 10)
            ws = [rng.randint(0, 8) for _ in range(n)]
            vs = [rng.randint(0, 15) for _ in range(n)]
            cap = rng.randint(0, 15)
            best = 0
            for r in range(n + 1):
                for combo in combinations(range(n), r):
                    w = sum(ws[i] for i in combo)
                    if w <= cap:
                        best = max(best, sum(vs[i] for i in combo))
            self.assertEqual(m.knapsack_01_max(ws, vs, cap), best,
                             (ws, vs, cap))

    def test_rod_cut_max(self):
        self.assertEqual(m.rod_cut_max([1, 5, 8, 9, 10, 17, 17, 20]), 22)
        self.assertEqual(m.rod_cut_max([3]), 3)
        self.assertEqual(m.rod_cut_max([1, 1, 1, 1]), 4)
        with self.assertRaises(ValueError):
            m.rod_cut_max([])
        with self.assertRaises(ValueError):
            m.rod_cut_max([1, -2])

    def test_rod_cut_bruteforce_oracle(self):
        def oracle(prices, length):
            if length == 0:
                return 0
            return max(prices[cut - 1] + oracle(prices, length - cut)
                       for cut in range(1, length + 1))

        rng = random.Random(19)
        for _ in range(40):
            n = rng.randint(1, 9)
            prices = [rng.randint(0, 20) for _ in range(n)]
            self.assertEqual(m.rod_cut_max(prices),
                             oracle(prices, n), prices)

    def test_registry_knows_batch37(self):
        from app.modules.instinct_doc import p235_concepts_registry as reg
        own = [e for e in reg.ENTRIES if e["batch"] == 37]
        self.assertEqual(len(own), 10)
        names = [e["name"] for e in own]
        for name in ("adler32_sum", "crc16_ccitt_value",
                     "base32_encode_text", "base32_decode_text",
                     "json_number_check", "json_string_escape",
                     "json_string_unescape", "matrix_chain_cost",
                     "knapsack_01_max", "rod_cut_max"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
