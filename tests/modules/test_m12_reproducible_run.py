from fastapi.testclient import TestClient
from app.main import app
C=TestClient(app);U='/api/v1/ai-research-lab/reproducible-run/checkpoint';H={'X-Atlas-Tenant':'science','X-Atlas-Actor':'owner'};Z='0'*64;A='a'*64;B='b'*64
def test_checkpoint_pins_reproducibility_and_resume_truth():
 p={'run_id':'r1','workflow_sha256':Z,'code_version':'abc123','created_at':'2026-09-22T07:00:00Z','datasets':[{'dataset_id':'d','sha256':A,'source_ref':'doi:1'}],'nodes':[{'node_id':'clean','status':'completed','provider':'ollama','model':'qwen','seed':7,'budget_cents':10,'spent_cents':4,'input_sha256':A,'output_sha256':B},{'node_id':'analyze','status':'queued','provider':'ollama','model':'qwen','seed':7,'budget_cents':20,'spent_cents':0,'input_sha256':B}],'resume_from_node_id':'analyze'}
 r=C.post(U,json=p,headers=H);assert r.status_code==200;b=r.json();assert b['tenant_id']=='science' and b['completed_nodes']==1 and b['total_budget_cents']==30 and b['resumable'];assert len(b['checkpoint_sha256'])==64 and 'does not execute' in b['boundary']
def test_checkpoint_rejects_budget_overrun_completed_without_output_and_bad_resume():
 n={'node_id':'n','status':'completed','provider':'p','model':'m','budget_cents':1,'spent_cents':2,'input_sha256':A}
 base={'run_id':'r','workflow_sha256':Z,'code_version':'v','created_at':'2026-09-22T07:00:00Z','nodes':[n]}
 r=C.post(U,json=base,headers=H);assert r.status_code==422 and 'exceeds' in r.text
 n['spent_cents']=1;r=C.post(U,json=base,headers=H);assert r.status_code==422 and 'output_sha256' in r.text
