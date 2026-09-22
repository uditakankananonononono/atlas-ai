from app.modules.m08_startup_growth.schemas import LandingPageIn,DocumentationIn,PitchDeckIn
from app.modules.m08_startup_growth.service import Service
class Repo:
 def __init__(s):s.tenant_id="tenant-test";s.x={}
 def save(s,**d):s.x[d['id']]=type('R',(),d)
 def get(s,i):return s.x.get(i)
class Approvals:
 def __init__(s):s.items=[]
 def put(s,x):s.items.append(x);return x
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
