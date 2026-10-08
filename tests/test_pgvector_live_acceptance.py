"""Real pgvector storage/query acceptance in a private scratch database."""
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.vector_store import MemoryEmbeddingRow


def test_real_pgvector_1024_cosine_order_tenant_filter_and_dimension_rejection(tmp_path):
    pgserver=pytest.importorskip('pgserver')
    pytest.importorskip('psycopg')
    server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
    url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
    engine=sa.create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(sa.text('CREATE EXTENSION IF NOT EXISTS vector'))
            version=conn.scalar(sa.text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
            assert version
        MemoryEmbeddingRow.__table__.create(engine)
        x=[1.0]+[0.0]*1023
        y=[0.0,1.0]+[0.0]*1022
        with Session(engine) as db:
            for owner,text,vector in [('a','near',x),('a','far',y),('b','secret',x)]:
                db.add(MemoryEmbeddingRow(id=str(uuid.uuid4()),tenant_id=owner,namespace='ltm',
                                         text=text,metadata_json={'canary':text},embedding=vector))
            db.commit()
        engine.dispose()
        engine=sa.create_engine(url)
        with Session(engine) as db:
            distance=MemoryEmbeddingRow.embedding.cosine_distance(x)
            rows=db.execute(sa.select(MemoryEmbeddingRow.text,distance).where(
                MemoryEmbeddingRow.tenant_id=='a',MemoryEmbeddingRow.namespace=='ltm'
            ).order_by(distance)).all()
            assert [r[0] for r in rows]==['near','far']
            assert rows[0][1]==pytest.approx(0.0) and rows[1][1]==pytest.approx(1.0)
            assert db.scalar(sa.select(sa.func.count()).select_from(MemoryEmbeddingRow))==3
        with pytest.raises(sa.exc.DBAPIError):
            with engine.begin() as conn:
                conn.execute(sa.text("INSERT INTO memory_embeddings (id,tenant_id,namespace,text,metadata_json,embedding) VALUES (:id,'a','ltm','bad','{}','[1,0]')"),{'id':str(uuid.uuid4())})
    finally:
        engine.dispose()
        server.cleanup()
