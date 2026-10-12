"""Mutation receipts. Run from repo root:  python audits/rows-47-64-delta/run_mutations.py audits/rows-47-64-delta/mutation_receipts.txt
Each mutant is an exact single textual replacement (old -> new) in one file; the named test file(s) are run
before (must be green) and after (a mutant is CAUGHT if the run fails). The file is restored afterwards, and the
tree is checked clean at the end."""
import os, subprocess, sys

C = "backend/app/modules/c31/clicky.py"
P = "backend/app/modules/m25_knowledge_copilot_training/pipeline.py"
T = "backend/app/modules/m20_general_cognitive_worker/training_data_units.py"
CT = "tests/modules/test_c31_clicky_transport.py"
RT = "tests/modules/test_m25_row64_scale_workflow.py"
UT = "tests/t_units/test_row63_advice_pipeline_workflow.py"
MUT = [
 # id, file, old, new, tests
 ("C1 follow redirects", C, "_urlreq.ProxyHandler({}), _NoRedirect", "_urlreq.ProxyHandler({})", CT),
 ("C2 honor proxy env", C, "_urlreq.ProxyHandler({}), _NoRedirect", "_NoRedirect", CT),
 ("C3 drop live gate", C, 'if live_approved is not True or os.environ.get(LIVE_ENV_FLAG) != "1":', "if False:", CT),
 ("C4 env alone enough", C, "if live_approved is not True or os.environ", "if os.environ", CT),
 ("C5 no total deadline (per-op only)", C, "status, raw = fut.result(timeout=timeout)", "status, raw = fut.result()", CT),
 ("C6 drop deadline check in read loop", C, "if time.monotonic() > deadline:", "if False:", CT),
 ("C7 result url hardcoded", C, 'out["request"] = {"method": "GET", "url": url}', 'out["request"] = {"method": "GET", "url": DOCUMENTED_API_BASE}', CT),
 ("C8 skip plan rebuild check", C, "if rebuilt != plan:", "if False:", CT),
 ("C9 leak url in transport error", C, 'return "APPLY_REFUSED_TRANSPORT", None\n\n\ndef execute', 'return "APPLY_REFUSED_TRANSPORT " + url, None\n\n\ndef execute', CT),
 ("C10 allow base_url with query", C, "or parts.query or parts.fragment", "or parts.fragment", CT),
 ("S1 tenant check removed", P, "if tenant_id and tenant_id!=self.tenant_id:raise", "if False:raise", RT),
 ("S2 ranking reversed", P, "sorted(self.chunks,key=score,reverse=True)", "sorted(self.chunks,key=score)", RT),
 ("S3 contradictions never flag", P, "neg(a['text'])!=neg(b['text'])", "False", RT),
 ("S4 delete is a no-op", P, "def delete_verified(self,source_id:str)->dict:", "def delete_verified(self,source_id:str)->dict:\n        return {}", RT),
 ("S5 restore skips attestation", P, "if same_adapters_attested is not True:", "if False:", RT),
 ("R1 robots check dropped", T, "if not rp.can_fetch('AtlasPublicCorpus',url):raise Refusal('TREND_REFUSED_SCRAPE')", "pass", UT),
 ("R2 rate limit dropped", T, "if now-self.last.get(host,float('-inf'))<self.interval:raise", "if False:raise", UT),
 ("R3 script text kept", T, "if not self.hidden:self.parts.append(data)", "self.parts.append(data)", UT),
 ("R4 candidate status flipped", T, "'status':'candidate_not_installed'", "'status':'installed'", UT),
 ("R5 hash taken over another page", T, "'source_sha256':r['sha256']", "'source_sha256':records[0]['sha256']", UT),
 ("R6 robots non-200 tolerated", T, "if robots.status!=200 or len(robots.text.encode())>self.limit:raise Refusal('TREND_REFUSED_SCRAPE')", "if len(robots.text.encode())>self.limit:raise Refusal('TREND_REFUSED_SCRAPE')", UT),
 ("R7 crawl-delay ignored", T, "if delay>self.interval:raise Refusal('TREND_REFUSED_RATELIMIT')", "pass", UT),
 ("R8 page oversize allowed", T, "if len(reply.text.encode())>self.limit:raise Refusal('TREND_REFUSED_OVERSIZE')", "pass", UT),
 ("R9 shared policy import failure swallowed as allow", T, "except ImportError as exc:raise Refusal(prefix+'_REFUSED_UNAVAILABLE') from exc", "except ImportError as exc:return", UT),
 ("R10 policy callable result ignored", T, "if not (result is None or result is True or isinstance(result,dict) and result.get('allowed') is True):\n            raise Refusal(prefix+'_REFUSED_ACTION')", "pass", UT),
]
ENV = dict(os.environ, ATLAS_DEV_NO_AUTH="1", ATLAS_ENV="development", PYTHONPATH="backend")

def run(tests):
    r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", tests, "-q", "-x"], capture_output=True, text=True, env=ENV)
    last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1]
    return r.returncode, last

def main(out):
    lines = []
    for tests in (CT, RT, UT):
        rc, last = run(tests); lines.append("BASELINE %s -> rc=%d %s" % (tests, rc, last)); assert rc == 0, last
    for mid, f, old, new, tests in MUT:
        src = open(f).read()
        if src.count(old) < 1:
            lines.append("%s | NOT-APPLICABLE (old text not found)" % mid); continue
        open(f, "w").write(src.replace(old, new, 1))
        try:
            rc, last = run(tests)
        finally:
            open(f, "w").write(src)
        lines.append("%s | %s | %s | rc=%d | %s" % (mid, f.split("/")[-1], "CAUGHT" if rc != 0 else "SURVIVED", rc, last))
    status = subprocess.run(["git", "status", "--porcelain", "--", "backend"], capture_output=True, text=True).stdout.strip()
    lines.append("tree clean after run: %s" % (status == ""))
    open(out, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
main(sys.argv[1])
