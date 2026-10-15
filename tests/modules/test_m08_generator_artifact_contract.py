"""Real M08 generators, archive dependency and untrusted-text regressions."""
import io,json,unittest,zipfile
from app.modules.m08_startup_growth.service import Service
from app.modules.m08_startup_growth.runtime_service import Service as RuntimeService
from app.modules.m08_startup_growth.schemas import DocumentationIn,LandingPageIn

class Repository:
    tenant_id='tenant-a'
    def __init__(self):self.rows={}
    def save(self,**row):self.rows[row['id']]=row
    def get(self,ident):return self.rows.get(ident)
class Approvals:
    def put(self,*args,**kwargs):raise AssertionError('generation must not propose or send')

class GeneratorArtifactsTest(unittest.TestCase):
    def setUp(self):self.repo=Repository();self.service=Service(self.repo,Approvals())
    def files(self,build):
        with zipfile.ZipFile(io.BytesIO(self.repo.get(build.id)['archive'])) as archive:
            return {name:archive.read(name).decode() for name in archive.namelist()}
    def test_redoc_selection_includes_referenced_spec(self):
        build=self.service.documentation(DocumentationIn(project_id='p',title='API',outputs=['redoc'],
              code_files={'api.py':'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/items")\ndef items():return []\n'}))
        files=self.files(build)
        self.assertEqual(set(files),{'redoc.html','openapi.json','evidence.json'})
        self.assertIn('spec-url="openapi.json"',files['redoc.html'])
        self.assertIn('/items',json.loads(files['openapi.json'])['paths'])
        self.assertEqual(json.loads(files['evidence.json'])['completeness'],'partial_static_inventory')
    def test_manual_only_does_not_smuggle_spec_or_redoc(self):
        build=self.service.documentation(DocumentationIn(project_id='p',title='Manual',outputs=['user_manual']))
        self.assertEqual(set(self.files(build)),{'USER_MANUAL.md','evidence.json'})
    def test_source_hash_and_unresolved_mount_limit_retained(self):
        source='from fastapi import APIRouter\nr=APIRouter(prefix="/v1")\n@r.post("/things")\ndef create():pass\n'
        from hashlib import sha256
        files=self.files(self.service.documentation(DocumentationIn(project_id='p',title='API',code_files={'routes.py':source})))
        evidence=json.loads(files['evidence.json'])
        self.assertEqual(evidence['code_files']['routes.py'],sha256(source.encode()).hexdigest())
        self.assertTrue(any('include_router' in warning for warning in evidence['limitations']))
    def test_both_generator_entrypoints_treat_owner_text_as_data(self):
        hostile='</h1>{(()=>{throw Error("injected")})()}<script>alert(1)</script>"\\\n'
        data=LandingPageIn(project_id='p',product_name=hostile,hero=hostile,features=[hostile])
        for cls in (Service,RuntimeService):
            with self.subTest(service=cls.__name__):
                files=self.files(cls(self.repo,Approvals()).landing_page(data))
                content=json.loads(files['app/content.json'])
                self.assertEqual(content,{'product_name':hostile,'hero':hostile,'features':[hostile]})
                self.assertNotIn(hostile,files['app/page.tsx'])
                self.assertIn('content.features.map',files['app/page.tsx'])
                self.assertIn('package.json',files)
                self.assertNotIn('SUPABASE_SERVICE_ROLE_KEY',files['app/page.tsx'])
    def test_mounted_documentation_route_duplicate_returns_422(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.auth.context import require_tenant,TenantContext
        from app.modules.m08_startup_growth.routes import router,get_service
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[require_tenant]=lambda:TenantContext('tenant-a','actor')
        app.dependency_overrides[get_service]=lambda:self.service
        duplicate='from fastapi import FastAPI\napp=FastAPI()\n@app.get("/x")\ndef x():pass\n@app.get("/x")\ndef y():pass\n'
        with TestClient(app) as client:
            response=client.post('/startup-growth/documentation',json={'project_id':'p','title':'API','code_files':{'api.py':duplicate}})
            self.assertEqual(response.status_code,422,response.text)
            self.assertIn('duplicate operation',response.json()['detail'])
        self.assertEqual(self.repo.rows,{})
if __name__=='__main__':unittest.main()
