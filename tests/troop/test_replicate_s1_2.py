"""S1.2 capability-replication planner. Source (v2 mega-spec S1.2, relayed): same line as S1.1 plus "replicate them and
integrate into atlas" and "actually integrate it into themselves if its opensource of build it into themselves if itsnt".
Offline, stdlib only; run with PYTHONPATH=backend."""
import copy
import random

import pytest

from app.troop import landscape as L
from app.troop import replicate as R


def scan_of(*specs, atlas=()):
    """The supplied pages and Atlas list; S1.2 derives the matrix from these itself."""
    recs = [{"name": n, "source_kind": "product_page", "text": t} for n, t in specs]
    return {"records": recs, "atlas_capabilities": list(atlas)}


def plan(scan, **kw):
    return R.plan_replication({**scan, **kw})


def refusal(r):
    with pytest.raises(ValueError) as cm:
        R.plan_replication(r)
    return str(cm.value)


def test_open_permissive_free_integrates():
    p = plan(scan_of(("oss", "MIT licensed memory layer. free")))
    t = p["tickets"][0]
    assert t["decision"] == "integrate (open source, license ok)" and t["source_tool"] == "oss"
    assert t["reason"] == "license_ok" and t["ticket_id"] == "REP-memory" and t["capability"] == "memory"
    assert p["counts"] == {"tickets": 1, "integrate": 1, "build": 0}


def test_closed_builds_ourselves_and_never_names_a_copy_source():
    t = plan(scan_of(("shut", "proprietary memory")))["tickets"][0]
    assert (t["decision"], t["source_tool"], t["reason"]) == ("build ourselves", None, "no_open_provider_license_ok")


def test_unknown_license_builds():
    t = plan(scan_of(("u", "memory")))["tickets"][0]
    assert t["decision"] == "build ourselves"


def test_copyleft_builds_with_review_reason():
    t = plan(scan_of(("g", "GPL-3.0 memory")))["tickets"][0]
    assert (t["decision"], t["reason"]) == ("build ourselves", "copyleft_needs_human_review")


def test_open_but_paid_tier_not_adopted():
    t = plan(scan_of(("p", "MIT memory, costs $9")))["tickets"][0]
    assert (t["decision"], t["reason"]) == ("build ourselves", "paid_tier_not_adopted")


def test_mixed_providers_pick_permissive_and_prefer_adopted():
    s = scan_of(("zeta", "MIT memory"), ("alpha", "MIT memory"), ("closed", "proprietary memory"))
    assert plan(s)["tickets"][0]["source_tool"] == "alpha"
    p = plan(s, adopt=["zeta"])
    assert p["tickets"][0]["source_tool"] == "zeta" and p["adopted"] == ["zeta"]


def test_copyleft_beats_permissive_paid_in_reason_order():
    s = scan_of(("g", "GPL-3.0 memory"), ("p", "MIT memory $9"))
    assert plan(s)["tickets"][0]["reason"] == "copyleft_needs_human_review"


def test_acceptance_tests_first_and_ticket_shape():
    p = plan(scan_of(("o", "MIT memory inbox")))
    assert [t["capability"] for t in p["tickets"]] == ["email_inbox", "memory"]
    for t in p["tickets"]:
        assert t["steps"][0] == "write acceptance tests (red)"
        assert t["steps"] == ["write acceptance tests (red)", "implement or integrate", "run acceptance tests (green)",
                              "audit review"]
        assert len(t["acceptance_tests"]) == 3 and len(set(t["acceptance_tests"])) == 3
        assert all(t["capability"] in a for a in t["acceptance_tests"])
        assert t["estimated_spend_usd"] == 0 and t["status"] == "PROPOSED" and t["basis"] == "vendor-stated"
        assert sorted(t) == sorted(["ticket_id", "capability", "decision", "source_tool", "reason", "acceptance_tests",
                                    "steps", "estimated_spend_usd", "status", "basis"])


def test_no_gaps_no_tickets():
    p = plan(scan_of(("o", "MIT memory"), atlas=["memory"]))
    assert p["tickets"] == [] and p["counts"] == {"tickets": 0, "integrate": 0, "build": 0}


