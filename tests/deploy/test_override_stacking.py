"""Actual Compose config rendering only; no containers or service acceptance."""
import copy,json,os,subprocess
from pathlib import Path
import pytest,yaml
ROOT=Path(__file__).resolve().parents[2]
PAIRS={'vault+loki':['vault','loki'],'otel+loki':['otel','loki'],'rabbitmq+vault':['vault','rabbitmq'],'mtls+vault':['vault','mtls'],'grafana+otel':['grafana','otel']}
EP=['python','-m','app.platform.vault_dev_adapter','--volume','/vault-fallback-dev','--']
ENV={'POSTGRES_PASSWORD':'parse-only','REDIS_PASSWORD':'parse-only','ATLAS_TOKEN_KEY':'parse-only','ATLAS_API_KEY_ENCRYPTION_KEY':'parse-only','ATLAS_OIDC_ISSUER':'https://issuer.invalid','ATLAS_OIDC_AUDIENCE':'parse-only','RABBITMQ_PASSWORD':'parse-only','ATLAS_API_DOCKER_LOG_DIR':'/tmp/api-parse-only','ATLAS_WORKER_DOCKER_LOG_DIR':'/tmp/worker-parse-only'}
def render(pair,order=None,layer=None):
 exe=os.environ.get('ATLAS_COMPOSE_BINARY')
 if not exe:pytest.fail('ATLAS_COMPOSE_BINARY required: real Compose config acceptance cannot be replaced by YAML emulation')
 args=[exe,'--project-directory',str(ROOT/'deploy/local'),'-f',str(ROOT/'deploy/local/docker-compose.yml')]
 for name in (order or PAIRS[pair]):args+=['-f',str(ROOT/f'deploy/local/docker-compose.{name}.yml')]
 args+=['-f',str(layer or ROOT/f'deploy/local/stacking/{pair.replace("+","-")}.yml'),'config','--format','json']
 r=subprocess.run(args,cwd=ROOT,env={**os.environ,**ENV},capture_output=True,text=True,timeout=15)
 assert r.returncode==0,r.stderr
 return json.loads(r.stdout)
@pytest.mark.parametrize('pair',PAIRS)
def test_real_compose_pair_contract(pair):
 from scripts.compose_stack_contract import validate
 model=render(pair);validate(pair,PAIRS[pair],model,ROOT)
 s=model['services'];assert set(s)>= {'api','worker','migrate','postgres','redis'}
 for service in s.values():
  for port in service.get('ports',[]):assert port['host_ip']=='127.0.0.1'
 if 'vault' in pair:
  for role in ('api','worker','migrate'):
   assert s[role]['entrypoint']==EP
   assert s[role]['environment']['ATLAS_DEV_NO_AUTH']=='0'
   assert s[role]['environment']['ATLAS_TOKEN_KEY']==''
   assert any(v['target']=='/vault-fallback-dev' for v in s[role]['volumes'])
 if 'loki' in pair:
  assert set(s['loki']['networks'])=={'atlas-log-sink','atlas-log-host'}
  assert model['networks']['atlas-log-sink']['internal'] is True
  assert model['networks']['atlas-log-host'].get('internal',False) is False
  assert s['promtail']['networks']=={'atlas-log-sink':None}
 if pair=='vault+loki':
  for role in ('api','worker'):assert s[role]['command']==['python','-m','app.platform.logging_bootstrap',role]
 if pair=='otel+loki':
  for role in ('api','worker'):assert s[role]['command']==['python','-m','app.platform.stacked_observability_bootstrap',role]
  assert s['api']['environment']['ATLAS_OTEL_PROBE']=='1'
 if pair=='rabbitmq+vault':
  for role in ('api','worker'):
   assert 'celery_broker_config --print-url' in s[role]['command'][2]
   assert s[role]['build']['dockerfile']=='deploy/local/Dockerfile.rabbitmq'
 if pair=='mtls+vault':
  assert 'sslmode=verify-full' in s['api']['environment']['ATLAS_DATABASE_URL']
  assert '--ssl-cert-reqs 2' in s['api']['command'][2]
  assert 'app.workers.celery_tls_config' in s['worker']['command'][2]
 if pair=='grafana+otel':assert s['grafana']['environment']['GF_AUTH_ANONYMOUS_ENABLED']=='false'
