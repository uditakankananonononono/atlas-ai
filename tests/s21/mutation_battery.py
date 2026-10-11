"""Single-change guard flips, restored after each subprocess. No remote writes."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'backend/app/modules/m20_general_cognitive_worker/c33_self_feed/core.py'
ROUTES = CORE.with_name('routes.py')
# Guard, refusal and limit flips; runtime variants must be killed by assertions.
mutations = [
 ('policy_call', CORE, "self.policy(action) is not True", 'False'),
 ('local_effect_ban', CORE, " or action != 'analyze'", ''),
 ('tenant_required', CORE, "or not tenant_id.strip()", 'or False'),
 ('aware_timestamp', CORE, 'if moment.utcoffset() is None:', 'if False:'),
 ('payload_byte_limit', CORE, 'if len(payload) > self.max_bytes:', 'if False:'),
 ('record_limit', CORE, 'if supplied > self.max_records:', 'if False:'),
 ('text_limit', CORE, "if len(row['text']) > max_text or", 'if False or'),
 ('config_exact_int', CORE, 'if type(value) is not int or', 'if False or'),
 ('config_positive', CORE, 'not 1 <= value <= upper', 'not 0 <= value <= upper'),
 ('config_upper', CORE, 'not 1 <= value <= upper', 'not 1 <= value'),
 ('visibility', CORE, "if row['visibility'] not in {'public', 'owner'} or", 'if False or'),
 ('followed_public', CORE, "(row['kind'] == 'followed_account' and row['visibility'] != 'public')", 'False'),
 ('conflicting_dedupe', CORE, 'if key in unique and unique[key] != row:', 'if False:'),
 ('platform_dedupe', CORE, "key = (row['platform'], row['kind'], row['id'])", "key = (row['kind'], row['id'])"),
 ('json_exact_version', CORE, "type(data['schema_version']) is not int", 'False'),
 ('duplicate_json_key', CORE, 'if key in out:', 'if False:'),
 ('csv_columns', CORE, 'len(reader.fieldnames) != len(FIELDS)', 'False'),
 ('record_fields', CORE, 'set(row) != FIELDS', 'False'),
 ('record_kind', CORE, "if row['kind'] not in KINDS:", 'if False:'),
 ('blank_identity', CORE, "if any(not row[key].strip() for key in FIELDS - {'text'}):", 'if False:'),
 ('source_scheme', CORE, "if not re.match(r'^(https?://[^\\s]+|export:[^\\s]+)$', row['source_ref']):", 'if False:'),
 ('unicode_scalar', CORE, 'if any(any(0xD800 <= ord(char) <= 0xDFFF for char in value) for value in row.values()):', 'if False:'),
 ('detached_run', CORE, 'self._reports[(tenant_id, report_id)] = copy.deepcopy(out)', 'self._reports[(tenant_id, report_id)] = out'),
 ('detached_report', CORE, 'return copy.deepcopy(self._reports[key])', 'return self._reports[key]'),
 ('report_retention', CORE, 'while len(self._reports) > self.max_reports:', 'while False:'),
 ('cluster_word_boundary', CORE, 'len(words & terms)', "sum(1 for term in terms if term in row['text'].lower())"),
 ('unknown_no_brief', CORE, "if group['theme'] != 'unclassified'", 'if True'),
 ('body_extra_fields', ROUTES, "extra='forbid'", "extra='ignore'"),
 ('auth_run', ROUTES, 'tenant: TenantContext = Depends(require_tenant)', "tenant: str = 'a'"),
 ('tenant_report', ROUTES, 'service.report(tenant.tenant_id, report_id)', "service.report('a', report_id)"),
 ('schema_refusal_code', CORE, "except (ValueError, UnicodeError, RecursionError):\n            reject('SOCIAL_REFUSED_SCHEMA')", "except (ValueError, UnicodeError, RecursionError):\n            reject('SOCIAL_REFUSED_OTHER')"),
 ('private_refusal_code', CORE, "reject('SOCIAL_REFUSED_THIRDPARTYPRIVATE')", "reject('SOCIAL_REFUSED_OTHER')"),
 ('oversize_refusal_code', CORE, "reject('SOCIAL_REFUSED_OVERSIZE')", "reject('SOCIAL_REFUSED_OTHER')"),
 ('policy_refusal_code', CORE, "reject('POLICY_REFUSED_ACTION')", "reject('POLICY_REFUSED_OTHER')"),
]
baseline=subprocess.run([sys.executable,'-m','pytest','tests/s21','-q'],cwd=ROOT,capture_output=True,text=True,timeout=10)
assert baseline.returncode==0, baseline.stdout+baseline.stderr
results=[]
for name,path,old,new in mutations:
    original=path.read_text()
    assert old in original, name
    try:
        path.write_text(original.replace(old,new,1))
        # Python bytecode caches can retain a same-size rewrite within a second.
        for cached in path.parent.glob('__pycache__/*.pyc'):
            cached.unlink()
        try:
            done=subprocess.run([sys.executable,'-m','pytest','tests/s21','-q'],cwd=ROOT,capture_output=True,text=True,timeout=4)
            output=done.stdout+done.stderr
        except subprocess.TimeoutExpired:
            done=type('Timeout', (), {'returncode':124})()
            output='Runtime boundedness test timed out at 4 seconds.'
        (ROOT/'audits/s21'/f'mutant-{name}.log').write_text(output)
        results.append({'name':name,'killed':done.returncode!=0,'exit_code':done.returncode,'test_failures': output.split('short test summary info')[-1][-1500:]})
    finally:
        path.write_text(original)
        for cached in path.parent.glob('__pycache__/*.pyc'):
            cached.unlink()
print(json.dumps({'mutants':len(results),'killed':sum(r['killed'] for r in results),'results':results},indent=2))
assert all(r['killed'] for r in results), 'SURVIVING MUTANT'
