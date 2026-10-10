"""Opt-in JSON stdout startup for the local Loki/Promtail compose override.

Google Cloud Logging sink, GCP alerting, log-based metrics. The bootstrap wires JSON logging at startup; it does NOT change existing services' default config, and no log pipeline is added to the collector.

Uses the existing CloudJsonFormatter without changing its schema, including
its service='atlas-api' value for BOTH app and worker records. Sink component
labels distinguish producers. Arbitrary print output is not promised to be JSON.
No import-time logging changes. Activate via python -m ... api or worker only.
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.platform.observability import CloudJsonFormatter

_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "celery", "celery.task", "celery.redirected")
_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _level(value: str) -> str:
    if not isinstance(value, str) or value.upper() not in _LEVELS:
        raise ValueError("unsupported logging level")
    return value.upper()


def install_json_logging(level: str = "INFO") -> None:
    """Replace startup root/known framework handlers with one JSON stdout sink."""
    level = _level(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudJsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.disabled = False
    for name in _LOGGERS:
        logger = logging.getLogger(name)
        logger.handlers[:] = []
        logger.setLevel(level)
        logger.propagate = True
        logger.disabled = False


def uvicorn_logging_config(level: str = "INFO") -> dict:
    """Uvicorn applies this config before loading app.main:app, not its defaults."""
    level = _level(level)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"atlas_json": {"()": "app.platform.observability.CloudJsonFormatter"}},
        "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "atlas_json",
                                "stream": "ext://sys.stdout"}},
        "root": {"handlers": ["stdout"], "level": level},
        "loggers": {name: {"handlers": [], "level": level, "propagate": True}
                    for name in _LOGGERS},
    }


def connect_worker_logging(level: str = "INFO"):
    """A real setup_logging receiver suppresses Celery's own default setup.

    Prefork children inherit the configured handlers. The receiver
    is returned for hermetic teardown. CLI invocation connects it exactly once.
    """
    from celery.signals import setup_logging

    level = _level(level)

    def configure(sender=None, **kwargs):
        install_json_logging(level)

    setup_logging.connect(configure, weak=False)
    return configure


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Opt-in Atlas local JSON logging")
    parser.add_argument("mode", choices=("api", "worker"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--log-level", choices=sorted(_LEVELS), default="INFO")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    install_json_logging(args.log_level)
    if args.mode == "api":
        import uvicorn

        uvicorn.run("app.main:app", host=args.host, port=args.port,
                    log_level=args.log_level.lower(), log_config=uvicorn_logging_config(args.log_level))
    else:
        # Connect BEFORE loading worker tasks/starting Celery. No existing module
        # is edited, and the application's existing routing/config stays intact.
        connect_worker_logging(args.log_level)
        from app.workers.celery_app import celery_app

        return celery_app.worker_main(["worker", "--loglevel=" + args.log_level])


if __name__ == "__main__":
    main()
