"""Instinct-doc group 2: dataset artifact evidence over real repo trees.

The landed p254 register validates caller-SUPPLIED dataset declarations and
renders them verbatim; nothing is counted from the world. This instrument
closes that gap the honest way: it walks real repository trees and counts
dataset ARTIFACTS - files with recognized data extensions living under
dataset-named directories (data/, datasets/, dataset/) - per project repo,
against the 120 gate. It reports exactly what it found: counts by
extension, the data directories that exist, and capped evidence paths.

Honest scope (stated, not implied): artifact presence is not dataset
quality, not record counts, not licensing, not proof a dataset is loaded or
used. A repo can pass the artifact gate with junk files and fail it with
datasets stored elsewhere (LFS, object storage, databases). The verdict is
an evidence floor, labeled as such.
"""
from __future__ import annotations

import os

TARGET = 120
MAX_REPOS = 64
MAX_WALK_FILES = 200000
MAX_EVIDENCE = 20
DATA_DIRS = frozenset({"data", "datasets", "dataset"})
DATA_EXTS = frozenset({".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet",
                       ".xml", ".yaml", ".yml", ".db", ".sqlite", ".sqlite3",
                       ".arrow", ".feather", ".h5", ".hdf5", ".txt"})
MEASURE = "dataset artifact presence scan (not quality/usage/licensing)"
SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules", ".venv", "venv"})


def _refuse(reason):
    return ValueError("G2_REFUSED_" + reason)


def scan_repo(repo_root, target=TARGET):
    """Count dataset artifacts under one repo root. Read-only walk."""
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        raise _refuse("BAD_TYPE:target")
    if not os.path.isdir(repo_root):
        raise _refuse("NO_REPO")
    root = os.path.realpath(repo_root)
    artifact_count = 0
    by_extension = {}
    data_dirs = set()
    evidence = []
    seen_real = set()
    walked = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        walked += len(filenames)
        if walked > MAX_WALK_FILES:
            raise _refuse("OVERSIZE:files")
        parts = os.path.relpath(dirpath, root).split(os.sep)
        if not any(p.lower() in DATA_DIRS for p in parts):
            continue
        data_dirs.add(os.path.relpath(dirpath, root))
        for name in sorted(filenames):
            ext = os.path.splitext(name)[1].lower()
            if ext not in DATA_EXTS:
                continue
            full = os.path.join(dirpath, name)
            real = os.path.realpath(full)
            if os.path.islink(full) and not real.startswith(root + os.sep):
                continue  # symlink escaping the repo is not repo evidence
            if real in seen_real:
                continue  # in-repo symlink/alias to an artifact already counted
            seen_real.add(real)
            artifact_count += 1
            by_extension[ext] = by_extension.get(ext, 0) + 1
            if len(evidence) < MAX_EVIDENCE:
                evidence.append(os.path.relpath(full, root))
    return {"artifact_count": artifact_count,
            "by_extension": dict(sorted(by_extension.items())),
            "data_dirs": sorted(data_dirs),
            "evidence": evidence,
            "target": target,
            "verdict": "EVIDENCE_AT_TARGET" if artifact_count >= target
                       else "EVIDENCE_BELOW_TARGET"}


def ledger(repos, target=TARGET):
    """Per-project dataset artifact ledger. repos: {name: path} mapping."""
    if not isinstance(repos, dict) or not repos:
        raise _refuse("EMPTY:repos")
    if len(repos) > MAX_REPOS:
        raise _refuse("OVERSIZE:repos")
    rows = []
    for name in sorted(repos):
        if not isinstance(name, str) or not name.strip():
            raise _refuse("BAD_TYPE:name")
        scan = scan_repo(repos[name], target)
        rows.append({"project": name, "measure": MEASURE, **scan})
    return {"target": target, "measure": MEASURE, "repos": rows,
            "projects_at_target": sum(1 for r in rows if r["verdict"] == "EVIDENCE_AT_TARGET"),
            "projects_below_target": sum(1 for r in rows if r["verdict"] == "EVIDENCE_BELOW_TARGET")}


def verify(repos, result):
    """Re-scan the same trees and compare every reported field.

    Honest limit: the scan is deterministic over a static tree, so this
    reruns the same instrument and proves the result matches the trees -
    it does not prove the artifacts are genuine, loadable datasets.
    """
    checks = ["structure", "exact_keys", "repos", "summary", "measure"]
    if not isinstance(result, dict):
        return {"verified": False, "failed": ["structure"], "checks": checks}
    failed = []
    if set(result) != {"target", "measure", "repos", "projects_at_target",
                       "projects_below_target"}:
        failed.append("exact_keys")
    expected = ledger(repos, result.get("target", TARGET) if isinstance(
        result.get("target"), int) and not isinstance(result.get("target"), bool)
        else TARGET)
    if result.get("repos") != expected["repos"]:
        failed.append("repos")
    if result.get("projects_at_target") != expected["projects_at_target"] or \
            result.get("projects_below_target") != expected["projects_below_target"] or \
            result.get("target") != expected["target"]:
        failed.append("summary")
    if result.get("measure") != MEASURE:
        failed.append("measure")
    return {"verified": not failed, "failed": sorted(set(failed)), "checks": checks}


def run(repos, target=TARGET):
    result = ledger(repos, target)
    receipt = verify(repos, result)
    return {"status": "measured" if receipt["verified"] else "verification_failed",
            "result": result, "verification": receipt}
