"""Real trusted-local subprocesses, authored fixture scripts, no external calls."""
import sys
import time
import hashlib
from pathlib import Path

import pytest

from app.runtime.guardrails.tool_execution_receipts import ExecutionStore


def pin(tmp_path, source, name="tool.py"):
    script = tmp_path / name
    script.write_text(source)
    return [sys.executable, str(script)], [str(script)]


def test_success_persists_and_is_project_bound(tmp_path):
    argv, inputs = pin(tmp_path, "print('actual output')")
    path = tmp_path / "receipts.sqlite"
    with ExecutionStore(path) as store:
        store.register("project-a", "one", argv, inputs=inputs)
        receipt = store.execute("project-a", "one")
        assert receipt["status"] == "succeeded"
        assert receipt["stdout_sha256"] == hashlib.sha256(b"actual output\n").hexdigest()
        assert receipt["returncode"] == 0
        assert store.evaluate("project-a", bar=1)["met"] is True
        assert store.evaluate("project-b", bar=1)["met"] is False
    with ExecutionStore(path) as store:
        assert store.receipt(receipt["id"]) == receipt
        assert store.evaluate("project-a", bar=200)["shortfall"] == 199


def test_aliases_and_repeated_runs_cannot_inflate_count(tmp_path):
    argv, inputs = pin(tmp_path, "print('same tool')")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs)
        store.register("p", "alias", argv, inputs=inputs)
        for name in ("one", "one", "alias"):
            store.execute("p", name)
        assert store.evaluate("p", bar=2)["distinct_executed_tools"] == 1
        assert store.evaluate("p", bar=2)["met"] is False


def test_changed_input_before_execution_refuses_and_never_counts(tmp_path):
    argv, inputs = pin(tmp_path, "print('old')")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs)
        Path(inputs[0]).write_text("print('replaced')")
        with pytest.raises(ValueError, match="pin_changed"):
            store.execute("p", "one")
        assert store.evaluate("p", bar=1)["distinct_executed_tools"] == 0


def test_changed_input_during_execution_does_not_count(tmp_path):
    argv, inputs = pin(tmp_path, "from pathlib import Path\nPath(__file__).write_text('changed')\n")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs)
        receipt = store.execute("p", "one")
        assert receipt["status"] == "pin_changed"
        assert store.evaluate("p", bar=1)["met"] is False


@pytest.mark.parametrize("source,status", [
    ("raise SystemExit(3)", "failed"),
    ("import time; time.sleep(20)", "timeout"),
    ("import os; os.write(1, b'x'*100000)", "output_limit"),
])
def test_unsuccessful_processes_never_count(tmp_path, source, status):
    argv, inputs = pin(tmp_path, source)
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs, timeout=.2, output_limit=1024)
        start = time.monotonic()
        receipt = store.execute("p", "one")
        assert time.monotonic() - start < 3
        assert receipt["status"] == status
        assert receipt["stdout_bytes"] + receipt["stderr_bytes"] <= 1024
        assert store.evaluate("p", bar=1)["met"] is False


def test_refuses_unregistered_and_cross_project_execution(tmp_path):
    argv, inputs = pin(tmp_path, "print('safe')")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs)
        with pytest.raises(ValueError, match="unregistered"):
            store.execute("other", "one")
        with pytest.raises(ValueError, match="unregistered"):
            store.execute("p", "invented")


def test_registration_is_immutable(tmp_path):
    argv, inputs = pin(tmp_path, "print('a')")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs)
        with pytest.raises(ValueError, match="already_registered"):
            store.register("p", "one", argv, inputs=inputs)


def test_no_receipt_import_or_attestation_path(tmp_path):
    with ExecutionStore(tmp_path / "db") as store:
        assert store.evaluate("p", bar=1)["distinct_executed_tools"] == 0
        with pytest.raises(ValueError, match="unknown_receipt"):
            store.receipt("fabricated")


def test_timeout_kills_same_session_descendants(tmp_path):
    marker = tmp_path / "escaped"
    source = ("import subprocess, sys, time\n"
              f"subprocess.Popen([sys.executable, '-c', {('import time; from pathlib import Path; time.sleep(.7); Path('+repr(str(marker))+').write_text(\"bad\")')!r}])\n"
              "time.sleep(20)\n")
    argv, inputs = pin(tmp_path, source)
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs, timeout=.1)
        assert store.execute("p", "one")["status"] == "timeout"
    time.sleep(.9)
    assert not marker.exists()


