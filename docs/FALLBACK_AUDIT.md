# Fallback and stand-in audit

A fallback is classified from behavior, not naming. **Legitimate graceful degradation** requires a real primary path and only handles an unavailable optional dependency, missing provider key, upstream failure, or invalid provider output. **Disguised stub** means the requested primary path does not exist and deterministic or simplified logic stands in for it.

| Location | Classification | Evidence | Action |
|---|---|---|---|
| `m10_email_assistant/extraction.py` | legitimate graceful degradation | Primary calls an injected LLM, validates structured JSON, retries once; heuristic runs only after invalid outputs | keep; provenance should show extraction path |
| `m06_social_media_manager/service.py` | legitimate graceful degradation | Primary calls the shared BYOK generator and parses per-platform JSON; deterministic copy runs on provider failure/invalid JSON | keep; expose provider/fallback provenance |
| `m07_brand_collaboration/service.py` | legitimate graceful degradation | WeasyPrint produces a real PDF when installed; HTML retains complete inspectable content if optional renderer is absent | keep; production image must pin WeasyPrint |
| `m08_startup_growth/service.py` | legitimate graceful degradation | `python-pptx` produces a real deck; Markdown retains complete slide content if the optional dependency is absent | keep; production image must pin `python-pptx` |
| `m12_ai_research_lab/executor.py` | legitimate graceful degradation | Router selects eligible real model providers and bounded fallback models; no fake output is synthesized | keep |
| `m01_opportunity_discovery/service.py` lexical normalizer | legitimate non-key fallback | Live spaCy NER + cue-anchored dateparser is the default in the production routes (`nlp_stack.default_stack`); regex parsing runs only if the model/dependency is missing or no cue-anchored date is found, and `deadline_engine` records which | done 2026-09-24 (PB2): provenance surfaced per row and at `/opportunity-discovery/nlp-status` |
| `m01_opportunity_discovery/service.py` token cosine | legitimate non-key fallback | Free in-process fastembed (`BAAI/bge-small-en-v1.5`) embedding similarity is the default in the production routes; Ollama/BYOK OpenAI by config; token cosine only on missing dependency, opt-out, or per-item backend failure, recorded as `token-cosine:fallback(reason)` | done 2026-09-24 (PB2) |
| `m01_opportunity_discovery/service.py` impact heuristic | disguised stub | No trained outcome model primary exists | train only from real applied/won labels; otherwise label score heuristic, not model |
| `m10_email_assistant/classifier.py` rule classifier | legitimate explicitly configured baseline | `ATLAS_EMAIL_CLASSIFIER=bert` now activates a required verified checkpoint through the live service; missing checkpoint fails closed. Rules remain the explicit default when no trained model is claimed | production must select and record a verified checkpoint; never fabricate training labels |
| `m08_startup_growth` generated application templates | real generator, not a fallback | Produces concrete archives and outputs from supplied facts | no reclassification needed |
| `m20_general_cognitive_worker` bounded retry path | real safety mechanism, not a fallback answer | Failed tools retry up to a cap then fail/escalate; no synthetic success | keep |

## Marker review

Occurrences of `pending` mostly represent approval/workflow state, not placeholders. Test mocks are offline integration harnesses around real adapters. `stub` in the old README and the default value in `modules/catalog.py` were stale metadata; all catalog entries explicitly override it, but the default is removed so new modules cannot silently present as stubs.
