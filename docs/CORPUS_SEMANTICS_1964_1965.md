# Corpus-fit Embeddings and Semantic Search

Scope: Extra-doc rows 1964 "Embeddings" and 1965 "Semantic Search". Another
occurrence in that doc says "Semantic Search - Finds by meaning".

This implementation learns distributional word embeddings from the caller's
text corpus using distance-weighted within-document co-occurrence, positive
pointwise mutual information (PPMI), and truncated SVD. Text is encoded as the
normalized mean of learned word vectors. Search encodes text documents and text
queries in the same fitted space and ranks cosine similarity. There are no
hardcoded synonyms, hash vectors, externally supplied query vectors, downloads,
paid services, or network calls. NumPy is already a base project dependency.

This is a real corpus-fit statistical model, not a pretrained language model.
It can recover terms used in similar contexts but cannot infer unseen meanings.
Negation, word order, polysemy, and out-of-domain meaning are not solved. All-OOV
queries return no hits. Coverage is returned by encode() and by the search entry point. Partial-OOV
queries are ranked using their known terms only; inspect query_coverage rather
than treating a high similarity as complete understanding of the query. Scores are similarities,
not probabilities. Tiny positive floating-point scores can occur between unrelated
vectors; callers can set min_score for their corpus. There is no universal
relevance cutoff. No general-language quality claim or completed-ledger regrade
is made by these tests.

## API

```python
from app.modules.m20_general_cognitive_worker.corpus_semantics import (
    CorpusEmbeddings, CorpusSemanticSearch,
)
model = CorpusEmbeddings.fit(training_texts, dimensions=32, window=2)
vector_and_coverage = model.encode("text query")
index = CorpusSemanticSearch(model, [{"id": "doc-1", "text": "document text"}])
hits = index.search("text query", top_k=10, min_score=0.1)
```

Fit once and reuse for repeated queries. `to_dict()` / `from_dict()` preserve the
fitted vocabulary, vectors and corpus digest in JSON-safe form, without pickle.
The digest records training corpus identity, not provenance/authenticity.
The model owns a copy of its read-only vector array; exported values cannot
mutate it. The caller owns tenant separation, storage, corpus authorization and
rebuild/reindex policy. There is no global model/cache or persistence side effect.

`run_corpus_semantics(method, data)` is a separate entry point for either
`embeddings` or `semantic_search`. Both require `corpus`; embeddings requires
`texts`; semantic_search requires `documents` with unique id/text and `query`.
Optional fields: dimensions, window, min_count, max_vocab, top_k, min_score.
The standalone entry point fits on every call; use classes for reuse.

## Local resource boundary

- Up to 2000 training texts, 50000 tokens total, 20000 characters per text.
- At most 512 retained words; dense SVD is cubic in vocabulary size.
- Up to 128 dimensions, bounded by observed numerical rank.
- Window 1..10; documents are never joined across boundaries.
- Up to 2000 indexed documents and 50000 indexed tokens.
- No OS execution, file writes, model downloads, or application/account access.

This is intentionally a small local corpus model, not a large-scale vector
service. A larger corpus vocabulary needs an independently evaluated sparse or
pretrained route, rather than silently increasing this dense bound.

## Integration and evidence

The additive implementation/test patch does not change the legacy registry.
A separate optional wiring patch adds an explicit `corpus` opt-in in the existing
1960-2009 dispatcher. Old tokens/query_embedding inputs retain their existing
reference-substitute labels. Malformed explicit corpus inputs fail rather than
silently falling back to character hashes. An integrator should coordinate this
single shared insertion with other cognitive lanes.

Run:

```
python3 -m unittest discover -s tests -p test_corpus_semantics_1964_1965.py -v
```

Tests use production NumPy, not API/NumPy shims. Mathematical oracles cover
PPMI/SVD Gram reconstruction through an independent eigen-decomposition and
search through direct cosine calculations. Semantic tests use a small authored
corpus with a deliberately held-out lexical-match query/document pair and a
training-context ablation. That proves this mechanism can learn from corpus
contexts; it is not an independent real-world retrieval benchmark.

Initial execution environment: Python 3.10, NumPy 2.2.6. Project target Python
is >=3.12; target-version/full-application execution remains for integration.

## Numeric ranking contract

Cosine scores within an absolute1e-12 band are numerical ties. Sort raw scores
high-to-low, anchor the band at its highest score, include every following score
whose difference from that anchor is <=1e-12, then sort that band by document id
ascending. Start a fresh band at the next highest unassigned score. Pairwise
near-tie chains never merge bands. Raw scores are preserved; min_score remains a
strict raw-score cutoff before banding, and top_k truncates the banded order.
This handles observed sub-ULP-to-few-ULP BLAS/SVD score differences without hiding
meaningful score differences. The independent cosine oracle uses this same
explicit policy, not an assumption that machine-order near-ties are meaningful.
