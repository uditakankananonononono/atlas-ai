"""M09 graph service layer on a real PostgreSQL (pgserver): alembic migrations, node/edge writes, neighborhood read,
versioned update conflict, and tenant isolation both ways. Service layer only: the HTTP route, auth and the production
embedding path are NOT exercised (the route builds Service without an embedder). Skips when pgserver is unavailable."""
import json
import os
import subprocess
import sys
import textwrap

import pytest

SCRIPT = textwrap.dedent('''
    import json
    from app.modules.m09_knowledge_workspace.repository import SqlGraphRepository
    from app.modules.m09_knowledge_workspace.service import ConflictError, Service
    from app.modules.m09_knowledge_workspace.schemas import NodeCreate, NodeUpdate, EdgeCreate, Edge, Relationship
    from datetime import datetime, timezone
    a_svc = Service(SqlGraphRepository("tenant-a", "actor-a"))
    b_svc = Service(SqlGraphRepository("tenant-b", "actor-b"))
    a = a_svc.create_node(NodeCreate(node_type="note", title="PG paris plan", body="A note about visiting Paris."))
    b = a_svc.create_node(NodeCreate(node_type="task", title="PG review note", body="Read the plan."))
    node_a = a["node"] if isinstance(a, dict) else getattr(a, "node", a)
    node_b = b["node"] if isinstance(b, dict) else getattr(b, "node", b)
    a_svc.create_edge(EdgeCreate(source_id=node_b.id, target_id=node_a.id, relationship="references"))
    hood = a_svc.neighborhood(node_a.id, depth=2)
    updated = a_svc.update_node(node_a.id, NodeUpdate(expected_version=1, title="PG paris plan v2"))
    try:
        a_svc.update_node(node_a.id, NodeUpdate(expected_version=1, title="stale write"))
        stale = "accepted"
    except ConflictError:
        stale = "conflict"
    b_node = b_svc.create_node(NodeCreate(node_type="note", title="tenant b only"))
    b_node = b_node["node"] if isinstance(b_node, dict) else getattr(b_node, "node", b_node)
    try:
        a_svc.neighborhood(b_node.id, depth=1)
        a_sees_b = True
    except LookupError as error:
        assert error.args == (b_node.id,), error
        a_sees_b = False
    try:
        b_svc.neighborhood(node_a.id, depth=1)
        b_sees_a = True
    except LookupError as error:
        assert error.args == (node_a.id,), error
        b_sees_a = False
    # Repository-level overlapping IDs make the tenant predicate essential; UUID
    # generation in Service otherwise hides this leak when tenants have disjoint IDs.
    foreign_edge = Edge(id="tenant-b-edge", source_id=node_a.id, target_id=node_b.id,
                        relationship=Relationship.REFERENCES, confidence=1,
                        created_at=datetime.now(timezone.utc))
    b_svc.repository.save_edge(foreign_edge)
    assert {e.id for e in b_svc.repository.edges_for({node_a.id})} == {foreign_edge.id}
    assert foreign_edge.id not in {e.id for e in a_svc.repository.edges_for({node_a.id})}
    assert b_svc.repository.edges_for({b_node.id}) == []
    assert {e.id for e in a_svc.neighborhood(node_a.id).edges} == {e.id for e in hood.edges}
    print(json.dumps({"nodes": len(hood.nodes), "edges": len(hood.edges), "version_after_update": updated.version,
                      "stale_update": stale, "a_nodes": len(a_svc.repository.list_nodes(limit=50)),
                      "b_nodes": len(b_svc.repository.list_nodes(limit=50)), "a_sees_b": a_sees_b, "b_sees_a": b_sees_a}))
''')


def test_m09_graph_data_path_on_real_postgres(tmp_path):
    pgserver = pytest.importorskip("pgserver")
    pytest.importorskip("psycopg")
    server = pgserver.get_server(tmp_path / "pg", cleanup_mode="stop")
    url = server.get_uri().replace("postgresql://", "postgresql+psycopg://")
    env = {**os.environ, "ATLAS_DATABASE_URL": url, "ATLAS_ENV": "production", "PYTHONPATH": "backend"}
    migrate = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, text=True, capture_output=True, timeout=120)
    assert migrate.returncode == 0, migrate.stderr[-800:]
    run = subprocess.run([sys.executable, "-c", SCRIPT], env=env, text=True, capture_output=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    result = json.loads(run.stdout.strip().splitlines()[-1])
    assert result == {"nodes": 2, "edges": 1, "version_after_update": 2, "stale_update": "conflict",
                      "a_nodes": 2, "b_nodes": 1, "a_sees_b": False, "b_sees_a": False}, result
    import psycopg
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as conn:
        counts = dict(conn.execute("select tenant_id, count(*) from m09_nodes group by 1").fetchall())
    assert counts == {"tenant-a": 2, "tenant-b": 1}, counts
