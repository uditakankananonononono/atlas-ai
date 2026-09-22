from pathlib import Path
import yaml

from app.platform.integrations import CloudStorageAssets


def test_a26_cloud_run_manifest_is_stateless_pinned_autoscaled_and_probed():
    doc=yaml.safe_load(Path('deploy/cloud-run/service.yaml').read_text())
    template=doc['spec']['template'];annotations=template['metadata']['annotations'];container=template['spec']['containers'][0]
    assert doc['apiVersion']=='serving.knative.dev/v1' and doc['kind']=='Service'
    assert annotations['autoscaling.knative.dev/maxScale']=='20'
    assert '@sha256:' in container['image'] and container['startupProbe']['httpGet']['path']=='/health'
    assert not container.get('volumeMounts')


def test_a27_gke_manifest_has_real_workloads_health_resources_and_no_secrets():
    docs=list(yaml.safe_load_all(Path('deploy/k8s/atlas.yaml').read_text()))
    deployments=[d for d in docs if d and d.get('kind')=='Deployment']
    assert deployments
    for deployment in deployments:
        container=deployment['spec']['template']['spec']['containers'][0]
        assert container.get('resources',{}).get('limits')
        assert container.get('livenessProbe') or container.get('readinessProbe')
    raw=Path('deploy/k8s/atlas.yaml').read_text().lower()
    assert 'password:' not in raw and 'api_key:' not in raw


class Blob:
    generation=7
    def __init__(self,name): self.name=name;self.calls=[]
    def upload_from_string(self,data,content_type): self.calls.append((data,content_type))
class Bucket:
    name='atlas-assets'
    def blob(self,name): self.last=Blob(name);return self.last
class Client:
    def bucket(self,name): self.requested=name;self.value=Bucket();return self.value


def test_a28_cloud_storage_adapter_uploads_bytes_content_type_and_generation():
    client=Client();assets=CloudStorageAssets('atlas-assets',client=client)
    result=assets.upload('reports/a.pdf',b'pdf-bytes','application/pdf')
    assert client.requested=='atlas-assets' and client.value.last.calls==[(b'pdf-bytes','application/pdf')]
    assert result=={'bucket':'atlas-assets','name':'reports/a.pdf','generation':'7'}
    config=yaml.safe_load(Path('deploy/cloud-run/storage.yaml').read_text())
    assert config['uniform_bucket_level_access'] and config['versioning']


def test_a29_cloud_sql_target_is_bound_by_instance_annotation_and_secret_database_url():
    doc=yaml.safe_load(Path('deploy/cloud-run/service.yaml').read_text());template=doc['spec']['template']
    assert template['metadata']['annotations']['run.googleapis.com/cloudsql-instances']=='PROJECT:REGION:atlas-postgres'
    env={x['name']:x for x in template['spec']['containers'][0]['env']}
    assert env['ATLAS_DATABASE_URL_SECRET']['value']=='atlas-database-url'
    assert 'ATLAS_DATABASE_URL' not in env
