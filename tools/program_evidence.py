#!/usr/bin/env python3
"""Build truthful checkout evidence. Test execution is explicit opt-in."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.modules.instinct_doc.repo_evidence import build_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source', default='docs/program-evidence/source-manifest.json')
    parser.add_argument('--test', action='append', default=[])
    parser.add_argument('--allow-local-code-execution', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.test and not args.allow_local_code_execution:
        parser.error('tests execute repository code; opt in with --allow-local-code-execution')
    report = build_report(args.root, args.source, args.test or None)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report_sha256': report['report_sha256'],
                      'unverified_lines': report['candy_gate']['unverified_lines'],
                      'release': report['candy_gate']['release'],
                      'test_status': report['executed_tests']['status'] if report['executed_tests'] else 'NOT_EXECUTED'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
