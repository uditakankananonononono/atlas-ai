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

Final run: 282 tests passed across every test_m09*.py and test_m25*.py file on Linux Python 3.12.14. See test-output.txt. The earlier broader attempt failed collection for an uninstalled unrelated bs4 dependency; its log is preserved. After required dependency installation the full entrypoint imported and all 282 tests passed.

## Costs and limits

First public model download was approximately 66.5 MB ONNX plus tokenizer/config files; spaCy wheel was 12.8 MB. Models are NOT included in this source bundle; setup needs internet once and writable cache storage. Local inference needs neither an account nor a paid API. A cached Linux diagnostic used two ONNX CPU threads; load/runtime and peak RSS measurements are in diagnostic.json, not a Dell performance guarantee. Initial Python 3.10 tests passed, but final evidence is on the declared-supported Python 3.12 series.

English models; embedding truncates at 512 tokens. Existing threshold 0.78 unchanged, uncalibrated. Exact title matching only for mentions, and duplicate titles may create multiple suggestions. Diagnostics show spaCy mislabelled Alice as ORG, a concrete NER limitation. Scores are not probabilities. Comparison is limited to the first 500 repository nodes. Old vectors require node updates, not an automatic migration.

Node and suggestion writes remain separate SQL transactions. Database failure after node save can leave missing suggestions. Existing stale suggestion, optimistic concurrency, truncation, graph-scaling and production readiness concerns are not fixed by this scope. No PostgreSQL, OIDC deployment, Windows or owner-PC validation. No module-wide implemented claim.

## Reproduce

Use Python >=3.12. Model download requires internet on first setup.

    python -m venv .venv
    .venv/bin/pip install -r audits/m09-local-runtime/environment-lock.txt
    ATLAS_DATABASE_URL=sqlite:////tmp/m09-acceptance.db ATLAS_M09_MODEL_CACHE=/tmp/m09-model-cache ATLAS_M09_RUN_REAL_TESTS=1 ATLAS_M09_EVIDENCE_PATH=/tmp/m09-evidence.json .venv/bin/pytest -q tests/modules/test_m09*.py tests/modules/test_m25*.py
    PYTHONPATH=backend ATLAS_M09_MODEL_CACHE=/tmp/m09-model-cache .venv/bin/python scripts/m09_local_probe.py

The environment lock is the tested focused dependency set, not a replacement for the full project's dependency manifest. For product install use `pip install -e '.[m09-local]'`. Module-owned settings and HTTP behavior are documented in backend/app/modules/m09_knowledge_workspace/INTEGRATION.md.

Artifacts: real-api.json and real-api-full-app.json, missing-model.json, diagnostic.json, test-output.txt, environment-lock.txt. Real-model tests are explicitly enabled by ATLAS_M09_RUN_REAL_TESTS=1; without that variable they skip rather than fake acceptance.
