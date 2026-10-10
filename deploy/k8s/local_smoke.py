"""Local single-node kind smoke substitute for X12 (Kubernetes production deployment acceptance).

What this does: builds an OVERLAY copy of deploy/k8s/atlas.yaml (existing file is read only and never edited), and plans/runs
`kind create cluster` (single control-plane node), `kind load docker-image`, `kubectl apply`, `kubectl rollout status`, then
checks Deployment ready replicas and GET /health and GET /ready through the API server service proxy, then deletes the cluster.
Everything uses free local components (Docker, kind, kubectl). Every command pins `--context kind-<cluster>`.

Overlay changes (each recorded in the report): the image reference replaced by the one you pass (it must be a pinned reference: an explicit non-latest tag or an @sha256 digest) and imagePullPolicy set to IfNotPresent; replicas lowered;
CPU/memory requests lowered (limits untouched); HorizontalPodAutoscaler dropped by default (kind has no metrics-server);
env PORT set to the manifest's containerPort 8000 (the Dockerfile's PORT defaults to 8080 and uvicorn listens on ${PORT:-8080},
while the manifest's containerPort, probes and Service targetPort are 8000). No Secret is created unless add_empty_secret is passed.

IMAGE SOURCE: the Atlas image is locally built, not registry-published. The manifest's registry reference has no resolvable owner and the
repo has no workflow that pushes an image. The image comes from the root Dockerfile (`docker build -t <tag> .`), then `kind load docker-image`;
the harness does the build and load, this module only plans `kind load` and sets imagePullPolicy IfNotPresent. This exception covers only the
local Atlas image.

RUNTIME PREREQUISITES (read from the root Dockerfile, scripts/validate_config.py, scripts/migrate.py, backend/app/platform/config.py,
backend/app/platform/health.py, backend/app/main.py; not provided by deploy/k8s/atlas.yaml):
- The container CMD runs `python scripts/validate_config.py`, then `python scripts/migrate.py`, then uvicorn. ATLAS_ENV defaults to production
  when unset, so an EMPTY atlas-runtime Secret makes validate_config exit and the pod never starts.
- Production config needs ATLAS_DATABASE_URL (PostgreSQL, postgresql or postgresql+psycopg scheme), ATLAS_REDIS_URL (redis or rediss),
  ATLAS_OIDC_ISSUER, ATLAS_OIDC_AUDIENCE, and ATLAS_SECRET_PROVIDER set to gcp-secret-manager, vault-literal, or platform-environment together with
  ATLAS_TRUST_PLATFORM_SECRETS=1 (the value `environment` is rejected in production).
- In production migrate.py runs `alembic upgrade head` against that database before the server starts; /ready returns 200 only when the database
  answers, Redis answers PING and the Alembic revision equals head.
- GAP: atlas.yaml has no PostgreSQL, no Redis, and its default-deny NetworkPolicy blocks all pod egress and ingress with no allow rule, so a green run
  needs in-cluster PostgreSQL and Redis plus an egress allowance, all provisioned outside this script. This script does not create secrets or
  databases; the check-secret step fails the run if the Secret is absent.

What it honestly cannot cover (stated verbatim as required):
Multi-node production cluster behavior, cloud load balancers, real ingress

UNVERIFIED (nobody has run this; the builder authored it without running anything, and verification is the peer's runtime audit responsibility): real kind cluster creation, whether the image boots, Secret materialization (the empty atlas-runtime Secret may leave the image unable to start), and the API-server service proxy under the default-deny NetworkPolicy. The tests use a fake runner, so they check planning and orchestration logic only, not a cluster. The timeouts (kind --wait 120s, rollout --timeout=180s) are guesses.

Also not covered: HorizontalPodAutoscaler behavior (dropped by default), whether the cluster's CNI enforces the default-deny
NetworkPolicy (not checked), production replica counts and resource requests, secrets content. A passing run is a local smoke result,
not production acceptance and not an attestation; it never writes audits/production/kubernetes-acceptance.json.
"""
from __future__ import annotations
import argparse,copy,json,re,shutil,subprocess,sys
from dataclasses import dataclass
from pathlib import Path
import yaml
NOT_COVERED_GAP="Multi-node production cluster behavior, cloud load balancers, real ingress"
CLUSTER_NAME="atlas-smoke"
NAMESPACE="atlas"
DEPLOYMENT="atlas-api"
SERVICE_PROXY="/api/v1/namespaces/atlas/services/atlas-api:8000/proxy"
KIND_CONFIG=str(Path(__file__).resolve().parent/"kind-cluster.yaml")
ATTESTATION_FILENAME="kubernetes-acceptance.json"
DEFAULT_REPORT_PATH=None
SCOPE="single-node kind cluster, overlay of deploy/k8s/atlas.yaml"
@dataclass(frozen=True)
class Step:
    name:str;argv:list
@dataclass(frozen=True)
class Eval:
    ok:bool;detail:str
