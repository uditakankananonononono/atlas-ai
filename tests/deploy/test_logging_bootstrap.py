"""Authored-not-run: hermetic real formatter and startup logging contracts."""
import importlib
import io
import json
import logging
from contextlib import redirect_stdout

import pytest
from app.platform import logging_bootstrap as bootstrap
from app.platform.observability import CloudJsonFormatter, trace_id_var


@pytest.fixture(autouse=True)
def restore_logging():
    names = ("", "uvicorn", "uvicorn.error", "uvicorn.access", "celery", "celery.task", "celery.redirected")
    saved = {name: (list(logging.getLogger(name).handlers), logging.getLogger(name).level,
                    logging.getLogger(name).propagate, logging.getLogger(name).disabled) for name in names}
    token = trace_id_var.set("fixture-trace")
    yield
    trace_id_var.reset(token)
    for name, (handlers, level, propagate, disabled) in saved.items():
        logger = logging.getLogger(name)
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate
        logger.disabled = disabled


def parse_lines(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_import_does_not_install_handlers():
    root = logging.getLogger()
    before = list(root.handlers)
    importlib.reload(bootstrap)
    assert root.handlers == before


def test_stdout_schema_is_existing_formatter_with_trace_and_escaping():
    stream = io.StringIO()
    with redirect_stdout(stream):
        bootstrap.install_json_logging("INFO")
        logging.getLogger("atlas.test").warning('line one\n"line two"')
    row, = parse_lines(stream)
    assert row == {"severity": "WARNING", "message": 'line one\n"line two"',
                   "logger": "atlas.test", "trace_id": "fixture-trace", "service": "atlas-api"}
    assert type(logging.getLogger().handlers[0].formatter) is CloudJsonFormatter


def test_reinstallation_does_not_duplicate_and_filters_level():
    stream = io.StringIO()
    with redirect_stdout(stream):
        bootstrap.install_json_logging("WARNING")
        bootstrap.install_json_logging("WARNING")
        logging.getLogger("atlas.test").info("filtered")
        logging.getLogger("atlas.test").error("one")
    assert [r["message"] for r in parse_lines(stream)] == ["one"]


def test_real_uvicorn_configuration_keeps_json_access_and_error_logs():
    from uvicorn import Config
    stream = io.StringIO()
    with redirect_stdout(stream):
        Config("app.main:app", log_config=bootstrap.uvicorn_logging_config("INFO"), log_level="info")
        logging.getLogger("uvicorn.error").info("server start")
        logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "client", "GET", "/health", "1.1", 200)
    rows = parse_lines(stream)
    assert len(rows) == 2
    assert {r["logger"] for r in rows} == {"uvicorn.error", "uvicorn.access"}
    assert all(set(r) == {"severity", "message", "logger", "trace_id", "service"} for r in rows)
    assert all(r["trace_id"] == "fixture-trace" for r in rows)


def test_real_celery_setup_signal_installs_json_and_prevents_default_override():
    from celery.signals import setup_logging
    stream = io.StringIO()
    receiver = bootstrap.connect_worker_logging("INFO")
    try:
        with redirect_stdout(stream):
            responses = setup_logging.send(sender=None, loglevel=logging.INFO, logfile=None,
                                           format="ignored", colorize=False)
            logging.getLogger("celery.task").info("task lifecycle")
            logging.getLogger("celery.redirected").warning("redirected output")
        assert any(fn is receiver and result is None for fn, result in responses)
        rows = parse_lines(stream)
        assert [r["message"] for r in rows] == ["task lifecycle", "redirected output"]
        assert all(r["service"] == "atlas-api" for r in rows)
    finally:
        setup_logging.disconnect(receiver)


@pytest.mark.parametrize("level", ["unknown", "", "warn; echo nope"])
def test_invalid_log_level_fails_before_logging_change(level):
    before = list(logging.getLogger().handlers)
    with pytest.raises(ValueError):
        bootstrap.install_json_logging(level)
    assert logging.getLogger().handlers == before


def test_cli_selects_exact_existing_startup_targets_and_defaults():
    api = bootstrap.parse_args(["api"])
    worker = bootstrap.parse_args(["worker"])
    assert api.mode == "api" and api.host == "0.0.0.0" and api.port == 8080
    assert worker.mode == "worker" and worker.log_level == "INFO"
    with pytest.raises(SystemExit):
        bootstrap.parse_args(["other"])


def test_module_help_entrypoint_exits_without_starting_app_or_worker():
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "backend")
    result = subprocess.run([sys.executable, "-m", "app.platform.logging_bootstrap", "--help"],
                            cwd=root, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "{api,worker}" in result.stdout
    assert not result.stderr
