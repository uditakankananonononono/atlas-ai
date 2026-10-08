"""Real generated archive build, typecheck and local browser/HTTP acceptance.
Requires Node >=20.9, Python project dependencies and Playwright Chromium.
No remote writes, deployment, mocks or fake storage-success tests.
Run: PYTHONPATH=backend python scripts/m08_verify_landing_runtime.py --output /tmp/m08-evidence
"""
import argparse, json, os, subprocess, time, urllib.request, urllib.error, tempfile, zipfile
from io import BytesIO
from app.modules.m08_startup_growth.schemas import LandingPageIn
from app.modules.m08_startup_growth.runtime_service import Service
from app.modules.m08_startup_growth.sql_repository import Repository
from app.modules.m08_startup_growth import sql_repository
from app.core.approvals import approvals
from app.core.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser()
parser.add_argument('--output',required=True)
parser.add_argument('--chrome',default='/usr/bin/google-chrome')
parser.add_argument('--port',type=int,default=3188)
args=parser.parse_args()
out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
workspace=tempfile.TemporaryDirectory(prefix='m08-runtime-')
root=Path(workspace.name)/'app';root.mkdir()
engine=create_engine('sqlite:///'+str(Path(workspace.name)/'builds.db'))
Base.metadata.create_all(engine)
sql_repository.engine=engine
repo=Repository('runtime-verification',sessionmaker(bind=engine))
service=Service(repo,approvals)
build=service.landing_page(LandingPageIn(project_id='local-verification', product_name='Atlas <script>alert("x")</script> {launch}',hero='Build safely & ship real work. "Quotes", $cash, and <tags> stay text.',features=['Approve before publishing','Evidence from real runs','No placeholders {or code}']))
archive=repo.get(build.id).archive
(out/'generated-landing.zip').write_bytes(archive)
with zipfile.ZipFile(BytesIO(archive)) as z:z.extractall(root)
for name,command in [('npm-install',['npm','install','--no-audit','--no-fund']),('next-build',['npm','run','build']),('typecheck',['npm','run','typecheck'])]:
 with (out/(name+'.log')).open('w') as log:
  subprocess.run(command,cwd=root,env=os.environ|{'NEXT_TELEMETRY_DISABLED':'1'},stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
(out/'package-lock.json').write_bytes((root/'package-lock.json').read_bytes())
base_url=f'http://127.0.0.1:{args.port}' 
env=os.environ.copy();env.pop('SUPABASE_SERVICE_ROLE_KEY',None);env.pop('NEXT_PUBLIC_SUPABASE_URL',None)
with open(out/'next-start.log','w') as log:
 server=subprocess.Popen(['npm','run','start','--','--hostname','127.0.0.1','--port',str(args.port)],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  for _ in range(80):
   try:
    urllib.request.urlopen(base_url+'/',timeout=1);break
   except Exception: time.sleep(.25)
  else:raise RuntimeError('server did not start')
  data=json.loads((root/'app/content.json').read_text())
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=args.chrome,headless=True,args=['--no-sandbox'])
   page=browser.new_page(viewport={'width':1280,'height':900})
   dialogs=[];errors=[]
   page.on('dialog',lambda d:(dialogs.append(d.message),d.dismiss()))
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(base_url+'/',wait_until='networkidle')
   assert page.locator('h1').inner_text()==data['product_name']
   assert page.locator('main p').inner_text()==data['hero']
   assert page.locator('main li').all_inner_texts()==data['features']
   assert page.locator('main script').count()==0
   assert not dialogs and not errors
   for width,name in [(1280,'desktop.png'),(390,'mobile.png')]:
    page.set_viewport_size({'width':width,'height':900});page.screenshot(path=str(out/name),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
   results=[]
   for body,content_type,expected in [('email=bad','application/x-www-form-urlencoded',400),('email=person%40example.com','application/x-www-form-urlencoded',503),('not-json','application/json',400),('email=a%40b%40c.com','application/x-www-form-urlencoded',400)]:
    response=page.request.post(base_url+'/api/waitlist',data=body,headers={'Content-Type':content_type})
    assert response.status==expected,(response.status,response.text())
    results.append({'input':body,'status':response.status,'body':response.json()})
   (out/'browser-http.json').write_text(json.dumps({'literal_text_exact':True,'no_dialogs':not dialogs,'no_page_errors':not errors,'desktop_and_mobile_no_overflow':True,'http':results},indent=2))
   browser.close()
  print('PASS: exact literal DOM, no script execution, desktop/mobile overflow, actual HTTP 400/503')
 finally:
  import signal
  os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=10)
  engine.dispose();workspace.cleanup()
