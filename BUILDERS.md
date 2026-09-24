# Atlas builders

One line per builder claim. Claim a distinct component before building; work on your own branch.

- pb8 (branch `pb8`, 2026-09-24): M4 Research Scientist - approved sandbox execution (approval consumption, bubblewrap/Docker isolated runs, hashed logs/outputs, sealed receipts, artifact download). Files: `backend/app/modules/m04_research_scientist/approved_sandbox.py`, sandbox routes appended to `m04_research_scientist/routes.py`, `tests/modules/test_m04_approved_sandbox.py`.
- pb8 (branch `pb8`, 2026-09-24): M15 Document Generator - approved delivery (approval consumption, verified PDF/LaTeX/DOCX/PPTX render, signed download links). Files: `backend/app/modules/m15_document_generator/delivery.py`, delivery routes appended to `m15_document_generator/routes.py`, `templates/report.tex.j2`, `tests/modules/test_m15_approved_delivery.py`.
- pb8 (branch `pb8`, 2026-09-24): M04 environment lock + executed reproducibility bundle; Dockerfile TeX for M15 PDF. Files: `m04_research_scientist/approved_sandbox.py`, `m04_research_scientist/execution_bundle.py`, `Dockerfile`, `docs/DEPLOYMENT.md`.
- pb8 (branch `pb8`, 2026-09-24): M04 approval-gated re-run with output-hash and environment diff. Files: `m04_research_scientist/rerun.py`, routes appended to `m04_research_scientist/routes.py`.
- pb8 (branch `pb8`, 2026-09-24): M04 scheduled re-run proposals + stats. Files: `m04_research_scientist/rerun_schedule.py`, routes in `m04_research_scientist/routes.py`, beat entry in `workers/celery_app.py`, task in `workers/tasks.py`.
