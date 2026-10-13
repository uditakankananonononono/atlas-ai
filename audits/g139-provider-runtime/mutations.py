"""Run exact-site mutations sequentially; always restore original source bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

path = Path('backend/app/integrations/owner_account_runtime_g139.py')
original = path.read_bytes()
source = original.decode()
mutations = [
 ('operation_redirect', 'follow_redirects=False', 'follow_redirects=True'),
 ('proxy_environment', 'trust_env=False', 'trust_env=True'),
 ('subject_drift', 'if self._subject(service, identity) != subject:', 'if False:'),
 ('tenant_lookup', "(tenant, service)).fetchone()\n            outcome", "('tenant1', service)).fetchone()\n            outcome"),
 ('revocation', "if row is None or row['revoked']:", 'if row is None:'),
 ('redirect_status', 'if identity.status_code != 200:', 'if False:'),
 ('postprobe_authority', "if self.authority(row['authority_ref'], binding_digest(tenant, service, subject)) is not True:\n                        raise", 'if False:\n                        raise'),
 ('postprobe_read', 'if self.read_authority(tenant, service, subject, url) is not True:\n                        raise', 'if False:\n                        raise'),
 ('size_bound', 'if size > limit:', 'if False:'),
 ('strict_google_subject', 'if type(sub) is not str or not sub or len(sub) > 255 or not sub.isascii() or not sub.isprintable():', 'if False:'),
 ('drop_bearer_metadata', "request=httpx.Request('GET', url))", "request=httpx.Request('GET', url, headers=headers))"),
]
results=[]
try:
 for name,old,new in mutations:
  assert source.count(old)==1,(name,source.count(old))
  path.write_text(source.replace(old,new))
  run=subprocess.run([sys.executable,'-m','pytest','--noconftest','-p','no:cacheprovider','tests/modules/test_owner_account_runtime_g139.py','-q','-k','not sqlite_lock_timeout'],capture_output=True,text=True,timeout=40)
  status='CAUGHT' if run.returncode==1 and 'FAILED ' in run.stdout and 'ERROR ' not in run.stdout else 'SURVIVED' if run.returncode==0 else 'INVALID'
  results.append({'mutation':name,'status':status,'rc':run.returncode,'failed_tests':[l for l in run.stdout.splitlines() if l.startswith('FAILED ')]})
  path.write_bytes(original)
  assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(original).digest()
finally:
 path.write_bytes(original)
print(json.dumps({'mutations':results,'source_restored_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'basis':'builder-run exact edit sensitivity, not independent audit'},indent=2))
if any(r['status']!='CAUGHT' for r in results):sys.exit(1)
