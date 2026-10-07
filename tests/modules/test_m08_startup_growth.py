from app.modules.m08_startup_growth.schemas import LandingPageIn,DocumentationIn,PitchDeckIn
from app.modules.m08_startup_growth.service import Service
class Repo:
 def __init__(s):s.tenant_id="tenant-test";s.x={}
 def save(s,**d):s.x[d['id']]=type('R',(),d)
 def get(s,i):return s.x.get(i)
class Approvals:
 def __init__(s):s.items=[]
 def put(s,x,*,user_id=None):s.items.append((x,user_id));return x
def test_growth_builds_are_real_archives_and_gated():
 r=Repo();a=Approvals();svc=Service(r,a)
 site=svc.landing_page(LandingPageIn(project_id='p',product_name='Atlas',hero='Ship safely',features=['Approvals']))
 assert 'app/page.tsx' in site.manifest['files'] and 'app/api/waitlist/route.ts' in site.manifest['files']
 docs=svc.documentation(DocumentationIn(project_id='p',title='API',code_files={'routes.py':'@router.get("/x")\ndef x(): pass'}))
 assert 'openapi.json' in docs.manifest['files'] and 'evidence.json' in docs.manifest['files']
 proposal=svc.propose(site.id,'deploy_startup_site');assert proposal.status=='pending' and len(a.items)==1

def test_publish_approval_preserves_tenant_boundary():
 r=Repo();a=Approvals();svc=Service(r,a)
 site=svc.landing_page(LandingPageIn(project_id='p',product_name='Atlas',hero='Ship safely',features=['Approvals']))
 assert svc.propose(site.id,'deploy_startup_site').payload['tenant_id']=='tenant-test'
 assert a.items[-1][1]=='tenant-test'

def test_documentation_preserves_multiple_methods_and_reports_duplicate_operation():
 import json,zipfile
 from io import BytesIO
 import pytest
 r=Repo();svc=Service(r,Approvals())
 code='@router.get("/items")\ndef read(): pass\n@router.post("/items")\ndef create(): pass'
 result=svc.documentation(DocumentationIn(project_id='p',title='API',code_files={'routes.py':code}))
 with zipfile.ZipFile(BytesIO(r.get(result.id).archive)) as archive:
  document=json.loads(archive.read('openapi.json'))
 assert set(document['paths']['/items'])=={'get','post'}
 with pytest.raises(ValueError,match='duplicate operation'):
  svc.documentation(DocumentationIn(project_id='p',title='API',code_files={'a.py':'@router.get("/items")','b.py':'@app.get("/items")'}))

def test_landing_text_is_literal_tsx_content_and_waitlist_table_is_validated(tmp_path):
 import json,zipfile,subprocess,shutil
 from io import BytesIO
 import pytest
 from pydantic import ValidationError
 with pytest.raises(ValidationError):
  LandingPageIn(project_id='p',product_name='Name',hero='Hero',features=['Feature'],waitlist_table='bad"table')
 r=Repo();svc=Service(r,Approvals())
 strings=['Curly { literal } < > " quote', '</li>{process.exit()} & braces', 'Line one\nLine two']
 site=svc.landing_page(LandingPageIn(project_id='p',product_name=strings[0],hero=strings[1],features=strings[2:]))
 with zipfile.ZipFile(BytesIO(r.get(site.id).archive)) as z:
  page=z.read('app/page.tsx').decode()
 # JSX string expressions must contain JSON literals, not executable raw input.
 for text in strings:assert '{'+json.dumps(text)+'}' in page
 if not shutil.which('node'):pytest.skip('Node parser unavailable')
 parser="const ts=require('./frontend/node_modules/typescript');const fs=require('fs');const p=ts.createSourceFile('page.tsx',fs.readFileSync(process.argv[1],'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);if(p.parseDiagnostics.length){console.error(p.parseDiagnostics.map(d=>d.messageText));process.exit(1)}"
 source=tmp_path/'page.tsx';source.write_text(page)
 subprocess.run(['node','-e',parser,str(source)],check=True)


def test_documentation_route_maps_duplicate_operation_to_reviewable_422():
 import pytest
 from fastapi import HTTPException
 from app.modules.m08_startup_growth.routes import docs
 with pytest.raises(HTTPException) as exc:
  docs(DocumentationIn(project_id='p',title='API',code_files={'a.py':'@router.get("/x")','b.py':'@router.get("/x")'}),Service(Repo(),Approvals()))
 assert exc.value.status_code==422
 assert 'duplicate operation' in exc.value.detail
