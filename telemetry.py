"""OpenTelemetry setup; no-op unless OTLP endpoint is configured."""
from __future__ import annotations
import os
def configure(service_name:str='atlas-api'):
 endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
 if not endpoint:return None
 from opentelemetry import trace
 from opentelemetry.sdk.resources import Resource
 from opentelemetry.sdk.trace import TracerProvider
 from opentelemetry.sdk.trace.export import BatchSpanProcessor
 from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
 provider=TracerProvider(resource=Resource.create({'service.name':service_name}));provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint,insecure=False)));trace.set_tracer_provider(provider);return provider
