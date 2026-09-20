# Fallback and stand-in audit

A fallback is classified from behavior, not naming. **Legitimate graceful degradation** requires a real primary path and only handles an unavailable optional dependency, missing provider key, upstream failure, or invalid provider output. **Disguised stub** means the requested primary path does not exist and deterministic or simplified logic stands in for it.

| Location | Classification | Evidence | Action |
|---|---|---|---|
| `m10_email_assistant/extraction.py` | legitimate graceful degradation | Primary calls an injected LLM, validates structured JSON, retries once; heuristic runs only after invalid outputs | keep; provenance should show extraction path |
| `m06_social_media_manager/service.py` | legitimate graceful degradation | Primary calls the shared BYOK generator and parses per-platform JSON; deterministic copy runs on provider failure/invalid JSON | keep; expose provider/fallback provenance |
| `m07_brand_collaboration/service.py` | legitimate graceful degradation | WeasyPrint produces a real PDF when installed; HTML retains complete inspectable content if optional renderer is absent | keep; production image must pin WeasyPrint |
| `m08_startup_growth/service.py` | legitimate graceful degradation | `python-pptx` produces a real deck; Markdown retains complete slide content if the optional dependency is absent | keep; production image must pin `python-pptx` |
| `m12_ai_research_lab/executor.py` | legitimate graceful degradation | Router selects eligible real model providers and bounded fallback models; no fake output is synthesized | keep |
| `m01_opportunity_discovery/service.py` lexical normalizer | legitimate non-key fallback | A real injectable spaCy/dateparser primary is wired; deployments lacking an explicit checkpoint use deterministic parsing | production must install and set `ATLAS_SPACY_MODEL`; surface provenance |
| `m01_opportunity_discovery/service.py` token cosine | legitimate non-key fallback | Real OpenAI/Ollama embedding similarity is wired as an injectable primary; lexical scoring is used only when no matcher is configured | production must configure matcher; surface provenance |
| `m01_opportunity_discovery/service.py` impact heuristic | disguised stub | No trained outcome model primary exists | train only from real applied/won labels; otherwise label score heuristic, not model |
| `m10_email_assistant/classifier.py` rule classifier | useful baseline but disguised spec substitute | Fine-tuned BERT class exists, but no verified checkpoint ships and default service uses rules | add configured checkpoint activation and explicit classifier provenance; never fabricate training data |
| `m08_startup_growth` generated application templates | real generator, not a fallback | Produces concrete archives and outputs from supplied facts | no reclassification needed |
| `m20_general_cognitive_worker` bounded retry path | real safety mechanism, not a fallback answer | Failed tools retry up to a cap then fail/escalate; no synthetic success | keep |

## Marker review

Occurrences of `pending` mostly represent approval/workflow state, not placeholders. Test mocks are offline integration harnesses around real adapters. `stub` in the old README and the default value in `modules/catalog.py` were stale metadata; all catalog entries explicitly override it, but the default is removed so new modules cannot silently present as stubs.
