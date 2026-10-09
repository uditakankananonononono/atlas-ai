"""Real fixture extension initialization, no fake vector column/type removal."""
import pytest
from sqlalchemy import create_engine, text
from app.core.database import Base
from app.core.vector_store import MemoryEmbeddingRow


@pytest.mark.parametrize('database', ['sqlite', 'postgres'])
def test_fixture_vector_initialization_idempotent_and_metadata_complete(tmp_path, database, m24_postgres_schema):
    if database == 'postgres':
        import pgserver
        pg = pgserver.get_server(tmp_path / 'pg', cleanup_mode='stop')
        uri = pg.get_uri().replace('postgresql://', 'postgresql+psycopg://')
    else:
        uri = f'sqlite:///{tmp_path}/fixture.db'
    engine = create_engine(uri)
    try:
        if database == 'postgres':
            with engine.begin() as db:
                assert db.scalar(text("SELECT count(*) FROM pg_extension WHERE extname='vector'")) == 0
        m24_postgres_schema(engine)
        m24_postgres_schema(engine)
        Base.metadata.create_all(engine)
        with engine.begin() as db:
            if database == 'postgres':
                assert db.scalar(text("SELECT count(*) FROM pg_extension WHERE extname='vector'")) == 1
            assert db.scalar(text('SELECT count(*) FROM memory_embeddings')) == 0
    finally:
        engine.dispose()
        if database == 'postgres':
            pg.cleanup()
