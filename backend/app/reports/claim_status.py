"""Claim-status check for reports (instinct-doc unit P65|L55).

The rule this module checks: every claim in a report must carry an
explicit status label - by default VERIFIED or UNVERIFIED - and the check
fails when a claim is unmarked, carries conflicting labels, or carries a
label that is ambiguous at the structure level.

Claim grammar (the complete, documented claim surface; anything else is
prose, not a claim):

1. Table claims: every body row of a markdown table whose header contains
   EXACTLY ONE "Label" or "Status" column (case-insensitive). The claim
   text is the first cell; the status is the label cell, normalized with
   strip().upper(). The header and the |---| separator row are not claims.
   A header naming two or more label columns makes every body row a
   structural-ambiguous finding (the columns could contradict silently).
   A pipe-run of one or two lines that carries a label header is a
   truncated claim table: a structural-ambiguous finding, never silently
   ignored and never an IndexError. A pipe-run of three or more lines
   without a valid separator row is not a table at all.
2. Marker claims: lines beginning with "CLAIM:" (case-insensitive; an
   optional bullet or numbered-list prefix allowed) whose body carries a
   bracketed [LABEL] marker. Exactly one recognized label and no
   unrecognized bracketed token: marked. Two or more DIFFERENT recognized
   labels: conflicting. One recognized label plus any unrecognized
   bracketed token: structural-ambiguous (the unrecognized token could be
   a misspelled label). No recognized token: unmarked.

Fenced code blocks are skipped entirely, with CommonMark fence pairing: an
opening fence is a run of three or more backticks or tildes (an info string
is allowed on the opener); the fence closes only on a line whose run uses
the SAME delimiter character and is at least as long as the opener. A
mismatched or shorter run does not close the fence.

Label matching is case-insensitive after upper() normalization; the
accepted label set is a parameter, defaulting to {"VERIFIED", "UNVERIFIED"}.

Vacuity: a document with zero claims is not ok - a check that finds nothing
proves nothing. check_text reports "vacuous": true and ok false; the CLI
exits 2 when no input produced any claim and treats a claim-free file in a
mixed run as a failing finding.

CLI: python -m app.reports.claim_status [--labels A,B] PATH...
Exit codes: 0 = every claim marked; 1 = unmarked, conflicting,
structural-ambiguous, or per-file vacuous findings (printed as path:line);
2 = zero claims found across all inputs or an input could not be read.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_LABELS = frozenset({"VERIFIED", "UNVERIFIED"})

_FENCE_OPEN_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*CLAIM\s*:\s*(?P<body>.*)$", re.IGNORECASE)
_BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")
_LABEL_COLUMNS = frozenset({"label", "status"})


def _fence_close_re(char: str, length: int) -> "re.Pattern[str]":
    """A closing fence: same delimiter char, run at least as long as the
    opener, nothing else on the line."""
    return re.compile(r"^\s*" + re.escape(char) + "{" + str(length) + ",}\\s*$")


@dataclass(frozen=True)
class Claim:
    """One claim found in a report. status is the normalized label, or None
    when the claim is unmarked, conflicting, or structural-ambiguous (see
    check_text for all three)."""

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


def _analyze(text: str, labels: frozenset[str]) -> tuple[list[dict], list[dict]]:
    """Parse the document and grade every claim. Internal; the public API is
    extract_claims / check_text. Returns (claim entries, structural findings
    that are not claims). The scan is a single for-loop over the lines, so
    termination is structural: every line is visited exactly once."""
    entries: list[dict] = []
    structural: list[dict] = []
    table_run: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None  # (delimiter char, opener run length)

    def flush_run() -> None:
        if table_run:
            entries.extend(_analyze_table_run(table_run, labels, structural))
            table_run.clear()

    for index, line in enumerate(text.splitlines()):
        line_no = index + 1
        if fence is not None:
            if _fence_close_re(fence[0], fence[1]).match(line):
                fence = None
            continue
        opener = _FENCE_OPEN_RE.match(line)
        if opener:
            flush_run()
            run = opener.group(1)
            fence = (run[0], len(run))
            continue
        if _TABLE_ROW_RE.match(line):
            table_run.append((line_no, line))
            continue
        flush_run()
        marker = _MARKER_RE.match(line)
        if marker:
            entries.append(_analyze_marker(line_no, marker.group("body"), labels))
    flush_run()
    return entries, structural


def _analyze_table_run(
    run: list[tuple[int, str]], labels: frozenset[str], structural: list[dict]
) -> list[dict]:
    entries: list[dict] = []
    header_cells = _split_cells(run[0][1])
    label_hits = [i for i, cell in enumerate(header_cells) if cell.strip().lower() in _LABEL_COLUMNS]
    if not label_hits:
        return entries  # not a claim table
    if len(run) < 3:  # header (+ maybe separator) but no body row
        structural.append(
            {
                "line": run[0][0],
                "text": run[0][1].strip(),
                "reason": (
                    "truncated claim table: label header present but no body rows "
                    f"({len(run)} line(s) in run)"
                ),
            }
        )
        return entries
    separator_cells = _split_cells(run[1][1])
    if not separator_cells or not all(_SEPARATOR_CELL_RE.match(cell) for cell in separator_cells):
        return entries  # no separator row: not a markdown table
    if len(label_hits) > 1:
        for line_no, row in run[2:]:
            cells = _split_cells(row)
            entries.append(
                {
                    "line": line_no,
                    "text": cells[0].strip() if cells else "",
                    "status": None,
                    "source": "table",
                    "problem": "structural-ambiguous",
                    "detail": (
                        f"ambiguous header: {len(label_hits)} label columns; "
                        "exactly one Label/Status column is required"
                    ),
                }
            )
        return entries
    label_index = label_hits[0]
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
    tokens = [token.strip().upper() for token in _BRACKET_RE.findall(body) if token.strip()]
    recognized = [token for token in tokens if token in labels]
    unrecognized = [token for token in tokens if token not in labels]
    entry = {"line": line_no, "text": body.strip(), "status": None, "source": "marker", "problem": None, "detail": None}
    distinct = set(recognized)
    if len(distinct) > 1:
        entry["problem"] = "conflicting"
        entry["detail"] = sorted(distinct)
    elif len(distinct) == 1 and not unrecognized:
        entry["status"] = recognized[0]
    elif len(distinct) == 1 and unrecognized:
        entry["problem"] = "structural-ambiguous"
        entry["detail"] = (
            f"unrecognized marker token(s) {sorted(set(unrecognized))} present "
            f"alongside recognized label {sorted(distinct)[0]!r}"
        )
    elif tokens:
        entry["problem"] = "unmarked"
        entry["detail"] = f"no recognized token present in markers {tokens}"
    else:
        entry["problem"] = "unmarked"
        entry["detail"] = "no [LABEL] marker on the CLAIM line"
    return entry


def extract_claims(text: str, labels: Iterable[str] = DEFAULT_LABELS) -> list[Claim]:
    """Every claim in the document, marked or not (status None =
    unmarked/conflicting/structural-ambiguous)."""
    accepted = _normalize_labels(labels)
    entries, _structural = _analyze(text, accepted)
    return [
        Claim(line=e["line"], text=e["text"], status=e["status"], source=e["source"])
        for e in entries
    ]


def check_text(text: str, labels: Iterable[str] = DEFAULT_LABELS) -> dict:
    """Grade one document. ok is True only when at least one claim was found
    and every claim carries exactly one accepted label: no unmarked claims,
    no conflicting labels, no structural-ambiguous findings. A zero-claim
    document is vacuous, not accepted."""
    accepted = _normalize_labels(labels)
    entries, structural = _analyze(text, accepted)
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
    structural_ambiguous = structural + [
        {"line": e["line"], "text": e["text"], "reason": e["detail"]}
        for e in entries
        if e["problem"] == "structural-ambiguous"
    ]
    structural_ambiguous.sort(key=lambda item: item["line"])
    vacuous = len(entries) == 0
    return {
        "claims": [
            {"line": e["line"], "text": e["text"], "status": e["status"], "source": e["source"]}
            for e in entries
        ],
        "claims_total": len(entries),
        "marked": sum(1 for e in entries if e["status"] is not None),
        "unmarked": unmarked,
        "conflicting": conflicting,
        "structural_ambiguous": structural_ambiguous,
        "vacuous": vacuous,
        "ok": not vacuous and not unmarked and not conflicting and not structural_ambiguous,
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
        if result["claims_total"] == 0:
            print(f"{result['path']}: VACUOUS: no claims found in this file")
            bad = True
        for item in result["unmarked"]:
            print(f"{result['path']}:{item['line']}: UNMARKED: {item['reason']}: {item['text']}")
            bad = True
        for item in result["conflicting"]:
            print(f"{result['path']}:{item['line']}: CONFLICTING labels {item['tokens']}: {item['text']}")
            bad = True
        for item in result["structural_ambiguous"]:
            print(f"{result['path']}:{item['line']}: STRUCTURAL-AMBIGUOUS: {item['reason']}: {item['text']}")
            bad = True
    if bad:
        return 1
    print(f"{total} claims, all marked with accepted labels {sorted(labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
