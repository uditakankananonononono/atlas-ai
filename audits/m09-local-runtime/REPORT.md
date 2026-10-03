# M09 real local runtime repair

Builder verdict: SCOPED. Independent acceptance remains required.

Base: 313309be. Local branch: local/m09-real-local-runtime. No push and no main changes.

## Reproduced

- The actual default M09 API dependency runs trained FastEmbed ONNX on CPU and spaCy NER, not dummy vectors or empty adapters.
- Both the isolated M09 router and the full `app.main` application were exercised with real models, HTTP create/update, real tenant-scoped SQLite persistence, and pending suggestions.
- Model: BAAI/bge-small-en-v1.5, 384 dimensions, quantized ONNX artifact from FastEmbed's qdrant/bge-small-en-v1.5-onnx-q source. Entity model: en_core_web_sm 3.8.0.
- Identical text produced cosine 1.0 and a pending related_to suggestion. Actual Paris extraction produced a pending mentions suggestion. There is no paraphrase quality acceptance claim.
- Unsupported configuration produces HTTP 503 with zero stored nodes. A separate missing trained spaCy model attempt also produced HTTP 503 and zero stored nodes. Inference failure tests verify no creation/update is saved before both pipelines succeed.
- Legacy/unversioned and incompatible embedding identities are skipped and counted. Equal vector dimension alone is not sufficient. Model, artifact and preprocessing-file hashes are persisted with the node.
- Read-only paths do not need models. No cloud/key fallback is added; shared core defaults are unchanged.
- M25 stays a 16-bin SHA-256 token-hash plus lexical-overlap heuristic, now explicitly labelled in class documentation and returned retrieval metadata. No learned M25 model is claimed.

Final run: 289 tests passed across every test_m09*.py and test_m25*.py file on Linux Python 3.12.14. See test-output.txt. The earlier broader attempt failed collection for an uninstalled unrelated bs4 dependency; its log is preserved. After required dependency installation the full entrypoint imported and all 282 tests passed on the initial candidate (19fc49f); the revised candidate adds seven real-runtime safety tests.

## Costs and limits

First public model download was approximately 66.5 MB ONNX plus tokenizer/config files; spaCy wheel was 12.8 MB. Models are NOT included in this source bundle; setup needs internet once and writable cache storage. Local inference needs neither an account nor a paid API. A cached Linux diagnostic used two ONNX CPU threads; load/runtime and peak RSS measurements are in diagnostic.json, not a Dell performance guarantee. Initial Python 3.10 tests passed, but final evidence is on the declared-supported Python 3.12 series.

English models; embedding truncates at 512 tokens. Existing threshold 0.78 unchanged, uncalibrated. Exact title matching only for mentions, and duplicate titles may create multiple suggestions. Diagnostics show spaCy mislabelled Alice as ORG, a concrete NER limitation. Scores are not probabilities. Comparison is limited to the first 500 repository nodes. Old vectors require node updates, not an automatic migration.

Node, audit and suggestion writes now share a transaction; review status, edge and audit are also atomic. SQL expected-version compare-and-swap prevents lost updates. Pending proposals are invalidated on either endpoint edit and approval rechecks captured versions. Real SQLite regressions reproduced these failures before the fixes and now pass. PostgreSQL tenant advisory locking is coded but not tested. Manual cycle/concurrent-edge behavior, truncation, graph-scaling and production readiness remain outside this scope. No PostgreSQL, OIDC deployment, Windows or owner-PC validation. No module-wide implemented claim.

## Reproduce

Use Python >=3.12. Model download requires internet on first setup.

    python -m venv .venv
    .venv/bin/pip install -r audits/m09-local-runtime/environment-lock.txt
    ATLAS_DATABASE_URL=sqlite:////tmp/m09-acceptance.db ATLAS_M09_MODEL_CACHE=/tmp/m09-model-cache ATLAS_M09_RUN_REAL_TESTS=1 ATLAS_M09_EVIDENCE_PATH=/tmp/m09-evidence.json .venv/bin/pytest -q tests/modules/test_m09*.py tests/modules/test_m25*.py
    PYTHONPATH=backend ATLAS_M09_MODEL_CACHE=/tmp/m09-model-cache .venv/bin/python scripts/m09_local_probe.py

The environment lock is the tested focused dependency set, not a replacement for the full project's dependency manifest. For product install use `pip install -e '.[m09-local]'`. Module-owned settings and HTTP behavior are documented in backend/app/modules/m09_knowledge_workspace/INTEGRATION.md.

Artifacts: real-api.json and real-api-full-app.json, missing-model.json, diagnostic.json, test-output.txt, environment-lock.txt. Real-model tests are explicitly enabled by ATLAS_M09_RUN_REAL_TESTS=1; without that variable they skip rather than fake acceptance.


## Independent-audit-driven repairs

The first candidate's runtime inference was independently reproduced, but audit found three pre-existing SQL safety defects plus an overly broad NER-config acceptance condition. Their failing-first evidence is retained in sql-failing-first.txt (3 failures) and ner-failing-first.txt (1 failure). Changes now tested with actual models and SQLite:

1. Stale proposal approval after either source or target edit returns 409, and creates no edge.
2. SQL suggestion insert failure rolls back new node and audit. Update refresh failure preserves old node version, pending proposal IDs/status and audit.
3. Two overlapping expected-version-1 updates produce one version-2 winner and one conflict. Two overlapping reviews produce one accepted winner, one conflict, one edge.
4. Edge insertion failure rolls back review status and audit.
5. A blank initialized NER with a component named ner is not accepted. Only the packaged en_core_web_sm 3.8.0 model is supported, verified against the actual full pipeline SHA-256 and NER weight SHA-256. Arbitrary user configuration cannot create a trained-model claim.

Seven real-model/SQL safety test functions are additional to the two router/full-app real inference acceptance cases. The bulk of 289 passing tests are adjacent M09/M25 contracts, not 289 model quality tests. No independent re-audit result is claimed for this revised bundle.
