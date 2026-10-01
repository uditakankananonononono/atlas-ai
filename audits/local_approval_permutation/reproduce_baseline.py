"""Run against 313309be using PYTHONPATH=<base-checkout>/backend python this-file."""
import pathlib
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core import discovery
from app.core.collection import CollectionSourceRow
from app.modules.m21_claire.training import TrainingService

engine = create_engine('sqlite:///' + str(pathlib.Path(tempfile.mkdtemp()) / 'native.db'))
Base.metadata.create_all(engine)
discovery.SessionLocal = sessionmaker(bind=engine)
with discovery.SessionLocal.begin() as db:
    candidate = discovery.DiscoveryCandidateRow(tenant_id='test-owner', platform='instagram',
        account_key='public-fixture-only', profile_url='https://example.test/fixture', evidence=[])
    db.add(candidate); db.flush(); cid = candidate.id
sid = discovery.promote_candidate('test-owner', cid)
with discovery.SessionLocal() as db:
    assert db.get(discovery.DiscoveryCandidateRow, cid).status == 'approved'
    assert db.get(CollectionSourceRow, sid).enabled is True
    print('A: no approval supplied; candidate approved and source enabled')
dataset = TrainingService(None).preference_dataset([
    {'options': ['a','b'], 'ranking':['a','a','b']} for _ in range(20)])
assert dataset.examples[0]['ranking'] == ['a','a','b']
print('E: duplicate ranking accepted')
