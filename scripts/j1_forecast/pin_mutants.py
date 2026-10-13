import subprocess, os, sys, pathlib, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
"""Runs the pin tests against each mutant of j1_forecast.py; every mutant must be killed."""
src = (ROOT / 'backend/app/modules/m20_general_cognitive_worker/j1_forecast.py').read_text()
M = [
 ("time non-str", "if not isinstance(value, str) or len(value) > 64:", "if len(value) > 64:"),
 ("time len 64->65", "len(value) > 64", "len(value) > 65"),
 ("time len 64->63", "len(value) > 64", "len(value) > 63"),
 ("event keys or->and", "if not isinstance(event, dict) or set(event) != {'seq', 'prev', 'kind', 'data', 'sha256'}:", "if not isinstance(event, dict) and set(event) != {'seq', 'prev', 'kind', 'data', 'sha256'}:"),
 ("header or->and", "if event['kind'] != 'header' or not isinstance(event['data'], dict) or set(event['data'])", "if event['kind'] != 'header' or not isinstance(event['data'], dict) and set(event['data'])"),
 ("dup prediction ok", "if ident in predictions or ident != digest", "if ident != digest"),
 ("unknown kind ok", "refuse('INTEGRITY', 'unknown event kind')", "pass"),
 ("bad json code", "refuse('INTEGRITY', 'invalid ledger JSON')", "refuse('SCHEMA', 'invalid ledger JSON')"),
 ("guard ignores injected", "classifier = policy_guard or policy.classify", "classifier = policy.classify"),
 ("code fallback", "code or 'POLICY_REFUSED_UNKNOWN'", "code or 'X'"),
 ("split [1]", "str(exc).split(':')[0]", "str(exc).split(':')[1]"),
 ("split [-1]", "str(exc).split(':')[0]", "str(exc).split(':')[-1]"),
 ("ensure_ascii", "ensure_ascii=False", "ensure_ascii=True"),
 ("sort_keys", "sort_keys=True", "sort_keys=False"),
 ("bins default", "bins=10, calibrated=True):\n    \"\"\"ONE", "bins=5, calibrated=True):\n    \"\"\"ONE"),
 ("report bins default", "def report(self, *, calibrated=True, bins=10)", "def report(self, *, calibrated=True, bins=5)"),
 ("upper bound", "'upper': (i + 1) / bins", "'upper': i / bins"),
 ("MAX_EVENTS", "MAX_EVENTS = 20001", "MAX_EVENTS = 20000"),
 ("MAX_BYTES", "MAX_BYTES = 16000000", "MAX_BYTES = 16000001"),
 ("event cap load >", "if len(events) > MAX_EVENTS:", "if len(events) >= MAX_EVENTS:"),
 ("event cap append >=", "if len(events) >= MAX_EVENTS:\n            refuse('LIMIT', 'ledger event cap reached')", "if len(events) > MAX_EVENTS:\n            refuse('LIMIT', 'ledger event cap reached')"),
 ("byte cap load", "if len(raw) > MAX_BYTES:", "if len(raw) >= MAX_BYTES:"),
 ("byte cap append", "if f.tell() + len(line) > MAX_BYTES:", "if f.tell() + len(line) >= MAX_BYTES:"),
 ("pred cap append", "if len(ps) >= MAX_PREDICTIONS:", "if len(ps) > MAX_PREDICTIONS:"),
 ("pred cap check", "if len(predictions) > MAX_PREDICTIONS:\n            refuse('LIMIT', 'prediction cap exceeded')", "if len(predictions) >= MAX_PREDICTIONS:\n            refuse('LIMIT', 'prediction cap exceeded')"),
 ("score cap", "len(predictions) > MAX_PREDICTIONS or len(resolutions) > MAX_PREDICTIONS", "len(predictions) > MAX_PREDICTIONS"),
 ("ZZ_TIME", "refuse('TIME', 'horizon must be strictly after made_at')", "refuse('SCHEMA', 'horizon must be strictly after made_at')"),
 ("ZZ_LIMIT", "refuse('LIMIT', 'ledger byte cap reached')", "refuse('SCHEMA', 'ledger byte cap reached')"),
 ("ZZ_INTEGRITY", "refuse('INTEGRITY', 'incomplete trailing ledger event')", "refuse('SCHEMA', 'incomplete trailing ledger event')"),
 ("clean_text domain", "policy.clean_text(value, 'INTEL', name, MAX_TEXT)", "policy.clean_text(value, 'J1', name, MAX_TEXT)"),
 ("module_id", "'module_id': 20", "'module_id': 21"),
 ("flock removed", "fcntl.flock(fd, fcntl.LOCK_EX)", "pass"),
 ("fsync before flush", "f.write(line); f.flush(); os.fsync(f.fileno())", "f.write(line); os.fsync(f.fileno()); f.flush()"),
 ("mkdir parents", "mkdir(parents=True, exist_ok=True)", "mkdir(exist_ok=True)"),
 ("MAX_TEXT", "MAX_TEXT = 4096", "MAX_TEXT = 4097"),
]
surv=[]
for name, old, new in M:
    assert src.count(old)>=1, name
    out=pathlib.Path(tempfile.gettempdir()) / ('j1_pin_mut_%d.py' % M.index((name, old, new))); out.write_text(src.replace(old,new,1))
    env=dict(os.environ, J1_SOURCE=str(out), PYTHONPATH=str(ROOT / 'backend'))
    r=subprocess.run([sys.executable,'-m','pytest','-q','-x',str(ROOT / 'tests/j1_forecast/test_j1_forecast_pins.py')],capture_output=True,text=True,env=env,cwd=str(ROOT),timeout=100)
    k = r.returncode == 1
    print(('KILLED  ' if k else 'SURVIVED'), name)
    if not k: surv.append(name)
print('survivors:',surv)
sys.exit(1 if surv else 0)
