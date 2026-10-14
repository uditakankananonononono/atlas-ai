"""P235 concepts batch 28 (271-280, dates/durations/words): red-first tests.
Calendar functions are cross-checked against stdlib datetime as an
independent oracle."""
from __future__ import annotations

import datetime
import unittest


class Batch28Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch28 as m
        self.m = m

    def test_is_valid_date(self):
        self.assertTrue(self.m.is_valid_date("2024-02-29"))
        self.assertFalse(self.m.is_valid_date("2026-02-29"))
        # leap-year predicate: century years need the 400-year rule
        self.assertFalse(self.m.is_valid_date("1900-02-29"))
        self.assertTrue(self.m.is_valid_date("2000-02-29"))
        self.assertFalse(self.m.is_valid_date("2100-02-29"))
        self.assertTrue(self.m.is_valid_date("2400-02-29"))
        self.assertTrue(self.m.is_valid_date("0001-01-01"))
        self.assertTrue(self.m.is_valid_date("9999-12-31"))
        for bad in ("2026-13-01", "2026-1-5", "2026-01-5", "0000-01-01",
                    "2026-00-10", "2026-04-31", "2026-01-05\n",
                    "2026-01-05 ", "26-01-05", ""):
            self.assertFalse(self.m.is_valid_date(bad), bad)

    def test_calendar_functions_against_datetime(self):
        # every day of 2019-2031 cross-checked against stdlib datetime
        day = datetime.date(2019, 1, 1)
        end = datetime.date(2031, 12, 31)
        while day <= end:
            text = day.isoformat()
            self.assertTrue(self.m.is_valid_date(text), text)
            self.assertEqual(self.m.day_of_year(text), day.timetuple().tm_yday,
                             text)
            iso = day.isocalendar()
            self.assertEqual(self.m.iso_week_number(text),
                             (iso[0], iso[1]), text)
            day += datetime.timedelta(days=1)
        for year in range(1990, 2041):
            jan4 = datetime.date(year, 1, 4)
            weeks = datetime.date(year, 12, 28).isocalendar()[1]
            self.assertEqual(self.m.iso_year_weeks(year), weeks, year)

    def test_iso_week_number_spot(self):
        self.assertEqual(self.m.iso_week_number("2025-12-29"), (2026, 1))
        self.assertEqual(self.m.iso_week_number("2026-01-05"), (2026, 2))
        self.assertEqual(self.m.iso_week_number("2021-01-01"), (2020, 53))
        # ISO year boundaries: Dec 28 to Jan 4 straddle the year edge;
        # 2020 and 2026 are 53-week years (also covered by the 2019-2031
        # daily cross-check against stdlib datetime)
        self.assertEqual(self.m.iso_week_number("2019-12-30"), (2020, 1))
        self.assertEqual(self.m.iso_week_number("2020-12-28"), (2020, 53))
        self.assertEqual(self.m.iso_week_number("2021-01-03"), (2020, 53))
        self.assertEqual(self.m.iso_week_number("2021-01-04"), (2021, 1))
        self.assertEqual(self.m.iso_week_number("2026-12-28"), (2026, 53))
        self.assertEqual(self.m.iso_week_number("2027-01-03"), (2026, 53))
        self.assertEqual(self.m.iso_week_number("2027-01-04"), (2027, 1))
        # helper shape guards with exact coded refusals
        with self.assertRaises(ValueError) as c:
            self.m.iso_week_number(123)
        self.assertEqual(str(c.exception),
                         "P235:iso_week_number:bad_type:text")
        with self.assertRaises(ValueError) as c:
            self.m.iso_week_number("2" * 10_001)
        self.assertEqual(str(c.exception),
                         "P235:iso_week_number:too_many:text")
        with self.assertRaises(ValueError) as c:
            self.m.iso_week_number("2026-1-05")
        self.assertEqual(str(c.exception),
                         "P235:iso_week_number:bad_format:text")
        with self.assertRaises(ValueError) as c:
            self.m.iso_week_number("2026-02-29")
        self.assertEqual(str(c.exception),
                         "P235:iso_week_number:bad_value:text")
        with self.assertRaises(ValueError) as c:
            self.m.day_of_year(True)
        self.assertEqual(str(c.exception),
                         "P235:day_of_year:bad_type:text")

    def test_iso_year_weeks_spot(self):
        self.assertEqual(self.m.iso_year_weeks(2026), 53)
        self.assertEqual(self.m.iso_year_weeks(2027), 52)
        self.assertEqual(self.m.iso_year_weeks(2020), 53)
        with self.assertRaises(ValueError):
            self.m.iso_year_weeks(0)

    def test_duration_parse_compact(self):
        self.assertEqual(self.m.duration_parse_compact("1h30m"), 5400)
        self.assertEqual(self.m.duration_parse_compact("2d"), 172800)
        self.assertEqual(self.m.duration_parse_compact("90s"), 90)
        self.assertEqual(self.m.duration_parse_compact("1d2h3m4s"), 93784)
        self.assertEqual(self.m.duration_parse_compact("0s"), 0)
        for bad in ("1h1h", "1m30h", "1x", "", "1h30", "-1h", "0.5h",
                    "1h 30m", "h"):
            with self.assertRaises(ValueError, msg=bad):
                self.m.duration_parse_compact(bad)
        # numeric domain matches the renderer cap of 1e9 seconds
        self.assertEqual(self.m.duration_parse_compact("11574d1h46m40s"),
                         10**9)
        with self.assertRaises(ValueError) as c:
            self.m.duration_parse_compact("11574d1h46m41s")
        self.assertEqual(str(c.exception),
                         "P235:duration_parse_compact:too_big:text")
        # per-unit digit bound before int(): 9 digits passes, 10 refuses
        # coded, and a 5,000-digit run cannot leak the library error
        self.assertEqual(self.m.duration_parse_compact("999999999s"),
                         999_999_999)
        for big in ("1000000000s", "9" * 5_000 + "s"):
            with self.assertRaises(ValueError, msg=big[:20]) as c:
                self.m.duration_parse_compact(big)
            self.assertEqual(str(c.exception),
                             "P235:duration_parse_compact:too_big:text")

    def test_duration_render_compact(self):
        self.assertEqual(self.m.duration_render_compact(5400), "1h30m")
        # value-0 unit output: zero renders as "0s" so the canonical
        # form always has exactly one unit and round-trips (pinned in
        # test_duration_roundtrip)
        self.assertEqual(self.m.duration_render_compact(0), "0s")
        self.assertEqual(self.m.duration_render_compact(93784), "1d2h3m4s")
        self.assertEqual(self.m.duration_render_compact(90), "1m30s")
        self.assertEqual(self.m.duration_render_compact(86400), "1d")
        # domain cap: 1e9 renders and round-trips; cap+1 refuses coded
        self.assertEqual(self.m.duration_render_compact(10**9),
                         "11574d1h46m40s")
        self.assertEqual(self.m.duration_parse_compact(
            self.m.duration_render_compact(10**9)), 10**9)
        with self.assertRaises(ValueError) as c:
            self.m.duration_render_compact(10**9 + 1)
        self.assertEqual(str(c.exception),
                         "P235:duration_render_compact:bad_value:seconds")
        with self.assertRaises(ValueError) as c:
            self.m.duration_render_compact(True)
        self.assertEqual(str(c.exception),
                         "P235:duration_render_compact:bad_type:seconds")
        with self.assertRaises(ValueError):
            self.m.duration_render_compact(-1)
        with self.assertRaises(ValueError):
            self.m.duration_render_compact(10**9 + 1)

    def test_duration_roundtrip(self):
        for seconds in (0, 1, 59, 61, 3600, 5400, 93784, 10**9):
            self.assertEqual(self.m.duration_parse_compact(
                self.m.duration_render_compact(seconds)), seconds)

    def test_int_to_english_words(self):
        self.assertEqual(self.m.int_to_english_words(0), "zero")
        self.assertEqual(self.m.int_to_english_words(5), "five")
        self.assertEqual(self.m.int_to_english_words(42), "forty-two")
        self.assertEqual(self.m.int_to_english_words(100), "one hundred")
        self.assertEqual(self.m.int_to_english_words(115),
                         "one hundred fifteen")
        self.assertEqual(self.m.int_to_english_words(1000), "one thousand")
        self.assertEqual(self.m.int_to_english_words(1234),
                         "one thousand two hundred thirty-four")
        self.assertEqual(self.m.int_to_english_words(999999),
                         "nine hundred ninety-nine thousand nine hundred "
                         "ninety-nine")
        with self.assertRaises(ValueError):
            self.m.int_to_english_words(-1)
        with self.assertRaises(ValueError):
            self.m.int_to_english_words(1_000_000)

    def test_weekday_name_en(self):
        self.assertEqual(self.m.weekday_name_en(0), "Monday")
        self.assertEqual(self.m.weekday_name_en(6), "Sunday")
        with self.assertRaises(ValueError):
            self.m.weekday_name_en(7)
        with self.assertRaises(ValueError):
            self.m.weekday_name_en(-1)

    def test_month_name_en(self):
        self.assertEqual(self.m.month_name_en(1), "January")
        self.assertEqual(self.m.month_name_en(12), "December")
        with self.assertRaises(ValueError):
            self.m.month_name_en(0)
        with self.assertRaises(ValueError):
            self.m.month_name_en(13)

    def test_quote_csv_field(self):
        self.assertEqual(self.m.quote_csv_field("a"), "a")
        self.assertEqual(self.m.quote_csv_field("a,b"), '"a,b"')
        self.assertEqual(self.m.quote_csv_field('a"b'), '"a""b"')
        self.assertEqual(self.m.quote_csv_field("a\nb"), '"a\nb"')
        # empty early-return: the empty field renders as the empty string;
        # an unquoted empty single-field row parses back to "" (pinned in
        # the roundtrip below), so quoting it would be a different row
        self.assertEqual(self.m.quote_csv_field(""), "")
        # roundtrip through the batch-15 parser
        from app.modules.instinct_doc import p235_concepts_batch15 as b15
        for field in ("plain", "a,b", 'q"q', "line\nbreak", "", "x"):
            rendered = self.m.quote_csv_field(field)
            self.assertEqual(b15.csv_row_split(rendered), [field], field)


if __name__ == "__main__":
    unittest.main()