def load_manifests(path):
    return [d for d in yaml.safe_load_all(Path(path).read_text()) if d]
def dump_manifests(manifests):
    return yaml.safe_dump_all(manifests,sort_keys=False)
_IMAGE_RE=re.compile(r"^[a-z0-9][a-z0-9._/:-]*(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|@sha256:[0-9a-f]{64})$")
def validate_image(image):
    """Accept only a pinned reference: name:tag (tag not 'latest') or name@sha256:<64 hex>. Does not pull or inspect the image."""
    if not isinstance(image,str) or not _IMAGE_RE.match(image):raise ValueError("image must be name:tag or name@sha256:<64 hex>")
    if "@sha256:" not in image and image.rsplit(":",1)[-1]=="latest":raise ValueError("image tag 'latest' is not a pinned reference")
    if "@sha256:" not in image and ":" not in image.rsplit("/",1)[-1]:raise ValueError("image has no tag")
def build_overlay(manifests,image,replicas=1,cpu_request="100m",memory_request="256Mi",drop_hpa=True,add_empty_secret=False):
    """Return (overlay manifests, change descriptions). Input is not mutated."""
    validate_image(image)
    if type(replicas) is not int or replicas<1:raise ValueError("replicas must be an integer >= 1")
    ms=copy.deepcopy(manifests);changes=[]
    for m in ms:
        if m.get("kind")!="Deployment":continue
        spec=m["spec"];spec["replicas"]=replicas;changes.append(f"Deployment {m['metadata']['name']}: replicas set to {replicas}")
        for c in spec["template"]["spec"]["containers"]:
            old=c.get("image");c["image"]=image;c["imagePullPolicy"]="IfNotPresent"
            changes.append(f"container {c['name']}: image {old} -> {image}, imagePullPolicy IfNotPresent")
            port=str(c["ports"][0]["containerPort"])
            c["env"]=[e for e in c.get("env",[]) if e.get("name")!="PORT"]+[{"name":"PORT","value":port}]
            changes.append(f"container {c['name']}: env PORT set to {port} (Dockerfile default is 8080; manifest containerPort/probes/Service use {port})")
            res=c.setdefault("resources",{});res["requests"]={"cpu":cpu_request,"memory":memory_request}
            changes.append(f"container {c['name']}: resource requests set to cpu {cpu_request}, memory {memory_request} (limits unchanged)")
    if drop_hpa:
        dropped=[m for m in ms if m.get("kind")=="HorizontalPodAutoscaler"]
        ms=[m for m in ms if m.get("kind")!="HorizontalPodAutoscaler"]
        for m in dropped:changes.append(f"HorizontalPodAutoscaler {m['metadata']['name']} dropped (kind has no metrics-server)")
    if add_empty_secret and not any(m.get("kind")=="Secret" and m["metadata"].get("name")=="atlas-runtime" for m in ms):
        ms.append({"apiVersion":"v1","kind":"Secret","metadata":{"name":"atlas-runtime","namespace":NAMESPACE}})
        changes.append("Secret atlas-runtime added EMPTY (opt-in; no values supplied; the image will not start in production mode without real config)")
    return ms,changes
def _kubectl(*args):return ["kubectl","--context",f"kind-{CLUSTER_NAME}",*args]
def plan_commands(overlay_path,image):
    return [Step("create-cluster",["kind","create","cluster","--name",CLUSTER_NAME,"--config",KIND_CONFIG,"--wait","120s"]),
            Step("load-image",["kind","load","docker-image",image,"--name",CLUSTER_NAME]),
            Step("apply",_kubectl("apply","-f",str(overlay_path))),
            Step("check-secret",_kubectl("-n",NAMESPACE,"get","secret","atlas-runtime")),
            Step("rollout",_kubectl("-n",NAMESPACE,"rollout","status",f"deployment/{DEPLOYMENT}","--timeout=180s"))]
def plan_cleanup():
    return [Step("delete-cluster",["kind","delete","cluster","--name",CLUSTER_NAME])]
def evaluate_deployment(obj):
    try:
        want=obj["spec"]["replicas"];st=obj.get("status") or {}
        ready=st["readyReplicas"];avail=st["availableReplicas"]
    except (KeyError,TypeError):return Eval(False,"deployment status missing replicas/readyReplicas/availableReplicas")
    if ready==want and avail==want:return Eval(True,f"{ready}/{want} ready")
    return Eval(False,f"{ready}/{want} ready, {avail} available")
