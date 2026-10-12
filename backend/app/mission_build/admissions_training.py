"""Train a local multinomial naive-Bayes admissions-advice topic classifier.

Training is explicit, offline and produces fitted token/class counts. This is
not an essay generator or an admissions-outcome predictor. Rights receipts
are asserted inputs requiring host verification, not web-link permission.
"""
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from urllib.parse import urlsplit


def tokens(text):
    return re.findall(r'[a-z0-9]{2,40}', text.casefold())


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _text(value, limit=20000):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ValueError('bounded nonempty text required')
    return value


def fit(corpus, sources, *, minimum_sites=10):
    if type(minimum_sites) is not int or not 1 <= minimum_sites <= 100:
        raise ValueError('minimum_sites must be 1..100')
    if type(sources) is not list or not 1 <= len(sources) <= 100:
        raise ValueError('1..100 sources required')
    source_map = {}
    domains = set()
    for s in sources:
        ident = _text(s.get('id'), 120)
        url = urlsplit(_text(s.get('url'), 2000))
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('source requires HTTPS without credentials')
        if ident in source_map:
            raise ValueError('duplicate source id')
        # Host must verify the actual license/permission identified here.
        if s.get('training_allowed') is not True or not s.get('rights_receipt'):
            raise PermissionError('explicit training rights receipt required')
        _text(s['rights_receipt'], 2000)
        source_map[ident] = s
    if type(corpus) is not list or not 4 <= len(corpus) <= 10000:
        raise ValueError('4..10000 examples required')
    seen_text = set(); seen_ids = set(); train = []; heldout = []; used_sources = set()
    for row in corpus:
        ident = _text(row.get('id'), 120)
        sid = row.get('source_id')
        if ident in seen_ids or sid not in source_map:
            raise ValueError('unique example id and known source required')
        seen_ids.add(ident)
        text = _text(row.get('text'))
        words = tokens(text)
        if not words:
            raise ValueError('example needs tokens')
        canonical = ' '.join(words)
        if canonical in seen_text:
            raise ValueError('duplicate normalized text across splits')
        seen_text.add(canonical)
        label = _text(row.get('label'), 120)
        split = row.get('split')
        if split not in {'train', 'heldout'}:
            raise ValueError('explicit train/heldout split required')
        (train if split == 'train' else heldout).append((ident,sid,words,label))
        if split == 'train':
            domains.add(urlsplit(source_map[sid]['url']).hostname.casefold().removeprefix('www.'))
            used_sources.add(sid)
    if len(domains) < minimum_sites:
        raise ValueError('insufficient distinct training source domains')
    labels = sorted({r[3] for r in train})
    if len(labels) < 2 or not heldout or {r[3] for r in heldout} != set(labels):
        raise ValueError('two training classes and heldout coverage of every class required')
    counts = defaultdict(Counter); documents = Counter(); vocabulary = set()
    for _,_,words,label in train:
        counts[label].update(words);documents[label] += 1;vocabulary.update(words)
    model = {'schema': 1, 'kind': 'multinomial_naive_bayes_advice_topics', 'labels': labels,
             'class_documents': dict(documents), 'token_counts': {k: dict(v) for k,v in counts.items()},
             'vocabulary': sorted(vocabulary), 'training_examples': len(train),
             'training_source_domains': sorted(domains), 'corpus_sha256': _hash(corpus),
             'source_manifest_sha256': _hash(sources), 'rights_verified': False}
    reports = []
    for ident,sid,words,label in heldout:
        result = predict(model, ' '.join(words))
        reports.append({'id':ident,'source_id':sid,'expected':label,'predicted':result['label'],'correct':result['label']==label})
    model['evaluation'] = {'heldout_count':len(reports),'accuracy':sum(r['correct'] for r in reports)/len(reports),
                           'cases':reports,'split_provenance':'caller-declared; temporal/source independence not verified'}
    model['artifact_sha256'] = _hash(model)
    return model


def predict(model, text):
    # Integrity detects accidental content drift; it does not authenticate source.
    if 'artifact_sha256' in model and _hash({k:v for k,v in model.items() if k != 'artifact_sha256'}) != model['artifact_sha256']:
        raise ValueError('model artifact checksum mismatch')
    words = tokens(_text(text))
    vocab = set(model['vocabulary']);known = [w for w in words if w in vocab]
    if not known:
        return {'label':None,'status':'out_of_vocabulary','scores':{}}
    scores = {}
    size = len(vocab)
    for label in model['labels']:
        counts = model['token_counts'][label]
        denominator = sum(counts.values()) + size
        score = math.log(model['class_documents'][label]/model['training_examples'])
        score += sum(math.log((counts.get(word,0)+1)/denominator) for word in known)
        scores[label] = score
    label = sorted(scores, key=lambda k:(-scores[k],k))[0]
    return {'label':label,'status':'classified','scores':scores,'unknown_token_count':len(words)-len(known),
            'admissions_success_prediction':False}
