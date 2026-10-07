"""Static image/manifest port contract, no build or deployment acceptance."""
import re
from pathlib import Path
import yaml


def test_k8s_api_port_override_matches_declared_ports_and_probes():
 docker=Path('Dockerfile').read_text()
 default=int(re.search(r'PORT=(\d+)',docker).group(1))
 docs=list(yaml.safe_load_all(Path('deploy/k8s/atlas.yaml').read_text()))
 deployment=next(d for d in docs if d['kind']=='Deployment')
 container=deployment['spec']['template']['spec']['containers'][0]
 env={x['name']:x['value'] for x in container.get('env',[])}
 effective=int(env.get('PORT',default))
 assert effective==container['ports'][0]['containerPort']
 assert effective==container['readinessProbe']['httpGet']['port']
 assert effective==container['livenessProbe']['httpGet']['port']
 service=next(d for d in docs if d['kind']=='Service')
 assert effective==service['spec']['ports'][0]['targetPort']
