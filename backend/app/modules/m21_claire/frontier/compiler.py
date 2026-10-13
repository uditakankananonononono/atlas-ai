from __future__ import annotations
import hashlib, json, re
from typing import Any
from ._canon import canonical_json

# The compiler emits a verifiable workflow graph, never claims it performed the work.
_TEMPLATES: list[tuple[tuple[str, ...], str, list[tuple[str, str, str]]]] = [
    (("competition", "olympiad", "scholarship", "college", "application", "admission"), "opportunity_application", [
        ("discover", "Collect relevant opportunities from configured sources", "source_records_exist"),
        ("verify", "Check eligibility, deadlines, fees and funding against official sources", "official_source_links_and_unknowns_recorded"),
        ("profile", "Match requirements against user-confirmed profile facts and documents", "every_claim_has_provenance_or_is_marked_missing"),
        ("draft", "Prepare application packet and flag missing fields", "packet_has_no_unverified_claims"),
        ("review", "Human reviews the complete packet; no automatic submission", "review_receipt_exists"),
    ]),
    (("social", "feed", "trend", "brand", "content", "pinterest", "instagram", "linkedin"), "social_trend_to_prototype", [
        ("observe", "Ingest only authorized or public allowed sources", "source_authority_and_provenance_recorded"),
        ("cluster", "Find recurring signals while discounting duplicates and source concentration", "cluster_has_multiple_independent_sources"),
        ("hypothesize", "Generate a falsifiable audience/product hypothesis", "hypothesis_has_failure_condition"),
        ("prototype", "Build a small draft or local prototype", "prototype_artifact_exists"),
        ("test", "Design a demand test and compare with a baseline", "metric_and_negative_result_are_defined"),
        ("review", "Review before publishing or contacting anyone", "payload_bound_approval_exists"),
    ]),
    (("research", "science", "hypothesis", "discover", "paper", "theory"), "scientific_discovery", [
        ("retrieve", "Collect a bounded source set with provenance", "source_set_is_reproducible"),
        ("extract", "Separate observations, claims, assumptions and unknowns", "claim_evidence_map_exists"),
        ("compete", "Construct rival mechanisms and predictions", "at_least_two_rival_hypotheses"),
        ("experiment", "Design a discriminating experiment with baseline and confounders", "preregistered_test_exists"),
        ("confirm", "Evaluate on untouched confirmation data", "confirmation_data_not_used_for_selection"),
        ("report", "Preserve failures, uncertainty and reproducibility instructions", "report_includes_negative_results"),
    ]),
    (("build", "code", "tool", "software", "website", "prototype", "app"), "software_build", [
        ("specify", "Translate request into acceptance tests and constraints", "acceptance_tests_are_machine_readable"),
        ("design", "Propose the smallest architecture that meets the tests", "architecture_and_threat_model_exist"),
        ("patch", "Create a reviewable patch in a bounded workspace", "diff_exists_and_is_scoped"),
        ("test", "Run allow-listed offline tests in isolation", "test_receipt_and_exit_code_exist"),
        ("audit", "Inspect security, dependencies and regressions", "review_findings_are_recorded"),
        ("review", "Human approves merge, deployment or external changes", "approval_is_bound_to_exact_diff"),
    ]),
    (("personal", "learn me", "preference", "thinking", "taste", "career"), "preference_grounded_personalization", [
        ("ask", "Ask explicit pairwise questions about preferences and priorities", "answers_are_user_authored"),
        ("model", "Update an inspectable preference model with uncertainty", "model_has_provenance_and_confidence"),
        ("recommend", "Generate recommendations with reasons tied to preferences", "each_reason_maps_to_observed_preference"),
        ("correct", "Offer revision and deletion controls", "correction_and_erasure_are_tested"),
    ]),
]

