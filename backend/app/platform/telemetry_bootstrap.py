"""Opt-in tracing bootstrap for the Atlas API and Celery worker startup paths.

Run only by the local override deploy/local/docker-compose.otel.yml, as
`python -m app.platform.telemetry_bootstrap api|worker`. Nothing imports it, and
importing it does nothing. It edits no Atlas file. For `api` it builds a tracer
provider (exporting OTLP/gRPC in plaintext to ATLAS_OTEL_COLLECTOR_ENDPOINT),
imports app.main, adds one outermost ASGI middleware that wraps each HTTP request
in a server span, optionally registers the probe route, then serves the app with
uvicorn. For `worker` it builds a provider, registers one probe task and starts
the Celery worker with the solo pool.

Network binding and auth, both required, neither a substitute for the other:
- Binding: the override publishes every port of this stack on 127.0.0.1 only
  (the api host port replaces the base file's all-interface mapping). Inside the
  container uvicorn still listens on 0.0.0.0 so that the published mapping works.
- Auth: the probe route GET /_otel/probe is registered on the main API with the
  same Atlas dependency the routers in app.main use (app.auth.context.require_tenant),
  and it sits behind the existing ProductionBoundaryMiddleware.
  There is no unauthenticated path. A request without valid Atlas credentials is refused
  before anything is enqueued.
- ATLAS_OTEL_PROBE=1 is an extra opt-in gate on top of both. Without it the
  route does not exist.

What is traced: every HTTP request through the API (server span only), and the
probe. The probe publishes the task atlas.otel.probe with the W3C traceparent in a
task kwarg, and the worker continues that trace. This is the only API-to-worker
propagation.

What it honestly cannot cover:
- Production-scale trace pipeline and retention.
- Instrumentation coverage: the bootstrap covers app + worker startup paths ONLY; NO claim of full auto-instrumentation coverage of every service/library.
- Image freshness beyond author time: digests are pinned and verified via read-only public registry fetches at author time; they are not a rolling latest.

Also not covered: no database, Redis or outbound-HTTP spans; no propagation for
real Atlas tasks; no metrics or logs; telemetry.configure() is not used and
OTEL_EXPORTER_OTLP_ENDPOINT must stay unset so it stays a no-op.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from opentelemetry import trace
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

PROBE_TASK_NAME = 'atlas.otel.probe'
PROBE_PATH = '/_otel/probe'
MODES = ('api', 'worker')
_ENDPOINT = re.compile(r'^[A-Za-z0-9.-]+:[0-9]{2,5}$')
_PROPAGATOR = TraceContextTextMapPropagator()
_CARRIER_KEYS = ('traceparent', 'tracestate')


@dataclass(frozen=True)
class Settings:
    mode: str
    service_name: str
    endpoint: str
    probe_enabled: bool


def load_settings(mode: str, env: Mapping[str, str]) -> Settings:
    """Validate settings. Raises ValueError rather than silently disabling tracing."""
    if mode not in MODES:
        raise ValueError(f'mode must be one of {MODES}')
    endpoint = (env.get('ATLAS_OTEL_COLLECTOR_ENDPOINT') or '').strip()
    if not _ENDPOINT.match(endpoint):
        raise ValueError('ATLAS_OTEL_COLLECTOR_ENDPOINT must be host:port without a scheme')
    name = (env.get('ATLAS_OTEL_SERVICE_NAME') or f'atlas-{mode}').strip()
    return Settings(mode, name, endpoint, (env.get('ATLAS_OTEL_PROBE') or '') == '1')


def build_provider(service_name: str, span_processor: Any):
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    provider = TracerProvider(resource=Resource.create({'service.name': service_name}))
    provider.add_span_processor(span_processor)
    return provider


def otlp_processor(endpoint: str):
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    return BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))


def _clean_carrier(carrier: Any) -> dict:
    if not isinstance(carrier, Mapping):
        return {}
    return {k: carrier[k] for k in _CARRIER_KEYS if isinstance(carrier.get(k), str)}


def publish_probe(tracer, send_task: Callable[[str, dict], Any]) -> str:
    """Open a producer span, hand its W3C context to the broker call, return the trace id."""
    with tracer.start_as_current_span('atlas.otel.probe.publish', kind=SpanKind.PRODUCER) as span:
        carrier: dict = {}
        _PROPAGATOR.inject(carrier)
        send_task(PROBE_TASK_NAME, {'carrier': carrier})
        return format(span.get_span_context().trace_id, '032x')


def run_probe_task(tracer, carrier: Any) -> dict:
    """Worker side: continue the trace from the carrier, or start a new one if it is unusable."""
    ctx = _PROPAGATOR.extract(_clean_carrier(carrier))
    with tracer.start_as_current_span('atlas.otel.probe.run', context=ctx, kind=SpanKind.CONSUMER) as span:
        return {'trace_id': format(span.get_span_context().trace_id, '032x')}


def register_probe_route(app, *, tracer, send_task, auth_dependency) -> None:
    """Add GET PROBE_PATH to a FastAPI app. The route carries auth_dependency, the same
    way app.main attaches require_tenant to its routers, so it never bypasses auth."""
    from fastapi import Depends

    async def otel_probe():
        return {'trace_id': publish_probe(tracer, send_task), 'task': PROBE_TASK_NAME}

    app.add_api_route(PROBE_PATH, otel_probe, methods=['GET'], include_in_schema=False,
                      dependencies=[Depends(auth_dependency)])


class TraceMiddleware:
    """Pure ASGI middleware: one server span per HTTP request. Never answers a request itself."""

    def __init__(self, app, *, tracer):
        self.app, self.tracer = app, tracer

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            return await self.app(scope, receive, send)
        headers = {k.decode('latin-1').lower(): v.decode('latin-1') for k, v in scope.get('headers', [])}
        ctx = _PROPAGATOR.extract(_clean_carrier(headers))
        path = scope.get('path', '')
        with self.tracer.start_as_current_span(f"{scope.get('method', 'GET')} {path}", context=ctx,
                                               kind=SpanKind.SERVER) as span:
            span.set_attribute('url.path', path)

            async def traced_send(message):
                if message.get('type') == 'http.response.start':
                    span.set_attribute('http.response.status_code', message['status'])
                await send(message)
            await self.app(scope, receive, traced_send)


def _start_api(settings: Settings) -> None:
    import atexit
    import uvicorn
    from app.auth.context import require_tenant
    from app.workers.celery_app import celery_app
    provider = build_provider(settings.service_name, otlp_processor(settings.endpoint))
    trace.set_tracer_provider(provider)
    atexit.register(provider.shutdown)
    from app.main import app
    tracer = provider.get_tracer('atlas.telemetry_bootstrap')
    if settings.probe_enabled:
        register_probe_route(app, tracer=tracer, auth_dependency=require_tenant,
                             send_task=lambda name, kwargs: celery_app.send_task(name, kwargs=kwargs))
    app.add_middleware(TraceMiddleware, tracer=tracer)
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8080')), proxy_headers=True)


def _start_worker(settings: Settings) -> None:
    import atexit
    from app.workers.celery_app import celery_app
    provider = build_provider(settings.service_name, otlp_processor(settings.endpoint))
    trace.set_tracer_provider(provider)
    atexit.register(provider.shutdown)
    tracer = provider.get_tracer('atlas.telemetry_bootstrap')

    @celery_app.task(name=PROBE_TASK_NAME)
    def probe(carrier=None):
        return run_probe_task(tracer, carrier)

    # Solo pool: the batch exporter's thread would not survive prefork children.
    celery_app.worker_main(['worker', '--loglevel=INFO', '--pool=solo'])


def main(argv: list[str] | None = None) -> int:
    import sys
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in MODES:
        raise SystemExit(f'usage: python -m app.platform.telemetry_bootstrap {{{"|".join(MODES)}}}')
    settings = load_settings(args[0], os.environ)
    (_start_api if args[0] == 'api' else _start_worker)(settings)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
