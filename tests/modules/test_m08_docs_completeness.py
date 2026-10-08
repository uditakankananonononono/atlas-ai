import json,io,zipfile
from test_m08_startup_growth import Repo,Approvals
from app.modules.m08_startup_growth.service import Service
from app.modules.m08_startup_growth.schemas import DocumentationIn

def test_static_router_prefix_head_and_options_documented():
    repo=Repo();approvals=Approvals();svc=Service(repo,approvals)
    code='''from fastapi import APIRouter
api = APIRouter(prefix="/v1")
@api.head("/health")
def health(): pass
@api.options("/health")
def options(): pass
@api.get("/items")
def items(): pass
'''
    out=svc.documentation(DocumentationIn(project_id='p',title='API',code_files={'routes.py':code}))
    with zipfile.ZipFile(io.BytesIO(repo.get(out.id).archive)) as z:
        paths=json.loads(z.read('openapi.json'))['paths']
        assert set(paths)=={'/v1/health','/v1/items'}
        assert set(paths['/v1/health'])=={'head','options'}