def test_environment_is_not_inherited(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PRIVATE_CREDENTIAL", "secret-for-test")
    argv, inputs = pin(tmp_path, "import os; print(os.environ.get('FAKE_PRIVATE_CREDENTIAL', 'absent'))")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs)
        receipt = store.execute("p", "one")
        assert receipt["stdout_sha256"] == hashlib.sha256(b"absent\n").hexdigest()


@pytest.mark.parametrize("bar", [True, 0, -1, 1.0, 100001])
def test_bad_bar(tmp_path, bar):
    with ExecutionStore(tmp_path / "db") as store:
        with pytest.raises(ValueError, match="bad_bar"):
            store.evaluate("p", bar=bar)


def test_require_bar_refuses_declarations_and_allows_observed_execution(tmp_path):
    from app.runtime.guardrails.errors import GuardrailRefusal
    argv, inputs = pin(tmp_path, "print('actual')")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs)
        with pytest.raises(GuardrailRefusal) as held:
            store.require_bar("p", bar=1)
        assert held.value.code == "TOOLEXEC:bar_unmet"
        assert held.value.details["shortfall"] == 1
        store.execute("p", "one")
        assert store.require_bar("p", bar=1)["met"] is True


def test_two_different_pinned_tools_count_two(tmp_path):
    first, inp1 = pin(tmp_path, "print('first')", "first.py")
    second, inp2 = pin(tmp_path, "print('second')", "second.py")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "first", first, inputs=inp1)
        store.register("p", "second", second, inputs=inp2)
        store.execute("p", "first")
        store.execute("p", "second")
        assert store.require_bar("p", bar=2)["distinct_executed_tools"] == 2


def test_parent_closed_pipes_still_times_out(tmp_path):
    argv, inputs = pin(tmp_path, "import os,time; os.close(1); os.close(2); time.sleep(20)")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs, timeout=.1)
        start = time.monotonic()
        assert store.execute("p", "one")["status"] == "timeout"
        assert time.monotonic()-start < 3


def test_receipts_are_committed_between_connections(tmp_path):
    argv, inputs = pin(tmp_path, "print('actual')")
    with ExecutionStore(tmp_path / "db") as first, ExecutionStore(tmp_path / "db") as second:
        first.register("p", "one", argv, inputs=inputs)
        receipt = second.execute("p", "one")
        assert first.receipt(receipt["id"]) == receipt
        assert first.require_bar("p", bar=1)["met"]


@pytest.mark.parametrize("field,value", [
    ("timeout", True), ("timeout", float('nan')), ("timeout", 0),
    ("output_limit", True), ("output_limit", 0),
])
def test_registration_bounds(tmp_path, field, value):
    argv, inputs = pin(tmp_path, "print('actual')")
    with ExecutionStore(tmp_path / "db") as store:
        with pytest.raises(ValueError, match="bad_"):
            store.register("p", "one", argv, inputs=inputs, **{field: value})


def test_dependency_symlink_retarget_is_refused(tmp_path):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("print('first')")
    second.write_text("print('second')")
    alias = tmp_path / "alias.py"
    alias.symlink_to(first)
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", [sys.executable, str(alias)], inputs=[str(alias)])
        alias.unlink()
        alias.symlink_to(second)
        with pytest.raises(ValueError, match="pin_changed"):
            store.execute("p", "one")


def test_descendant_holding_pipes_after_parent_exit_is_not_success(tmp_path):
    # Parent exits zero; its child still holds output pipes. The deadline must
    # refuse this unfinished invocation rather than count parent returncode zero.
    argv, inputs = pin(tmp_path, "import subprocess,sys\nsubprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n")
    with ExecutionStore(tmp_path / "db") as store:
        store.register("p", "one", argv, inputs=inputs, timeout=.2)
        receipt = store.execute("p", "one")
        assert receipt["status"] == "timeout"
        assert receipt["returncode"] == 0
        assert store.evaluate("p", bar=1)["met"] is False
