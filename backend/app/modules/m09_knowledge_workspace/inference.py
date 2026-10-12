"""Free-first graph inference adapters; missing models are reported, never fabricated."""
from functools import lru_cache
import os
import math

class GraphInference:
    def __init__(self, backend=None, nlp=None):
        self.backend, self.nlp = backend, nlp
        self.errors = {}

    def embed(self, text):
        if self.backend is None:
            return None
        try:
            rows = self.backend.embed([text])
            if len(rows) != 1 or not rows[0] or any(not math.isfinite(float(x)) for x in rows[0]):
                raise ValueError('invalid embedding result')
            return [float(x) for x in rows[0]]
        except Exception as exc:
            self.errors['embedding'] = type(exc).__name__
            return None

    def entities(self, text):
        if self.nlp is None:
            return []
        try:
            return [{'text': ent.text, 'type': ent.label_} for ent in self.nlp(text[:20000]).ents]
        except Exception as exc:
            self.errors['ner'] = type(exc).__name__
            return []

    def status(self):
        return {'embedding_loaded': self.backend is not None, 'ner_loaded': self.nlp is not None,
                'errors': dict(self.errors), 'boundary': 'Loaded adapters are not proof of model accuracy or live acceptance.'}

@lru_cache(maxsize=1)
def configured_inference():
    inference = GraphInference()
    selected = os.getenv('ATLAS_M09_EMBEDDING_PROVIDER', 'fastembed').lower()
    try:
        from app.modules.m01_opportunity_discovery.nlp_stack import FastEmbedBackend, OllamaBackend
        if selected == 'fastembed':
            inference.backend = FastEmbedBackend()
        elif selected in {'ollama', 'bge'}:
            inference.backend = OllamaBackend()
        elif selected not in {'off', 'none'}:
            raise ValueError('use fastembed, ollama or off; paid embeddings are not enabled implicitly')
        else:
            inference.errors['embedding'] = 'disabled by configuration'
    except Exception as exc:
        inference.errors['embedding'] = type(exc).__name__
    try:
        import spacy
        inference.nlp = spacy.load(os.getenv('ATLAS_M09_SPACY_MODEL', 'en_core_web_sm'))
    except Exception as exc:
        inference.errors['ner'] = type(exc).__name__
    return inference
