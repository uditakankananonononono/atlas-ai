"""Source receipt null/presence/ambiguity against real local databases."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m00_approval_center.service import Service,ApprovalRequestRow,ApprovalEventRow

@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_source_query_excludes_missing_null_keys_before_limit_and_detects_duplicates(tmp_path,kind):
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/source.db'
 engine=create_engine(url)
 for table in (ApprovalRequestRow.__table__,ApprovalEventRow.__table__):table.create(engine)
 svc=Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False))
 def add(payload,user='a'):return svc.submit(user_id=user,module_id=10,action_type='send_email_reply',payload=payload)
 for _ in range(3):add({'body':'fixture'})
 add({'body':'fixture','thread_id':None},'b')
 valid=add({'body':'fixture','thread_id':None})
 query=lambda:svc.matching_source_approvals(user_id='a',module_id=10,action_type='send_email_reply',payload={'body':'fixture','thread_id':None})
 assert [x['id'] for x in query()]==[valid['id']]
 duplicate=add({'body':'fixture','thread_id':None})
 assert {x['id'] for x in query()}=={valid['id'],duplicate['id']}
 engine.dispose()
