#!/usr/bin/env python3
"""Generate limited, reproducible repository acceptance evidence per module."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def evidence() -> dict[str, object]:
    tests = list((ROOT / "tests").rglob("test_*.py")); rows = []
    for module_id in range(26):
        prefix = f"m{module_id:02d}_"
        packages = sorted(p for p in (ROOT / "backend/app/modules").iterdir() if p.is_dir() and p.name.startswith(prefix))
        matched_tests = sorted(str(p.relative_to(ROOT)) for p in tests if prefix in p.name.lower() or f"m{module_id:02d}" in p.read_text(errors="ignore").lower())
        code_files = sorted(str(p.relative_to(ROOT)) for package in packages for p in package.rglob("*.py") if "__pycache__" not in p.parts)
        rows.append({"module_id": module_id, "package_paths": [str(p.relative_to(ROOT)) for p in packages], "code_file_count": len(code_files), "offline_test_files": matched_tests, "repository_evidence": "present" if code_files and matched_tests else "incomplete", "live_acceptance": "not_run", "production_acceptance": "not_run"})
    payload = {"schema_version": 1, "scope": "repository code and offline test discovery only", "limitations": ["Test discovery is not proof that every requirement is implemented.", "No provider account, browser target, payment, production deployment, load target, or recovery drill was exercised.", "Run the named tests and record their exit status separately; this report does not execute them."], "modules": rows}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(); payload["evidence_sha256"] = hashlib.sha256(canonical).hexdigest(); return payload
def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path);parser.add_argument("--check",action="store_true");args=parser.parse_args();payload=evidence();rendered=json.dumps(payload,indent=2)+"\n"
    if args.output: args.output.write_text(rendered)
    else: print(rendered,end="")
    return int(args.check and any(row["repository_evidence"]!="present" for row in payload["modules"]))
if __name__=="__main__": raise SystemExit(main())
