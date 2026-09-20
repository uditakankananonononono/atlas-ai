# Module 4 integration notes

## Shared wiring needed

1. The supplied snapshot does not contain `backend/app/modules/types.py`, although `docs/MODULE_CONVENTIONS.md` requires every module to import `ModuleSpec` from it. The integrator must add the shared `ModuleSpec` definition before importing this package.
2. Import `backend.app.modules.m04_research_scientist.spec`, include its router under the global `/api/v1` prefix, and register its `service_type` in the shared module registry. No shared file was changed in this lane.
3. Literature ingestion should be wired to official or licensed sources only: NCBI E-utilities/PubMed, arXiv API, bioRxiv API/RSS, Crossref, publisher RSS, and user-configured journal RSS. Respect source rate limits, licenses, and robots policies. The lane accepts normalized `PaperInput` objects and performs no scraping itself.
4. Wire an approved sandbox runner later for `ProposedAnalysis`. It must require a granted Human Approval Center request, run in an ephemeral container, default to no network, enforce CPU/memory/time/file limits, use a read-only input mount, and retain logs/artifacts for review. This module intentionally never executes submitted/generated code.
5. Dataset discovery should use official Hugging Face Hub, Kaggle, NCBI, or Zenodo APIs and validate each dataset's license, consent, and intended-use restrictions. Do not add self-bots, unofficial social wrappers, rotating residential proxies, stealth/evasion, or ToS-violating scraping.
6. Manuscript generation and target-journal lookup belong behind Modules 15 and compliant official journal-finder APIs. Publishing/submission must remain separately approval-gated.

## Behavior delivered

- Deterministic offline clustering of normalized papers using transparent Jaccard similarity and connected components.
- BYOK-backed hypothesis drafting through `app.core.providers.generate`, with evidence IDs and explicit scientific/data-use caveats.
- Typed, inert Python/R analysis proposals that reject network-enabled execution and always require approval.
