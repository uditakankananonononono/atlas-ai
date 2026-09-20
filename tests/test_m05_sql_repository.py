from datetime import datetime,timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m05_outreach_manager.schemas import Contact
from app.modules.m05_outreach_manager.sql_repository import SqlContactRepository

def repo(tmp_path,tenant):
    engine=create_engine(f"sqlite:///{tmp_path/'contacts.db'}")
    Base.metadata.create_all(engine)
    return SqlContactRepository(tenant,sessionmaker(bind=engine,expire_on_commit=False))

def test_sql_repository_is_durable_and_tenant_scoped(tmp_path):
    a=repo(tmp_path,"a"); b=repo(tmp_path,"b"); now=datetime.now(timezone.utc)
    item=Contact(id="c1",project_id="p",name="Dr X",email="x@example.edu",research_topics=["ai"],metadata={},created_at=now,updated_at=now,version=1)
    a.save(item,{"event":"created"})
    assert a.get("c1").email == "x@example.edu"
    assert b.get("c1") is None
    assert a.changes("c1")[0].changes["event"] == "created"
