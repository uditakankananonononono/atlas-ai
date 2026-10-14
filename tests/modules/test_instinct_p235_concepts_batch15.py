"""P235 concepts batch 15 (141-150, strings/parsing): red-first tests."""
from __future__ import annotations

import unittest


class Batch15Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch15 as m
        self.m = m

    def test_csv_row_split(self):
        self.assertEqual(self.m.csv_row_split('a,"b,c",d'), ["a", "b,c", "d"])
        self.assertEqual(self.m.csv_row_split('a,"b""c"'), ["a", 'b"c'])
        self.assertEqual(self.m.csv_row_split(""), [""])
        self.assertEqual(self.m.csv_row_split("x,y"), ["x", "y"])
        with self.assertRaises(ValueError) as c:
            self.m.csv_row_split('a,"unterminated')
        self.assertEqual(str(c.exception), "P235:csv_row_split:bad_value:csv")
        with self.assertRaises(ValueError) as c2:
            self.m.csv_row_split("x" * 10_001)
        self.assertEqual(str(c2.exception), "P235:csv_row_split:too_many:text")

    def test_snake_to_camel(self):
        self.assertEqual(self.m.snake_to_camel("hello_world_x"), "helloWorldX")
        self.assertEqual(self.m.snake_to_camel("abc"), "abc")
        with self.assertRaises(ValueError) as c:
            self.m.snake_to_camel("_lead")
        self.assertEqual(str(c.exception), "P235:snake_to_camel:bad_value:text")
        with self.assertRaises(ValueError):
            self.m.snake_to_camel("trail_")
        with self.assertRaises(ValueError):
            self.m.snake_to_camel("double__under")
        with self.assertRaises(ValueError):
            self.m.snake_to_camel("")

    def test_initials_of(self):
        self.assertEqual(self.m.initials_of("John Ronald Reuel Tolkien"), "JRRT")
        self.assertEqual(self.m.initials_of("  ada   lovelace "), "AL")
        self.assertEqual(self.m.initials_of("Cher"), "C")
        with self.assertRaises(ValueError) as c:
            self.m.initials_of("   ")
        self.assertEqual(str(c.exception), "P235:initials_of:bad_value:text")

    def test_longest_word(self):
        self.assertEqual(self.m.longest_word("the quick brown fox"), "quick")
        self.assertEqual(self.m.longest_word("aa bb cc"), "aa")
        self.assertEqual(self.m.longest_word(""), "")
        self.assertEqual(self.m.longest_word("one"), "one")
        with self.assertRaises(ValueError):
            self.m.longest_word(42)

    def test_word_count(self):
        self.assertEqual(self.m.word_count("the quick brown fox"), 4)
        self.assertEqual(self.m.word_count(""), 0)
        self.assertEqual(self.m.word_count("   spaced   out  "), 2)
        with self.assertRaises(ValueError):
            self.m.word_count(None)

    def test_strip_html_tags(self):
        self.assertEqual(self.m.strip_html_tags("<p>Hello <b>world</b></p>"),
                         "Hello world")
        self.assertEqual(self.m.strip_html_tags("plain"), "plain")
        self.assertEqual(self.m.strip_html_tags("<br/>"), "")
        with self.assertRaises(ValueError) as c:
            self.m.strip_html_tags("<unterminated")
        self.assertEqual(str(c.exception), "P235:strip_html_tags:bad_value:html")

    def test_url_query_parse(self):
        self.assertEqual(self.m.url_query_parse("a=1&b=2"), {"a": "1", "b": "2"})
        self.assertEqual(self.m.url_query_parse("a="), {"a": ""})
        self.assertEqual(self.m.url_query_parse(""), {})
        with self.assertRaises(ValueError) as c:
            self.m.url_query_parse("a=1&a=2")
        self.assertEqual(str(c.exception),
                         "P235:url_query_parse:duplicate:key")
        with self.assertRaises(ValueError):
            self.m.url_query_parse("noequals")
        with self.assertRaises(ValueError):
            self.m.url_query_parse("=v")

    def test_base64_encode_text(self):
        self.assertEqual(self.m.base64_encode_text("hello"), "aGVsbG8=")
        self.assertEqual(self.m.base64_encode_text(""), "")
        self.assertEqual(self.m.base64_encode_text("f"), "Zg==")
        # byte cap keeps every encoder output decodable by the pair
        encoded = self.m.base64_encode_text("x" * 7_500)
        self.assertEqual(len(encoded), 10_000)
        self.assertEqual(self.m.base64_decode_text(encoded), "x" * 7_500)
        with self.assertRaises(ValueError) as c:
            self.m.base64_encode_text("x" * 7_501)
        self.assertEqual(str(c.exception),
                         "P235:base64_encode_text:too_many:bytes")
        with self.assertRaises(ValueError) as c2:
            self.m.base64_encode_text("\u20ac" * 2_501)
        self.assertEqual(str(c2.exception),
                         "P235:base64_encode_text:too_many:bytes")

    def test_base64_decode_text(self):
        self.assertEqual(self.m.base64_decode_text("aGVsbG8="), "hello")
        self.assertEqual(self.m.base64_decode_text(""), "")
        with self.assertRaises(ValueError) as c:
            self.m.base64_decode_text("!!!")
        self.assertEqual(str(c.exception), "P235:base64_decode_text:bad_value:b64")
        with self.assertRaises(ValueError):
            self.m.base64_decode_text("aGVsbG8")

    def test_morse_encode(self):
        self.assertEqual(self.m.morse_encode("SOS"), "... --- ...")
        self.assertEqual(self.m.morse_encode("sos"), "... --- ...")
        self.assertEqual(self.m.morse_encode("E T"), ". / -")
        with self.assertRaises(ValueError) as c:
            self.m.morse_encode("hello!")
        self.assertEqual(str(c.exception), "P235:morse_encode:bad_value:text")
        with self.assertRaises(ValueError):
            self.m.morse_encode("")

    def test_csv_row_split_quote_state_edges(self):
        # escaped quote inside a quoted field
        self.assertEqual(self.m.csv_row_split('"a""b",c'), ["a\"b", "c"])
        # comma inside quotes is data
        self.assertEqual(self.m.csv_row_split('"a,b",c'), ["a,b", "c"])
        # empty quoted field
        self.assertEqual(self.m.csv_row_split('""'), [""])
        # trailing escaped quote then close
        self.assertEqual(self.m.csv_row_split('"a"""'), ["a\""])
        # open, escaped quote, close, then comma: field is a single quote
        self.assertEqual(self.m.csv_row_split('"""",x'), ['"', "x"])
        # three quotes: escaped quote inside quotes, comma becomes quoted
        # data and the field is unterminated - refuses
        with self.assertRaises(ValueError):
            self.m.csv_row_split('""",x')
        # newline inside quotes is preserved as data
        self.assertEqual(self.m.csv_row_split('"a\nb",c'), ["a\nb", "c"])
        # content after a closing quote without a comma refuses
        with self.assertRaises(ValueError):
            self.m.csv_row_split('"a"b')
        # quote mid-field refuses
        with self.assertRaises(ValueError):
            self.m.csv_row_split('a"b')
        # space after a closing quote refuses
        with self.assertRaises(ValueError):
            self.m.csv_row_split('"a" ,"b"')
        # unterminated quote refuses
        with self.assertRaises(ValueError):
            self.m.csv_row_split('"abc')
        # odd run of quotes leaves the machine in-quotes and refuses
        with self.assertRaises(ValueError):
            self.m.csv_row_split('"a""""')

    def test_base64_boundary_alignment(self):
        # 7,500 utf-8 bytes encodes to exactly 10,000 base64 chars,
        # which the decoder cap accepts: the pair is inverse at the edge.
        encoded = self.m.base64_encode_text("a" * 7_500)
        self.assertEqual(len(encoded), 10_000)
        self.assertEqual(self.m.base64_decode_text(encoded), "a" * 7_500)
        # 7,501 bytes refuses at encode time
        with self.assertRaises(ValueError) as c:
            self.m.base64_encode_text("a" * 7_501)
        self.assertEqual(str(c.exception),
                         "P235:base64_encode_text:too_many:bytes")
        # multibyte text at the same byte edge: 3,750 * 2-byte chars
        encoded = self.m.base64_encode_text("\u00e9" * 3_750)
        self.assertEqual(self.m.base64_decode_text(encoded),
                         "\u00e9" * 3_750)
        with self.assertRaises(ValueError):
            self.m.base64_encode_text("\u00e9" * 3_751)
        # decoder refuses an over-cap base64 string
        with self.assertRaises(ValueError) as c:
            self.m.base64_decode_text("YQ" * 5_000 + "YQ==")
        self.assertEqual(str(c.exception),
                         "P235:base64_decode_text:too_many:text")
        # decoder refuses malformed input and non-utf-8 payloads
        for bad in ("a", "a===", "Y Q==", "/w==", "\u00e9"):
            with self.assertRaises(ValueError, msg=bad):
                self.m.base64_decode_text(bad)

    def test_csv_row_split_exhaustive_small_grammar(self):
        # Independent oracle: a declarative grammar (regex) for the same
        # row format, checked against the module's state machine on every
        # string over {"a", quote, comma} up to length 5 (364 strings).
        import itertools
        import re
        field = r'(?:[^",]*|"(?:[^"]|"")*")'
        row_re = re.compile(field + r"(?:," + field + r")*\Z")
        scan_re = re.compile(r'"((?:[^"]|"")*)"|([^",]*)')

        def oracle(text):
            if not row_re.fullmatch(text):
                return None
            out = []
            pos = 0
            while True:
                match = scan_re.match(text, pos)
                if match is None:
                    return "ORACLE-BUG"
                if match.group(1) is not None:
                    out.append(match.group(1).replace('""', '"'))
                else:
                    out.append(match.group(2))
                pos = match.end()
                if pos == len(text):
                    return out
                if text[pos] != ",":
                    return "ORACLE-BUG"
                pos += 1
                if pos == len(text):
                    out.append("")
                    return out

        alphabet = ("a", '"', ",")
        checked = 0
        for length in range(0, 6):
            for chars in itertools.product(alphabet, repeat=length):
                text = "".join(chars)
                expected = oracle(text)
                if expected is None:
                    with self.assertRaises(ValueError, msg=repr(text)):
                        self.m.csv_row_split(text)
                else:
                    self.assertEqual(self.m.csv_row_split(text), expected,
                                     repr(text))
                checked += 1
        self.assertEqual(checked, 364)

    def test_snake_to_camel_guards(self):
        # empty text refuses (guard before split)
        with self.assertRaises(ValueError) as c:
            self.m.snake_to_camel("")
        self.assertEqual(str(c.exception),
                         "P235:snake_to_camel:bad_value:text")
        # any empty segment refuses: leading, trailing, doubled underscore
        for bad in ("_", "a_", "_a", "a__b", "__"):
            with self.assertRaises(ValueError, msg=bad):
                self.m.snake_to_camel(bad)
        self.assertEqual(self.m.snake_to_camel("abc"), "abc")
        self.assertEqual(self.m.snake_to_camel("a_b_c"), "aBC")
        self.assertEqual(self.m.snake_to_camel("a1_b2"), "a1B2")

    def test_url_query_parse_guards(self):
        self.assertEqual(self.m.url_query_parse(""), {})
        self.assertEqual(self.m.url_query_parse("a=b"), {"a": "b"})
        # values may contain "="; only the first splits
        self.assertEqual(self.m.url_query_parse("a=b=c"), {"a": "b=c"})
        # empty value is fine
        self.assertEqual(self.m.url_query_parse("a="), {"a": ""})
        # missing "=", empty key, duplicate key refuse
        for bad in ("abc", "=v", "a=1&a=2", "a=1&=2"):
            with self.assertRaises(ValueError, msg=bad):
                self.m.url_query_parse(bad)
        # literal keys and values: no percent/plus decoding
        self.assertEqual(self.m.url_query_parse("a%20b=c+d"),
                         {"a%20b": "c+d"})
        # the 10,000-pair guard cannot fire first: the 10,000-char text
        # cap binds earlier (a pair needs at least "k=&"), so an over-cap
        # query refuses with the text cap code
        with self.assertRaises(ValueError) as c:
            self.m.url_query_parse("&".join("k%d=v" % i
                                            for i in range(2_000)))
        self.assertEqual(str(c.exception),
                         "P235:url_query_parse:too_many:text")
        # 1,000 short pairs stay well under both caps and parse
        many = "&".join("k%d=v" % i for i in range(1_000))
        result = self.m.url_query_parse(many)
        self.assertEqual(len(result), 1_000)
        self.assertEqual(result["k999"], "v")


if __name__ == "__main__":
    unittest.main()
