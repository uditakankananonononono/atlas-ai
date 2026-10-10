"""ATLAS-U-1219 (X12 free substitute) acceptance tests for deploy/k8s/local_smoke.py.
Authored BEFORE the implementation. AUTHORED NOT RUN by the builder.
Hermetic: no cluster, no docker, no network. Commands are captured through an injected fake runner.
They do not claim a Kubernetes cluster was ever started."""
import copy,dataclasses,importlib.util,json,sys
from pathlib import Path
import pytest
import yaml
ROOT=Path(__file__).resolve().parents[2]
GAP="Multi-node production cluster behavior, cloud load balancers, real ingress"
def load():
    spec=importlib.util.spec_from_file_location("local_smoke",ROOT/"deploy"/"k8s"/"local_smoke.py");m=importlib.util.module_from_spec(spec)
    sys.modules["local_smoke"]=m  # must be registered BEFORE exec_module: @dataclass with `from __future__ import annotations` looks the module up in sys.modules
    try:spec.loader.exec_module(m)
    except BaseException:
        sys.modules.pop("local_smoke",None);raise
    return m
S=load()
IMG="atlas-ai:kind-local"
def base():return S.load_manifests(ROOT/"deploy"/"k8s"/"atlas.yaml")
def kinds(ms):return [m["kind"] for m in ms]
def dep(ms):return next(m for m in ms if m["kind"]=="Deployment")

class Runner:
    """Records argv; answers by a function of argv. Never executes anything."""
    def __init__(s,fail_on=None,ready=None,desired=1):
        s.calls=[];s.fail_on=fail_on;s.ready=desired if ready is None else ready;s.desired=desired
    def __call__(s,argv):
        s.calls.append(list(argv));j=" ".join(argv)
        if s.fail_on and s.fail_on in j:return 1,"boom"
        if "get deployment" in j:return 0,json.dumps({"spec":{"replicas":s.desired},"status":{"replicas":s.desired,"readyReplicas":s.ready,"availableReplicas":s.ready}})
        if "get --raw" in j:return 0,"ok"
        return 0,""
    def joined(s):return [" ".join(c) for c in s.calls]

# ---- docstring / honesty ----
def test_module_docstring_contains_named_gap_verbatim_and_no_production_claim():
    d=S.__doc__;assert GAP in d
    assert "single-node" in d.lower() and "not" in d.lower()
def test_loader_registers_module_in_sys_modules_so_future_annotations_dataclasses_work():
    assert sys.modules.get("local_smoke") is S
    assert dataclasses.is_dataclass(S.Step) and dataclasses.is_dataclass(S.Eval)
    assert [f.name for f in dataclasses.fields(S.Step)]==["name","argv"] and S.Step.__module__=="local_smoke"
def test_loader_source_registers_before_exec_module():
    src=Path(__file__).read_text();body=src[src.index("def load():"):src.index("S=load()")]
    assert body.index('sys.modules["local_smoke"]=m')<body.index("exec_module(m)")
def test_gap_constant_matches_contract_text():assert S.NOT_COVERED_GAP==GAP

# ---- kind cluster file ----
def test_kind_cluster_yaml_is_single_node_control_plane_only():
    c=yaml.safe_load((ROOT/"deploy"/"k8s"/"kind-cluster.yaml").read_text())
    assert c["kind"]=="Cluster" and c["apiVersion"].startswith("kind.x-k8s.io/")
    assert [n["role"] for n in c["nodes"]]==["control-plane"]
def test_kind_cluster_yaml_has_no_extra_port_mappings_or_ingress_hosts():
    c=yaml.safe_load((ROOT/"deploy"/"k8s"/"kind-cluster.yaml").read_text())
    assert not c["nodes"][0].get("extraPortMappings")

# ---- overlay ----
def test_overlay_replaces_placeholder_image_and_sets_pull_policy_never_latest_default():
    ms,ch=S.build_overlay(base(),IMG);c=dep(ms)["spec"]["template"]["spec"]["containers"][0]
    assert c["image"]==IMG and c["imagePullPolicy"]=="IfNotPresent"
    assert any("image" in x for x in ch)
def test_overlay_rejects_unpinned_images_and_bad_replicas():
    for bad in ("atlas-ai:latest","atlas-ai","","ghcr.io/x/atlas-ai","atlas-ai@sha256:abc","Atlas AI:1",None):
        with pytest.raises(ValueError):S.build_overlay(base(),bad)
    with pytest.raises(ValueError):S.build_overlay(base(),IMG,replicas=0)
    with pytest.raises(ValueError):S.build_overlay(base(),IMG,replicas=True)
