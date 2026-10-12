"""Resolving wrappers over the p77/p254/p255/p258 registers (groups 1-4, 6, 9).

The base registers record caller declarations and are kept unchanged (their
existing contracts and tests stand). Datasets, papers and "active" integrations are
refused unless their evidence resolves here (file hash, PDF format gate, an executed run).
"planned" and other non-active integration entries pass without evidence: they are
declarations by design and make no run claim. Use these for any
"is it done" statement; use the base registers only as declarations.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    key = "pe_" + name
    if key in sys.modules:
        return sys.modules[key]
    s = importlib.util.spec_from_file_location(key, os.path.join(_here, name + ".py"))
    m = importlib.util.module_from_spec(s)
    sys.modules[key] = m
    s.loader.exec_module(m)
    return m


pe = _load("program_evidence_g1_16")
datasets = _load("dataset_register_p254")
integrations = _load("integrations_register_p255")
papers = _load("paper_register_p258")


def _refuse(code):
    return ValueError("G1-16:unresolved:" + code)


def add_dataset(register, entry, base, sha256):
    """entry is a p254 entry; source_ref must be a file under base hashing to sha256."""
    if not isinstance(entry, dict):
        raise _refuse("bad_entry")
    r = pe.check_datasets(base, [{"path": entry.get("source_ref", ""), "sha256": sha256, "origin": entry.get("source", "")}], 1)
    if not r["ok"]:
        raise _refuse("dataset_file")
    return datasets.add_entry(register, entry)


def append_integration(register, entry, base, run_spec, allowlist, runner=None):
    """Status 'active' requires the tool to be executed here: run_spec is
    {argv, output_path?, output_sha256}; it must exit 0 and match its output hash."""
    if entry.get("status") == "active":
        spec = dict(run_spec or {}, name=entry.get("name", ""))
        if not pe.check_tools(base, [spec], runner, allowlist):
            raise _refuse("tool_run")
    return integrations.append(register, entry)


def append_paper(register, entry, base, thresholds=pe.LENIENT):
    """Paper entry accepted only if the PDF at entry['path'] meets page count and font."""
    if not isinstance(entry, dict):
        raise _refuse("bad_entry")
    r = pe.check_paper(base, {"path": entry.get("path", "")}, thresholds)
    if not r["ok"]:
        raise _refuse("paper_pdf:" + str(r.get("reason", r)))
    return papers.append(register, dict(entry, page_count_claim=r["pages"], font_rule_flag="pass",
                                         page_evidence_ref="pdfinfo+pdffonts"))


def resolved_counts(project_manifests, base, thresholds=pe.LENIENT, runner=None, probe=None, tool_allowlist=()):
    rep = pe.verify_program(base, project_manifests, thresholds, runner, probe, tool_allowlist)
    return {"program_verdict": rep["verdict"], "tools": rep["program_distinct_tools_verified"],
            "by_project": {r["project"]: r["verdict"] for r in rep["projects"]}}