def _check(name,ok,detail=""):return {"name":name,"ok":bool(ok),"detail":detail}
def run_smoke(runner,overlay_path,image,keep_cluster=False,overlay_changes=None):
    """runner(argv)->(returncode,stdout). Stops at the first failing step; always attempts cleanup unless keep_cluster."""
    checks=[];changes=[]
    def go(step):
        try:rc,out=runner(step.argv)
        except Exception as e:rc,out=1,f"{type(e).__name__}: {e}"
        checks.append(_check(step.name,rc==0,"" if rc==0 else str(out)[:300]));return rc==0,out
    try:
        ok=True
        for step in plan_commands(overlay_path,image):
            ok,_=go(step)
            if not ok:break
        if ok:
            try:rc,out=runner(_kubectl("-n",NAMESPACE,"get","deployment",DEPLOYMENT,"-o","json"))
            except Exception as e:rc,out=1,str(e)
            try:ev=evaluate_deployment(json.loads(out)) if rc==0 else Eval(False,"kubectl get deployment failed")
            except (ValueError,TypeError):ev=Eval(False,"deployment output was not JSON")
            checks.append(_check("deployment-ready",ev.ok,ev.detail))
            for path in ("/health","/ready"):
                try:rc,out=runner(_kubectl("get","--raw",SERVICE_PROXY+path))
                except Exception as e:rc,out=1,str(e)
                checks.append(_check(f"probe {path}",rc==0,"" if rc==0 else str(out)[:300]))
    finally:
        if not keep_cluster:
            for step in plan_cleanup():
                try:rc,out=runner(step.argv)
                except Exception as e:rc,out=1,str(e)
                checks.append(_check(step.name,rc==0,"" if rc==0 else str(out)[:300]))
    passed=all(c["ok"] for c in checks if c["name"]!="delete-cluster") and any(c["name"]=="probe /ready" for c in checks)
    return build_report(checks,passed,overlay_changes)
def build_report(checks,passed,overlay_changes=None):
    covered=["manifests applied to a single-node kind cluster","deployment ready replicas match desired","GET /health via API server service proxy","GET /ready via API server service proxy"] if passed else []
    return {"kind":"kind-local-smoke","scope":SCOPE,"passed":bool(passed),"checks":checks,"covered":covered,
            "not_covered":[NOT_COVERED_GAP,"HorizontalPodAutoscaler behavior (dropped by default)","NetworkPolicy enforcement by the cluster CNI (not checked)","production replica counts and resource requests","runtime secret contents"],
            "overlay_changes":list(overlay_changes) if overlay_changes else [],
            "prerequisites":["image is locally built from the root Dockerfile, not registry-published; harness builds and runs kind load","ATLAS_ENV defaults to production: atlas-runtime needs ATLAS_DATABASE_URL (PostgreSQL), ATLAS_REDIS_URL, ATLAS_OIDC_ISSUER, ATLAS_OIDC_AUDIENCE, ATLAS_SECRET_PROVIDER (not 'environment')","in-cluster PostgreSQL and Redis reachable from the pod; alembic upgrade head runs before boot and /ready needs the revision at head","default-deny NetworkPolicy has no allow rule: an egress allowance is needed","PORT is set to 8000 by the overlay (Dockerfile default 8080)"],
            "unverified":["real kind cluster creation","image boot","Secret materialization (provisioned by the harness, not by this script)","API-server service proxy under default-deny NetworkPolicy","timeouts 120s/180s are guesses","verification is the peer's runtime audit responsibility"],
            "claims_production_acceptance":False,"attestation":False}
def write_report(report,path):
    p=Path(path)
    if p.name==ATTESTATION_FILENAME:raise ValueError("refusing to write the production attestation filename; this is a local smoke report")
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
def _subprocess_runner(argv):
    r=subprocess.run(argv,capture_output=True,text=True);return r.returncode,(r.stdout if r.returncode==0 else r.stdout+r.stderr)
def main(argv=None):
    ap=argparse.ArgumentParser(description="Local single-node kind smoke for deploy/k8s/atlas.yaml. "+NOT_COVERED_GAP+" are NOT covered.")
    ap.add_argument("--image",required=True);ap.add_argument("--manifest",default=str(Path(__file__).resolve().parent/"atlas.yaml"))
    ap.add_argument("--overlay-out",required=True);ap.add_argument("--replicas",type=int,default=1);ap.add_argument("--keep-hpa",action="store_true");ap.add_argument("--add-empty-secret",action="store_true")
    ap.add_argument("--keep-cluster",action="store_true");ap.add_argument("--out",default=DEFAULT_REPORT_PATH)
    a=ap.parse_args(argv)
    for tool in ("kind","kubectl","docker"):
        if not shutil.which(tool):print(f"missing required tool: {tool}",file=sys.stderr);return 2
    ms,changes=build_overlay(load_manifests(a.manifest),a.image,replicas=a.replicas,drop_hpa=not a.keep_hpa,add_empty_secret=a.add_empty_secret)
    Path(a.overlay_out).write_text(dump_manifests(ms))
    rep=run_smoke(_subprocess_runner,a.overlay_out,a.image,keep_cluster=a.keep_cluster,overlay_changes=changes)
    if a.out:write_report(rep,a.out)
    print(json.dumps(rep,indent=2,sort_keys=True));return 0 if rep["passed"] else 1
if __name__=="__main__":sys.exit(main())
