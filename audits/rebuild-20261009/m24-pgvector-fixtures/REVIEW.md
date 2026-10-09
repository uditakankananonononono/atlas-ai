# Fresh PostgreSQL fixture pgvector repair

Base: 5c57fa95b361c1cf4926abbb73992a04d032a43a.
Branch: m24-pgvector-fixture-repair-20261009.

## Change and boundary

One shared pytest fixture initializes vector in each of the seven private M24
PostgreSQL databases before Base.metadata.create_all. SQLite is a no-op.
CREATE EXTENSION IF NOT EXISTS is followed by a real pg_extension assertion.
Missing installation privileges or extension binaries fail, without a skip,
mock, metadata removal, provider change, or workflow-only patch.
Migration fixtures are unchanged: their existing Alembic path installs vector.
The new regression test imports MemoryEmbeddingRow at collection, starts with
no installed extension in a fresh PostgreSQL database, runs initialization
twice, and creates and queries the actual memory_embeddings table. Its SQLite
node checks that the same metadata still works there.

This is test-fixture repair, not a production migration or runtime activation.
No backend product files, workflows, existing assertion bodies, readiness,
provider adapters, workers, models, money paths, Claire, or memo3 changed.
The two known tests/test_billing.py failures remain frozen.

## Diagnosis and availability

The complete backend CI at fbb1fc78 recorded 189 setup errors from uninitialized
fresh PostgreSQL fixture databases. The CI service database's vector extension
cannot initialize different private pgserver databases.

https://github.com/uditakankananonononono/atlas-ai/actions/runs/37950375094
https://github.com/uditakankananonononono/atlas-ai/actions/runs/37950375094/job/113887714628

Installed pgserver 0.1.4 bundles PostgreSQL 16.2 and vector 0.6.2 in this
execution environment. Before edits, actual pg_available_extensions and
CREATE EXTENSION in a fresh database confirmed availability and installation.
That environmental observation is not a promise for every future host:
unsupported builds fail visibly and require providing the extension binaries.

## Builder receipts

Environment: /tmp/atlas-memo3-venv/bin/python, Python 3.12, PYTHONPATH=backend.
The existing-module runs explicitly import app.core.vector_store before
pytest.main, reproducing full collection's shared metadata instead of relying
on isolated collection accidentally omitting vector.

- RED-before-extension.log: original type vector missing setup reproduction.
- GREEN-forced-vector-first.log: original write-ahead PostgreSQL node, 1 PASS.
- GREEN-generation116.log: new regression pair plus 114 generation nonmigration
  nodes, 116 PASS, 2 deselected.
- GREEN-inbox94.log: 94 PASS, 2 migration nodes deselected.
- GREEN-slice4-104.log: cancellation and reconciliation, 104 PASS, 4 deselected.
- GREEN-invoice76.log: 76 PASS, 2 migration nodes deselected.
- GREEN-checkout84.log: 84 PASS, 2 migration nodes deselected.
- GREEN-storage.log: 27 PASS, 2 migration nodes deselected.
- GREEN-migrations-storage-checkout.log: 4 PASS, 111 deselected.
- GREEN-migrations-invoice-cancel.log: 4 PASS, 142 deselected.
- GREEN-migrations-reconciliation-inbox.log: 4 PASS, 132 deselected.
- GREEN-migrations-generation.log: 2 PASS, 114 deselected.
- GREEN-restored2.log: final new regression pair, 2 PASS.

Unique named coverage is 515 nodes: 513 existing M24 nodes and 2 new nodes.
The single-node and restored-pair runs are repeated controls, not extra coverage.

GREEN-migrations.log is an interrupted 120-second combined attempt, with four
progress dots and no completion summary. Despite its filename, it is NOT a
PASS receipt. Complete split runs above replace its unfinished coverage, not
its historical outcome. No full-suite CI result is claimed by these receipts.

## Decisive negative control

Run with the same interpreter:
python audits/rebuild-20261009/m24-pgvector-fixtures/control-initializer-removal.py

The harness removes both CREATE EXTENSION and the initializer's verification
assertion in disposable local bytes. The PostgreSQL regression fails with
UndefinedObject: type "vector" does not exist during actual metadata creation;
the SQLite node passes. Exact original conftest bytes restore in finally.
RED-initializer-removal.log records the 1 FAIL / 1 PASS shape. Removing both
statements avoids treating the redundant count assertion as proof of the DDL.
Final restored pair is green. The harness is not collected by pytest.

## Handoff

Candidate is ready for independent review. Main is still 5c57fa95 at preparation.
After independent gate and landing, a new complete backend CI run is required.
Expected old billing failures must remain visible; targeted passes do not make
whole CI green. There is no new full CI result in this candidate packet.
