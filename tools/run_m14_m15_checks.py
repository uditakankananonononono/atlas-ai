#!/usr/bin/env python3
"""Run all M14/M15 checks with mandatory embedded-Postgres dependencies."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    import pgserver
    import psycopg
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'backend')
    paths = sorted({*ROOT.glob('tests/modules/test_m14*.py'),
                    *ROOT.glob('tests/modules/test_m15*.py'),
                    ROOT / 'tests/modules/test_repair_m14_m15_remaining.py'})
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError('Required test files missing: ' + ', '.join(missing))
    return subprocess.call([sys.executable, '-m', 'pytest',
                            *[str(path.relative_to(ROOT)) for path in paths],
                            '-q', '--tb=short'], cwd=ROOT, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
