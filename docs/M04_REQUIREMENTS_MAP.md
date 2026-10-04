# M04 Research Scientist: requirements map (internal repo artifact)

Status words: REAL = runs and produces the real thing (evidence named). HEURISTIC = runs, but the method is a stated approximation. STUBBED = echoes or validates caller input, executes nothing. MISSING = no code. UNAUDITED = not read or run by me. Nothing here is product acceptance. Last updated at the commit that added this file.

| Rows / feature | Status | Evidence and limits |
|---|---|---|
| 211 PubMed surveillance | REAL (collector) | `pubmed_collector.py`, POST `/surveillance/collect/pubmed`. A live manual call returned real records. No scheduler. NCBI tool/email not registered. |
| 212 arXiv surveillance | REAL (collector) | `arxiv_collector.py`, POST `/surveillance/collect/arxiv`. Live manual calls (observed in my sandbox; not independently reproduced by the reviewer). Throttle covers one host only (`source_throttle.py`). |
| 213-216 bioRxiv, Nature, Science, custom journals | MISSING (collector) | `lane_surveillance.parse_syndication_feed` parses RSS/Atom offline. I did not verify any fetch or route wiring. |
| Continuous polling / scheduler | MISSING | Needs a shared cross-host lock and a verified cadence. |
| 217-221 summaries, embeddings, clustering, gap candidates, hypotheses (expanded rows 217-222) | STUBBED (read and checked) | `_summary` echoes caller sections; `_embedding` only checks the dimensions of caller vectors; `_clusters` echoes caller assignments; `_gaps` thresholds caller counts; `_hyp` echoes caller hypotheses. |
| Extractive paper summary (`/papers/summarize`) | HEURISTIC, REAL | `extractive_summary.py`: TF-IDF sentence ranking, verbatim sentences, title+abstract only, not abstractive. Short abbreviation list; other abbreviations can split wrongly. |
| Embedding and clustering real paths (instead of rows 218-219) | REAL (lexical) / HEURISTIC | `/surveillance/ingest` (lexical embedding is free and not semantic; Ollama or OpenAI are untested here), `/surveillance/clusters`. |
| Gap finders (`/surveillance/gaps`, `/surveillance/term-gaps`) | HEURISTIC | The first uses a cosine band with a template sentence. The second uses corpus-relative term pairs that never co-occur. Neither is global novelty. |
| 222 hypothesis generation | REAL only with a provider key | `/hypotheses` calls the BYOK provider. Not exercised here (no keys). Free and local is not met without Ollama or the shared-model layer. |
| 223, 239 ReAct and question-then-research loops (expanded rows) | STUBBED | They echo the caller's iterations or search_steps. |
| Question-then-research loop (`/research-loop`) | HEURISTIC over REAL retrieval | Live arXiv/PubMed queries; term-expansion planning with no language model; soft deadline only. |
| 224-225, 232-238, 243-247 (expanded rows) | STUBBED | Echo dicts (`executed: False`, `rendered: False`, `compiled: False`, `google_doc_created: False` and similar). |
| 226-227 HF/Kaggle datasets | STUBBED | Echo, `executed: False`. Dataset fetch for approved analyses is separate (below). |
| 228-229 code generation (Python/R) | STUBBED (read) | `_code` echoes caller-supplied code, `executed: False`. Generating code needs a model: MISSING under the free/local constraint. |
| 230, 240-242, 248-250 scanpy, simulation, docking, AlphaFold, Galaxy, PyMOL | STUBBED | Adapter echoes with `credentials_present: False`; `tools/adapters.py` has command wrappers, untested here. |
| 231 sandboxed execution (expanded row itself) | STUBBED | The row echoes image_digest, command and resource_limits with `executed: False`. |
| Approved-code sandbox executor (`approved_sandbox.py`, a separate operation from row 231) | REAL (bubblewrap) | `approved_sandbox.py` executes approved code in bwrap here (27 tests, none skipped). The Docker backend is untested (docker absent). Not the Dell target. |
| 234 LaTeX manuscript (expanded row) | STUBBED | Echo. Separately: `/research-loop/report` makes a REAL pdflatex PDF of retrieved metadata and abstracts. It is an evidence compendium, NOT an authored paper. |
| "40 page" authored research output | MISSING | Needs LLM prose; conflicts with the free/local constraint unless a local model is available. |
| "Think like a human, then research" | MISSING | Heuristic query expansion only. |
| Reproducibility bundle, reruns, rerun schedules | UNAUDITED beyond tests | Covered by the m04 tests (rows listed in their test files). |
| 252-258 and rows not named | UNAUDITED | |

Core-spec rows (m01-m04 `core_spec_round6`) are `plan_only`, not executed. Real work for M04 lives in the table above.
Tests: `tests/modules/test_m04*.py` and `tests/test_m04*.py` (counts in the latest report).
