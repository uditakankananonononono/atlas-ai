"""Embedded PostgreSQL connection, rollback and per-test teardown receipts."""
from sqlalchemy import create_engine, text

PGDATA = None


def test_pgserver_start_and_rollback(tmp_path, m14_m15_postgres_lifecycle):
    import pgserver
    global PGDATA
    PGDATA = tmp_path / 'pg-lifecycle'
    server = pgserver.get_server(PGDATA, cleanup_mode='stop')
    engine = create_engine(server.get_uri().replace('postgresql://', 'postgresql+psycopg://'))
    try:
        with engine.begin() as conn:
            assert conn.scalar(text('SELECT version()')).startswith('PostgreSQL')
            conn.execute(text('CREATE TABLE lifecycle_check (id integer PRIMARY KEY)'))
        with engine.connect() as conn:
            tx = conn.begin()
            conn.execute(text('INSERT INTO lifecycle_check VALUES (1)'))
            tx.rollback()
            assert conn.scalar(text('SELECT count(*) FROM lifecycle_check')) == 0
    finally:
        engine.dispose()


def test_previous_cluster_stopped_after_test():
    assert PGDATA is not None
    assert not (PGDATA / 'postmaster.pid').exists()
