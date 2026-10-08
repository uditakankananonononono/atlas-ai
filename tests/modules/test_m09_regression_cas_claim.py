from datetime import datetime,timezone
from sqlalchemy import create_engine,event,select,func
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m09_knowledge_workspace.repository import SqlGraphRepository,NodeRow,AuditRow
from app.modules.m09_knowledge_workspace.schemas import Node,NodeType

def test_competitor_between_read_and_write_preserved_without_loser_audit(tmp_path):
 e=create_engine(f'sqlite:///{tmp_path / "cas.db"}');Base.metadata.create_all(e);sf=sessionmaker(bind=e,expire_on_commit=False);r=SqlGraphRepository('t','u',sf);now=datetime.now(timezone.utc)
 node=Node(id='n',node_type=NodeType.NOTE,title='original',version=1,created_at=now,updated_at=now)
 r.save_node(node);fired=[]
 @event.listens_for(e,'before_cursor_execute')
 def competitor(conn,cursor,statement,params,ctx,many):
  if not fired and statement.lstrip().upper().startswith('UPDATE') and 'm09_nodes' in statement:
   fired.append(True);winner=node.model_copy(update={'title':'winner','version':2});assert r.save_node(winner,'node.updated',expected_version=1)
 loser=node.model_copy(update={'title':'loser','version':2});assert r.save_node(loser,'node.updated',expected_version=1) is None
 assert r.get_node('n').title=='winner'
 with sf() as db:assert db.scalar(select(func.count()).select_from(AuditRow))==2
