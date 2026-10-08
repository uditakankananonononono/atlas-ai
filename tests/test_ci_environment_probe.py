"""Environment gates must never turn sandbox implementation failures green."""
import subprocess
from types import SimpleNamespace
import pytest
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("atlas_root_test_fixtures", Path(__file__).with_name("conftest.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
_check_bubblewrap_probe = fixtures._check_bubblewrap_probe
real_bubblewrap_environment = fixtures.real_bubblewrap_environment

@pytest.mark.parametrize("code,out,err", [
    (1, "", "bwrap: Unknown option --malformed\n"),
    (1, "unexpected output\n", "bwrap: Creating new namespace failed: Operation not permitted\n"),
    (1, "", "unexpected failure\n"),
    (2, "", ""),
    (0, "wrong marker\n", ""),
    (0, "atlas-isolation-probe\n", "unexpected warning\n"),
    (1, "", "bwrap: Creating new namespace failed: Operation not permitted\nextra error\n"),
])
def test_probe_failures_never_skip(code,out,err):
    with pytest.raises(AssertionError):
        _check_bubblewrap_probe(SimpleNamespace(returncode=code,stdout=out,stderr=err))

@pytest.mark.parametrize("error", [OSError("fixture os failure"), subprocess.TimeoutExpired("bwrap", 10),
                                    FileNotFoundError(2,"fixture missing interpreter","/missing/python")])
def test_probe_os_errors_and_timeout_fail(monkeypatch,error):
    from app.modules.m04_research_scientist.approved_sandbox import BubblewrapBackend
    monkeypatch.setattr(BubblewrapBackend,"available",lambda *a: True)
    monkeypatch.setattr(BubblewrapBackend,"__init__",lambda self: setattr(self,"bwrap","/probe/bwrap"))
    def fail(*args,**kwargs): raise error
    monkeypatch.setattr(subprocess,"run",fail)
    with pytest.raises(type(error)):
        real_bubblewrap_environment.__wrapped__()

def test_recognized_namespace_refusal_skips():
    with pytest.raises(pytest.skip.Exception):
        _check_bubblewrap_probe(SimpleNamespace(returncode=1,stdout="",stderr="bwrap: Creating new namespace failed: Operation not permitted\n"))

def test_probe_exact_success():
    _check_bubblewrap_probe(SimpleNamespace(returncode=0,stdout="atlas-isolation-probe\n",stderr=""))