def test_honesty_fields():
    p = plan(scan_of(("o", "MIT memory")))
    assert p["claims"] == {"built_anything": False, "copied_code": False, "spent_money": False, "license_verified": False}
    assert p["action"] == "none" and p["feature"] == "capability_replication_planner"
    assert "not legal" in p["method_limits"]


def test_policy_refusals():
    s = scan_of(("shut", "proprietary memory"), ("oss", "MIT memory"), ("gpl", "GPL-3.0 memory"),
                ("paid", "MIT memory costs $9"), ("unk", "memory"))
    assert refusal({**s, "adopt": ["shut"]}) == "FLEET_REFUSED_UNLICENSED"
    assert refusal({**s, "adopt": ["gpl"]}) == "FLEET_REFUSED_UNLICENSED"
    assert refusal({**s, "adopt": ["unk"]}) == "FLEET_REFUSED_UNLICENSED"
    assert refusal({**s, "adopt": ["paid"]}) == "FLEET_REFUSED_SPEND"
    assert refusal({**s, "adopt": ["paid", "shut"]}) == "FLEET_REFUSED_UNLICENSED"
    assert refusal({**s, "spend_usd": 1}) == "FLEET_REFUSED_SPEND"
    assert plan(s, adopt=["oss"])["adopted"] == ["oss"]


def test_oracle_corpus():
    rnd = random.Random(312)
    lic = {"MIT": "perm", "Apache-2.0": "perm", "GPL-3.0": "copy", "proprietary": "closed", "": "unk"}
    for i in range(300):
        specs, info = [], {}
        for j in range(rnd.randint(1, 4)):
            l = rnd.choice(list(lic))
            price = rnd.choice(["", "free", "costs $9"])
            caps = rnd.sample(["memory", "inbox", "planner"], rnd.randint(1, 3))
            specs.append(("n%d" % j, " ".join([l, price] + caps)))
            info["n%d" % j] = (lic[l], price == "costs $9", set(caps))
        s = scan_of(*specs)
        out = plan(s)
        capmap = {"memory": "memory", "inbox": "email_inbox", "planner": "planning"}
        for t in out["tickets"]:
            provs = sorted(n for n, (_, _, cs) in info.items() if any(capmap[c] == t["capability"] for c in cs))
            ok = [n for n in provs if info[n][0] == "perm" and not info[n][1]]
            if ok:
                assert (t["decision"], t["source_tool"]) == ("integrate (open source, license ok)", ok[0]), i
            else:
                kinds = [info[n][0] for n in provs]
                want = ("copyleft_needs_human_review" if "copy" in kinds else
                        "paid_tier_not_adopted" if "perm" in kinds else "no_open_provider_license_ok")
                assert (t["decision"], t["reason"]) == ("build ourselves", want), i
        assert len(out["tickets"]) == len({capmap[c] for _, _, cs in info.values() for c in cs}), i


def test_build_counts_and_exact_templates():
    p = plan(scan_of(("o", "MIT memory"), ("c", "proprietary inbox"), ("d", "proprietary planner")))
    assert p["counts"] == {"tickets": 3, "integrate": 1, "build": 2}
    assert p["tickets"][0]["acceptance_tests"] == [
        "given a supplied fixture input, the email_inbox capability returns the documented output",
        "given empty or malformed input, the email_inbox capability refuses with a stable code",
        "the email_inbox capability is deterministic: the same input twice gives equal output"]
    assert R.METHOD_LIMITS.startswith("Tickets are proposals") and R.METHOD_LIMITS.endswith("installed or bought.")
    assert sorted(p) == sorted(["feature", "tickets", "adopted", "counts", "claims", "method_limits", "action"])




def test_bad_inputs_codes():
    s = scan_of(("o", "MIT memory"))
    assert refusal([]) == "S1.2:bad_type:request"
    assert refusal({}) == "S1.2:missing_field:request"
    assert refusal({"records": []}) == "S1.2:missing_field:request"
    assert refusal({**s, "x": 1}) == "S1.2:unknown_field:request"
    assert refusal({"scan": {"records": [], "gaps": []}, **s}) == "S1.2:unknown_field:request"
    for v in (-1, True, 1.0, "0", None):
        assert refusal({**s, "spend_usd": v}) == "S1.2:bad_spend"
    assert refusal({**s, "adopt": {}}) == "S1.2:bad_type:adopt"
    assert refusal({**s, "adopt": [5]}) == "S1.2:bad_type:adopt"
    assert refusal({**s, "adopt": ["o", "o"]}) == "S1.2:duplicate_adopt"
    assert refusal({**s, "adopt": ["nope"]}) == "S1.2:unknown_adopt_name"


