"""A matching stored edge cannot turn unrelated driver errors into duplicates."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.modules.m09_knowledge_workspace.service import Service
def _sql_service():
 from sqlalchemy import create_engine
 from sqlalchemy.orm import sessionmaker
 from sqlalchemy.pool import StaticPool
 from app.core.database import Base
 from app.modules.m09_knowledge_workspace.repository import SqlGraphRepository
 e=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
 Base.metadata.create_all(e)
 sf=sessionmaker(bind=e,expire_on_commit=False)
 return Service(SqlGraphRepository("t","u",sf))

from app.modules.m09_knowledge_workspace.schemas import NodeCreate,EdgeCreate

@pytest.mark.parametrize('signal',['non_unique','foreign_unique'])
def test_existing_edge_plus_trigger_failure_is_not_duplicate(signal):
    svc=_sql_service();a=svc.create_node(NodeCreate(node_type='note',title='A'));b=svc.create_node(NodeCreate(node_type='note',title='B'))
    request=EdgeCreate(source_id=a.id,target_id=b.id,relationship='related_to')
    svc.create_edge(request)
    with svc.repository.sessions().get_bind().begin() as conn:
        if signal=='non_unique':
            conn.execute(text("CREATE TRIGGER refuse_edge BEFORE INSERT ON m09_edges BEGIN SELECT RAISE(ABORT,'unrelated edge policy failure'); END"))
        else:
            conn.execute(text("CREATE TABLE other_unique(value TEXT UNIQUE)"))
            conn.execute(text("INSERT INTO other_unique VALUES('occupied')"))
            conn.execute(text("CREATE TRIGGER refuse_edge BEFORE INSERT ON m09_edges BEGIN INSERT INTO other_unique VALUES('occupied'); END"))
    with pytest.raises(IntegrityError) as error: svc.create_edge(request)
    assert ('unrelated edge policy failure' if signal=='non_unique' else 'other_unique.value') in str(error.value)
