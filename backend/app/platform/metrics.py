"""Private, low-cardinality product metrics. No prompt, tenant or credential labels."""
from __future__ import annotations

import hmac
import os
import time
from prometheus_client import CollectorRegistry, Counter, Histogram, ProcessCollector, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import GaugeMetricFamily
from starlette.responses import Response

REGISTRY = CollectorRegistry()
ProcessCollector(registry=REGISTRY)
HTTP_DURATION = Histogram('http_server_request_duration_seconds', 'API request time including boundary checks',
                          ['method', 'route', 'status'], registry=REGISTRY)
PROVIDER_LATENCY = Histogram('atlas_provider_latency_seconds', 'Invoked provider attempt latency',
                             ['provider', 'outcome'], registry=REGISTRY)
PROVIDER_TOKENS = Counter('atlas_provider_tokens', 'Provider-reported tokens only',
                          ['provider', 'kind'], registry=REGISTRY)
PROVIDERS = {'needle-local', 'ornith-local', 'inkling-local', 'inkling-hf-router', 'hermes-local', 'lexical-local', 'openclaw-owner', 'jev'}


def provider_label(provider):
    return provider if provider in PROVIDERS else 'other'


def observe_provider(provider, elapsed, outcome, raw=None):
    label = provider_label(provider)
    PROVIDER_LATENCY.labels(label, outcome).observe(max(0, elapsed))
    usage = raw.get('usage') if isinstance(raw, dict) else None
    if outcome == 'success' and isinstance(usage, dict):
        for source, kind in [('prompt_tokens', 'input'), ('completion_tokens', 'output')]:
            value = usage.get(source)
            if type(value) is int and 0 <= value <= 1_000_000_000:
                PROVIDER_TOKENS.labels(label, kind).inc(value)


class QueueDepthCollector:
    """Kombu's Redis channel counts all configured priority lists for each queue.

    Failures emit scrape_success=0 and NO depth values, never a fabricated zero.
    """
    def __init__(self, app=None):
        self.app = app

    def collect(self):
        success = GaugeMetricFamily('atlas_celery_queue_scrape_success', 'Broker queue depth read succeeded')
        depths = GaugeMetricFamily('atlas_celery_queue_depth', 'Waiting broker messages, excluding executing tasks', labels=['queue'])
        try:
            if self.app is None:
                from app.workers.celery_app import celery_app
                app = celery_app
            else:
                app = self.app
            queues = {app.conf.task_default_queue, *[r['queue'] for r in app.conf.task_routes.values()]}
            # Bound label cardinality to the fixed product route configuration.
            with app.connection_for_read(connect_timeout=1) as connection:
                connection.transport_options.update(socket_timeout=1, socket_connect_timeout=1)
                with connection.channel() as channel:
                    values = [(name, channel._size(name)) for name in sorted(queues)]
            for name, value in values:
                depths.add_metric([name], value)
            success.add_metric([], 1)
            yield depths
        except Exception:
            success.add_metric([], 0)
        yield success


REGISTRY.register(QueueDepthCollector())


from starlette.requests import Request


def scrape(request: Request):
    token = os.getenv('ATLAS_METRICS_TOKEN', '')
    provided = request.headers.get('authorization', '')
    if not token or not hmac.compare_digest(provided.encode(), ('Bearer ' + token).encode()):
        return Response(status_code=404)
    return Response(generate_latest(REGISTRY), headers={'Content-Type': CONTENT_TYPE_LATEST})


class MetricsMiddleware:
    """Outermost ASGI middleware also observes rejected API requests and exceptions."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') == '/metrics':
            return await self.app(scope, receive, send)
        started = time.monotonic()
        status = 500
        async def observe_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
            await send(message)
        try:
            await self.app(scope, receive, observe_send)
        finally:
            route = scope.get('route')
            # Never put raw paths or client-provided IDs into metric labels.
            path = getattr(route, 'path', '__unmatched__')
            method = scope.get('method', '')
            if method not in {'GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'}:
                method = 'OTHER'
            HTTP_DURATION.labels(method, path, str(status)).observe(time.monotonic() - started)
