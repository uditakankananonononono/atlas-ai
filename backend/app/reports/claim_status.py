"""Claim-status check for reports (instinct-doc unit P65|L55).

The rule this module checks: every claim in a report must carry an
explicit status label - by default VERIFIED or UNVERIFIED - and the check
fails when a claim is unmarked or carries conflicting labels.

Claim grammar (the complete, documented claim surface; anything else is
prose, not a claim):

1. Table claims: every body row of a markdown table whose header contains a
   "Label" or "Status" column (case-insensitive). The claim text is the first
   cell; the status is the label cell, normalized with strip().upper(). The
   header and the |---| separator row are not claims.
2. Marker claims: lines beginning with "CLAIM:" (case-insensitive; an
   optional bullet or numbered-list prefix allowed) whose body carries a
   bracketed [LABEL] marker. One recognized label: marked. No recognized
   label: unmarked. Two or more DIFFERENT recognized labels: conflicting.

Fenced code blocks (``` or ~~~) are skipped entirely. Label matching is
case-insensitive after upper() normalization; the accepted label set is a
parameter, defaulting to {"VERIFIED", "UNVERIFIED"}.

CLI: python -m app.reports.claim_status [--labels A,B] PATH...
Exit codes: 0 = every claim marked; 1 = unmarked or conflicting claims
(findings printed as path:line); 2 = vacuous run (zero claims found) or an
input could not be read. A check that finds nothing proves nothing, so zero
claims never exits 0.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_LABELS = frozenset({"VERIFIED", "UNVERIFIED"})

_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*CLAIM\s*:\s*(?P<body>.*)$", re.IGNORECASE)
_BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")
_LABEL_COLUMNS = frozenset({"label", "status"})


@dataclass(frozen=True)
class Claim:
    """One claim found in a report. status is the normalized label, or None
    when the claim is unmarked or conflicting (see check_text for both)."""

    line: int  # 1-based line number in the source document
    text: str
    status: str | None
    source: str  # "table" | "marker"


def _normalize_labels(labels: Iterable[str]) -> frozenset[str]:
    normalized = frozenset(str(label).strip().upper() for label in labels if str(label).strip())
    if not normalized:
        raise ValueError("at least one accepted label is required")
    return normalized


def _split_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _analyze(text: str, labels: frozenset[str]) -> list[dict]:
    """Parse the document and grade every claim. Internal; the public API is
    extract_claims / check_text."""
    entries: list[dict] = []
    in_fence = False
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        line_no = index + 1
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            index += 1
            continue
        if in_fence:
            index += 1
            continue
        if _TABLE_ROW_RE.match(line):
            run: list[tuple[int, str]] = []
            while index < len(lines) and _TABLE_ROW_RE.match(lines[index]) and not _FENCE_RE.match(lines[index]):
                run.append((index + 1, lines[index]))
                index += 1
            entries.extend(_analyze_table_run(run, labels))
            continue
        marker = _MARKER_RE.match(line)
        if marker:
            entries.append(_analyze_marker(line_no, marker.group("body"), labels))
        index += 1
    return entries


def _analyze_table_run(run: list[tuple[int, str]], labels: frozenset[str]) -> list[dict]:
    entries: list[dict] = []
    if len(run) < 3:  # header + separator + at least one body row
        return entries
    header_cells = _split_cells(run[0][1])
    label_index = next(
        (i for i, cell in enumerate(header_cells) if cell.strip().lower() in _LABEL_COLUMNS), None
    )
    if label_index is None:
        return entries  # not a claim table
    separator_cells = _split_cells(run[1][1])
    if not separator_cells or not all(_SEPARATOR_CELL_RE.match(cell) for cell in separator_cells):
        return entries  # no separator row: not a markdown table
    for line_no, row in run[2:]:
        cells = _split_cells(row)
        claim_text = cells[0].strip() if cells else ""
        entry = {"line": line_no, "text": claim_text, "status": None, "source": "table", "problem": None, "detail": None}
        if label_index >= len(cells):
            entry["problem"] = "unmarked"
            entry["detail"] = "missing label cell in row"
        else:
            token = cells[label_index].strip()
            if not token:
                entry["problem"] = "unmarked"
                entry["detail"] = "empty label cell"
            elif token.upper() in labels:
                entry["status"] = token.upper()
            else:
                entry["problem"] = "unmarked"
                entry["detail"] = f"label {token!r} is not in the accepted labels {sorted(labels)}"
        entries.append(entry)
    return entries


def _analyze_marker(line_no: int, body: str, labels: frozenset[str]) -> dict:
    tokens = [token.strip().upper() for token in _BRACKET_RE.findall(body)]
    recognized = [token for token in tokens if token in labels]
    entry = {"line": line_no, "text": body.strip(), "status": None, "source": "marker", "problem": None, "detail": None}
    distinct = set(recognized)
    if len(distinct) > 1:
        entry["problem"] = "conflicting"
        entry["detail"] = sorted(distinct)
    elif len(distinct) == 1:
        entry["status"] = recognized[0]
    else:
        entry["problem"] = "unmarked"
        entry["detail"] = (
            f"no accepted label in markers {tokens}" if tokens else "no [LABEL] marker on the CLAIM line"
        )
    return entry


def extract_claims(text: str, labels: Iterable[str] = DEFAULT_LABELS) -> list[Claim]:
    """Every claim in the document, marked or not (status None = unmarked/conflicting)."""
    accepted = _normalize_labels(labels)
    return [
        Claim(line=e["line"], text=e["text"], status=e["status"], source=e["source"])
        for e in _analyze(text, accepted)
    ]


def check_text(text: str, labels: Iterable[str] = DEFAULT_LABELS) -> dict:
    """Grade one document. ok is True only when every claim carries exactly one
    accepted label: no unmarked claims, no conflicting labels."""
    accepted = _normalize_labels(labels)
    entries = _analyze(text, accepted)
    unmarked = [
        {"line": e["line"], "text": e["text"], "reason": e["detail"]}
        for e in entries
        if e["problem"] == "unmarked"
    ]
    conflicting = [
        {"line": e["line"], "text": e["text"], "tokens": e["detail"]}
        for e in entries
        if e["problem"] == "conflicting"
    ]
    return {
        "claims": [
            {"line": e["line"], "text": e["text"], "status": e["status"], "source": e["source"]}
            for e in entries
        ],
        "claims_total": len(entries),
        "marked": sum(1 for e in entries if e["status"] is not None),
        "unmarked": unmarked,
        "conflicting": conflicting,
        "ok": not unmarked and not conflicting,
    }


def check_file(path: str | Path, labels: Iterable[str] = DEFAULT_LABELS) -> dict:
    result = check_text(Path(path).read_text(encoding="utf-8"), labels=labels)
    result["path"] = str(path)
    return result


def check_paths(paths: Sequence[str | Path], labels: Iterable[str] = DEFAULT_LABELS) -> dict:
    files = [check_file(path, labels=labels) for path in paths]
    return {
        "files": files,
        "files_total": len(files),
        "claims_total": sum(f["claims_total"] for f in files),
        "files_with_zero_claims": [f["path"] for f in files if f["claims_total"] == 0],
        "ok": all(f["ok"] for f in files),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="claim_status",
        description="Fail when any claim in a report lacks an explicit status label.",
    )
    parser.add_argument("paths", nargs="+", help="report files to check")
    parser.add_argument(
        "--labels",
        default=",".join(sorted(DEFAULT_LABELS)),
        help="comma-separated accepted labels (default: UNVERIFIED,VERIFIED); matched case-insensitively",
    )
    args = parser.parse_args(argv)
    labels = _normalize_labels(args.labels.split(","))
    files = []
    for raw_path in args.paths:
        try:
            files.append(check_file(raw_path, labels=labels))
        except OSError as exc:
            print(f"{raw_path}: cannot read: {exc}", file=sys.stderr)
            return 2
    total = sum(f["claims_total"] for f in files)
    if total == 0:
        print("no claims found in any input; a vacuous check proves nothing", file=sys.stderr)
        return 2
    bad = False
    for result in files:
        for item in result["unmarked"]:
            print(f"{result['path']}:{item['line']}: UNMARKED: {item['reason']}: {item['text']}")
            bad = True
        for item in result["conflicting"]:
            print(f"{result['path']}:{item['line']}: CONFLICTING labels {item['tokens']}: {item['text']}")
            bad = True
    if bad:
        return 1
    print(f"{total} claims, all marked with accepted labels {sorted(labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
