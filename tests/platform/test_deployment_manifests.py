import json
from pathlib import Path
import yaml
def test_kubernetes_has_deployment_service_hpa_and_default_deny():
 docs=list(yaml.safe_load_all(Path('deploy/k8s/atlas.yaml').read_text()));kinds={x['kind'] for x in docs};assert {'Deployment','Service','HorizontalPodAutoscaler','NetworkPolicy'}<=kinds
def test_strict_mtls_and_otel_cloud_prometheus_and_grafana():
 mtls=yaml.safe_load(Path('deploy/mtls/strict.yaml').read_text());assert mtls['spec']['mtls']['mode']=='STRICT'
 otel=yaml.safe_load(Path('deploy/otel/collector.yaml').read_text());assert {'googlecloud','prometheus'}<=set(otel['exporters'])
 dash=json.loads(Path('deploy/grafana/dashboard.json').read_text());assert len(dash['panels'])>=3
