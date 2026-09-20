# Module 3 integration notes

## Shared wiring required

- Add `app.modules.types.ModuleSpec` if it has not landed yet. This module exports `spec` with ID `3`, slug `grant-writer`, name `Grant & Fellowship Writer`, its router, and `Service` type.
- Register `app.modules.m03_grant_writer.spec` through the shared module registry/router. The local router already uses `/grant-writer`; the integrator should add only the global `/api/v1` prefix.
- The existing shared BYOK provider currently supports OpenAI and Anthropic. The original specification names Gemini for guideline research, but this lane uses the supported shared BYOK providers rather than adding a direct client or reading credentials. Add Gemini centrally only if it becomes a supported BYOK provider.
- The approved `generate_grant_documents` action should be fulfilled by Module 15 or another shared document renderer. Pass the approved payload to a DOCX/PDF renderer and save resulting artifact references. This lane intentionally does not add `python-docx` or WeasyPrint to shared dependencies.
- If document generation is classified as reversible in the final approval policy, keep the approval anyway: it is an explicit handoff boundary to a renderer and prevents hidden artifact creation from a draft request.

## Compliant replacements

- Literature/background material is accepted only as user-supplied or licensed `EvidenceItem` records. The module does not scrape successful proposals or bypass database access controls. A future integration may use official arXiv, PubMed, Crossref, or licensed grant-database APIs and pass normalized evidence into the service.
- Budget rates must be supplied with a `source_note` after checking an official vendor API, published rate card, or other permitted source. The calculator marks rates as requiring verification and does not scrape prices.
- Success analysis operates only on permissioned funded examples and reports language overlap as diagnostic, not predictive. It does not claim that similarity implies funding success.
- Export is represented as an approval request. No DOCX/PDF generation, publishing, submission, browser form submission, or payment occurs in this module.
