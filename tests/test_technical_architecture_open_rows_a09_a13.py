"""Exact evidence for the two remaining architecture rows, including acceptance gaps."""
from pathlib import Path
import tomllib
import yaml
from app.runtime.technical_architecture_a01_a33 import BackendContract, EventBus


def test_a09_postgres16_supabase_compatible_configuration_with_live_acceptance_unrun():
    compose=yaml.safe_load(Path('deploy/local/docker-compose.yml').read_text())
    postgres=compose['services']['postgres']
    assert postgres['image']=='pgvector/pgvector:pg16'
    assert postgres['healthcheck']['test']==['CMD-SHELL','pg_isready -U atlas -d atlas']
    manifest=BackendContract().manifest()
    assert manifest['database']=='PostgreSQL 16' and manifest['managed_targets']==['Supabase','Cloud SQL']
    assert not Path('audits/production/supabase-postgres16-acceptance.json').exists()


def test_a13_rabbitmq_topic_contract_is_optional_facade_not_configured_backend():
    binding=EventBus().binding('module.*','workers')
    assert binding=={'backend':'RabbitMQ','optional':True,'exchange_type':'topic','routing_pattern':'module.*','queue':'workers'}
    dependencies=tomllib.loads(Path('pyproject.toml').read_text())['project']['dependencies']
    compose=yaml.safe_load(Path('docker-compose.prod.yml').read_text())
    assert not any('pika' in x.lower() or 'rabbitmq' in x.lower() for x in dependencies)
    assert 'rabbitmq' not in compose['services']
    assert not Path('audits/production/rabbitmq-routing-acceptance.json').exists()