def test_overlay_accepts_explicit_tag_and_sha256_digest_only():
    d="atlas-ai@sha256:"+"a"*64
    for ok in (IMG,"registry.local:5000/atlas/api:1.2.3",d):
        assert dep(S.build_overlay(base(),ok)[0])["spec"]["template"]["spec"]["containers"][0]["image"]==ok
def test_local_smoke_source_has_no_registry_owner_placeholder_literal():
    assert ("OW"+"NER") not in (ROOT/"deploy"/"k8s"/"local_smoke.py").read_text()
def test_overlay_does_not_mutate_input_manifests():
    ms=base();snap=copy.deepcopy(ms);S.build_overlay(ms,IMG);assert ms==snap
def test_overlay_sets_replicas_and_lowers_requests_only_and_records_each_change():
    ms,ch=S.build_overlay(base(),IMG,replicas=1,cpu_request="100m",memory_request="256Mi")
    c=dep(ms)["spec"]["template"]["spec"]["containers"][0]
    assert dep(ms)["spec"]["replicas"]==1 and c["resources"]["requests"]=={"cpu":"100m","memory":"256Mi"}
    assert c["resources"]["limits"]==dep(base())["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]
    joined=" ".join(ch);assert "replicas" in joined and "requests" in joined
def test_overlay_drops_hpa_by_default_and_records_it_but_keeps_when_asked():
    ms,ch=S.build_overlay(base(),IMG);assert "HorizontalPodAutoscaler" not in kinds(ms) and any("HorizontalPodAutoscaler" in x for x in ch)
    ms2,_=S.build_overlay(base(),IMG,drop_hpa=False);assert "HorizontalPodAutoscaler" in kinds(ms2)
def test_overlay_keeps_namespace_service_networkpolicy_unchanged():
    orig=base();ms,_=S.build_overlay(orig,IMG)
    for k in ("Namespace","Service","NetworkPolicy"):
        assert next(m for m in ms if m["kind"]==k)==next(m for m in orig if m["kind"]==k)
def test_overlay_does_not_materialize_any_secret_by_default():
    ms,ch=S.build_overlay(base(),IMG);assert "Secret" not in kinds(ms) and not any("Secret" in x for x in ch)
def test_overlay_adds_empty_runtime_secret_only_when_opted_in_and_records_it():
    ms,ch=S.build_overlay(base(),IMG,add_empty_secret=True);sec=next(m for m in ms if m["kind"]=="Secret")
    assert sec["metadata"]["name"]=="atlas-runtime" and sec["metadata"]["namespace"]=="atlas"
    assert not sec.get("data") and not sec.get("stringData") and any("Secret" in x and "EMPTY" in x for x in ch)
def test_overlay_does_not_duplicate_secret_if_manifest_already_has_one():
    orig=base()+[{"apiVersion":"v1","kind":"Secret","metadata":{"name":"atlas-runtime","namespace":"atlas"}}]
    ms,_=S.build_overlay(orig,IMG,add_empty_secret=True);assert kinds(ms).count("Secret")==1
def test_overlay_sets_PORT_env_to_manifest_container_port_because_dockerfile_defaults_to_8080():
    ms,ch=S.build_overlay(base(),IMG);c=dep(ms)["spec"]["template"]["spec"]["containers"][0]
    assert {"name":"PORT","value":"8000"} in c["env"] and c["ports"][0]["containerPort"]==8000
    assert any("PORT" in x and "8080" in x and "8000" in x for x in ch)
def test_overlay_replaces_existing_PORT_env_instead_of_duplicating():
    o=base();dep(o)["spec"]["template"]["spec"]["containers"][0]["env"]=[{"name":"PORT","value":"9999"},{"name":"X","value":"1"}]
    c=dep(S.build_overlay(o,IMG)[0])["spec"]["template"]["spec"]["containers"][0]
    assert [e for e in c["env"] if e["name"]=="PORT"]==[{"name":"PORT","value":"8000"}] and {"name":"X","value":"1"} in c["env"]
def test_service_proxy_path_uses_service_port_8000_matching_manifest():
    svc=next(m for m in base() if m["kind"]=="Service");assert svc["spec"]["ports"][0]["port"]==8000 and "atlas-api:8000" in S.SERVICE_PROXY
def test_overlay_keeps_probe_paths_and_port():
    c=dep(S.build_overlay(base(),IMG)[0])["spec"]["template"]["spec"]["containers"][0]
    assert c["readinessProbe"]["httpGet"]["path"]=="/ready" and c["livenessProbe"]["httpGet"]["path"]=="/health" and c["ports"][0]["containerPort"]==8000
def test_dump_manifests_roundtrips_through_yaml():
    ms,_=S.build_overlay(base(),IMG);assert list(yaml.safe_load_all(S.dump_manifests(ms)))==ms

# ---- command plan ----
def test_plan_creates_single_cluster_loads_image_applies_overlay_checks_secret_and_waits_in_order():
    plan=S.plan_commands("/tmp/overlay.yaml",IMG);names=[s.name for s in plan]
    assert names==["create-cluster","load-image","apply","check-secret","rollout"]
    j=[" ".join(s.argv) for s in plan]
    assert j[0].startswith("kind create cluster") and f"--name {S.CLUSTER_NAME}" in j[0] and "kind-cluster.yaml" in j[0]
    assert j[1]==f"kind load docker-image {IMG} --name {S.CLUSTER_NAME}"
    assert "apply -f /tmp/overlay.yaml" in j[2] and f"--context kind-{S.CLUSTER_NAME}" in j[2]
    assert j[3]==f"kubectl --context kind-{S.CLUSTER_NAME} -n atlas get secret atlas-runtime"
    assert "rollout status deployment/atlas-api" in j[4] and "-n atlas" in j[4]
def test_plan_never_uses_shell_cloud_or_push_commands():
    for s in S.plan_commands("/tmp/o.yaml",IMG)+S.plan_cleanup():
        assert isinstance(s.argv,list) and s.argv[0] in ("kind","kubectl")
        assert not set(s.argv)&{"push","gcloud","aws","az","sh","bash","-c"}
def test_every_kubectl_step_pins_the_kind_context_so_no_other_cluster_is_touched():
    for s in S.plan_commands("/tmp/o.yaml",IMG):
        if s.argv[0]=="kubectl":assert f"--context kind-{S.CLUSTER_NAME}" in " ".join(s.argv)
def test_cleanup_plan_deletes_only_the_named_cluster():
    p=S.plan_cleanup();assert [" ".join(s.argv) for s in p]==[f"kind delete cluster --name {S.CLUSTER_NAME}"]

# ---- deployment evaluation ----
def test_evaluate_deployment_ok_only_when_ready_equals_desired():
    ok=S.evaluate_deployment({"spec":{"replicas":2},"status":{"readyReplicas":2,"availableReplicas":2}});assert ok.ok
    bad=S.evaluate_deployment({"spec":{"replicas":2},"status":{"readyReplicas":1,"availableReplicas":1}});assert not bad.ok and "1/2" in bad.detail
def test_evaluate_deployment_missing_status_fields_is_failure_not_zero_pass():
    r=S.evaluate_deployment({"spec":{"replicas":1},"status":{}});assert not r.ok
    assert not S.evaluate_deployment({}).ok

# ---- run_smoke orchestration ----
def run(r,**k):return S.run_smoke(r,"/tmp/overlay.yaml",IMG,**k)
def test_run_smoke_passes_when_all_steps_and_probes_succeed_and_cleans_up():
    r=Runner();rep=run(r);j=r.joined()
    assert rep["passed"] is True
    assert any("get --raw" in x and "/health" in x for x in j) and any("get --raw" in x and "/ready" in x for x in j)
    assert j[-1]==f"kind delete cluster --name {S.CLUSTER_NAME}"
def test_run_smoke_stops_at_first_failing_step_and_reports_failure():
    r=Runner(fail_on="apply");rep=run(r);j=r.joined()
    assert rep["passed"] is False and not any("rollout" in x for x in j)
    assert [c["name"] for c in rep["checks"] if not c["ok"]]==["apply"]
def test_run_smoke_stops_at_missing_runtime_secret_before_rollout_and_says_who_provisions_it():
    r=Runner(fail_on="get secret");rep=run(r);j=r.joined()
    assert rep["passed"] is False and not any("rollout" in x for x in j)
    assert [c["name"] for c in rep["checks"] if not c["ok"]]==["check-secret"]
def test_run_smoke_still_cleans_up_after_failure():
    r=Runner(fail_on="load docker-image");run(r);assert r.joined()[-1]==f"kind delete cluster --name {S.CLUSTER_NAME}"
def test_run_smoke_keep_cluster_skips_delete():
    r=Runner();run(r,keep_cluster=True);assert not any("delete cluster" in x for x in r.joined())
def test_run_smoke_fails_when_not_all_replicas_ready():
    rep=run(Runner(ready=0,desired=1));assert rep["passed"] is False and any(c["name"]=="deployment-ready" and not c["ok"] for c in rep["checks"])
def test_run_smoke_fails_when_a_probe_path_fails():
    rep=run(Runner(fail_on="/ready"));assert rep["passed"] is False and any(c["name"]=="probe /ready" and not c["ok"] for c in rep["checks"])
def test_runner_exception_is_reported_as_failure_and_cleanup_still_attempted():
    calls=[]
    def r(argv):
        calls.append(" ".join(argv))
        if "create cluster" in calls[-1]:raise FileNotFoundError("kind")
        return 0,""
    rep=run(r);assert rep["passed"] is False and calls[-1].startswith("kind delete cluster")

# ---- report honesty ----
def test_passing_report_states_scope_and_not_covered_and_no_production_claim():
    rep=run(Runner())
    assert rep["claims_production_acceptance"] is False and rep["attestation"] is False
    assert GAP in rep["not_covered"] and rep["scope"]=="single-node kind cluster, overlay of deploy/k8s/atlas.yaml"
    assert any("HorizontalPodAutoscaler" in x for x in rep["not_covered"])
    assert any("NetworkPolicy" in x for x in rep["not_covered"])
def test_overlay_changes_are_passed_through_exactly_and_default_empty():
    ch=["a","b"];assert run(Runner(),overlay_changes=ch)["overlay_changes"]==ch
    assert run(Runner())["overlay_changes"]==[]
    ms,real=S.build_overlay(base(),IMG);assert run(Runner(),overlay_changes=real)["overlay_changes"]==real and len(real)>=4
def test_report_lists_unverified_items_and_guessed_timeouts():
    u=" ".join(run(Runner())["unverified"]);
    for s in ("cluster creation","image boot","Secret materialization","service proxy","default-deny","guess","runtime audit"):assert s in u
def test_report_lists_exact_runtime_prerequisites():
    p=" ".join(run(Runner())["prerequisites"])
    for s in ("locally built","not registry-published","ATLAS_DATABASE_URL","ATLAS_REDIS_URL","ATLAS_OIDC_ISSUER","ATLAS_OIDC_AUDIENCE","ATLAS_SECRET_PROVIDER","PostgreSQL","Redis","alembic","egress"):assert s in p
def test_module_docstring_marks_runtime_unverified_fake_runner_planning_only_and_timeouts_guesses():
    d=S.__doc__
    for s in ("UNVERIFIED","Secret materialization","default-deny","fake runner","planning and orchestration logic only","guesses"):assert s in d
def test_module_docstring_documents_image_source_port_mapping_and_config_prerequisites():
    d=S.__doc__
    for s in ("locally built","not registry-published","root Dockerfile","kind load","8080","8000","PORT","validate_config","migrate","alembic upgrade head","ATLAS_ENV","production","ATLAS_DATABASE_URL","ATLAS_REDIS_URL","ATLAS_OIDC_ISSUER","ATLAS_OIDC_AUDIENCE","ATLAS_SECRET_PROVIDER","/ready","egress"):assert s in d
def test_failing_report_claims_nothing_covered():
    rep=run(Runner(fail_on="apply"));assert rep["covered"]==[] and rep["passed"] is False
def test_passing_report_covered_lists_only_what_was_checked():
    rep=run(Runner());assert set(rep["covered"])=={"manifests applied to a single-node kind cluster","deployment ready replicas match desired","GET /health via API server service proxy","GET /ready via API server service proxy"}
def test_report_is_json_serialisable_and_deterministic():
    a=run(Runner());b=run(Runner());assert json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)

# ---- write guard ----
def test_write_report_refuses_the_attestation_filename_that_existing_x12_test_expects_absent(tmp_path):
    with pytest.raises(ValueError):S.write_report({"passed":True},tmp_path/"kubernetes-acceptance.json")
    assert not (tmp_path/"kubernetes-acceptance.json").exists()
def test_write_report_writes_json_to_other_path(tmp_path):
    p=tmp_path/"kind-smoke-report.json";S.write_report({"passed":False},p);assert json.loads(p.read_text())=={"passed":False}
def test_no_default_report_path_so_nothing_is_written_unless_asked():
    assert S.DEFAULT_REPORT_PATH is None
def test_existing_x12_guard_file_is_still_absent_in_repo():
    assert not (ROOT/"audits"/"production"/"kubernetes-acceptance.json").exists()
