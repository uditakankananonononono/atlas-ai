#!/bin/sh
# Run from repository root. Explicit interpreter may be passed as first argument.
set -eu
PY=${1:-python3.12}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
"$PY" -c 'import sys; assert sys.version_info[:2] == (3,12), sys.version'
"$PY" -m unittest discover -s experiments/e9_formalism -p 'test_*.py' -v
"$PY" -m unittest discover -s experiments/e10_metric_critique -p 'test_*.py' -v
"$PY" experiments/e9_formalism/run_experiment.py --output "$TMP/e9.json"
"$PY" experiments/e10_metric_critique/run_experiment.py --output "$TMP/e10.json"
"$PY" - "$TMP" <<'PY'
import importlib.util
import json
from pathlib import Path
import sys
out = Path(sys.argv[1])
for expected,actual in [('experiments/e9_formalism/results.json',out/'e9.json'),
                        ('experiments/e10_metric_critique/results.json',out/'e10.json')]:
    a,b = json.loads(Path(expected).read_text()),json.loads(actual.read_text())
    # Patch interpreter version is metadata, not algorithmic evidence.
    a.pop('python',None); b.pop('python',None)
    assert a == b, f'evidence mismatch: {expected}'
sys.path.insert(0,'experiments/e10_metric_critique')
spec = importlib.util.spec_from_file_location('family_holdout','experiments/e10_metric_critique/family_holdout.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
actual = json.loads(json.dumps(module.run()))
expected = json.loads(Path('experiments/e10_metric_critique/family_holdout_results.json').read_text())
assert actual == expected, 'family holdout evidence mismatch'
print('All three committed evidence artifacts match independent reruns.')
PY
