# Module 15 integration

Replace the in-process version store with tenant-scoped SQL/object storage. The supplied service creates immutable, hashed versions, structural diffs, source manifests, accessible figure specs and Human Approval Center export proposals. Run LaTeX, DOCX and PPTX renderers only in an approved Celery job; pin TeX/docxtpl/python-pptx/Plotly/Kaleido/matplotlib images and retain render logs. Advancement pass: deterministic content hashes, parent lineage, semantic JSON diffs, citation provenance, alt-text enforcement, template validation and reproducible artifacts.

## Approved delivery (builder pb8, 2026-09-24)

`delivery.py` closes the "approval consumption that delivers a verified downloadable File" gap:

- `POST /document-generator/approvals/{approval_id}/deliver` -> 201 receipt with `download_url` (signed, expiring, tenant-bound). Pending/denied, wrong action or a version that no longer matches the approval -> 403; other tenant/unknown -> 404; already delivered or permit consumed -> 409; render failure -> 422.
- `GET /document-generator/deliveries/{approval_id}` re-reads the receipt with a fresh link; `GET /document-generator/deliveries` lists; `GET /document-generator/downloads/{token}` streams the file (hash re-checked, `Cache-Control: private, no-store`).

Order of operations: tenant + action + approved checks, load the immutable version and compare document id, format, template and a *recomputed* content hash with the approved payload, refuse if Module 0 already shows `effect_consumed`, render and structurally validate, then `consume_effect`. Rendering happens before the permit is consumed so a render failure does not burn the human's approval.

Renderers: PDF via Jinja2 LaTeX (every value escaped, so content cannot inject TeX commands) compiled by `pdflatex -no-shell-escape` with `openin_any=p`/`openout_any=p`; LaTeX source; DOCX via python-docx; PPTX via python-pptx (cover, bullets/body, speaker notes, figure slides with alt text, references). Figures are drawn with matplotlib from the stored spec (plotly specs use the same data). Optional template files `templates/<template_id>.docx|.pptx` are used when present; LaTeX requires `templates/<template_id>.tex.j2`. `report.tex.j2` now uses T1/lmodern and renders figures and references.

Validation: PDF parsed with PyMuPDF (page and image counts), DOCX/PPTX checked as OOXML packages with their main part, LaTeX checked for a complete document.

Config: `ATLAS_RUNTIME_DATA_DIR` (store root `m15-delivery`), `ATLAS_DOWNLOAD_SIGNING_KEY` (else a 0600 random key file in the store), `ATLAS_DOWNLOAD_LINK_TTL_SECONDS` (default 3600), `ATLAS_TEXMFHOME` (extra TeX tree).

Not done: object storage (S3/GCS) behind `DeliveryStore`; the production Dockerfile does not install TeX yet, so PDF delivery returns 422 there until `texlive-latex-recommended texlive-fonts-recommended lmodern` is added; the legacy `/publication-worker/execute` route still uses the unconfigured adapters.
