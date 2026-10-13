"""P254 bounded record counter for dataset artifacts (standalone component).

Counts records in an operator-named format: "jsonl" (non-empty lines, each
valid JSON), "csv" (rows minus the header row) or "json" (top-level array
length). Any other format, malformed content, empty content or content over
the fixed byte cap is UNVERIFIED; nothing is guessed. NaN, Infinity and -Infinity constants are refused; other Python json leniency
(duplicate keys, huge ints) is not checked. Cap: each read asks for at
most the bytes left under MAX_BYTES + 1 and a longer reply is refused, so the
bytes accepted (returned) never exceed MAX_BYTES + 1 and an endless stream stops.
With short reads the summed request sizes can exceed that; only returned bytes
are bounded. Parser objects and list overhead are not bounded by this cap.
Byte equality is never a count.
A COUNT_MATCH says the counted records equal the declared number, not
authorship, licensing or scientific adequacy.
Not wired into bind_artifacts; integration is a separate decision.
"""
from __future__ import annotations

import csv
import io
import json

MAX_BYTES = 8_000_000
CHUNK = 65536
FORMATS = ("jsonl", "csv", "json")


def _result(status, reason, fmt, counted=None, nbytes=0):
    return {"status": status, "reason": reason, "format": fmt, "counted_records": counted,
            "bytes_read": nbytes, "byte_cap": MAX_BYTES, "authorship_verified": False}


def _read_bounded(stream):
    parts, total = [], 0
    while total <= MAX_BYTES:
        want = min(CHUNK, MAX_BYTES + 1 - total)
        chunk = stream.read(want)
        if type(chunk) is not bytes or len(chunk) > want:
            raise ValueError("stream must return bounded bytes")
        if not chunk:
            break
        parts.append(chunk)
        total += len(chunk)
    return b"".join(parts), total


def _no_constant(name):
    raise ValueError("non-standard JSON constant " + name)


def _loads(text):
    return json.loads(text, parse_constant=_no_constant)


def _count(data, fmt):
    text = data.decode("utf-8")
    if fmt == "jsonl":
        lines = text.split("\n")
        if lines and lines[-1].strip() == "":
            lines.pop()
        for line in lines:
            _loads(line)
        return len(lines)
    if fmt == "csv":
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
        if not rows or any(not row for row in rows):
            raise ValueError("csv needs a header and no blank rows")
        return len(rows) - 1
    value = _loads(text)
    if type(value) is not list:
        raise ValueError("json top level must be an array")
    return len(value)


def count_records(stream, fmt):
    """Count records from a binary stream; never raises on bad content."""
    if fmt not in FORMATS:
        return _result("UNVERIFIED", "unsupported format", fmt if isinstance(fmt, str) else None)
    try:
        data, total = _read_bounded(stream)
    except Exception as exc:
        return _result("UNVERIFIED", "read failed: " + type(exc).__name__, fmt)
    if total > MAX_BYTES:
        return _result("UNVERIFIED", "over byte cap", fmt, None, total)
    if not data.strip():
        return _result("UNVERIFIED", "empty content", fmt, None, total)
    try:
        counted = _count(data, fmt)
    except Exception as exc:
        return _result("UNVERIFIED", "malformed content: " + type(exc).__name__, fmt, None, total)
    return _result("COUNTED", "counted", fmt, counted, total)


def check_declared(stream, fmt, declared_records):
    """Compare the counted records with a declared integer count."""
    result = count_records(stream, fmt)
    result["declared_records"] = declared_records
    if result["status"] != "COUNTED":
        return result
    if type(declared_records) is not int or declared_records < 0:
        result.update(status="UNVERIFIED", reason="declared count must be a non-negative int")
    elif result["counted_records"] == declared_records:
        result.update(status="COUNT_MATCH", reason="counted records equal declared count")
    else:
        result.update(status="COUNT_MISMATCH", reason="counted records differ from declared count")
    return result


def check_artifact(root, relative_path, fmt, declared_records):
    """Open a bounded local artifact through safe_file and compare its count."""
    from pathlib import Path
    from .repo_evidence import safe_file
    try:
        path = safe_file(Path(root).resolve(), relative_path)
        with open(path, "rb") as handle:
            return check_declared(handle, fmt, declared_records)
    except Exception as exc:
        result = _result("UNVERIFIED", "artifact unavailable: " + type(exc).__name__, fmt if isinstance(fmt, str) else None)
        result["declared_records"] = declared_records
        return result