@pytest.mark.parametrize('pair',PAIRS)
def test_swapped_order_is_rejected(pair):
 from scripts.compose_stack_contract import validate
 with pytest.raises(ValueError,match='ordered recipe'):validate(pair,list(reversed(PAIRS[pair])),render(pair,order=list(reversed(PAIRS[pair]))),ROOT)
@pytest.mark.parametrize('pair',PAIRS)
@pytest.mark.parametrize('mutation',['command','entrypoint','network','loopback'])
def test_contract_rejects_model_drift(pair,mutation):
 from scripts.compose_stack_contract import validate
 model=render(pair)
 if mutation=='command':model['services']['api']['command']=['echo','lost-startup']
 elif mutation=='entrypoint':
  if 'vault' not in pair:return
  model['services']['api'].pop('entrypoint')
 elif mutation=='network':
  service='loki' if 'loki' in pair else 'api'
  model['services'][service]['networks'].pop(next(iter(model['services'][service]['networks'])))
 else:model['services']['api']['ports'][0].pop('host_ip')
 with pytest.raises(ValueError):validate(pair,PAIRS[pair],model,ROOT)

def test_combined_bootstrap_preserves_logging_and_otel_startup(monkeypatch):
 from app.platform import stacked_observability_bootstrap as b
 calls=[]
 monkeypatch.setattr(b,'install_json_logging',lambda:calls.append('json'))
 monkeypatch.setattr(b,'connect_worker_logging',lambda:calls.append('worker-json'))
 monkeypatch.setattr(b,'start_api',lambda settings:calls.append(('api',settings)))
 monkeypatch.setattr(b.telemetry,'_start_worker',lambda settings:calls.append(('worker',settings)))
 monkeypatch.setenv('ATLAS_OTEL_COLLECTOR_ENDPOINT','otel-collector:4317')
 b.main(['api']);assert calls[0]=='json' and calls[1][0]=='api'
 calls.clear();b.main(['worker']);assert calls[:2]==['json','worker-json'] and calls[2][0]=='worker'
 with pytest.raises(SystemExit):b.main(['bad'])

def test_api_startup_passes_json_log_config_with_trace_probe(monkeypatch):
 from app.platform import stacked_observability_bootstrap as b
 import uvicorn
 from app.main import app
 from app.workers.celery_app import celery_app
 calls=[]
 class Provider:
  def shutdown(self):pass
  def get_tracer(self,name):return 'tracer'
 monkeypatch.setattr(b.telemetry,'build_provider',lambda name,proc:Provider())
 monkeypatch.setattr(b.telemetry,'otlp_processor',lambda endpoint:'processor')
 monkeypatch.setattr(b.telemetry.trace,'set_tracer_provider',lambda provider:None)
 monkeypatch.setattr(b.telemetry,'register_probe_route',lambda *a,**kw:calls.append(kw))
 monkeypatch.setattr(app,'add_middleware',lambda *a,**kw:calls.append(('middleware',kw)))
 monkeypatch.setattr(uvicorn,'run',lambda *a,**kw:calls.append(('run',kw)))
 b.start_api(b.telemetry.Settings('api','atlas-api','otel-collector:4317',True))
 assert calls[0]['auth_dependency'] and calls[0]['tracer']=='tracer'
 assert calls[1]==('middleware',{'tracer':'tracer'})
 assert calls[2][1]['log_config']['formatters']['atlas_json']['()']=='app.platform.observability.CloudJsonFormatter'

def test_original_compose_sources_match_read_receipts():
 import hashlib
 pins=json.loads((ROOT/'deploy/local/stacking/read-receipts.json').read_text())
 files={'docker-compose.yml','deploy/local/docker-compose.yml',*[str(p.relative_to(ROOT)) for p in (ROOT/'deploy/local').glob('docker-compose.*.yml')]}
 assert set(pins)==files
 for path,digest in pins.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest

@pytest.mark.parametrize('pair',PAIRS)
def test_actual_order_swap_detected_or_declared_equivalent(pair):
 from scripts.compose_stack_contract import normalized
 normal=render(pair);swapped=render(pair,order=list(reversed(PAIRS[pair])))
 if pair in ('grafana+otel','otel+loki'):
  # Grafana/OTEL disjoint; final combined command normalizes OTEL/Loki.
  assert normalized(normal,ROOT)==normalized(swapped,ROOT)
 else:assert normal['services']['api']['command']!=swapped['services']['api']['command']
