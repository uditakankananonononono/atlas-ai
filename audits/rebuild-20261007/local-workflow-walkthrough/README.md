# Actual no-model local workflow

Run from the repository root:

```sh
PYTHONPATH=backend .venv/bin/python audits/rebuild-20261007/local-workflow-walkthrough/run.py
```

The script creates a private temporary file-backed SQLite repository, prepares a supplied two-step DAG, runs the actual default CSV filter, closes and reopens the engine, then runs the actual default summary through a persisted dependency binding. It prints the computed total 15, retained action/trace evidence and retrospective. No mock handler, model, network, account, production database or money is involved. Temporary data is removed on exit.

This proves this narrow offline pipeline, not autonomous planning, model usefulness, authenticated invoice data, independent external verification, deployed UI or distributed execution. The runtime HTTP surface exposes registered tool schemas at GET /api/modules/20/runtime/tools; production callers still require configured tenant authentication and a separately bound tenant runtime.
