import hashlib,uuid
from datetime import datetime,timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m09_knowledge_workspace.repository import SqlGraphRepository,NodeRow
from app.modules.m09_knowledge_workspace.service import Service
from app.modules.m09_knowledge_workspace.google_workspace_ingest import ingest_export

def test_existing_export_beyond_first500_must_be_noop(tmp_path):
 e=create_engine('sqlite:///'+str(tmp_path/'m09.db'));Base.metadata.create_all(e);sf=sessionmaker(bind=e);tenant='audit-'+uuid.uuid4().hex;now=datetime.now(timezone.utc);raw=b'My original export';digest=hashlib.sha256(raw).hexdigest()
 with sf.begin() as db:
  for i in range(501):db.add(NodeRow(tenant_id=tenant,id=str(uuid.uuid4()),node_type='file',title='seed',body='body',source_uri=None,source_module='google_docs',external_id=f'doc{i}',metadata_json={'source_sha256':digest,'revision':1},embedding=None,version=1,created_at=now,updated_at=now))
 s=Service(SqlGraphRepository(tenant,'audit',sf))
 result=ingest_export(s,document_id='doc500',export_bytes=raw,export_format='text')
 assert result['status']=='noop'
