"""Named single-guard mutants; run with the same interpreter as core tests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'backend/app/modules/m20_general_cognitive_worker/c3_layers.py'
MUTANTS = {
    'packet_limit_removed': ('    if len(encoded) > 1000000:', '    if False:'),
    'policy_removed': ('    c3_policy(packet)', '    pass # policy removed'),
    'policy_effects_allowed': ('    if action in codes:', '    if False:'),
    'unknown_action_allowed': ("    if action != 'draft':", '    if False:'),
    'text_limit_removed': ('    if len(value) > MAX_TEXT:', '    if False:'),
    'row_limit_removed': ('    if len(value) > MAX_ROWS:', '    if False:'),
    'requirement_limit_removed': ('    if len(requirement_texts) > MAX_REQUIREMENTS:', '    if False:'),
    'reference_limit_removed': ("    if len(value) > MAX_ROWS:\n        refuse('LIMIT', label + ' exceeds reference cap')", "    if False:\n        refuse('LIMIT', label + ' exceeds reference cap')"),
    'reference_guard_removed': ('    if not set(value) <= known:', '    if False:'),
    'duplicate_reference_removed': ('    if len(set(value)) != len(value):', '    if False:'),
    'duplicate_id_removed': ('    if ident in bank:', '    if False:'),
    'private_access_allowed': ("        if row.get('access') not in ('public', 'user_supplied'):", '        if False:'),
    'source_url_guard_removed': ("        if parsed.scheme != 'https' or not host or parsed.username or parsed.password:", '        if False:'),
    'fact_authenticity_removed': ("            if not ids or any(claim != facts[fid]['text'] for fid in ids):", '            if False:'),
    'paid_tool_allowed': ('        free = type(cost) in (int, float) and cost == 0', '        free = True'),
    'bool_cost_allowed': ('        free = type(cost) in (int, float) and cost == 0', '        free = isinstance(cost, (int, float)) and cost == 0'),
    'truth_claim_flipped': ("'source_truth_verified': False", "'source_truth_verified': True"),
    'mind_claim_flipped': ("'human_mind_replication': False", "'human_mind_replication': True"),
    'untrusted_source_flag_removed': ("'untrusted_data': True", "'untrusted_data': False"),
    'coverage_count_fabricated': ("'unsupported': len(missing)", "'unsupported': 0"),
    'json_nan_allowed': ('allow_nan=False', 'allow_nan=True'),
    'unknown_field_guard_removed': ('not set(packet) <= FIELDS', 'False'),
    'empty_requirements_guard_removed': ("    if isinstance(packet.get('requirements_text'), str) and not packet['requirements_text'].strip():", '    if False:'),
    'requirements_id_guard_removed': ("not set(mapping) <= {r['id'] for r in requirements}", 'False'),
}


def main():
    source = SOURCE.read_text(); results = []
    with tempfile.TemporaryDirectory(prefix='c3-mutants-') as tmp:
        for name, (old, new) in MUTANTS.items():
            assert old in source, name + ' mutation target missing'
            path = Path(tmp) / (name + '.py'); path.write_text(source.replace(old, new, 1))
            env = dict(os.environ, C3_SOURCE=str(path))
            proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/c3_layers', '-p', 'test_layers.py'],
                                  cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            # Compilation or import failures do not count as killed behavior.
            killed = proc.returncode != 0 and 'Ran ' in proc.stderr and '_FailedTest' not in proc.stderr and 'SyntaxError' not in proc.stderr
            results.append({'mutant': name, 'killed': killed, 'returncode': proc.returncode,
                            'tail': proc.stderr[-1600:]})
    output = {'total': len(results), 'killed': sum(r['killed'] for r in results), 'results': results}
    print(json.dumps(output, indent=2))
    return 0 if all(r['killed'] for r in results) else 1

if __name__ == '__main__': raise SystemExit(main())
