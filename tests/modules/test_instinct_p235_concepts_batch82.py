"""Tests for P235 concepts batch 82 (doc 811-820)."""
import quopri
import random
import unittest
import urllib.parse

from app.modules.instinct_doc import p235_concepts_batch82 as m
from app.modules.instinct_doc import p235_concepts_registry as reg


class TestIbanCheck(unittest.TestCase):
    def test_canonical(self):
        self.assertTrue(m.iban_check("GB29NWBK60161331926819"))
        self.assertTrue(m.iban_check("DE89370400440532013000"))
        self.assertTrue(m.iban_check("FR1420041010050500013M02606"))
        self.assertFalse(m.iban_check("GB29NWBK60161331926818"))
        self.assertFalse(m.iban_check("DE89370400440532013001"))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.iban_check("")
        with self.assertRaises(ValueError):
            m.iban_check("GB29NWBK60161")
        with self.assertRaises(ValueError):
            m.iban_check("GB29 NWBK 6016 1331 9268 19")
        with self.assertRaises(ValueError):
            m.iban_check("gb29NWBK60161331926819")
        with self.assertRaises(ValueError):
            m.iban_check("G129NWBK60161331926819")
        with self.assertRaises(ValueError):
            m.iban_check("GB2ANWBK60161331926819")
        with self.assertRaises(ValueError):
            m.iban_check(123)

    def test_oracle_chunked_mod97(self):
        def oracle(code):
            rearranged = code[4:] + code[:4]
            numeric = ""
            for c in rearranged:
                numeric += c if c.isdigit() else str(ord(c) - 55)
            remainder = 0
            for i in range(0, len(numeric), 9):
                chunk = str(remainder) + numeric[i:i + 9]
                remainder = int(chunk) % 97
            return remainder == 1
        rng = random.Random(8201)
        for _ in range(200):
            body = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
                           for _ in range(rng.randint(11, 30)))
            country = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + \
                rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            base = country + "00" + body
            rearranged = body + country + "00"
            numeric = ""
            for c in rearranged:
                numeric += c if c.isdigit() else str(ord(c) - 55)
            check = 98 - int(numeric) % 97
            code = "%s%02d%s" % (country, check, body)
            self.assertTrue(m.iban_check(code))
            self.assertTrue(oracle(code))
            self.assertEqual(m.iban_check(base), oracle(base))


class TestPercentCodec(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.percent_encode("hello world/é"),
                         "hello%20world%2F%C3%A9")
        self.assertEqual(m.percent_decode("hello%20world%2F%C3%A9"),
                         "hello world/é")
        self.assertEqual(m.percent_encode("abc-._~"), "abc-._~")
        self.assertEqual(m.percent_decode("%61%62%63"), "abc")

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.percent_encode("")
        with self.assertRaises(ValueError):
            m.percent_decode("")
        with self.assertRaises(ValueError):
            m.percent_decode("abc%")
        with self.assertRaises(ValueError):
            m.percent_decode("abc%2")
        with self.assertRaises(ValueError):
            m.percent_decode("abc%GG")
        with self.assertRaises(ValueError):
            m.percent_decode("%C0%AF")
        with self.assertRaises(ValueError):
            m.percent_decode("café")
        with self.assertRaises(ValueError):
            m.percent_encode(["a"])

    def test_oracle_stdlib(self):
        rng = random.Random(8202)
        alphabet = "abcXYZ019 -._~/?#+&=é€中"
        for _ in range(300):
            text = "".join(rng.choice(alphabet)
                           for _ in range(rng.randint(1, 30)))
            self.assertEqual(m.percent_encode(text),
                             urllib.parse.quote(text, safe="-._~"))
            self.assertEqual(m.percent_decode(m.percent_encode(text)),
                             text)


