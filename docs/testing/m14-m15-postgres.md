# M14/M15 embedded PostgreSQL checks

Install project dev dependencies with `python -m pip install -e '.[dev]'`.
`pgserver==0.1.4` and the psycopg binary driver are mandatory, not optional
skip gates for these suites. The existing per-suite fixtures continue to create
PostgreSQL engines and run rollback, migration and concurrent-claim checks.

The autouse `m14_m15_postgres_lifecycle` fixture adds test-scoped cleanup of
embedded servers returned by `pgserver.get_server`. It does not replace the
server API, patch SQL execution, bypass assertions or turn missing dependencies
into skips. Other test families are unaffected. Teardown runs after module-local
fixtures dispose engines. The bundled server's cleanup API remains responsible
for stop/delete policy and cross-process handle tracking.

Run `python tools/run_m14_m15_checks.py` from a trusted checkout after applying
the associated product repair package. It refuses missing dependency imports or
the required remaining-repair test file and sets the child-process PYTHONPATH.
The selection includes every M14/M15 file plus the remaining-repair test file,
without keyword exclusions. Existing PDF engine package skips are a separate
limitation; this fixture does not implement a renderer.