class CapabilityCompiler:
    """Compiles a broad goal into a dependency graph with testable completion evidence."""
    VERSION = "frontier-compiler-2"
    def compile(self, goal: str, *, user_constraints: list[str] | None = None,
                budget: dict[str, Any] | None = None, installed_capabilities: list[str] | None = None) -> dict[str, Any]:
        goal = goal.strip()
        if not goal or len(goal) > 12000: raise ValueError("goal must be 1..12000 characters")
        goal_l = goal.casefold()
        words = set(re.findall(r"[a-z0-9]+", goal_l))
        matched=[]
        for keywords, key, steps in _TEMPLATES:
            score = sum(2 if phrase in goal_l else 1 for phrase in keywords if phrase in words or phrase in goal_l)
            if score > 0: matched.append((score,key,steps))
        matched.sort(key=lambda row:(-row[0],row[1]))
        # Limit by workflow budget, not by arbitrary model output. All matching lanes are
        # retained unless their combined verifiable plan would exceed the hard 30-step cap.
        if not matched:
            matched=[(1,"generic_goal",[
                ("define", "Make the desired outcome, constraints and baseline explicit", "acceptance_criteria_exist"),
                ("research", "Gather relevant sources and mark unknowns", "evidence_list_exists"),
                ("plan", "Produce a bounded task graph with cost/risk estimates", "plan_has_budget_and_dependencies"),
                ("execute_safe", "Execute only registered, permission-compatible tools", "tool_receipts_exist"),
                ("verify", "Evaluate the outcome independently against acceptance criteria", "independent_verification_exists"),
                ("review", "Request human approval for external or irreversible changes", "approval_or_no_action_recorded"),
            ])]
        external_intent=any(x in goal_l for x in ("send", "publish", "submit", "apply", "email", "post", "register", "contact", "reach out"))
        installed=set(installed_capabilities or []); constraints=user_constraints or []
        if len(constraints)>100 or any(not isinstance(x,str) or len(x)>500 for x in constraints):
            raise ValueError("constraints must be at most 100 strings of at most 500 characters")
        nodes=[]; terminals=[]; lane_plans=[]
        total_recipe_steps=sum(len(row[2]) for row in matched)
        # A cap ensures all lanes plus an optional merge and external-action gate fit.
        if total_recipe_steps + (1 if len(matched)>1 else 0) + (1 if external_intent else 0) > 30:
            matched=matched[:1]
        for bi,(_,key,steps) in enumerate(matched,1):
            prev=[]; lane_ids=[]
            for si,(kind,description,gate) in enumerate(steps,1):
                node_id=f"b{bi:02d}_n{si:02d}_{kind}"
                approval_step=kind=="review" and external_intent
                nodes.append({"node_id":node_id,"branch_id":key,"kind":kind,"description":description,
                    "depends_on":list(prev),"acceptance_gate":gate,"required_capability":kind,
                    "capability_available":kind in installed or key in installed,
                    "state":"ready" if not prev else "blocked_by_dependencies",
                    "side_effect_class":"human_approval_gate" if approval_step else "read_only_or_local",
                    "failure_route":"generate_counterexample_then_retry_within_budget_or_mark_blocked","outputs":[gate]})
                prev=[node_id]; lane_ids.append(node_id)
            terminals.extend(prev); lane_plans.append({"branch_id":key,"matched_score":matched[bi-1][0],"node_ids":lane_ids})
        if len(matched)>1:
            nodes.append({"node_id":"merge_cross_lane_evidence","branch_id":"global","kind":"cross_lane_synthesis",
                "description":"Merge outputs across workflows without erasing source disagreement or lane-specific constraints",
                "depends_on":terminals,"acceptance_gate":"all_branch_outputs_and_disagreements_recorded",
                "required_capability":"cross_lane_synthesis","capability_available":"cross_lane_synthesis" in installed,
                "state":"blocked_by_dependencies","side_effect_class":"read_only_or_local",
                "failure_route":"preserve_separate_results_and_report_unresolved_conflict","outputs":["merged_evidence_graph"]})
            terminals=["merge_cross_lane_evidence"]
        if external_intent:
            nodes.append({"node_id":"exact_payload_approval_gate","branch_id":"global","kind":"approval_gate",
                "description":"Require a human to inspect and approve the exact external payload before any publisher/sender/submission tool may run",
                "depends_on":terminals,"acceptance_gate":"unexpired_single_use_approval_matches_actor_and_exact_payload_sha256",
                "required_capability":"approval_gate","capability_available":"approval_gate" in installed,
                "state":"blocked_by_dependencies","side_effect_class":"approval_required_no_action_here",
                "failure_route":"block_external_action_and_report","outputs":["approval_receipt_or_no_action"]})
        requested_budget={"max_steps":30,"max_attempts_per_step":3,"wall_clock_seconds":1800,"external_actions":0}
        unknown_budget=set(budget or {})-set(requested_budget)
        if unknown_budget: raise ValueError(f"unknown budget fields: {sorted(unknown_budget)}")
        requested_budget.update(budget or {})
        bounds={"max_steps":(1,100),"max_attempts_per_step":(1,5),"wall_clock_seconds":(10,86400),"external_actions":(0,25)}
        for key,(low,high) in bounds.items():
            value=requested_budget.get(key)
            if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:
                raise ValueError(f"budget.{key} must be an integer in [{low}, {high}]")
        graph={"workflow_id":hashlib.sha256((goal+canonical_json(constraints)+self.VERSION).encode()).hexdigest()[:24],
            "compiler_version":self.VERSION,"goal":goal,
            "template":matched[0][1] if len(matched)==1 else "multi_lane",
            "selected_templates":[r[1] for r in matched],"lanes":lane_plans,"nodes":nodes,
            "budget":requested_budget,"constraints":constraints,
            "global_invariants":["Every factual claim carries evidence or is labeled an assumption.",
                "No node can mark itself complete without its acceptance gate.",
                "Any external side effect requires separate payload-bound approval.",
                "Unverifiable/impossible objectives remain explicitly open.",
                "Stop when the budget is exhausted; report blockers rather than pretending success.",
                "A compiled node is not execution evidence; only a runtime receipt can establish execution."],
            "status":"compiled_not_executed","integrated_into_host":False}
        return graph

    def validate_graph(self, graph: dict[str, Any]) -> tuple[bool, list[str]]:
        errors=[]; nodes=graph.get("nodes", []); ids={n.get("node_id") for n in nodes}
        if len(ids)!=len(nodes): errors.append("duplicate_node_id")
        for n in nodes:
            if not n.get("acceptance_gate"): errors.append(f"{n.get('node_id')}:missing_gate")
            if any(dep not in ids for dep in n.get("depends_on", [])): errors.append(f"{n.get('node_id')}:unknown_dependency")
        # detect cycles with Kahn's algorithm
        pending={n["node_id"]:set(n.get("depends_on",[])) for n in nodes}; done=set()
        while True:
            ready={k for k,v in pending.items() if k not in done and v<=done}
            if not ready: break
            done.update(ready)
        if len(done)!=len(nodes): errors.append("dependency_cycle")
        if int(graph.get("budget",{}).get("max_steps",0))<len(nodes): errors.append("budget_smaller_than_plan")
        return not errors, errors
