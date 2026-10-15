"""Offline executable regressions, using stdlib unittest (also pytest collects)."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

PATH = Path(__file__).resolve().parents[1] / 'backend/app/modules/m20_general_cognitive_worker/corpus_semantics.py'
SPEC = importlib.util.spec_from_file_location('atlas_corpus_semantics_under_test', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
CorpusEmbeddings = MODULE.CorpusEmbeddings
CorpusSemanticSearch = MODULE.CorpusSemanticSearch
run = MODULE.run_corpus_semantics

CORPUS = [
    'car engine road drive wheels',
    'automobile engine road drive wheels',
    'cat animal furry pet paws',
    'kitten animal furry pet paws',
    'orange fruit sweet juice citrus',
    'lemon fruit sour juice citrus',
]
DOCUMENTS = [{'id': 'vehicle', 'text': 'car'}, {'id': 'pet', 'text': 'kitten'},
             {'id': 'food', 'text': 'lemon'}]


class EmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.model = CorpusEmbeddings.fit(CORPUS)

    def test_learns_contextual_synonyms_without_spelling_overlap(self):
        self.assertGreater(self.model.word_similarity('car', 'automobile'), .99)
        self.assertLess(abs(self.model.word_similarity('car', 'kitten')), 1e-10)
        self.assertGreater(self.model.word_similarity('cat', 'kitten'), .99)

    def test_semantics_follow_corpus_not_fixed_synonyms(self):
        changed = CORPUS.copy()
        changed[1] = 'automobile animal furry pet paws'
        model = CorpusEmbeddings.fit(changed)
        self.assertGreater(model.word_similarity('automobile', 'cat'), .99)
        self.assertLess(abs(model.word_similarity('automobile', 'car')), 1e-10)
        self.assertNotEqual(model.to_dict()['corpus_sha256'], self.model.to_dict()['corpus_sha256'])

    def test_independent_ppmi_spectral_gram_oracle(self):
        # Full-rank U sqrt(S) embeddings have Gram sqrt(PPMI PPMI.T).
        # Oracle builds window-1 counts with adjacent pairs, then uses eigh,
        # independently of production's context loop and SVD decomposition.
        corpus = ['a b a c', 'c d c b', 'e f e g']
        model = CorpusEmbeddings.fit(corpus, window=1, dimensions=128)
        vocab = list(model.vocabulary)
        counts = np.zeros((len(vocab), len(vocab)))
        for doc in corpus:
            words = doc.split()
            for a, b in zip(words, words[1:]):
                counts[vocab.index(a), vocab.index(b)] += 1
                counts[vocab.index(b), vocab.index(a)] += 1
        ppmi = np.zeros_like(counts)
        for i in range(len(vocab)):
            for j in range(len(vocab)):
                if counts[i, j]:
                    ppmi[i, j] = max(0, math.log(counts[i, j] * counts.sum() /
                                                       (counts[i].sum() * counts[:, j].sum())))
        values, basis = np.linalg.eigh(ppmi @ ppmi.T)
        gram = (basis * np.sqrt(np.maximum(values, 0))) @ basis.T
        denominator = np.sqrt(np.outer(gram.diagonal(), gram.diagonal()))
        oracle = np.divide(gram, denominator, out=np.zeros_like(gram), where=denominator > 0)
        vectors = np.array(model.to_dict()['vectors'])
        np.testing.assert_allclose(vectors @ vectors.T, oracle, atol=1e-7)

    def test_vectors_finite_and_unit_length(self):
        vectors = np.array(self.model.to_dict()['vectors'])
        self.assertTrue(np.isfinite(vectors).all())
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1)

    def test_unknown_text_is_zero_not_fabricated_embedding(self):
        encoded = self.model.encode('unseenword')
        self.assertEqual(encoded['known_tokens'], 0)
        self.assertEqual(encoded['vector'], [0.0] * self.model.dimensions)
        self.assertIsNone(self.model.word_similarity('car', 'unknown'))

    def test_unicode_normalization_and_casefold(self):
        self.assertEqual(self.model.encode('ＣＡＲ')['vector'], self.model.encode('car')['vector'])
        self.assertEqual(self.model.encode('CAR')['vector'], self.model.encode('car')['vector'])

    def test_oov_coverage_is_reported(self):
        encoded = self.model.encode('car absent absent')
        self.assertEqual(encoded['known_tokens'], 1)
        self.assertEqual(encoded['total_tokens'], 3)
        self.assertEqual(encoded['out_of_vocabulary'], ['absent'])

    def test_json_roundtrip_preserves_search(self):
        restored = CorpusEmbeddings.from_dict(json.loads(json.dumps(self.model.to_dict())))
        before = CorpusSemanticSearch(self.model, DOCUMENTS).search('automobile', min_score=.1)
        after = CorpusSemanticSearch(restored, DOCUMENTS).search('automobile', min_score=.1)
        self.assertEqual(before, after)

    def test_export_cannot_mutate_model(self):
        state = self.model.to_dict()
        state['vectors'][0][0] = 99
        self.assertNotEqual(state, self.model.to_dict())

    def test_import_refuses_malformed_or_unbounded_models(self):
        mutations = [
            ('format', 'pickle'), ('dimensions', True), ('dimensions', 129),
            ('window', 0), ('corpus_sha256', 'not a digest'),
            ('vocabulary', ['a', 'a']), ('vocabulary', ['b', 'a']),
            ('vectors', [[0]]),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                state = copy.deepcopy(self.model.to_dict()); state[key] = value
                with self.assertRaises(ValueError):
                    CorpusEmbeddings.from_dict(state)
        for bad in [float('nan'), float('inf'), True, '1', 10**1000, 2.0]:
            with self.subTest(bad=repr(bad)[:30]):
                state = self.model.to_dict(); state['vectors'][0][0] = bad
                with self.assertRaises(ValueError):
                    CorpusEmbeddings.from_dict(state)

    def test_fit_input_and_resource_guards(self):
        cases = [None, [], [''], [5], ['word'], ['a', 'b'], ['a ' * 10001], ['a b'] * 2001]
        for corpus in cases:
            with self.subTest(corpus=str(corpus)[:30]):
                with self.assertRaises(ValueError): CorpusEmbeddings.fit(corpus)
        for kwargs in [{'dimensions': True}, {'dimensions': 129}, {'window': 0},
                       {'max_vocab': 513}, {'min_count': 0}, {'max_vocab': 1}]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError): CorpusEmbeddings.fit(CORPUS, **kwargs)
        with self.assertRaises(ValueError):
            CorpusEmbeddings.fit(['a b ' * 4000] * 7)

    def test_min_count_and_vocabulary_limit_are_real(self):
        model = CorpusEmbeddings.fit(CORPUS + ['rareword engine'], max_vocab=4, min_count=2)
        self.assertLessEqual(len(model.vocabulary), 4)
        self.assertNotIn('rareword', model.vocabulary)

    def test_no_context_crosses_document_boundaries(self):
        with self.assertRaisesRegex(ValueError, 'context pairs'):
            CorpusEmbeddings.fit(['one', 'two'])


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.model = CorpusEmbeddings.fit(CORPUS)
        self.index = CorpusSemanticSearch(self.model, DOCUMENTS)

    def test_text_query_finds_nonlexical_document(self):
        hits = self.index.search('automobile', min_score=.1)
        self.assertEqual([h.id for h in hits], ['vehicle'])
        self.assertNotIn('automobile', hits[0].text)
        self.assertAlmostEqual(hits[0].score, 1.0)

    def test_ranking_matches_independent_cosine_oracle(self):
        query = np.array(self.model.encode('car kitten')['vector'])
        expected = []
        for item in DOCUMENTS:
            vector = np.array(self.model.encode(item['text'])['vector'])
            score = float(np.dot(query, vector) / (np.linalg.norm(query) * np.linalg.norm(vector)))
            if score > .1: expected.append((item['id'], score))
        # Independent band oracle: repeatedly select the maximum remaining
        # cosine, then remove all values within the documented absolute bound.
        remaining = expected
        expected = []
        while remaining:
            anchor = max(score for _, score in remaining)
            band = sorted((item for item in remaining if anchor - item[1] <= 1e-12),
                          key=lambda item: item[0])
            expected.extend(band)
            selected = {identity for identity, _ in band}
            remaining = [item for item in remaining if item[0] not in selected]
        actual = self.index.search('car kitten', min_score=.1)
        self.assertEqual([h.id for h in actual], [x[0] for x in expected])
        np.testing.assert_allclose([h.score for h in actual], [x[1] for x in expected])

    def test_numeric_tie_contract_boundaries_and_nontransitive_chain(self):
        # Direct numeric pins make the declared ranking contract independent of
        # a particular SVD/BLAS roundoff pattern. This tests production banding.
        hit = MODULE.SemanticHit
        tolerance = MODULE.SCORE_TIE_TOLERANCE
        self.assertEqual(tolerance, 1e-12)
        cases = [
            ([hit('z', '', 0.0), hit('a', '', -tolerance)], ['a', 'z']),
            ([hit('z', '', 0.0), hit('a', '', -np.nextafter(tolerance, np.inf))], ['z', 'a']),
            ([hit('z', '', .8), hit('a', '', .8 - .75e-12),
              hit('b', '', .8 - 1.5e-12)], ['a', 'z', 'b']),
            ([hit('z', '', .8), hit('a', '', .8 - 1e-9)], ['z', 'a']),
            ([hit('z', '', .8), hit('a', '', np.nextafter(.8, 0))], ['a', 'z']),
        ]
        for hits, expected in cases:
            with self.subTest(scores=[x.score for x in hits]):
                self.assertEqual([x.id for x in MODULE._rank_hits(hits)], expected)
                self.assertEqual([x.id for x in MODULE._rank_hits(list(reversed(hits)))], expected)
                self.assertEqual(sorted(x.score for x in MODULE._rank_hits(hits)),
                                 sorted(x.score for x in hits))

    def test_search_applies_tie_band_before_top_k_but_after_threshold(self):
        # Exact known model rows isolate ranking from corpus/SVD training.
        cosine = 1 - 5e-13
        model = CorpusEmbeddings(['a', 'b'], [[1., 0.], [cosine, np.sqrt(1 - cosine*cosine)]],
                                 '0' * 64, 1, 2)
        index = CorpusSemanticSearch(model, [{'id': 'z', 'text': 'a'}, {'id': 'a', 'text': 'b'}])
        self.assertEqual([h.id for h in index.search('a', top_k=1)], ['a'])
        self.assertEqual([h.id for h in index.search('a', min_score=1 - 1e-13)], ['z'])
        hits = index.search('a')
        self.assertLess(hits[0].score, hits[1].score)  # Raw scores not rounded.

    def test_min_score_numeric_range_before_float_conversion(self):
        for score in [10**1000, -(10**1000), float('inf'), -float('inf'),
                      float('nan'), True, False, '0.5', None, -1, 2]:
            with self.subTest(score=repr(score)[:40]), self.assertRaises(ValueError):
                self.index.search('car', min_score=score)
        for score in [0, 0.0, .5, 1, 1.0]:
            with self.subTest(score=score):
                self.assertIsInstance(self.index.search('car', min_score=score), list)

    def test_unknown_query_no_hits(self):
        self.assertEqual(self.index.search('unseenword'), [])

    def test_zero_documents_no_hits(self):
        index = CorpusSemanticSearch(self.model, [{'id': 'oov', 'text': 'unseenword'}])
        self.assertEqual(index.search('car'), [])

    def test_ties_have_stable_id_order_and_top_k(self):
        index = CorpusSemanticSearch(self.model, [{'id': 'z', 'text': 'car'}, {'id': 'a', 'text': 'car'}])
        self.assertEqual([h.id for h in index.search('automobile')], ['a', 'z'])
        self.assertEqual([h.id for h in index.search('automobile', top_k=1)], ['a'])

    def test_index_copies_input_documents(self):
        docs = copy.deepcopy(DOCUMENTS)
        index = CorpusSemanticSearch(self.model, docs)
        docs[0]['text'] = 'changed'; docs[0]['id'] = 'changed'
        self.assertEqual(index.search('automobile', min_score=.1)[0].id, 'vehicle')

    def test_invalid_documents_queries_and_options(self):
        for docs in [None, [], [1], [{'id': 'x', 'text': ''}],
                     [{'id': 'x', 'text': 'car'}, {'id': 'x', 'text': 'cat'}]]:
            with self.subTest(docs=docs):
                with self.assertRaises(ValueError): CorpusSemanticSearch(self.model, docs)
        for query in ['', None, 5, 'a' * 20001]:
            with self.assertRaises(ValueError): self.index.search(query)
        for options in [{'top_k': True}, {'top_k': 0}, {'top_k': 2001},
                        {'min_score': float('nan')}, {'min_score': True}, {'min_score': -1}]:
            with self.subTest(options=options):
                with self.assertRaises(ValueError): self.index.search('car', **options)

    def test_end_to_end_both_entry_points(self):
        embedded = run('embeddings', {'corpus': CORPUS, 'texts': ['car', 'automobile']})
        self.assertEqual(embedded['status'], 'scoped_corpus_model')
        self.assertEqual(embedded['external_calls'], 0)
        result = run('semantic_search', {'corpus': CORPUS, 'documents': DOCUMENTS,
                                         'query': 'automobile', 'min_score': .1})
        self.assertEqual(result['hits'][0]['id'], 'vehicle')
        self.assertEqual(result['query_coverage']['known_tokens'], 1)
        partial = run('semantic_search', {'corpus': CORPUS, 'documents': DOCUMENTS,
                                         'query': 'automobile unknown', 'min_score': .1})
        self.assertEqual(partial['query_coverage']['out_of_vocabulary'], ['unknown'])
        self.assertIn('no pretrained', result['scope'])
        self.assertNotIn('named_capability_executed', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
