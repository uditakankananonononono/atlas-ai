import hashlib
from fastapi.testclient import TestClient
from app.core.models import ApprovalRequest,ApprovalStatus
from app.main import app
from app.modules.m15_document_generator.routes import get_publication_worker
import app.core.approvals as approval_module
C=TestClient(app);U='/api/v1/document-generator/publication-worker/execute';H={'X-Atlas-Tenant':'t','X-Atlas-Actor':'u'};DATA=b'PDF bytes'
class Worker:
 def render(self,v,f):return DATA
 def upload_private(self,key,data):return {'provider':'store','object_key':key,'access':'private','download_url':'https://files/x','published_sha256':hashlib.sha256(data).hexdigest(),'byte_size':len(data)}
class Approvals:
 def __init__(self,status=ApprovalStatus.APPROVED):self.status=status
 def get(self,i,user_id=None):return ApprovalRequest(id=i,module_id=15,action_type='render_document',status=self.status,payload={'tenant_id':user_id,'version_id':'v','format':'pdf','content_hash':'a'*64})
def setup_function():app.dependency_overrides[get_publication_worker]=lambda:Worker()
def teardown_function():app.dependency_overrides.clear()
def body():return {'approval_id':'a','version_id':'v','format':'pdf','expected_content_hash':'a'*64,'object_key':'private/v.pdf'}
def test_executes_bound_renderer_and_private_upload(monkeypatch):
 monkeypatch.setattr(approval_module,'approvals',Approvals());r=C.post(U,json=body(),headers=H);assert r.status_code==200;b=r.json();assert b['executed'] and b['access']=='private' and b['published_sha256']==hashlib.sha256(DATA).hexdigest()
def test_rejects_missing_or_mismatched_approval(monkeypatch):
 monkeypatch.setattr(approval_module,'approvals',Approvals(ApprovalStatus.PENDING));r=C.post(U,json=body(),headers=H);assert r.status_code==409 and 'approval is required' in r.text
 monkeypatch.setattr(approval_module,'approvals',Approvals());x=body();x['expected_content_hash']='b'*64;r=C.post(U,json=x,headers=H);assert r.status_code==409 and 'different render content' in r.text
def test_rejects_nonprivate_or_mismatched_upload_receipt(monkeypatch):
 class Bad(Worker):
  def upload_private(self,key,data):return {'access':'public','published_sha256':hashlib.sha256(data).hexdigest(),'byte_size':len(data)}
 app.dependency_overrides[get_publication_worker]=lambda:Bad();monkeypatch.setattr(approval_module,'approvals',Approvals());r=C.post(U,json=body(),headers=H);assert r.status_code==409 and 'private access' in r.text
