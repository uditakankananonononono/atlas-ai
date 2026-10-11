"""P258|L205 - "Output: Research paper files".

Per-project registry of research paper artifacts. Pure stdlib, offline,
deterministic. It never opens, renders or inspects a file. The page count is a
CLAIM, marked UNVERIFIED unless the caller supplies an evidence_ref (recorded,
never resolved). The Times New Roman rule (P85|L73) is a flag SUPPLIED by the
caller (pass|fail|unchecked); it is never computed here.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

FLAGS = ("pass", "fail", "unchecked")
FIELDS = ("id", "project_id", "path", "page_count_claim", "page_evidence_ref", "font_rule_flag")
REQUIRED = ("id", "project_id", "path")
TEXT_FIELDS = ("id", "project_id", "path", "page_evidence_ref", "font_rule_flag")
TEXT_LIMITS = {"id": 64, "project_id": 64, "path": 256, "page_evidence_ref": 128}
MAX_PAGES = 100000
MAX_PROJECTS = 1024
MAX_PAPERS_PER_PROJECT = 256


@dataclass(frozen=True)
class Register:
    # (id, project_id, path, page_count_claim|None, page_evidence_ref, font_rule_flag)
    entries: tuple = ()


def create_register() -> Register:
    return Register()


def _err(code: str) -> ValueError:
    return ValueError("P258:" + code)


def _has_control(text: str) -> bool:
    return any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in text)


def _validate(entry) -> tuple:
    if not isinstance(entry, dict):
        raise _err("bad_type:entry")
    if any(k not in FIELDS for k in entry):
        raise _err("unknown_fields:entry")
    for name in REQUIRED:
        if name not in entry:
            raise _err("empty_field:" + name)
    v = dict(entry)
    v.setdefault("page_count_claim", None)
    v.setdefault("page_evidence_ref", "")
    v.setdefault("font_rule_flag", "unchecked")
    for name in TEXT_FIELDS:
        if isinstance(v[name], bool) or not isinstance(v[name], str):
            raise _err("bad_type:" + name)
    claim = v["page_count_claim"]
    if claim is not None and (isinstance(claim, bool) or not isinstance(claim, int)):
        raise _err("bad_type:page_count_claim")
    if "page_count_claim" in entry and claim is None:
        raise _err("bad_type:page_count_claim")
    for name in TEXT_FIELDS:
        if _has_control(v[name]):
            raise _err("bad_chars:" + name)
    for name in REQUIRED:
        if not v[name].strip():
            raise _err("empty_field:" + name)
    if not v["page_evidence_ref"].strip():
        v["page_evidence_ref"] = ""
    for name, limit in TEXT_LIMITS.items():
        if len(v[name]) > limit:
            raise _err("text_too_long:" + name)
    if claim is not None and not 0 <= claim <= MAX_PAGES:
        raise _err("out_of_range:page_count_claim")
    if v["font_rule_flag"] not in FLAGS:
        raise _err("bad_flag:" + v["font_rule_flag"])
    if claim is None and v["page_evidence_ref"]:
        raise _err("evidence_without_claim:" + v["id"])
    return tuple(v[name] for name in FIELDS)


def append(register: Register, entry) -> Register:
    if not isinstance(register, Register):
        raise _err("bad_type:register")
    row = _validate(entry)
    if any(r[0] == row[0] for r in register.entries):
        raise _err("duplicate_id:" + row[0])
    mine = [r for r in register.entries if r[1] == row[1]]
    if any(r[2] == row[2] for r in mine):
        raise _err("duplicate_path:" + row[2])
    if len(mine) >= MAX_PAPERS_PER_PROJECT:
        raise _err("limit_exceeded:papers_per_project")
    if not mine and len({r[1] for r in register.entries}) >= MAX_PROJECTS:
        raise _err("limit_exceeded:projects")
    return Register(register.entries + (row,))


def render(register: Register, project_id=None) -> str:
    if not isinstance(register, Register):
        raise _err("bad_type:register")
    if project_id is None:
        ids = sorted({r[1] for r in register.entries})
    else:
        if isinstance(project_id, bool) or not isinstance(project_id, str):
            raise _err("bad_type:project_id")
        if not any(r[1] == project_id for r in register.entries):
            raise _err("unknown_project:" + project_id)
        ids = [project_id]
    lines = []
    for pid in ids:
        rows = sorted((r for r in register.entries if r[1] == pid), key=lambda r: r[2])
        lines.append("project %s (%d papers)" % (pid, len(rows)))
        for r in rows:
            pages = "none" if r[3] is None else str(r[3])
            ev = "[%s]" % r[4] if r[4] else "UNVERIFIED"
            lines.append("%s pages=%s %s font=%s" % (r[2], pages, ev, r[5]))
    return "\n".join(lines)