class TestQuotedPrintable(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.quoted_printable_encode("a=b c "), "a=3Db c=20")
        self.assertEqual(m.quoted_printable_decode("a=3Db c=20"), "a=b c ")
        self.assertEqual(m.quoted_printable_encode("d\te\t"), "d\te=09")
        self.assertEqual(m.quoted_printable_encode("d\te\tf"), "d\te\tf")
        self.assertEqual(m.quoted_printable_decode("ab=\ncd"), "abcd")
        self.assertEqual(m.quoted_printable_decode("ab=\r\ncd"), "abcd")

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.quoted_printable_encode("")
        with self.assertRaises(ValueError):
            m.quoted_printable_encode("café")
        with self.assertRaises(ValueError):
            m.quoted_printable_decode("a=b")
        with self.assertRaises(ValueError):
            m.quoted_printable_decode("a=3")
        with self.assertRaises(ValueError):
            m.quoted_printable_decode("a=3g")
        with self.assertRaises(ValueError):
            m.quoted_printable_decode("a=C3")
        with self.assertRaises(ValueError):
            m.quoted_printable_decode("a=0A")

    def test_oracle_stdlib_quopri(self):
        rng = random.Random(8203)
        alphabet = "abcdefg =!~\t"
        for _ in range(300):
            line_count = rng.randint(1, 3)
            lines = []
            for _ in range(line_count):
                line = "".join(rng.choice(alphabet)
                               for _ in range(rng.randint(1, 20)))
                # quopri leaves trailing space/tab at end-of-data
                # literal; our RFC-strict contract encodes them, so
                # keep generated lines free of trailing blanks.
                lines.append(line.rstrip(" \t") or "x")
            text = "\n".join(lines)
            self.assertEqual(m.quoted_printable_encode(text),
                             quopri.encodestring(
                                 text.encode("ascii")).decode("ascii"))
            self.assertEqual(
                quopri.decodestring(
                    m.quoted_printable_encode(text).encode("ascii")
                ).decode("ascii"), text)
            self.assertEqual(
                m.quoted_printable_decode(m.quoted_printable_encode(text)),
                text)


class TestHtmlEscape(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.html_escape_text('<a href="x">'),
                         "&lt;a href=&quot;x&quot;&gt;")
        self.assertEqual(m.html_escape_text("&it's"),
                         "&amp;it&#x27;s")
        self.assertEqual(m.html_unescape_text("&lt;a&gt;&amp;&#x41;&#66;"),
                         "<a>&AB")
        self.assertEqual(m.html_unescape_text("&#39;quote&#x27;"),
                         "'quote'")

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.html_escape_text("")
        with self.assertRaises(ValueError):
            m.html_escape_text("café")
        with self.assertRaises(ValueError):
            m.html_escape_text("a\x00b")
        with self.assertRaises(ValueError):
            m.html_unescape_text("&")
        with self.assertRaises(ValueError):
            m.html_unescape_text("&bogus;")
        with self.assertRaises(ValueError):
            m.html_unescape_text("&amp")
        with self.assertRaises(ValueError):
            m.html_unescape_text("&#x110000;")
        with self.assertRaises(ValueError):
            m.html_unescape_text("&#233;")
        with self.assertRaises(ValueError):
            m.html_unescape_text("&#xD800;")
        with self.assertRaises(ValueError):
            m.html_unescape_text("&#;")

    def test_oracle_stdlib_html(self):
        import html as stdlib_html
        rng = random.Random(8204)
        alphabet = "abc<>&\"' \t\n019"
        for _ in range(300):
            text = "".join(rng.choice(alphabet)
                           for _ in range(rng.randint(1, 30)))
            self.assertEqual(m.html_escape_text(text),
                             stdlib_html.escape(text, quote=True))
            self.assertEqual(
                stdlib_html.unescape(m.html_escape_text(text)), text)
            self.assertEqual(m.html_unescape_text(m.html_escape_text(text)),
                             text)


