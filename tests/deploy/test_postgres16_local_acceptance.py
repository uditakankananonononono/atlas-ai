"""ATLAS-U-1204 / A09 local Postgres 16 substitute - hermetic artifact contract.

AUTHORED-NOT-RUN (PREP-NORUN): the builder ran none of this. These tests are
deterministic and hermetic: they parse in-repo files and exercise the check's
pure provenance logic against the in-repo alembic scripts (no network, no
docker, no database, no paid API) and genuinely fail if the substitute
artifacts are wrong or weakened. Live loopback/container acceptance is a
separate main-side step; these tests cover the static contract and the
provenance verdict logic that step depends on.

UNVERIFIED: Docker Compose orchestration (build, dependency ordering and
one-shot acceptance run) - not exercised in audit; verified statically only.
"""
import ast
import importlib.util
from pathlib import Path

import yaml

BASE = Path('deploy/local/docker-compose.yml')
OVERRIDE = Path('deploy/local/docker-compose.postgres16.yml')
CHECK = Path('deploy/local/acceptance/postgres16_check.py')
ALEMBIC_INI = Path('alembic.ini')
GAP = 'Supabase-managed hosting, backups, dashboards and Supabase API surface'
UNVERIFIED_GAP = 'UNVERIFIED: Docker Compose orchestration'
EXPECTED_URL = 'postgresql+psycopg://atlas:${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}@postgres:5432/atlas'


def load_check_module():
    """Import the real acceptance check (imports psycopg/alembic only; no
    database connection happens at import time)."""
    spec = importlib.util.spec_from_file_location('postgres16_check', CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    # The named gap and the UNVERIFIED orchestration gap must be stated
    # verbatim in the OVERRIDE file, not only in the check script.
    raw = OVERRIDE.read_text()
    assert GAP in raw, 'override must state the named Supabase gap verbatim'
    assert UNVERIFIED_GAP in raw, 'override must state the UNVERIFIED orchestration gap verbatim'


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


def test_contract_paths_are_exact():
    # The contract names exact deliverable paths; any rename or variant fails.
    assert OVERRIDE.is_file(), 'override must live at deploy/local/docker-compose.postgres16.yml'
    assert CHECK.is_file(), 'check must live at deploy/local/acceptance/postgres16_check.py'
    # Both artifacts must name the override by its exact contract path.
    assert 'deploy/local/docker-compose.postgres16.yml' in CHECK.read_text()
    assert 'deploy/local/docker-compose.postgres16.yml' in OVERRIDE.read_text()
    # No wrong-path variants of the override name anywhere in the artifacts.
    for artifact in (CHECK, OVERRIDE):
        text = artifact.read_text()
        assert 'docker-compose.postgres16.yaml' not in text
        assert 'docker-compose.postgres16.override' not in text


def test_acceptance_check_states_named_gap_and_real_live_checks():
    src = CHECK.read_text()
    tree = ast.parse(src)  # deterministic syntax gate
    docstring = ast.get_docstring(tree)
    assert docstring is not None, 'acceptance check must carry a module docstring'
    # The named gap must be stated verbatim, not paraphrased or omitted.
    assert GAP in docstring
    assert UNVERIFIED_GAP in docstring
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


def test_alembic_provenance_matches_repo_head_and_rejects_bogus():
    """Regression for the audit-reproduced defect: stamping alembic_version
    with 'bogus' previously passed. Provenance must compare the stamped
    version_num against the actual repo alembic head read from the in-repo
    migration scripts via ScriptDirectory."""
    module = load_check_module()
    heads = module.repo_alembic_heads(ALEMBIC_INI)
    assert len(heads) == 1, f'this repo must have exactly one alembic head, got {sorted(heads)}'
    head = next(iter(heads))
    # The real head passes.
    ok, detail = module.provenance_verdict(1, [head], heads)
    assert ok, f'the actual repo head must be accepted: {detail}'
    assert detail == head
    # A bogus marker is rejected.
    ok, detail = module.provenance_verdict(1, ['bogus'], heads)
    assert not ok and 'bogus' in detail
    # A real but non-head (stale) revision is rejected.
    ok, detail = module.provenance_verdict(1, ['0001_baseline'], heads)
    assert not ok, 'a stale non-head revision must be rejected'
    # Multiple rows and an empty stamp are rejected.
    ok, _ = module.provenance_verdict(2, [head, head], heads)
    assert not ok
    ok, _ = module.provenance_verdict(1, [''], heads)
    assert not ok
    # The live check must route its alembic_schema verdict through these
    # functions (no parallel weaker logic).
    src = CHECK.read_text()
    assert 'ScriptDirectory' in src and 'get_heads' in src
    assert 'provenance_verdict(' in src


def test_acceptance_check_is_free_local_only():
    src = CHECK.read_text()
    # No network surface beyond the local Postgres DSN, no paid API client.
    for forbidden in ('import requests', 'import urllib', 'import httpx',
                      'http://', 'https://', 'supabase.co', 'SUPABASE'):
        assert forbidden not in src, f'acceptance check must stay free/local: found {forbidden!r}'
