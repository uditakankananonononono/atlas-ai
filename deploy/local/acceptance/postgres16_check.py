#!/usr/bin/env python3
"""A09 local substitute acceptance: Postgres 16 + pgvector, driven by the existing alembic migration runner.

What this substitute honestly cannot cover: Supabase-managed hosting, backups, dashboards and Supabase API surface.

Runs inside the local Docker Compose topology (deploy/local/docker-compose.yml
plus the additive deploy/local/docker-compose.postgres16.yml override), after
the postgres service is healthy and the existing migrate service
(scripts/migrate.py -> alembic upgrade head) has completed. It verifies, over
the SAME ATLAS_DATABASE_URL wiring the application uses:

1. the server is PostgreSQL 16 (server_version_num major == 16);
2. pgvector is installed (CREATE EXTENSION IF NOT EXISTS vector succeeds);
3. a real vector round-trip returns the exact nearest neighbour;
4. the existing alembic migration runner drove the schema (alembic_version
   holds exactly one non-empty head row).

Every line printed is true of what ran. Free/local only: no paid account, no
cloud service, no Supabase API, no 32GB hardware assumption. Exits 0 only if
every check passes; each failure names its check and exits 1.
"""
import json
import os
import sys

import psycopg

REQUIRED_DRIVER = 'postgresql+psycopg://'


def fail(check, detail):
    print(json.dumps({'check': check, 'ok': False, 'detail': detail}))
    sys.exit(1)


def main():
    url = os.environ.get('ATLAS_DATABASE_URL')
    if not url:
        fail('config', 'ATLAS_DATABASE_URL is not set')
    if not url.startswith(REQUIRED_DRIVER):
        fail('config', 'ATLAS_DATABASE_URL must use the application psycopg driver')
    dsn = url.replace(REQUIRED_DRIVER, 'postgresql://', 1)
    try:
        with psycopg.connect(dsn, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                # 1. PostgreSQL 16 exactly.
                cur.execute('SHOW server_version_num')
                num = int(cur.fetchone()[0])
                if num // 10000 != 16:
                    fail('postgres16', f'server_version_num {num} is not PostgreSQL 16.x')
                print(json.dumps({'check': 'postgres16', 'ok': True, 'server_version_num': num}))
                # 2. pgvector installed.
                cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
                cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
                row = cur.fetchone()
                if not row or not row[0]:
                    fail('pgvector', 'vector extension not installed')
                print(json.dumps({'check': 'pgvector', 'ok': True, 'extversion': row[0]}))
                # 3. Real vector round-trip with exact expected ordering.
                cur.execute('CREATE TEMP TABLE a09_acceptance_items (id int PRIMARY KEY, embedding vector(3))')
                cur.execute("INSERT INTO a09_acceptance_items (id, embedding) VALUES (1, '[1,0,0]'), (2, '[0,1,0]')")
                cur.execute("SELECT id FROM a09_acceptance_items ORDER BY embedding <-> %s LIMIT 1", ('[0.9,0.1,0]',))
                nearest = cur.fetchone()[0]
                if nearest != 1:
                    fail('vector_roundtrip', f'expected nearest id 1, got {nearest}')
                print(json.dumps({'check': 'vector_roundtrip', 'ok': True, 'nearest_id': nearest}))
                # 4. Schema provenance from the existing alembic migration runner.
                cur.execute('SELECT count(*), min(version_num), max(version_num) FROM alembic_version')
                count, vmin, vmax = cur.fetchone()
                if count != 1 or not vmin or vmin != vmax:
                    fail('alembic_schema', f'alembic_version holds {count} row(s): {vmin} / {vmax}')
                print(json.dumps({'check': 'alembic_schema', 'ok': True, 'head': vmin}))
    except SystemExit:
        raise
    except Exception as exc:
        fail('connect', f'{type(exc).__name__}: {exc}')
    sys.exit(0)


if __name__ == '__main__':
    main()
