#!/usr/bin/env python3
"""A09 local substitute acceptance: Postgres 16 + pgvector, driven by the existing alembic migration runner.

What this substitute honestly cannot cover: Supabase-managed hosting, backups, dashboards and Supabase API surface.

UNVERIFIED: Docker Compose orchestration (build, dependency ordering and
one-shot acceptance run) - not exercised in audit; verified statically only.

Runs inside the local Docker Compose topology (deploy/local/docker-compose.yml
plus the additive deploy/local/docker-compose.postgres16.yml override), after
the postgres service is healthy and the existing migrate service
(scripts/migrate.py -> alembic upgrade head) has completed. It verifies, over
the SAME ATLAS_DATABASE_URL wiring the application uses:

1. the server is PostgreSQL 16 (server_version_num major == 16);
2. pgvector is installed (CREATE EXTENSION IF NOT EXISTS vector succeeds);
3. a real vector round-trip returns the exact nearest neighbour;
4. the existing alembic migration runner drove the schema to THIS repo's
   actual head: alembic_version holds exactly one row whose version_num
   equals the repo's single alembic head revision, read from the in-repo
   migration scripts via alembic ScriptDirectory. A bogus or stale stamp,
   extra rows or an empty version are named failures, never a pass.

Every line printed is true of what ran. Free/local only: no paid account, no
cloud service, no Supabase API, no 32GB hardware assumption. Exits 0 only if
every check passes; each failure names its check and exits 1.
"""
import json
import os
import sys
from pathlib import Path

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory

REQUIRED_DRIVER = 'postgresql+psycopg://'
ALEMBIC_INI = Path('alembic.ini')


def repo_alembic_heads(ini_path):
    """The actual alembic head revision(s) of this repo, from the in-repo
    migration scripts via ScriptDirectory (no database involved)."""
    ini_path = Path(ini_path)
    cfg = Config(str(ini_path))
    script_location = cfg.get_main_option('script_location')
    if script_location and not os.path.isabs(script_location):
        # Pin resolution to the ini file's directory, independent of CWD.
        cfg.set_main_option('script_location', str(ini_path.resolve().parent / script_location))
    return set(ScriptDirectory.from_config(cfg).get_heads())


def provenance_verdict(count, version_nums, repo_heads):
    """Accept only when alembic_version holds exactly this repo's single head.

    Returns (ok, detail). A bogus or stale stamp, multiple rows, an empty
    version or a multi-head repo is a named failure, never a pass.
    """
    if count != 1 or len(version_nums) != 1:
        return False, f'alembic_version holds {count} row(s), expected exactly 1'
    stamped = version_nums[0]
    if not stamped:
        return False, 'alembic_version version_num is empty'
    if len(repo_heads) != 1:
        return False, f'repo has {len(repo_heads)} alembic heads, expected exactly 1'
    head = next(iter(repo_heads))
    if stamped != head:
        return False, f'stamped version_num {stamped!r} is not the repo alembic head {head!r}'
    return True, head


def fail(check, detail):
    print(json.dumps({'check': check, 'ok': False, 'detail': str(detail)[:1000]}))
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
                # 4. Schema provenance: the stamped version must BE this repo's
                # actual alembic head, read from the in-repo migration scripts.
                cur.execute('SELECT version_num FROM alembic_version')
                version_nums = [r[0] for r in cur.fetchall()]
                ok, detail = provenance_verdict(len(version_nums), version_nums,
                                                repo_alembic_heads(ALEMBIC_INI))
                if not ok:
                    fail('alembic_schema', detail)
                print(json.dumps({'check': 'alembic_schema', 'ok': True, 'head': detail}))
    except SystemExit:
        raise
    except Exception as exc:
        fail('connect', f'{type(exc).__name__}: {exc}')
    sys.exit(0)


if __name__ == '__main__':
    main()
