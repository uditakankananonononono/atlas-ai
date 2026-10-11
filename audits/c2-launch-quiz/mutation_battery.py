"""C2 hand-selected mutation battery. Never writes tracked source."""
import json
import pathlib
import subprocess
import tempfile

MUTANTS = [
    ('shared hook bypass', 'if self.policy_hook(action) is not True:', 'if False:'),
    ('consent bypass', 'if consent is not True:', 'if False:'),
    ('owner bypass', "if s['owner'] != owner:", 'if False:'),
    ('capacity bypass', 'if len(self._sessions) >= self.max_sessions:', 'if False:'),
    ('question guard bypass', "if q['id'] is None or question_id != q['id']:", 'if False:'),
    ('choice bypass', "if choice not in q['options']:", 'if False:'),
    ('blank/oversize bypass', 'if not isinstance(value, str) or not value.strip() or len(value) > maximum:', 'if not isinstance(value, str):'),
    ('doc consent bypass', "if not isinstance(doc, dict) or doc.get('consent') is not True:", 'if not isinstance(doc, dict):'),
    ('doc capacity bypass', "if not isinstance(docs, list) or len(docs) > LIMITS['documents']:", 'if not isinstance(docs, list):'),
    ('duplicate doc bypass', 'if did in ids:', 'if False:'),
    ('no profile copy', 'return deepcopy({', 'return dict({'),
    ('policy hook removed', '        enforce_policy(action)', '        pass'),
    ('policy refusal removed', 'if action in refused:', 'if False:'),
    ('incomplete guard bypass', "if len(s['preferences']) < len(BASE):", 'if False:'),
    ('delete no purge', '        del self._sessions[sid]', '        pass'),
    ('mind claim', "'claims_mind_copy': False", "'claims_mind_copy': True"),
    ('edit source false', "'source': 'user-edit'", "'source': 'inferred'"),
    ('document cue disabled', 'if words.intersection(terms)', 'if False'),
    ('answer text lost', "'explanation': explanation", "'explanation': ''"),
    ('profile count lies', "'answered_count': len(s['answers'])", "'answered_count': 99"),
]

def run(source, tests):
    original = source.read_text()
    outcomes = []
    for name, old, new in MUTANTS:
        if old not in original:
            raise RuntimeError('Mutation anchor missing: ' + name)
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            target = root / 'app/modules/m20_general_cognitive_worker/launch_quiz_c2.py'
            target.parent.mkdir(parents=True)
            target.write_text(original.replace(old, new, 1))
            (root / 'test_launch_quiz.py').write_text(tests.read_text())
            p = subprocess.run([__import__('sys').executable, '-m', 'unittest', 'test_launch_quiz'], cwd=root, capture_output=True, text=True)
            # A failure is recorded with its exact mode, not passed off as assertion.
            outcomes.append({'name': name, 'killed': p.returncode != 0, 'output': p.stderr.strip()})
    print(json.dumps(outcomes, indent=2))
    return all(m['killed'] for m in outcomes)

if __name__ == '__main__':
    import sys
    root = pathlib.Path(__file__).resolve().parent
    raise SystemExit(0 if run(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else root.parents[1] / 'backend/app/modules/m20_general_cognitive_worker/launch_quiz_c2.py', pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root.parents[1] / 'tests/modules/test_launch_quiz_c2.py') else 1)