class TestUtf8Codec(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.utf8_encode_bytes("aé€"),
                         [97, 195, 169, 226, 130, 172])
        self.assertEqual(m.utf8_decode_bytes([97, 195, 169, 226, 130, 172]),
                         "aé€")
        self.assertEqual(m.utf8_decode_bytes([240, 159, 152, 128]),
                         "\U0001F600")

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.utf8_encode_bytes("")
        with self.assertRaises(ValueError):
            m.utf8_encode_bytes("\ud800")
        with self.assertRaises(ValueError):
            m.utf8_decode_bytes([])
        with self.assertRaises(ValueError):
            m.utf8_decode_bytes([0xC0, 0xAF])
        with self.assertRaises(ValueError):
            m.utf8_decode_bytes([0xED, 0xA0, 0x80])
        with self.assertRaises(ValueError):
            m.utf8_decode_bytes([0x80])
        with self.assertRaises(ValueError):
            m.utf8_decode_bytes([0xC3])
        with self.assertRaises(ValueError):
            m.utf8_decode_bytes([256])
        with self.assertRaises(ValueError):
            m.utf8_decode_bytes([-1])

    def test_oracle_stdlib_codecs(self):
        rng = random.Random(8205)
        for _ in range(300):
            text = "".join(chr(rng.randint(1, 0x2FFF))
                           for _ in range(rng.randint(1, 20)))
            if any("\ud800" <= c <= "\udfff" for c in text):
                continue
            self.assertEqual(m.utf8_encode_bytes(text),
                             list(text.encode("utf-8")))
            self.assertEqual(
                m.utf8_decode_bytes(m.utf8_encode_bytes(text)), text)
        for _ in range(500):
            data = [rng.randint(0, 255)
                    for _ in range(rng.randint(1, 8))]
            try:
                want = bytes(data).decode("utf-8", "strict")
            except UnicodeDecodeError:
                want = None
            try:
                got = m.utf8_decode_bytes(data)
            except ValueError:
                got = None
            self.assertEqual(got, want)


class TestLz77Encode(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(m.lz77_encode_naive("ababcbababaa"),
                         [[0, 0, "a"], [0, 0, "b"], [2, 2, "c"],
                          [4, 3, "a"], [2, 2, "a"]])
        self.assertEqual(m.lz77_encode_naive("aaaa"),
                         [[0, 0, "a"], [1, 3, ""]])
        self.assertEqual(m.lz77_encode_naive("abc"),
                         [[0, 0, "a"], [0, 0, "b"], [0, 0, "c"]])

    def test_refusals(self):
        with self.assertRaises(ValueError):
            m.lz77_encode_naive("")
        with self.assertRaises(ValueError):
            m.lz77_encode_naive("café")
        with self.assertRaises(ValueError):
            m.lz77_encode_naive(["abc"])
        with self.assertRaises(ValueError):
            m.lz77_encode_naive("a\nb")

    def test_oracle_roundtrip_decoder(self):
        def decode(triplets):
            out = []
            for offset, length, char in triplets:
                if offset == 0:
                    out.append(char)
                else:
                    start = len(out) - offset
                    for i in range(length):
                        out.append(out[start + i])
                    if char:
                        out.append(char)
            return "".join(out)
        rng = random.Random(8206)
        alphabet = "aabbc_"
        for _ in range(300):
            text = "".join(rng.choice(alphabet)
                           for _ in range(rng.randint(1, 60)))
            triplets = m.lz77_encode_naive(text)
            self.assertEqual(decode(triplets), text)
            for offset, length, _ in triplets:
                self.assertGreaterEqual(length, 0)
                if offset == 0:
                    self.assertEqual(length, 0)


class TestRegistryKnowsBatch82(unittest.TestCase):
    def test_registry_knows_batch82(self):
        names = {e["name"] for e in reg.ENTRIES}
        for name in ("iban_check", "percent_encode", "percent_decode",
                     "quoted_printable_encode", "quoted_printable_decode",
                     "html_escape_text", "html_unescape_text",
                     "utf8_encode_bytes", "utf8_decode_bytes",
                     "lz77_encode_naive"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
