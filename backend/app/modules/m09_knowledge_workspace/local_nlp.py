"""M09's explicit free CPU inference runtime. No empty/hash/cloud fallback."""
from __future__ import annotations
import hashlib
import math
import os
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from threading import RLock

class NLPUnavailable(RuntimeError):
    pass

class LocalNLP:
    def __init__(self, model: str, ner_model: str, cache: str | None, threads: int):
        try:
            from fastembed import TextEmbedding
            import spacy
            self.encoder = TextEmbedding(model_name=model, cache_dir=cache, threads=threads,
                                         providers=['CPUExecutionProvider'])
            self.ner = spacy.load(ner_model)
            if 'ner' not in self.ner.pipe_names:
                raise ValueError('spaCy pipeline has no trained NER component')
            # Bind persisted vectors to the actual ONNX/tokenizer bytes, not just dimensions.
            model_dir = Path(self.encoder.model._model_dir)
            artifact = model_dir / self.encoder.model.model_description.model_file
            self.identity = {
                'provider': 'fastembed-cpu', 'model': model,
                'dimension': self.encoder.model.model_description.dim,
                'onnx_sha256': _sha(artifact),
                'tokenizer_sha256': _sha(model_dir / 'tokenizer.json'),
                'config_sha256': _sha(model_dir / 'config.json'),
                'tokenizer_config_sha256': _sha(model_dir / 'tokenizer_config.json'),
                'special_tokens_sha256': _sha(model_dir / 'special_tokens_map.json'),
                'fastembed_version': version('fastembed'),
            }
            self.entity_identity = {'provider': 'spacy', 'model': ner_model,
                                    'version': self.ner.meta.get('version'), 'language': self.ner.lang}
            self.lock = RLock()
        except Exception as exc:
            raise NLPUnavailable(f'M09 local NLP unavailable ({type(exc).__name__}). '
                                 'Install the m09-local extra and provision the configured FastEmbed '
                                 'and spaCy models; no node write was performed.') from exc

    def embed(self, text: str) -> list[float]:
        try:
            with self.lock:
                vector = [float(x) for x in next(self.encoder.embed([text]))]
            validate_vector(vector, self.identity['dimension'])
            return vector
        except Exception as exc:
            raise NLPUnavailable('M09 embedding inference failed; no node write was performed') from exc

    def extract_entities(self, text: str) -> list[dict]:
        try:
            with self.lock:
                doc = self.ner(text)
            return [{'text': e.text, 'type': e.label_, 'start': e.start_char, 'end': e.end_char}
                    for e in doc.ents]
        except Exception as exc:
            raise NLPUnavailable('M09 entity inference failed; no node write was performed') from exc


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_vector(vector, dimension=None):
    if not vector or (dimension is not None and len(vector) != dimension):
        raise NLPUnavailable('M09 embedding dimension mismatch or empty vector')
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
        raise NLPUnavailable('M09 embedding contains non-finite or non-numeric values')
    if not any(vector):
        raise NLPUnavailable('M09 embedding has zero norm')


@lru_cache(maxsize=2)
def _load(model, ner_model, cache, threads):
    return LocalNLP(model, ner_model, cache, threads)


def get_local_nlp():
    # Module-owned settings intentionally do not change the shared OpenAI/Ollama provider.
    provider = os.getenv('ATLAS_M09_EMBEDDING_PROVIDER', 'fastembed').lower()
    if provider != 'fastembed':
        raise NLPUnavailable('M09 supports only the free CPU fastembed provider; unsupported configuration')
    try:
        threads = int(os.getenv('ATLAS_M09_CPU_THREADS', '2'))
        if not 1 <= threads <= 32:
            raise ValueError()
    except ValueError as exc:
        raise NLPUnavailable('ATLAS_M09_CPU_THREADS must be an integer from 1 to 32') from exc
    return _load(os.getenv('ATLAS_M09_EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5'),
                 os.getenv('ATLAS_M09_SPACY_MODEL', 'en_core_web_sm'),
                 os.getenv('ATLAS_M09_MODEL_CACHE') or None, threads)
