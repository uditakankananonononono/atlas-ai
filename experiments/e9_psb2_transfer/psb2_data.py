"""Independent PSB2 loader. Original published labels, never target-generated labels."""
import hashlib, json, random
from pathlib import Path
ROOT = Path(__file__).parent
PROBLEMS = ('basement', 'cut-vector', 'find-pair', 'fuel-cost', 'leaders', 'luhn')
NATIVE = ('basement', 'fuel-cost', 'leaders', 'luhn')

def freeze(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'))

def read(name, kind):
    return [json.loads(s) for s in (ROOT/'data'/name/(kind+'.jsonl')).read_text().splitlines()]

def split(name, seed=0, n_train=200, n_test=1000):
    edge = read(name, 'edge')
    # Remove duplicate INPUTS, not only duplicate rows: no input can leak between splits.
    seen = {freeze([r[k] for k in sorted(r) if k.startswith('input')]) for r in edge}
    unique = []
    for row in read(name, 'random-sample'):
        key = freeze([row[k] for k in sorted(row) if k.startswith('input')])
        if key not in seen:
            seen.add(key); unique.append(row)
    random.Random(seed).shuffle(unique)
    n = n_train-len(edge)
    assert n >= 0 and len(unique) >= n+n_test
    return edge+unique[:n], unique[n:n+n_test]

def io(row, extended=False):
    inputs = [row[k] for k in sorted(row) if k.startswith('input')]
    outputs = [row[k] for k in sorted(row) if k.startswith('output')]
    if extended:
        return inputs, outputs[0] if len(outputs)==1 else tuple(outputs)
    assert len(inputs)==len(outputs)==1
    return tuple(inputs[0]), outputs[0]

def task(name, seed=0, extended=False):
    tr, te = split(name, seed)
    return dict(domain=name, desc=name, train=[io(r,extended) for r in tr],
                test=[io(r,extended) for r in te])

def manifest():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'data').glob('*/*.jsonl'))}
