from pathlib import Path
import yaml

def local_compose():
 return yaml.safe_load(Path('deploy/local/docker-compose.yml').read_text())

def test_local_paired_stack_is_free_open_source_persistent_and_password_gated():
 compose=local_compose();services=compose['services'];postgres=services['postgres'];redis=services['redis']
 assert postgres['image']=='pgvector/pgvector:pg16'
 assert redis['image']=='redis:7-alpine'
 assert postgres['volumes']==['atlas-postgres:/var/lib/postgresql/data']
 assert redis['volumes']==['atlas-redis:/data']
 assert compose['volumes']=={'atlas-postgres':{},'atlas-redis':{}}
 assert '${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}' in postgres['environment']['POSTGRES_PASSWORD']
 assert redis['command']==['redis-server','--appendonly','yes','--requirepass','${REDIS_PASSWORD:?set REDIS_PASSWORD}']
 assert '${REDIS_PASSWORD:?set REDIS_PASSWORD}' in redis['environment']['REDIS_PASSWORD']
 assert 'service_healthy' in str(services['api']['depends_on'])

def test_local_runtime_uses_passworded_database_and_redis_urls():
 env=local_compose()['x-runtime']['environment']
 assert '${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}' in env['ATLAS_DATABASE_URL']
 assert '${REDIS_PASSWORD:?set REDIS_PASSWORD}' in env['ATLAS_REDIS_URL']
 assert env['ATLAS_SECRET_PROVIDER']=='platform-environment'
 assert env['ATLAS_TRUST_PLATFORM_SECRETS']=='1'

def test_evidence_matrix_blocks_paid_cloud_claims():
 text=Path('docs/DEPLOYMENT_EVIDENCE_MATRIX.md').read_text()
 assert 'Paid Google Cloud is declined' in text
 assert 'stop rather than incur a paid upgrade' in text

def test_free_tier_doc_never_promises_availability():
 text=Path('deploy/free-tier/platforms.md').read_text()
 assert 'does not claim an account, capacity, uptime or zero cost' in text
 assert 'instead of spending' in text
