"""Optional RabbitMQ topic-routing backend (ATLAS-U-1205, technical-spec row A13).

A small adapter over a RabbitMQ topic exchange named ``atlas.events``, for the RabbitMQ container in
``deploy/local/docker-compose.rabbitmq.yml``. Its on/off flag and URL building (with percent-encoding of
reserved characters) live in ``app.workers.celery_broker_config``; the same flag turns on the Celery broker
route. It validates routing keys and binding patterns, declares durable queues bound to the topic exchange,
hands JSON events to the exchange, reads one message at a time with an explicit ack, and predicts locally
which declared bindings a key matches using AMQP topic rules (``*`` is exactly one word, ``#`` is zero or
more words).

Opt-in via the override only; the default deployment keeps Redis and is unchanged.
Managed/cloud RabbitMQ features (clustering, managed upgrades, cloud SLAs) are not covered.
Broker acceptance (real container routing) runs on the main side, not in this package.

Caller contract: new backend opt-in, unwired; legacy RabbitTopicBus on ATLAS_RABBITMQ_URL remains the active path; selection mechanism: setting ATLAS_RABBITMQ_URL to an amqp:// or amqps:// URL, or ATLAS_RABBITMQ_HOST, enables only the Celery task-broker config and only when the compose override is used (CELERY_CONFIG_MODULE=app.workers.celery_broker_config and CELERY_BROKER_URL exported from ``python -m app.workers.celery_broker_config --print-url``); RabbitRoutingBackend has no caller in application code and is built only by RabbitRoutingBackend.from_env() in tests or by explicit code. BOTH the legacy ATLAS_RABBITMQ_URL AND the ATLAS_RABBITMQ_HOST/USER/PASSWORD parts must point at the SAME broker; the override sets only the HOST/USER/PASSWORD parts, so ATLAS_RABBITMQ_URL must be set separately for the legacy bus. This is not an integrated-backend claim.
Build pin: an image built from deploy/local/Dockerfile.rabbitmq applies kombu==5.4.2 and celery==5.4.0 through PIP_CONSTRAINT; the stock Dockerfile does not, and the pin was not exercised by the author.

Not claimed: ``publish`` reports ``handed_to_broker`` only when the client library accepted the call
without raising; delivery to a queue is the broker's work. Nothing in the existing application calls this
module. kombu (installed with celery) is imported lazily and only when no factory is injected. The kombu
calls used (Exchange, Queue, queue(channel).declare(), queue(channel).get(no_ack=False), message.payload,
message.ack(), connection.Producer(...).publish(...), connection.channel()) were read against the public
kombu 5.4.2 source and py-amqp 5.2.0, and have not been run.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.workers import celery_broker_config as _config

EXCHANGE_NAME = 'atlas.events'
_WORD = re.compile(r'^[A-Za-z0-9_-]+$')
_QUEUE = re.compile(r'^[A-Za-z0-9_.-]+$')
_MAX_LEN = 255

is_enabled = _config.is_enabled


class RoutingError(ValueError):
    """Caller supplied an invalid key, pattern, queue name or event."""


class BackendUnavailable(RuntimeError):
    """The broker call failed. The message is fixed and never contains connection details."""


def _words(value: Any, allow_wildcards: bool) -> list[str]:
    if not isinstance(value, str) or not value or len(value) > _MAX_LEN:
        raise RoutingError('routing text must be a non-empty string up to 255 characters')
    words = value.split('.')
    for word in words:
        if allow_wildcards and word in ('*', '#'):
            continue
        if not _WORD.match(word):
            raise RoutingError('routing words may use letters, digits, underscore and hyphen only')
    return words


def validate_routing_key(key: Any) -> str:
    _words(key, allow_wildcards=False)
    return key


def validate_binding_pattern(pattern: Any) -> str:
    _words(pattern, allow_wildcards=True)
    return pattern


def topic_matches(pattern: str, key: str) -> bool:
    """AMQP 0-9-1 topic matching: ``*`` = exactly one word, ``#`` = zero or more words."""
    p = _words(validate_binding_pattern(pattern), True)
    k = _words(validate_routing_key(key), False)
    reach = [[False] * (len(k) + 1) for _ in range(len(p) + 1)]  # reach[i][j]: p[:i] matches k[:j]
    reach[0][0] = True
    for i in range(1, len(p) + 1):
        word = p[i - 1]
        for j in range(len(k) + 1):
            if word == '#':
                reach[i][j] = reach[i - 1][j] or (j > 0 and reach[i][j - 1])
            elif j > 0 and (word == '*' or word == k[j - 1]):
                reach[i][j] = reach[i - 1][j - 1]
    return reach[len(p)][len(k)]


