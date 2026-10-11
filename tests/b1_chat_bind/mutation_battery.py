"""Hand-selected behavioral mutations; every replacement must be killed."""
import json
import pathlib
import subprocess
import tempfile

MUTANTS = {
 'schema-guard': ("if not isinstance(row, dict) or set(row) != ROW_KEYS:", "if False:"),
 'string-fields': ("if not all(isinstance(v, str) for v in row.values()) or not row['message_id'] or not row['conversation_id']:", "if False:"),
 'timezone': ("if t.tzinfo is None:", "if False:"),
 'topic-guard': ("if not evidence.get('topic'):", "if False:"),
 'previous-revision': ("if previous is None:", "if False:"),
 'revision-newer': ("if previous_pin and _time(pin['ts']) <= _time(self._span(previous_pin)['ts']):", "if False:"),
 'revision-reason': ("if not evidence.get('reason'):", "if False:"),
 'stop-word': ("if state in {'STOPPED_BY_USER', 'PARKED_BY_USER'} and not re.search", "if False and not re.search"),
 'revise-validate': ("        self._validate(sid, state, evidence)\n        pin = self._pin", "        pin = self._pin"),
 'history-snapshot': ("digest=_digest(clean), history_complete=False,", "digest=_digest(clean), history_complete=True,"),
 'history-report': ("history_complete=False, history_gap=self.snapshot['history_gap']", "history_complete=True, history_gap=self.snapshot['history_gap']"),
 'exclude-audit': ("        self.audit.append(dict(span_id=sid, reviewed_nonrequest=True, reason=reason))", "        pass"),
 'owner-guard': ("if row['author'] != 'user' or row['service'] not in OWNER_CHANNELS:", "if False:"),
 'duplicate-guard': ("if row['message_id'] in seen:", "if False:"),
 'db-count': ("if type(observed_total) is not int or observed_total != len(clean):", "if False:"),
 'future-guard': ("if _time(row['ts']) > cutoff:", "if False:"),
 'digest-guard': ("if self.snapshot['digest'] != snapshot['digest']:", "if False:"),
 'unknown-span': ("if sid not in self._index:", "if False:"),
 'state-guard': ("if state not in STATES or not isinstance(evidence, dict):", "if False:"),
 'implementation-proof': ("if state == 'IMPLEMENTED':", "if False:"),
 'later-pin': ("if _time(pin['ts']) < _time(target['ts']) or pin['span_id'] == sid:", "if False:"),
 'substitute-guard': ("if state == 'REFUSED_WITH_SUBSTITUTE':", "if False:"),
 'nonrequest-review': ("if not isinstance(reason, str) or not reason.strip():", "if False:"),
 'revision-required': ("if sid in self.bindings or sid in self.exclusions:", "if False:"),
 'db-digest': ("if len(clean) != self.snapshot['observed_total'] or _digest(clean) != self.snapshot['digest']:", "if False:"),
 'stopped-refusal': ("return 'PLAN_REFUSED_STOPPED'", "return 'ALLOWED'"),
 'unmapped-refusal': ("return 'PLAN_REFUSED_UNMAPPED'", "return 'ALLOWED'"),
 'zero-unmapped-gate': ("passed = bool(self.snapshot['rows']) and counts['UNMAPPED'] == 0", "passed = True"),
 'private-report': ("return dict(unit='B1', passed=passed", "return dict(private_rows=self.snapshot['rows'], unit='B1', passed=passed"),
 'policy-removal': ("        policy(action)", "        pass"),
 'lossless-partition': ("text=text[start:end]", "text=text[start:end].strip()"),
}

def run():
    root = pathlib.Path(__file__).parent
    code = root.parents[1]/'backend/app/modules/m20_general_cognitive_worker/c30_b1'
    source = (code/'chat_bind.py').read_text()
    results=[]
    for name,(old,new) in MUTANTS.items():
        assert old in source, name
        with tempfile.TemporaryDirectory() as tmp:
            dest=pathlib.Path(tmp)
            (dest/'chat_bind.py').write_text(source.replace(old,new))
            (dest/'test_chat_bind.py').write_text('\n'.join(line for line in (root/'test_chat_bind.py').read_text().splitlines() if not line.startswith('sys.path.insert')))
            for file in ('db_chat_bind.py','route_adapter.py'):
                (dest/file).write_bytes((code/file).read_bytes())
            package = dest/'c30_b1'
            package.mkdir()
            (package/'__init__.py').touch()
            for file in ('chat_bind.py','db_chat_bind.py','route_adapter.py'):
                (package/file).write_bytes((dest/file).read_bytes())
            p=subprocess.run(['python3','-m','unittest','test_chat_bind'],cwd=dest,capture_output=True,text=True)
            # A syntax error or import failure is not a legitimate behavioral kill.
            killed=p.returncode!=0 and 'SyntaxError' not in p.stderr and 'ImportError' not in p.stderr
            results.append(dict(mutant=name,killed=killed))
    route_source = (code/'route_adapter.py').read_text()
    for name, old, new in (
        ('tenant-auth', "if not isinstance(tenant_id, str) or not tenant_id.strip():", "if False:"),
        ('tenant-isolation', "if tenant_id not in self.store:", "if False:"),
        ('route-refusal', "raise Refused('PLAN_REFUSED_ROUTE')", "return {}")):
        with tempfile.TemporaryDirectory() as tmp:
            dest=pathlib.Path(tmp)
            (dest/'chat_bind.py').write_text(source)
            (dest/'db_chat_bind.py').write_bytes((code/'db_chat_bind.py').read_bytes())
            (dest/'route_adapter.py').write_text(route_source.replace(old,new))
            (dest/'test_chat_bind.py').write_text('\n'.join(line for line in (root/'test_chat_bind.py').read_text().splitlines() if not line.startswith('sys.path.insert')))
            package = dest/'c30_b1'
            package.mkdir()
            (package/'__init__.py').touch()
            for file in ('chat_bind.py','db_chat_bind.py','route_adapter.py'):
                (package/file).write_bytes((dest/file).read_bytes())
            p=subprocess.run(['python3','-m','unittest','test_chat_bind'],cwd=dest,capture_output=True,text=True)
            killed=p.returncode!=0 and 'SyntaxError' not in p.stderr and 'ImportError' not in p.stderr
            results.append(dict(mutant=name,killed=killed))
    with tempfile.TemporaryDirectory() as tmp:
        dest=pathlib.Path(tmp)
        for file in ('chat_bind.py','route_adapter.py'):
            (dest/file).write_bytes((code/file).read_bytes())
        (dest/'db_chat_bind.py').write_text((code/'db_chat_bind.py').read_text().replace('if owner_total != total:', 'if False:'))
        (dest/'test_chat_bind.py').write_text('\n'.join(line for line in (root/'test_chat_bind.py').read_text().splitlines() if not line.startswith('sys.path.insert')))
        package=dest/'c30_b1'
        package.mkdir()
        (package/'__init__.py').touch()
        for file in ('chat_bind.py','db_chat_bind.py','route_adapter.py'):
            (package/file).write_bytes((dest/file).read_bytes())
        p=subprocess.run(['python3','-m','unittest','test_chat_bind'],cwd=dest,capture_output=True,text=True)
        results.append(dict(mutant='db-unfiltered-count',killed=p.returncode!=0 and 'SyntaxError' not in p.stderr and 'ImportError' not in p.stderr))
    print(json.dumps(dict(total=len(results),killed=sum(x['killed'] for x in results),results=results),indent=2))
    return all(x['killed'] for x in results)

if __name__=='__main__':raise SystemExit(0 if run() else 1)