def test_scan_input_is_not_accepted_so_it_cannot_be_forged():
    s = scan_of(("o", "MIT memory plans from $9"))
    t = plan(s)
    assert [x["decision"] for x in t["tickets"]] == ["build ourselves", "build ourselves"]
    forged = {"scan": {"records": [{"name": "o", "price_tier": "FREE", "license": {"class": "OPEN_PERMISSIVE"},
                                    "capabilities": ["memory"]}], "gaps": [{"capability": "memory", "providers": ["o"]}]},
              "records": s["records"], "atlas_capabilities": []}
    assert refusal(forged) == "S1.2:unknown_field:request"


def test_tier_comes_from_the_page_text_every_time():
    for text, decision in (("MIT memory", "integrate (open source, license ok)"),
                           ("MIT memory free", "integrate (open source, license ok)"),
                           ("MIT memory free plan, paid from $9", "integrate (open source, license ok)"),
                           ("MIT memory costs $9", "build ourselves")):
        assert plan(scan_of(("o", text)))["tickets"][0]["decision"] == decision, text
    assert refusal({**scan_of(("o", "MIT memory costs $9")), "adopt": ["o"]}) == "FLEET_REFUSED_SPEND"
    assert plan(scan_of(("o", "MIT memory free plan, paid from $9")), adopt=["o"])["adopted"] == ["o"]


def test_records_are_validated_by_the_scanner_and_its_codes_pass_through():
    assert refusal(scan_of(("o", "  "))) == "FLEET_REFUSED_NOSOURCE"
    assert refusal({"records": {}, "atlas_capabilities": []}) == "S1.1:bad_type:records"
    assert refusal({**scan_of(("o", "x")), "spend_usd": 0, "atlas_capabilities": [5]}) == "S1.1:bad_atlas_capability"
    r = scan_of(("a", "x"), ("a", "y"))
    assert refusal(r) == "S1.1:duplicate_name"


def test_adopt_bound_exact():
    s = scan_of(("o", "MIT memory"))
    assert refusal({**s, "adopt": ["x%d" % i for i in range(100)]}) == "S1.2:unknown_adopt_name"
    assert refusal({**s, "adopt": ["x%d" % i for i in range(101)]}) == "S1.2:limit_exceeded:adopt"


def test_strict_types_and_control_chars():
    class D(dict):
        pass

    class S(str):
        pass

    s = scan_of(("o", "MIT memory"))
    assert refusal(D(s)) == "S1.2:bad_type:request"
    assert refusal({**s, "records": [D(s["records"][0])]}) == "S1.2:bad_type:request"
    assert refusal({**s, "adopt": [S("o")]}) == "S1.2:bad_type:request"
    for c in ["\x00", "\n", "\x1b", "\u2028", "\x85"]:
        s2 = scan_of(("o" + c, "MIT memory"))
        m = refusal(s2)
        assert m == "S1.2:control_chars:request" and c not in m
        m = refusal({**s, "adopt": ["o" + c]})
        assert m == "S1.2:control_chars:request" and c not in m
    assert plan(scan_of(("o", "MIT memory\nline two\r\n\tok")))["counts"]["tickets"] == 1


def test_determinism_no_mutation_fresh_output():
    s = scan_of(("o", "MIT memory inbox"), ("p", "proprietary planner"))
    r = {**s, "adopt": ["o"]}
    snap = copy.deepcopy(r)
    a = R.plan_replication(r)
    assert r == snap and a == R.plan_replication(copy.deepcopy(r))
    a["tickets"][0]["steps"].append("x")
    a["tickets"][0]["acceptance_tests"].append("x")
    b = R.plan_replication(r)
    assert len(b["tickets"][0]["steps"]) == 4 and len(b["tickets"][0]["acceptance_tests"]) == 3
    r["records"].reverse()
    assert R.plan_replication(r) == b
