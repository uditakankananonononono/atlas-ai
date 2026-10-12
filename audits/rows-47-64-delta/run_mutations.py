"""Mutation receipts. Run from repo root:
    ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python audits/rows-47-64-delta/run_mutations.py [out.txt]
(out.txt defaults to audits/rows-47-64-delta/mutation_receipts.txt). Each mutant is an exact single textual
replacement (old -> new) in one file. The named test file is run before (must be green) and after.
A mutant is CAUGHT only when pytest exits 1 with at least one FAILED test (an assertion/test failure) and no
collection error, no timeout and no crash; the failing test ids are recorded. rc 2/4/5, a timeout, or a failure with
no FAILED line is recorded as INVALID (not counted as caught). rc 0 is SURVIVED. Restore is verified by SHA-256 of
every mutated file against its pre-run content (exact), independent of git state."""
import hashlib, os, subprocess, sys

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
 ("R11 redirect (302) accepted as page", T, "if reply.status!=200:raise Refusal('TREND_REFUSED_FETCH')", "if reply.status not in (200,302):raise Refusal('TREND_REFUSED_FETCH')", UT),
 ("R12 robots size check dropped", T, "if robots.status!=200 or len(robots.text.encode())>self.limit:raise Refusal('TREND_REFUSED_SCRAPE')", "if robots.status!=200:raise Refusal('TREND_REFUSED_SCRAPE')", UT),
 ("R13 paywall flag ignored", T, "if r.get('paywalled'):raise Refusal(prefix+'_REFUSED_PAYWALL')", "pass", UT),
 ("R14 candidate cap removed", T, "if re.search(r'\\b(always|test|verify|compare|practice|avoid|measure)\\b',line,re.I)][:500]", "if re.search(r'\\b(always|test|verify|compare|practice|avoid|measure)\\b',line,re.I)]", UT),
 ("R15 date format check dropped", T, "if not isinstance(r.get('as_of'),str) or not re.fullmatch(r'\\d{4}-\\d{2}-\\d{2}',r['as_of']):raise Refusal(prefix+'_REFUSED_DATE')", "pass", UT),
 ("R16 rate limit global instead of per host", T, "host=urlsplit(url).netloc;now=self.clock()", "host='*';now=self.clock()", UT),
 ("R17 record dedup removed", T, "if (r['source_id'],digest) in seen:continue", "pass", UT),
]
ENV =dict(os.environ, ATLAS_DEV_NO_AUTH="1", ATLAS_ENV="development", PYTHONPATH="backend")
TIMEOUT_S = 120

def run(tests):
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", tests, "-q", "-rf"],
                           capture_output=True, text=True, env=ENV, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", []
    lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    failed = [l.split(" - ")[0][len("FAILED "):] for l in lines if l.startswith("FAILED ")]
    return r.returncode, (lines[-1] if lines else ""), failed

def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

def main(out):
    lines = []
    files = sorted({m[1] for m in MUT})
    before = {f: sha(f) for f in files}
    for tests in (CT, RT, UT):
        rc, last, _ = run(tests); lines.append("BASELINE %s -> rc=%s %s" % (tests, rc, last)); assert rc == 0, last
    counts = {"CAUGHT": 0, "SURVIVED": 0, "INVALID": 0, "NOT-APPLICABLE": 0}
    for mid, f, old, new, tests in MUT:
        src = open(f).read()
        if src.count(old) < 1:
            counts["NOT-APPLICABLE"] += 1
            lines.append("%s | NOT-APPLICABLE (old text not found)" % mid); continue
        open(f, "w").write(src.replace(old, new, 1))
        try:
            rc, last, failed = run(tests)
        finally:
            open(f, "w").write(src)
        if rc == 0:
            verdict = "SURVIVED"
        elif rc == 1 and failed:
            verdict = "CAUGHT"
        else:
            verdict = "INVALID"
        counts[verdict] += 1
        lines.append("%s | %s | %s | rc=%s | %s | failing: %s" % (mid, f.split("/")[-1], verdict, rc, last, "; ".join(x.split("::")[-1] for x in failed[:3]) or "-"))
    restored = all(sha(f) == before[f] for f in files)
    lines.append("counts: " + ", ".join("%s=%d" % kv for kv in counts.items()))
    lines.append("mutated files byte-identical to pre-run state (sha256): %s" % restored)
    open(out, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
    sys.exit(0 if restored else 3)

main(sys.argv[1] if len(sys.argv) > 1 else "audits/rows-47-64-delta/mutation_receipts.txt")
