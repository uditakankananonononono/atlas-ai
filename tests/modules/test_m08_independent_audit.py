import io,json,zipfile,itertools,hashlib
from app.modules.m08_startup_growth.schemas import DocumentationIn,LandingPageIn
from app.modules.m08_startup_growth.service import Service
from app.modules.m08_startup_growth.runtime_service import Service as RuntimeService
from test_m08_generator_artifact_contract import Repository,Approvals

def extract(repo,build):
 row=repo.get(build.id);assert row['sha256']==hashlib.sha256(row['archive']).hexdigest()
 with zipfile.ZipFile(io.BytesIO(row['archive'])) as z:return {n:z.read(n).decode() for n in z.namelist()}
def test_all_output_subsets_keep_redoc_reference_closed():
 options=['openapi','redoc','user_manual','technical_blog'];mapping={'openapi':{'openapi.json'},'redoc':{'openapi.json','redoc.html'},'user_manual':{'USER_MANUAL.md'},'technical_blog':{'TECHNICAL_BLOG.md'}}
 for mask in itertools.product([False,True],repeat=4):
  selected=[o for o,b in zip(options,mask) if b];repo=Repository();s=Service(repo,Approvals());f=extract(repo,s.documentation(DocumentationIn(project_id='p',title='API',outputs=selected)))
  expected={'evidence.json'}.union(*(mapping[o] for o in selected));assert set(f)==expected
  if 'redoc.html' in f:assert 'spec-url="openapi.json"' in f['redoc.html'];assert json.loads(f['openapi.json'])['openapi']=='3.1.0'
def test_legacy_landing_exact_shared_runtime_files():
 for text in ['Plain text','Quote"\\\n','<script>throw Error(1)</script>','{process.exit()}','অসমীয়া 🚀','Text \u2028\u2029']:
  d=LandingPageIn(project_id='p',product_name=text,hero=text,features=[text]);files=[]
  for cls in [Service,RuntimeService]:
   repo=Repository();files.append(extract(repo,cls(repo,Approvals()).landing_page(d)))
  assert files[0]==files[1]
  assert json.loads(files[0]['app/content.json'])['product_name']==text
