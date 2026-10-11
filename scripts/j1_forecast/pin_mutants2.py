import os, pathlib, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
"""Runs test_pins2.py against each mutant of j1_forecast.py; every mutant must be killed."""
src = (ROOT / 'backend/app/modules/m20_general_cognitive_worker/j1_forecast.py').read_text()
M = [
 ("prev link unchecked", "event['prev'] != prev or ", ""),
 ("prev link or->and", "type(event['seq']) is not int or event['seq'] != index or event['prev'] != prev or event['sha256'] != actual", "type(event['seq']) is not int or event['seq'] != index or event['prev'] != prev and event['sha256'] != actual"),
 ("seq type check removed", "type(event['seq']) is not int or ", ""),
 ("seq index check removed", " or event['seq'] != index", ""),
 ("resolution dict check removed", "if not isinstance(row, dict) or set(row) != RES_KEYS:", "if set(row) != RES_KEYS:"),
 ("collections list check removed", "if not isinstance(predictions, list) or not isinstance(resolutions, list):", "if False:"),
 ("non-finite except narrowed", "except (ValueError, TypeError, RecursionError):", "except (TypeError, RecursionError):"),
 ("non-finite code changed", "refuse('INTEGRITY', 'event is not finite JSON')", "refuse('SCHEMA', 'event is not finite JSON')"),
 ("check cap removed", "if len(predictions) > MAX_PREDICTIONS:\n            refuse('LIMIT', 'prediction cap exceeded')", "pass"),
 ("check cap off by one", "if len(predictions) > MAX_PREDICTIONS:\n            refuse('LIMIT', 'prediction cap exceeded')", "if len(predictions) >= MAX_PREDICTIONS:\n            refuse('LIMIT', 'prediction cap exceeded')"),
 ("genesis prev", "prev = '0' * 64; predictions = {}", "prev = '1' * 64; predictions = {}"),
]
surv = []
for i, (name, old, new) in enumerate(M):
    assert src.count(old) == 1, name
    out = pathlib.Path(tempfile.gettempdir()) / ('j1_pin2_mut_%d.py' % i)
    out.write_text(src.replace(old, new))
    env = dict(os.environ, J1_SOURCE=str(out), PYTHONPATH=str(ROOT / 'backend'))
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', str(ROOT / 'tests/j1_forecast/test_pins2.py')],
                       capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=100)
    print('KILLED  ' if r.returncode else 'SURVIVED', name)
    if not r.returncode:
        surv.append(name)
print('survivors:', surv)
sys.exit(1 if surv else 0)