@dataclass(frozen=True)
class Binding:
    queue: str
    pattern: str


class RabbitRoutingBackend:
    def __init__(self, connection: Any, *, exchange_factory: Callable[..., Any] | None = None,
                 queue_factory: Callable[..., Any] | None = None, exchange_name: str = EXCHANGE_NAME):
        if exchange_factory is None or queue_factory is None:
            from kombu import Exchange, Queue  # lazy: only when no factories are injected
            exchange_factory = exchange_factory or Exchange
            queue_factory = queue_factory or Queue
        self.connection = connection
        self._queue_factory = queue_factory
        self.exchange = exchange_factory(name=exchange_name, type='topic', durable=True)
        self.bindings: list[Binding] = []
        self._queues: dict[str, Any] = {}

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *,
                 connection_factory: Callable[[str], Any] | None = None,
                 exchange_factory: Callable[..., Any] | None = None,
                 queue_factory: Callable[..., Any] | None = None) -> 'RabbitRoutingBackend | None':
        """Return a backend only when the optional flag is on; otherwise None and no connection attempt."""
        if not _config.is_enabled(env):
            return None
        url = _config.broker_url_from_env(env)
        if connection_factory is None:
            from kombu import Connection  # lazy
            connection_factory = Connection
        return cls(connection_factory(url), exchange_factory=exchange_factory, queue_factory=queue_factory)

    def bind(self, queue: str, pattern: str) -> Binding:
        if not isinstance(queue, str) or not queue or len(queue) > _MAX_LEN or not _QUEUE.match(queue):
            raise RoutingError('queue name must be 1-255 letters, digits, dot, underscore or hyphen')
        validate_binding_pattern(pattern)
        binding = Binding(queue, pattern)
        if binding in self.bindings:
            return binding
        spec = self._queue_factory(name=queue, exchange=self.exchange, routing_key=pattern, durable=True)
        try:
            with self.connection.channel() as channel:
                spec(channel).declare()
        except Exception:
            raise BackendUnavailable('rabbitmq bind failed') from None
        self.bindings.append(binding)
        self._queues.setdefault(queue, spec)
        return binding

    def expected_queues(self, routing_key: str) -> list[str]:
        """Local prediction from declared bindings; not a statement about what the broker delivered."""
        validate_routing_key(routing_key)
        return sorted({b.queue for b in self.bindings if topic_matches(b.pattern, routing_key)})

    def publish(self, routing_key: str, event: dict) -> dict:
        validate_routing_key(routing_key)
        if not isinstance(event, dict) or not all(isinstance(k, str) for k in event):
            raise RoutingError('event must be an object with string keys')
        try:
            json.dumps(event, allow_nan=False)
        except (TypeError, ValueError):
            raise RoutingError('event must be JSON serializable') from None
        try:
            with self.connection.Producer(serializer='json') as producer:
                producer.publish(event, exchange=self.exchange, routing_key=routing_key,
                                 declare=[self.exchange], retry=True)
        except Exception:
            raise BackendUnavailable('rabbitmq publish failed') from None
        return {'routing_key': routing_key, 'exchange': self.exchange.name,
                'exchange_type': 'topic', 'handed_to_broker': True}

    def consume_one(self, queue: str) -> dict | None:
        spec = self._queues.get(queue)
        if spec is None:
            raise RoutingError('queue has no declared binding in this backend')
        try:
            with self.connection.channel() as channel:
                message = spec(channel).get(no_ack=False)
                if message is None:
                    return None
                payload = message.payload
                message.ack()
                return payload
        except Exception:
            raise BackendUnavailable('rabbitmq consume failed') from None
