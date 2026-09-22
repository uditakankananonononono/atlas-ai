import json
from pathlib import Path
import yaml


def test_x01_mtls_manifest_is_strict_but_has_no_runtime_attestation():
    doc=yaml.safe_load(Path('deploy/mtls/strict.yaml').read_text())
    assert doc['spec']['mtls']['mode']=='STRICT'
    assert not Path('audits/production/mtls-runtime-attestation.json').exists()

def test_x02_vault_and_encryption_mechanisms_exist_but_live_vault_is_unattested():
    secrets=Path('backend/app/platform/secrets.py').read_text();cipher=Path('backend/app/platform/encryption.py').read_text()
    assert 'client.is_authenticated()' in secrets and 'read_secret_version' in secrets
    assert 'Fernet' in cipher and 'InvalidToken' in cipher
    assert not Path('audits/production/vault-runtime-attestation.json').exists()

def test_x03_otel_pipeline_is_configured_but_cross_service_trace_is_unattested():
    telemetry=Path('backend/app/platform/telemetry.py').read_text();collector=yaml.safe_load(Path('deploy/otel/collector.yaml').read_text())
    assert 'BatchSpanProcessor' in telemetry and 'OTLPSpanExporter' in telemetry
    assert collector['service']['pipelines']['traces']['exporters']==['googlecloud']
    assert not Path('audits/production/cross-service-trace.json').exists()

def test_x04_cloud_logging_format_and_export_are_configured_not_observed():
    source=Path('backend/app/platform/observability.py').read_text();collector=yaml.safe_load(Path('deploy/otel/collector.yaml').read_text())
    assert 'CloudJsonFormatter' in source and 'trace_id' in source
    assert 'googlecloud' in collector['exporters']
    assert not Path('audits/production/cloud-logging-query.json').exists()

def test_x05_grafana_dashboard_has_real_queries_but_hosted_dashboard_is_unattested():
    doc=json.loads(Path('deploy/grafana/dashboard.json').read_text())
    assert len(doc['panels'])>=3 and all(p['targets'][0]['expr'] for p in doc['panels'])
    assert not Path('audits/production/grafana-dashboard-attestation.json').exists()

def test_x11_compose_acceptance_remains_unrun_without_runtime_attestation():
    compose=yaml.safe_load(Path('deploy/local/docker-compose.yml').read_text())
    assert {'migrate','api','worker','postgres','redis'} <= set(compose['services'])
    assert not Path('audits/production/compose-acceptance.json').exists()

def test_x12_kubernetes_acceptance_remains_unrun_without_cluster():
    docs=list(yaml.safe_load_all(Path('deploy/k8s/atlas.yaml').read_text()))
    assert {'Deployment','Service','HorizontalPodAutoscaler','NetworkPolicy'} <= {d['kind'] for d in docs}
    assert not Path('audits/production/kubernetes-acceptance.json').exists()

def test_x13_ollama_profile_is_bounded_but_32gb_host_acceptance_is_unrun():
    profile=Path('deploy/local/ollama-32gb.env').read_text()
    assert 'ATLAS_AI_CONCURRENCY=1' in profile and 'llama3.1:8b' in profile
    assert not Path('audits/production/ollama-32gb-acceptance.json').exists()

def test_x14_celery_replica_config_exists_but_scaling_benchmark_is_unrun():
    compose=yaml.safe_load(Path('docker-compose.prod.yml').read_text())
    assert compose['services']['collector-worker']['deploy']['replicas']==2
    assert compose['services']['ai-worker']['deploy']['replicas']==2
    assert not Path('audits/production/celery-scaling-benchmark.json').exists()
