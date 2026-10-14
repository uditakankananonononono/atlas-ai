"""P235 concepts batch 28 (concepts 271-280, dates/durations/words) - ten
new small deterministic concepts. 271-280 of the doc's 1000 (anchor
P235|L184). Manual calendar arithmetic (no datetime in the module); the
tests cross-check against stdlib datetime as an independent oracle.
"""
from __future__ import annotations

import re

from .p235_concepts_batch1 import MAX_ITEMS, check_int, check_str, make_fail

MAX_DURATION_SECONDS = 10**9

_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _month_days(y, m):
    if m == 2 and _leap(y):
        return 29
    return _DAYS[m - 1]


def _to_days(y, m, d):
    """Days since 0001-01-01 (which was a Monday), zero-based."""
    days = 0
    for year in range(1, y):
        days += 366 if _leap(year) else 365
    for month in range(1, m):
        days += _month_days(y, month)
    return days + d - 1


def _parse(fail, text, name):
    check_str(fail, text, name)
    if len(text) > MAX_ITEMS:
        fail("too_many:" + name)
    if not text.isascii() or not _DATE.fullmatch(text):
        fail("bad_format:" + name)
    y = int(text[0:4])
    m = int(text[5:7])
    d = int(text[8:10])
    if y < 1 or m < 1 or m > 12 or d < 1 or d > _month_days(y, m):
        fail("bad_value:" + name)
    return (y, m, d)


def is_valid_date(text):
    """Strict yyyy-mm-dd shape and a real calendar day; False, never raises,
    for any string input."""
    fail = make_fail("is_valid_date")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS or not text.isascii():
        return False
    if not _DATE.fullmatch(text):
        return False
    y = int(text[0:4])
    m = int(text[5:7])
    d = int(text[8:10])
    return y >= 1 and 1 <= m <= 12 and 1 <= d <= _month_days(y, m)


def iso_week_number(text):
    """(iso_year, iso_week) tuple for a valid yyyy-mm-dd date."""
    fail = make_fail("iso_week_number")
    y, m, d = _parse(fail, text, "text")
    days = _to_days(y, m, d)
    dow = days % 7
    thursday = days + (3 - dow)
    if thursday < _to_days(y, 1, 1):
        iso_year = y - 1
    elif thursday >= _to_days(y + 1, 1, 1):
        iso_year = y + 1
    else:
        iso_year = y
    jan4 = _to_days(iso_year, 1, 4)
    jan4_thursday = jan4 + (3 - jan4 % 7)
    week = (thursday - jan4_thursday) // 7 + 1
    return (iso_year, week)


def day_of_year(text):
    fail = make_fail("day_of_year")
    y, m, d = _parse(fail, text, "text")
    total = d
    for month in range(1, m):
        total += _month_days(y, month)
    return total


def iso_year_weeks(year):
    """52 or 53: 53 when the year starts on a Thursday, or on a
    Wednesday in a leap year (ISO long years)."""
    fail = make_fail("iso_year_weeks")
    check_int(fail, year, "year")
    if year < 1 or year > 9_999:
        fail("bad_value:year")
    jan1_dow = _to_days(year, 1, 1) % 7
    if jan1_dow == 3 or (jan1_dow == 2 and _leap(year)):
        return 53
    return 52


_DURATION = re.compile(r"(?:[0-9]+d)?(?:[0-9]+h)?(?:[0-9]+m)?(?:[0-9]+s)?")


def duration_parse_compact(text):
    """Compact duration like 1d2h3m4s into seconds; units descending,
    each at most once, at least one component. Domain matches the
    renderer: totals over 1e9 seconds refuse, and each unit value is
    bounded to 9 digits before conversion."""
    fail = make_fail("duration_parse_compact")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    if not text or not text.isascii() or not _DURATION.fullmatch(text) \
            or not any(ch.isdigit() for ch in text):
        fail("bad_format:text")
    total = 0
    for value, unit in re.findall(r"([0-9]+)([dhms])", text):
        if len(value) > 9:
            fail("too_big:text")
        total += int(value) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
        if total > MAX_DURATION_SECONDS:
            fail("too_big:text")
    return total


def duration_render_compact(seconds):
    """Canonical compact duration: zero units omitted, 0 renders as 0s."""
    fail = make_fail("duration_render_compact")
    check_int(fail, seconds, "seconds")
    if seconds < 0 or seconds > MAX_DURATION_SECONDS:
        fail("bad_value:seconds")
    if seconds == 0:
        return "0s"
    out = []
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        value, seconds = divmod(seconds, size)
        if value:
            out.append("%d%s" % (value, unit))
    return "".join(out)


_ONES = ("zero one two three four five six seven eight nine ten eleven "
         "twelve thirteen fourteen fifteen sixteen seventeen eighteen "
         "nineteen").split(" ")
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety")


def _three(n):
    out = []
    if n >= 100:
        out.append(_ONES[n // 100])
        out.append("hundred")
        n %= 100
    if n >= 20:
        tens = _TENS[n // 10]
        out.append(tens + ("-" + _ONES[n % 10] if n % 10 else ""))
    elif n > 0:
        out.append(_ONES[n])
    return out


def int_to_english_words(n):
    """0..999,999 in English words, no and, hyphenated tens."""
    fail = make_fail("int_to_english_words")
    check_int(fail, n, "n")
    if n < 0 or n > 999_999:
        fail("bad_value:n")
    if n == 0:
        return "zero"
    out = []
    if n >= 1000:
        out += _three(n // 1000)
        out.append("thousand")
        n %= 1000
    out += _three(n)
    return " ".join(out)


_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


def weekday_name_en(weekday):
    """0 is Monday, 6 is Sunday (ISO order)."""
    fail = make_fail("weekday_name_en")
    check_int(fail, weekday, "weekday")
    if weekday < 0 or weekday > 6:
        fail("bad_value:weekday")
    return _WEEKDAYS[weekday]


def month_name_en(month):
    fail = make_fail("month_name_en")
    check_int(fail, month, "month")
    if month < 1 or month > 12:
        fail("bad_value:month")
    return _MONTHS[month - 1]


def quote_csv_field(text):
    """Render one CSV field: quote when it holds a comma, quote, or
    newline; double inner quotes. Empty stays empty (valid unquoted)."""
    fail = make_fail("quote_csv_field")
    check_str(fail, text, "text")
    if len(text) > MAX_ITEMS:
        fail("too_many:text")
    if text == "":
        return ""
    if any(ch in text for ch in '",\n'):
        return '"' + text.replace('"', '""') + '"'
    return text
