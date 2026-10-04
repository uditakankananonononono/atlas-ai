"""The test session must not leave ./atlas.db in the working directory, and must respect an explicit ATLAS_DATABASE_URL.
Runs a representative DB-writing file (m23 story, which created ./atlas.db before the conftest fix) in a subprocess whose cwd is a temp dir.
Scope: pytest rootdir only (tests/conftest.py); a different runner or a conftest-less invocation is not covered."""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "modules" / "test_m23_story.py"

def _run(cwd: Path, env_extra: dict):
    env = {k: v for k, v in os.environ.items() if k != "ATLAS_DATABASE_URL"}
    env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(ROOT),
                           "-c", str(ROOT / "pyproject.toml"), str(TARGET)],
                          cwd=cwd, env=env, capture_output=True, text=True, timeout=120)

def test_default_run_leaves_no_atlas_db_in_cwd(tmp_path):
    r = _run(tmp_path, {})
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    assert not (tmp_path / "atlas.db").exists()

def test_explicit_database_url_is_respected(tmp_path):
    db = tmp_path / "explicit.db"
    r = _run(tmp_path, {"ATLAS_DATABASE_URL": f"sqlite:///{db}"})
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    assert db.exists() and not (tmp_path / "atlas.db").exists()
