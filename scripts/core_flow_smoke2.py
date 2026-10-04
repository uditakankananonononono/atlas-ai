import os,tempfile,socket,json,sys
tmp=tempfile.mkdtemp(prefix="cf2_")
os.environ.update(ATLAS_DATABASE_URL=f"sqlite:///{tmp}/s.db",ATLAS_AUTO_CREATE_SCHEMA="1",ATLAS_RATE_LIMIT_PER_MINUTE="1000000",ATLAS_TOKEN_KEY="TEST-ONLY-throwaway-key-not-a-secret-0123456789abcdef")
os.environ.pop("ATLAS_ENV",None)
rc=socket.socket.connect
def blk(s,a,*x,**k):
    if isinstance(a,tuple) and a[0] not in("127.0.0.1","::1","localhost"): raise OSError("blocked "+a[0])
    return rc(s,a,*x,**k)
socket.socket.connect=blk
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app,raise_server_exceptions=False)
H={"x-atlas-tenant":"t1","x-atlas-actor":"u1"}

steps=[]
def st(n,m,p,**k):
    r=c.request(m,p,headers=H,**k); steps.append(dict(step=n,method=m,path=p,status=r.status_code,body=r.text[:600])); return r
E="/api/v1/executive-dashboard"; S="/api/v1/side-hustle-scraper"; C="/api/v1/claire"
# m16
r=st("m16 post event","POST",E+"/events",json={"topic":"opportunity.discovered","aggregate_type":"opportunity","aggregate_id":"o1","payload":{"title":"FIXTURE-event"}})
st("m16 post event missing field","POST",E+"/events",json={"topic":"x"})
st("m16 kpi after event","GET",E+"/kpis")
st("m16 snapshot","GET",E+"/snapshot"); st("m16 events","GET",E+"/events"); st("m16 csv export","GET",E+"/export/events.csv")
st("m16 command preview","POST",E+"/commands/preview",json={"utterance":"show pending approvals"})
st("m16 digest","GET",E+"/digest")
H2={"x-atlas-tenant":"t2","x-atlas-actor":"u2"}
r2=c.get(E+"/events",headers=H2); steps.append(dict(step="m16 other tenant events (expect [])",method="GET",path=E+"/events",status=r2.status_code,body=r2.text[:200]))
# m18 (network blocked)
st("m18 blueprints","POST",S+"/blueprints",json={"query":"freelance tutoring"})
st("m18 feasibility","POST",S+"/feasibility",json={"query":"freelance tutoring"})
st("m18 collect (network blocked)","POST",S+"/collect",json={"query":"freelance tutoring"})
st("m18 rank","POST",S+"/rank",json={"query":"freelance tutoring"})
st("m18 refresh","POST",S+"/refresh",json={})
st("m18 durable run create","POST",S+"/durable-runs",json={"query":"freelance tutoring"})
st("m18 durable list","GET",S+"/durable-runs")
# m21
g=st("m21 goal create","POST",C+"/goals",json={"goal":"Draft a weekly study plan","acceptance":["has 5 days"],"limits":{}})
gid=None
try: gid=g.json().get("id") or g.json().get("goal_id")
except Exception: pass
if gid: st("m21 goal realize","POST",f"{C}/goals/{gid}/realize")
st("m21 devices list","GET",C+"/devices")
st("m21 owner workflow empty","POST",C+"/owner-workflow-279-329",json={})
st("m21 other tenant realize","POST",f"{C}/goals/{gid}/realize") if False else None
json.dump(steps,open(sys.argv[1],"w"),indent=1)
for x in steps: print(x["status"],x["step"],"|",x["body"][:230].replace("\n"," "))
