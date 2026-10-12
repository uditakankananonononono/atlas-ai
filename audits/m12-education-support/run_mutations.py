"""Mutation receipts. Run from repo root:
    ATLAS_DEV_NO_AUTH=1 ATLAS_ENV=development python audits/m12-education-support/run_mutations.py [out.txt]
(out.txt defaults to audits/m12-education-support/mutation_receipts.txt). Each mutant is an exact single textual
replacement (old -> new) in one file. The named test file is run before (must be green) and after.
A mutant is CAUGHT only when pytest exits 1 with at least one FAILED test (an assertion/test failure) and no
collection error, no timeout and no crash; the failing test ids are recorded. rc 2/4/5, a timeout, or a failure with
no FAILED line is recorded as INVALID (not counted as caught). rc 0 is SURVIVED. Restore is verified by SHA-256 of
every mutated file against its pre-run content (exact), independent of git state."""
import hashlib, os, subprocess, sys

B = "backend/app/modules/m12_ai_research_lab/education_support.py"
TESTS = "tests/modules/test_m12_education_support_hardening.py"
MUT = [
 ('E1 high band boundary (>)', B, "'high' if s>=.7", "'high' if s>.7", TESTS),
 ('E2 medium band boundary (>)', B, "'medium' if s>=.4", "'medium' if s>.4", TESTS),
 ('E3 engagement weights ignored', B, 'sum(v*w for v,w in vs)/sum(w for _,w in vs)', 'sum(v for v,w in vs)/len(vs)', TESTS),
 ('E4 logistic sign flipped', B, '1/(1+exp(-y))', '1/(1+exp(y))', TESTS),
 ('E5 intercept dropped', B, "y=float(c.get('intercept',0))+sum(", 'y=sum(', TESTS),
 ('E6 missing-feature check removed', B, "missing=set(c)-set(x)-{'intercept'}", 'missing=set()', TESTS),
 ('E7 cosine not normalized', B, 'sum(x*y for x,y in zip(a,b))/z', 'sum(x*y for x,y in zip(a,b))', TESTS),
 ('E8 vector alignment check removed', B, 'if len(a)!=len(b) or not a:raise', 'if not a:raise', TESTS),
 ('E9 recommendation tie-break by id removed', B, "key=lambda x:(-x['score'],x['id'])),'selected':False", "key=lambda x:(-x['score'])),'selected':False", TESTS),
 ('E10 peer complementary weight 1 not 2', B, 'len(shared)+2*len(helped)', 'len(shared)+len(helped)', TESTS),
 ('E11 completed nodes not excluded', B, "n['id'] not in done and ", '', TESTS),
 ('E12 prerequisite check removed', B, "set(n.get('prerequisites',[]))<=done", 'True', TESTS),
 ('E13 rubric weight ignored in sum', B, 'num+=s/mx*w;den+=w', 'num+=s/mx;den+=w', TESTS),
 ('E14 normalized score not x100', B, 'round(100*num/den,2)', 'round(num/den,2)', TESTS),
 ('E15 rubric upper range check removed', B, 'if not 0<=s<=mx:raise', 'if not 0<=s:raise', TESTS),
 ('E16 zero max_score/weight allowed', B, 'if mx<=0 or w<=0:raise', 'if mx<0 or w<0:raise', TESTS),
 ('E17 feedback gap includes equal scores', B, "if x['score']<x['target']]", "if x['score']<=x['target']]", TESTS),
 ('E18 feedback sorted smallest gap first', B, "sorted(r,key=lambda x:-x['gap'])", "sorted(r,key=lambda x:x['gap'])", TESTS),
 ('E19 attainment counts all objectives', B, 'len(ids)-len(gaps)', 'len(ids)', TESTS),
 ('E20 unknown objective not rejected', B, "if unknown:raise ValueError('unknown objective ids')", "if False:raise ValueError('unknown objective ids')", TESTS),
 ("E21 standard 'meets' boundary (>)", B, 'mean(v)>=threshold', 'mean(v)>threshold', TESTS),
 ('E22 no-evidence status wrong', B, "'insufficient_evidence' if not v else", "'developing' if not v else", TESTS),
 ('E23 mastery boundary (>)', B, "ev.get(c['id'],0)>=number(c.get('mastery_threshold')", "ev.get(c['id'],0)>number(c.get('mastery_threshold')", TESTS),
 ('E24 celeration ratio inverted', B, 'round(rates[-1]/rates[0],3)', 'round(rates[0]/rates[-1],3)', TESTS),
 ('E25 aim comparison inverted', B, "rates[-1]<d['aim']", "rates[-1]>d['aim']", TESTS),
 ('E26 guided accuracy denominator', B, 'sum(bool(x) for x in checks)/len(checks)', 'sum(bool(x) for x in checks)/(len(checks)+1)', TESTS),
 ('E27 tutor worked-example boundary (<=)', B, "w['mastery']<.5", "w['mastery']<=.5", TESTS),
 ('E28 identifier match case sensitive', B, 'k.lower() in DIRECT_IDENTIFIERS', 'k in DIRECT_IDENTIFIERS', TESTS),
 ('E29 identifier dict recursion removed', B, 'reject_direct_identifiers(v,f"{path}.{k}")', 'pass', TESTS),
 ('E30 identifier list recursion removed', B, 'reject_direct_identifiers(v,f"{path}[{n}]")', 'pass', TESTS),
 ('E31 observed_at no longer required', B, "not x.get('source_id') or not x.get('observed_at') for x in sources", "not x.get('source_id') for x in sources", TESTS),
 ('E32 unsupported feature accepted', B, 'if i not in FEATURES:raise', 'if False:raise', TESTS),
 ('E33 prediction flag range widened', B, "'prediction_is_not_fact':i in range(1460,1467)", "'prediction_is_not_fact':i in range(1460,1468)", TESTS),
 ('E34 side_effects not empty', B, "'side_effects':[]", "'side_effects':['x']", TESTS),
 ('E35 cumulative review window shifted', B, 'steps[:n]', 'steps[:n-1]', TESTS),
 ('E36 need() treats empty as present', B, 'd.get(k) in (None,[],{})', 'd.get(k) is None', TESTS),
 ('E37 bool accepted as number', B, 'if isinstance(value,bool) or not isinstance(value,(int,float))', 'if not isinstance(value,(int,float))', TESTS),
 ('E38 weakest-item tie-break by id removed', B, "key=lambda x:(x.get('score',0),x.get('item_id',''))", "key=lambda x:(x.get('score',0),)", TESTS),
]
ENV =dict(os.environ, ATLAS_DEV_NO_AUTH="1", ATLAS_ENV="development", PYTHONPATH="backend")
TIMEOUT_S = 90

def run(tests):
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *tests.split(), "-q", "-rf"],
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
    for tests in (TESTS,):
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

main(sys.argv[1] if len(sys.argv) > 1 else "audits/m12-education-support/mutation_receipts.txt")
