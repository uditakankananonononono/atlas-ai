"""ATLAS-U-1204 / A09 local Postgres 16 substitute - hermetic artifact contract.

AUTHORED-NOT-RUN (PREP-NORUN): the builder ran none of this. These tests are
deterministic and hermetic: they parse only in-repo files (no network, no
docker, no paid API) and genuinely fail if the substitute artifacts are wrong
or weakened. Live loopback/container acceptance is a separate main-side step;
these tests cover the static contract that step depends on.
"""
import ast
from pathlib import Path

import yaml

BASE = Path('deploy/local/docker-compose.yml')
OVERRIDE = Path('deploy/local/docker-compose.postgres16.yml')
CHECK = Path('deploy/local/acceptance/postgres16_check.py')
GAP = 'Supabase-managed hosting, backups, dashboards and Supabase API surface'
EXPECTED_URL = 'postgresql+psycopg://atlas:${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}@postgres:5432/atlas'


def test_override_is_additive_only_and_preserves_base_wiring():
    base = yaml.safe_load(BASE.read_text())
    override = yaml.safe_load(OVERRIDE.read_text())
    # Additive-only: the override must not redefine any base service; it adds
    # exactly the one-shot acceptance service. Any edit-shaped override fails.
    assert set(override['services']) == {'postgres16-acceptance'}
    # Read-only reference guards: the substitute rides the existing topology.
    assert base['services']['postgres']['image'] == 'pgvector/pgvector:pg16'
    assert base['services']['migrate']['command'] == ['python', 'scripts/migrate.py']
    assert base['services']['migrate']['environment']['ATLAS_DATABASE_URL'] == EXPECTED_URL


def test_acceptance_service_is_driven_by_existing_migration_runner():
    override = yaml.safe_load(OVERRIDE.read_text())
    svc = override['services']['postgres16-acceptance']
    # Same runtime image the migrate/api/worker services build from ../...
    assert svc['build'] == {'context': '../..'}
    # One-shot evidence run, never a long-lived service.
    assert svc['restart'] == 'no'
    assert svc['command'] == ['python', '/opt/atlas-acceptance/postgres16_check.py']
    # Same DSN wiring as the application (psycopg driver, service host, atlas db).
    assert svc['environment']['ATLAS_ENV'] == 'production'
    assert svc['environment']['ATLAS_DATABASE_URL'] == EXPECTED_URL
    # Ordering: Postgres 16 healthy, then the EXISTING alembic migration runner
    # completes, then acceptance runs. Anything weaker fails here.
    assert svc['depends_on'] == {
        'postgres': {'condition': 'service_healthy'},
        'migrate': {'condition': 'service_completed_successfully'},
    }
    # The runtime image does not copy deploy/, so the check is mounted read-only.
    assert './acceptance/postgres16_check.py:/opt/atlas-acceptance/postgres16_check.py:ro' in svc['volumes']


def test_acceptance_check_states_named_gap_and_real_live_checks():
    src = CHECK.read_text()
    tree = ast.parse(src)  # deterministic syntax gate
    docstring = ast.get_docstring(tree)
    assert docstring is not None, 'acceptance check must carry a module docstring'
    # The named gap must be stated verbatim, not paraphrased or omitted.
    assert GAP in docstring
    # Real checks, not constant asserts: server major 16, pgvector installed,
    # a real ANN round-trip, and schema provenance from the migration runner.
    for marker in (
        'psycopg.connect',
        'SHOW server_version_num',
        '// 10000 != 16',
        'CREATE EXTENSION IF NOT EXISTS vector',
        "SELECT extversion FROM pg_extension WHERE extname='vector'",
        'vector(3)',
        '<->',
        'alembic_version',
        'sys.exit',
    ):
        assert marker in src, f'acceptance check is missing real check marker: {marker}'


def test_acceptance_check_is_free_local_only():
    src = CHECK.read_text()
    # No network surface beyond the local Postgres DSN, no paid API client.
    for forbidden in ('import requests', 'import urllib', 'import httpx',
                      'http://', 'https://', 'supabase.co', 'SUPABASE'):
        assert forbidden not in src, f'acceptance check must stay free/local: found {forbidden!r}'
