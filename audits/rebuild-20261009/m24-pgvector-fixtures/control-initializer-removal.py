"""Disposable mutation: no vector init must fail PostgreSQL, not SQLite."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
p = root / 'tests/conftest.py'
before = p.read_bytes()
needle = b"            db.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))"
assert before.count(needle) == 1
log = Path(__file__).resolve().parent / 'RED-initializer-removal.log'
try:
    mutated = before.replace(needle, b'            pass  # MUTATION: extension initialization removed')
    assertion = b'''            assert db.scalar(text("SELECT count(*) FROM pg_extension WHERE extname='vector'")) == 1'''
    assert mutated.count(assertion) == 1
    p.write_bytes(mutated.replace(assertion, b'            pass  # MUTATION: verification removed too'))
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q',
        'tests/modules/test_m24_pgvector_fixture.py'], cwd=root,
        env={**os.environ, 'PYTHONPATH': 'backend'}, capture_output=True, text=True, timeout=40)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == 1, result.returncode
    assert '1 failed, 1 passed' in result.stdout, result.stdout
    assert 'type \"vector\" does not exist' in result.stdout, result.stdout
finally:
    p.write_bytes(before)
    assert hashlib.sha256(p.read_bytes()).digest() == hashlib.sha256(before).digest()
print('Initializer removal: 1 PostgreSQL FAIL, 1 SQLite PASS; exact bytes restored.')
