# Rows 47-64 delta (post-landing deepening)

Scope literal: nothing here promotes any row beyond PARTIAL.

- Row 57 (Clicky): `execute_stats_request` in c31/clicky.py is a real stdlib GET transport for the documented
  stats endpoint. `tests/modules/test_c31_clicky_transport.py` runs it against a loopback server: success query
  shape, 403, non-JSON, oversize body, redirect not followed, timeout, connection refused, sitekey validation
  and non-leak, tampered plans, loopback-only base override. No call to api.clicky.com was made. Live use, pricing
  and the owner's sitekey stay unverified and pending her authorization.
- Row 56 (20 publisher links): `row56_link_liveness_2026-10-12.json` is a read-only run of the existing bounded
  fetcher (robots first, no redirects, 1s spacing, metadata only). Result: 16 page_reachable, 4 not (jhu 403,
  collegeessayguy 403, cornell 308 redirect, admitraven robots 307). Challenges and redirects were NOT bypassed.
  The index remains a link index, not a dataset or licensed corpus.
- Row 64 (pipeline): `tests/modules/test_m25_row64_scale_workflow.py` runs the real LocalKnowledgePipeline over 210
  SYNTHETIC local sources: per-source retrieval, citations, consent gate, tenant denial, dedup/versioning,
  deletion, attested restart restore. It is not a 200-real-source corpus and not learning into Atlas.
- Row 63: not built in this delta.
