"""The pin runner credits pytest test failures, not process or collection errors."""
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/j1_forecast/pin_mutants.py'

@pytest.mark.parametrize('returncode', [0, 1, 2, 3, 4, 5, -9])
def test_only_pytest_test_failure_is_killed(monkeypatch, tmp_path, capsys, returncode):
    calls = []
    def fake_run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=returncode, stdout='', stderr='')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(tmp_path))
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(SCRIPT), run_name='__main__')
    assert len(calls) == 35
    text = capsys.readouterr().out
    if returncode == 1:
        assert exit_info.value.code == 0
        assert text.count('KILLED  ') == 35
        assert 'survivors: []' in text
    else:
        assert exit_info.value.code == 1
        assert 'KILLED  ' not in text
        assert text.count('SURVIVED') == 35
