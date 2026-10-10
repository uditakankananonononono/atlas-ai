"""Additive Celery broker configuration for the optional RabbitMQ route (ATLAS-U-1205, spec row A13).

How it is wired without editing ``celery_app.py``: the override in ``deploy/local/docker-compose.rabbitmq.yml``
sets ``CELERY_CONFIG_MODULE`` to this module and exports ``CELERY_BROKER_URL`` from ``--print-url`` below.
In Celery 5.4.0 the ``CELERY_BROKER_URL`` environment variable takes precedence over the ``broker=`` argument
(celery/app/utils.py, ``Settings.broker_url``), and a config module can supply ``task_queues`` because
``celery_app.py`` does not set it. The module-level ``task_queues`` below declares one durable topic exchange
(``atlas.tasks``) with one exact-key queue per queue name that ``celery_app.py`` routes to, plus ``celery``.
The result backend stays Redis, as in ``celery_app.py``.

The flag: the broker is enabled only when ``ATLAS_RABBITMQ_URL`` is an ``amqp://`` or ``amqps://`` URL, or
``ATLAS_RABBITMQ_HOST`` is set. With the host form the URL is built here from ``ATLAS_RABBITMQ_USER``,
``ATLAS_RABBITMQ_PASSWORD``, ``ATLAS_RABBITMQ_PORT`` (default 5672) and ``ATLAS_RABBITMQ_VHOST`` (default ``/``)
and every reserved character is percent-encoded. When disabled, ``--print-url`` prints nothing and the Celery
default (Redis) is used.

Opt-in via the override only; the default deployment keeps Redis and is unchanged.
Managed/cloud RabbitMQ features (clustering, managed upgrades, cloud SLAs) are not covered.
Broker acceptance (real container routing) runs on the main side, not in this package.

Caller contract: new backend opt-in, unwired; legacy RabbitTopicBus on ATLAS_RABBITMQ_URL remains the active path; selection mechanism: setting ATLAS_RABBITMQ_URL to an amqp:// or amqps:// URL, or ATLAS_RABBITMQ_HOST, enables only the Celery task-broker config and only when the compose override is used (CELERY_CONFIG_MODULE=app.workers.celery_broker_config and CELERY_BROKER_URL exported from ``python -m app.workers.celery_broker_config --print-url``); RabbitRoutingBackend has no caller in application code and is built only by RabbitRoutingBackend.from_env() in tests or by explicit code. BOTH the legacy ATLAS_RABBITMQ_URL AND the ATLAS_RABBITMQ_HOST/USER/PASSWORD parts must point at the SAME broker; the override sets only the HOST/USER/PASSWORD parts, so ATLAS_RABBITMQ_URL must be set separately for the legacy bus. This is not an integrated-backend claim.
Build pin: an image built from deploy/local/Dockerfile.rabbitmq applies kombu==5.4.2 and celery==5.4.0 through PIP_CONSTRAINT; the stock Dockerfile does not, and the pin was not exercised by the author.

Not claimed: the kombu calls were read against the v5.4.2 public source, but nothing here has been run
against a broker. The existing ``RabbitTopicBus`` in ``app/platform/integrations.py`` still needs a ready
``ATLAS_RABBITMQ_URL`` and is not changed. TLS and IPv6 hosts are not handled by the host form.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlsplit, urlunsplit

VERIFIED_KOMBU_VERSION = '5.4.2'
ENV_URL = 'ATLAS_RABBITMQ_URL'
ENV_HOST = 'ATLAS_RABBITMQ_HOST'
ENV_PORT = 'ATLAS_RABBITMQ_PORT'
ENV_USER = 'ATLAS_RABBITMQ_USER'
ENV_PASSWORD = 'ATLAS_RABBITMQ_PASSWORD'
ENV_VHOST = 'ATLAS_RABBITMQ_VHOST'
TASK_EXCHANGE_NAME = 'atlas.tasks'
TASK_QUEUE_NAMES = ('ai', 'browser', 'celery', 'collection', 'default', 'documents')
_HOST = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?')


class ConfigError(ValueError):
    """Invalid or missing RabbitMQ settings. Messages name the variable, never its value."""


def _source(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _explicit_url(env: Mapping[str, str]) -> str:
    url = env.get(ENV_URL, '').strip()
    return url if url.startswith(('amqp://', 'amqps://')) else ''


def is_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = _source(env)
    return bool(_explicit_url(source)) or bool(source.get(ENV_HOST, '').strip())


def broker_url_from_env(env: Mapping[str, str] | None = None) -> str:
    source = _source(env)
    explicit = _explicit_url(source)
    if explicit:
        return explicit
    host = source.get(ENV_HOST, '')
    if not host:
        raise ConfigError('RabbitMQ is not enabled: set ' + ENV_URL + ' or ' + ENV_HOST)
    if not _HOST.fullmatch(host):
        raise ConfigError(ENV_HOST + ' must be a plain hostname')
    try:
        port = int(source.get(ENV_PORT, '5672'))
    except ValueError:
        raise ConfigError(ENV_PORT + ' must be 1-65535') from None
    if not 1 <= port <= 65535:
        raise ConfigError(ENV_PORT + ' must be 1-65535')
    user = source.get(ENV_USER, '')
    if not user:
        raise ConfigError(ENV_USER + ' is required')
    password = source.get(ENV_PASSWORD, '')
    if not password:
        raise ConfigError(ENV_PASSWORD + ' is required')
    vhost = source.get(ENV_VHOST) or '/'
    return f"amqp://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{quote(vhost, safe='')}"


def redacted_url(url: str) -> str:
    parts = urlsplit(url)
    if '@' not in parts.netloc:
        return url
    userinfo, hostpart = parts.netloc.rsplit('@', 1)
    netloc = userinfo.split(':', 1)[0] + ':***@' + hostpart
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def kombu_pin_status(installed: str | None, verified: str = VERIFIED_KOMBU_VERSION) -> str:
    if installed is None:
        return 'kombu-not-installed'
    return 'matches-verified-version' if installed == verified else 'differs-from-verified-version'


def installed_kombu_version() -> str | None:
    from importlib import metadata
    try:
        return metadata.version('kombu')
    except metadata.PackageNotFoundError:
        return None


def build_task_queues(exchange_factory: Callable[..., Any] | None = None,
                      queue_factory: Callable[..., Any] | None = None) -> list:
    if exchange_factory is None or queue_factory is None:
        from kombu import Exchange, Queue  # kombu 5.4.2 signatures read from its public source
        exchange_factory = exchange_factory or Exchange
        queue_factory = queue_factory or Queue
    exchange = exchange_factory(name=TASK_EXCHANGE_NAME, type='topic', durable=True)
    return [queue_factory(name=name, exchange=exchange, routing_key=name, durable=True) for name in TASK_QUEUE_NAMES]


try:  # Celery reads this module attribute when the module is used as CELERY_CONFIG_MODULE.
    task_queues = build_task_queues()
except ImportError:  # kombu missing: leave Celery's own queue defaults in place
    task_queues = None


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None, stdout: Any = None, stderr: Any = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    if args == ['--print-url']:
        if not is_enabled(env):
            return 0
        try:
            out.write(broker_url_from_env(env) + '\n')
        except ConfigError as exc:
            err.write(f'celery_broker_config: {exc}\n')
            return 2
        return 0
    if args == ['--kombu-status']:
        out.write(f'kombu {installed_kombu_version()}: {kombu_pin_status(installed_kombu_version())}\n')
        return 0
    err.write('usage: python -m app.workers.celery_broker_config --print-url | --kombu-status\n')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
