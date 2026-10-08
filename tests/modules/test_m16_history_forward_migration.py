import os,subprocess,sys
import pytest
from sqlalchemy import create_engine,text,inspect
@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_m16_unique_forward_preserves_published_history(tmp_path,kind):
 if kind=='postgres':
  pg=pytest.importorskip('pgserver').get_server(tmp_path/'pg',cleanup_mode='stop');url=pg.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path / "history.db"}'
 env={**os.environ,'ATLAS_DATABASE_URL':url,'ATLAS_ENV':'production','PYTHONPATH':os.environ.get('PYTHONPATH','backend')}
 def migrate(*args):return subprocess.run([sys.executable,'-m','alembic',*args],env=env,capture_output=True,text=True,timeout=120)
 r=migrate('upgrade','20261007_m20_model_unknown');assert r.returncode==0,r.stderr
 e=create_engine(url)
 with e.begin() as c:
  # Initial schema metadata may already carry new constraint; recreate legacy surface explicitly.
  c.execute(text('DROP TABLE m16_events'))
  c.execute(text('CREATE TABLE m16_events(tenant_id VARCHAR(120) NOT NULL,id VARCHAR(36) NOT NULL,sequence INTEGER)'))
  c.execute(text("INSERT INTO m16_events VALUES('t','e',1),('t','e',2)"))
 r=migrate('upgrade','20261008_m16_identity_forward');assert r.returncode!=0 and 'owner-reviewed reconciliation' in r.stderr
 with e.connect() as c:
  assert c.scalar(text('SELECT count(*) FROM m16_events'))==2
  assert c.scalar(text('SELECT version_num FROM alembic_version'))=='20261007_m20_model_unknown'
 with e.begin() as c:c.execute(text('DELETE FROM m16_events WHERE sequence=2'))
 r=migrate('upgrade','20261008_m16_identity_forward');assert r.returncode==0,r.stderr
 with e.connect() as c:assert c.scalar(text('SELECT version_num FROM alembic_version'))=='20261008_m16_identity_forward'
 assert any(x['unique'] and x['column_names']==['tenant_id','id'] for x in inspect(e).get_indexes('m16_events'))
 r=migrate('downgrade','20261007_m20_model_unknown');assert r.returncode!=0 and 'Cannot remove M16 identity protection' in r.stderr
 with e.connect() as c:assert c.scalar(text('SELECT count(*) FROM m16_events'))==1
