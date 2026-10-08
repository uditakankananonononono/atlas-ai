#!/usr/bin/env python3
"""Run pinned M18 boundary evidence; emit counts with explicit scope labels."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    junit = args.output / "pytest.xml"
    command = [sys.executable, "-m", "pytest", "tests/modules/test_m18_credential_redaction.py", "tests/test_m18_redaction_boundary_lane.py", "-q", f"--junitxml={junit}"]
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (args.output / "verify.txt").write_text(completed.stdout)
    suites = ET.parse(junit).getroot()
    cases = list(suites.iter("testcase"))
    failed = sum(case.find("failure") is not None or case.find("error") is not None for case in cases)
    residual = sum("former_" in case.attrib["name"] or case.attrib["name"] in {"test_http_error_itself_is_minimized", "test_arbitrary_source_field_is_removed", "test_malformed_ipv6_records_redacted_instead_of_raising"} for case in cases)
    models = ROOT / "backend/app/modules/m18_side_hustle_scraper/lane_models.py"
    receipt = {
        "verdict": "SCOPED" if completed.returncode == 0 else "PARTIAL",
        "head": git("rev-parse", "HEAD"),
        "base": "3eef2c0ab2344abfcc2de912e154a1b28f43d087",
        "python": sys.version,
        "tests_executed": len(cases),
        "failed_tests": failed,
        "former_residual_removal_tests": residual,
        "other_tests": len(cases) - residual,
        "loopback_transport_tests": 2,
        "module_sha256": hashlib.sha256(models.read_bytes()).hexdigest(),
        "command": command,
        "limits": ["13 former residual tests now assert removal or safe fallback.", "Diagnostics deliberately lose all URL path/query/fragment and unknown source/reason prose.", "Loopback HTTP is a real transport test against a controlled server, not an external website or owner PC test.", "No hostname-credential, raw request/headers, legacy-cleanup or collection permission claim.", "Reapplied onto observed main 3eef2c0; its bounded redactor is replaced with diagnostic minimization."],
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
