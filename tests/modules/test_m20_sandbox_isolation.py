import pytest
from app.modules.m20_general_cognitive_worker.safety import SandboxPolicy
from app.modules.m20_general_cognitive_worker.sandbox import SandboxRunner,SandboxViolation


def test_policy_canonical_containment_and_symlink_escape(tmp_path):
 root=tmp_path/'project';root.mkdir();outside=tmp_path/'outside';outside.mkdir()
 (root/'escape').symlink_to(outside,target_is_directory=True)
 p=SandboxPolicy(filesystem_root=str(root))
 assert p.allows_path(str(root/'new'/'ok'))
 assert not p.allows_path(str(root/'..'/'outside'))
 assert not p.allows_path(str(root/'escape'/'secret'))
 assert not p.allows_path('relative')
 assert not SandboxPolicy().allows_path(str(root))


def test_actual_execution_cannot_read_or_write_host_outside_project(tmp_path,monkeypatch):
 monkeypatch.setenv('ATLAS_SANDBOX_BACKEND','bubblewrap')
 outside=tmp_path/'private.txt';outside.write_text('host-secret-canary')
 target=tmp_path/'written-outside.txt'
 code=f'''from pathlib import Path
for name in [{str(outside)!r},{str(target)!r}]:
 try:
  if name.endswith('private.txt'): print(Path(name).read_text())
  else: Path(name).write_text('escape')
 except OSError: print('blocked')
print(2+2)
'''
 result=SandboxRunner(workspace_root=str(tmp_path/'volumes')).run_python('a',code)
 assert result.returncode==0,result.stderr
 assert result.stdout=='blocked\nblocked\n4\n'
 assert not target.exists()
 assert outside.read_text()=='host-secret-canary'


def test_no_backend_fails_closed_without_running_code(tmp_path,monkeypatch):
 monkeypatch.setenv('ATLAS_SANDBOX_BACKEND','missing')
 with pytest.raises(SandboxViolation,match='execution refused'):
  SandboxRunner(workspace_root=str(tmp_path)).run_python('a','print(4)')


def test_project_ids_and_symlink_volume_never_alias(tmp_path):
 runner=SandboxRunner(workspace_root=str(tmp_path/'volumes'))
 with pytest.raises(SandboxViolation):runner.project_volume('owner/a')
 outside=tmp_path/'outside';outside.mkdir();(tmp_path/'volumes').mkdir()
 (tmp_path/'volumes'/'a').symlink_to(outside,target_is_directory=True)
 with pytest.raises(SandboxViolation):runner.project_volume('a')


def test_network_permission_does_not_enable_unsafe_execution(tmp_path):
 runner=SandboxRunner(SandboxPolicy(network_enabled=True,allowed_hosts=frozenset({'example.com'})),workspace_root=str(tmp_path))
 with pytest.raises(SandboxViolation,match='unsupported'):
  runner.run_python('a','print(4)',allowed_hosts=['example.com'])


def test_actual_mounted_runtime_route_isolates_host_and_same_project_across_owners(tmp_path,monkeypatch,oidc_auth_headers):
 from fastapi.testclient import TestClient
 from sqlalchemy import create_engine
 from app.main import app
 from app.modules.m20_general_cognitive_worker import runtime_routes as routes
 from app.modules.m20_general_cognitive_worker.sql_repository import GCWRepository
 from app.modules.m20_general_cognitive_worker.runtime import GCWRuntime
 import app.modules.m20_general_cognitive_worker.runtime as runtime_module
 monkeypatch.setenv('ATLAS_ENV','production');monkeypatch.setenv('ATLAS_SANDBOX_BACKEND','bubblewrap')
 monkeypatch.setattr(routes,'_runtimes',{})
 monkeypatch.setattr(runtime_module.tempfile,'gettempdir',lambda:str(tmp_path))
 engine=create_engine('sqlite:///'+str(tmp_path/'shared.db'))
 for owner in ('a','b'):
  repo=GCWRepository(engine,tenant_id=owner);repo.create_schema();routes.bind_runtime(GCWRuntime(repo))
 assert routes._runtimes['a'].sandbox.workspace_root!=routes._runtimes['b'].sandbox.workspace_root
 c=TestClient(app);base='/api/v1/api/modules/20/api/modules/20/runtime/sandbox/run'
 a=oidc_auth_headers('a');b=oidc_auth_headers('b')
 r=c.post(base,headers=a,json={'project_id':'same','code':"open('owner-canary.txt','w').write('a-secret');print(4)"})
 assert r.status_code==200,r.text
 assert r.json()['returncode']==0,r.json()
 code="from pathlib import Path; print(Path('owner-canary.txt').exists())"
 r=c.post(base,headers=b,json={'project_id':'same','code':code})
 assert r.status_code==200 and r.json()['stdout']=='False\n',r.text
 outside=tmp_path/'hostsecret';outside.write_text('outside-project-canary')
 r=c.post(base,headers=a,json={'project_id':'same','code':f'print(open({str(outside)!r}).read())'})
 assert r.status_code==200 and r.json()['returncode']!=0,r.text
 assert 'outside-project-canary' not in r.text
 monkeypatch.setenv('ATLAS_SANDBOX_BACKEND','missing')
 r=c.post(base,headers=a,json={'project_id':'same','code':'print(4)'})
 assert r.status_code==403 and 'execution refused' in r.text
