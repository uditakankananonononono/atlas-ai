from __future__ import annotations
import hashlib
from typing import Any
from ._canon import canonical_json
from .closure import GapClosureEngine
from .compiler import CapabilityCompiler
from .evidence import EvidenceLattice
from .research_router import ResearchQuestion, ResearchRouter, CounterexampleForge
from .novelty_debt import NoveltyDebtLedger

class FrontierCycle:
    """One bounded loop joining plans, evidence, research priorities, and counterexamples.

    It creates an auditable next-step package. It does not fetch the web, call a model,
    execute tools, or perform side effects; callers must supply evidence and sources.
    """
    VERSION="frontier-cycle-1"
    def __init__(self):
        self.compiler=CapabilityCompiler(); self.lattice=EvidenceLattice(); self.router=ResearchRouter()
        self.counterexamples=CounterexampleForge(); self.novelty=NoveltyDebtLedger(); self.closure=GapClosureEngine()

    def run(self, request: dict[str,Any]) -> dict[str,Any]:
        goal=str(request.get("goal","")).strip()
        if not goal: raise ValueError("goal is required")
        questions=request.get("questions",[]); claims=request.get("claims",[]); hypotheses=request.get("hypotheses",[]); ideas=request.get("ideas",[])
        if len(questions)>1000 or len(claims)>100 or len(hypotheses)>50 or len(ideas)>50: raise ValueError("request exceeds bounded cycle limits")
        graph=self.compiler.compile(goal,user_constraints=request.get("constraints",[]),budget=request.get("budget",{}),installed_capabilities=request.get("installed_capabilities",[]))
        valid,graph_errors=self.compiler.validate_graph(graph)
        qobjs=[ResearchQuestion(**q) for q in questions]
        ranked=self.router.route(qobjs,limit=int(request.get("question_limit",10))) if qobjs else []
        claim_results=[]
        for row in claims:
            claim_results.append(self.lattice.adjudicate(str(row.get("claim","")),row.get("evidence",[]),half_life_days=float(row.get("half_life_days",365))))
        counterexamples=[]
        for i,row in enumerate(hypotheses):
            counterexamples.append({"hypothesis_id":row.get("hypothesis_id",f"hyp-{i+1}"),
                "tests":self.counterexamples.forge(str(row.get("hypothesis","")),known_assumptions=row.get("assumptions",[]),claimed_domain=str(row.get("domain","unknown")),max_tests=int(row.get("max_tests",5)))})
        idea_results=[]; prior_art=request.get("prior_art",[])
        for row in ideas:
            idea_results.append(self.novelty.assess(row,prior_art,prior_art_review=row.get("prior_art_review"),mechanism_test=row.get("mechanism_test"),execution_test=row.get("execution_test")))
        gaps=self.closure.list_gaps(limit=int(request.get("gap_limit",10)))
        unresolved_claims=[c for c in claim_results if c["grade"] in {"contested","insufficient_evidence","weakly_supported","weakly_refuted"}]
        open_ideas=[i for i in idea_results if i["status"]!="evidence_complete_for_review"]
        if not valid:
            next_step={"kind":"repair_plan","reason":"compiled workflow failed graph validation","items":graph_errors}
        elif unresolved_claims:
            next_step={"kind":"gather_independent_evidence","reason":"at least one claim is not strongly corroborated within supplied evidence","claim":unresolved_claims[0]["claim"]}
        elif open_ideas:
            next_step={"kind":"pay_novelty_debt","reason":"idea has an open evidence gate","idea_id":open_ideas[0]["idea_id"],"debt":open_ideas[0]["next_step"]}
        elif ranked:
            next_step={"kind":"investigate_next_question","reason":"highest-value question selected by value/uncertainty/diversity heuristic","question_id":ranked[0]["question_id"],"question":ranked[0]["question"]}
        elif gaps:
            next_step={"kind":"close_capability_gap","reason":"prior audit still contains unverified or incomplete requirements","requirement_id":gaps[0]["requirement_id"],"action":gaps[0]["recommended_next_action"]}
        else:
            next_step={"kind":"request_independent_review","reason":"no automatic completion is asserted; an independent reviewer must inspect receipts"}
        report={"version":self.VERSION,"goal":goal,"workflow":graph,"workflow_valid":valid,"workflow_errors":graph_errors,
            "ranked_questions":ranked,"claim_evaluations":claim_results,"counterexample_designs":counterexamples,
            "idea_novelty_debt":idea_results,"highest_priority_open_gaps":gaps,"next_step":next_step,
            "status":"analysis_package_ready_not_executed","external_actions_executed":0,
            "epistemic_rules":["Analogy creates a testable hypothesis, never proof.","Low similarity to supplied sources does not establish global novelty.",
               "An evidence grade is limited to the supplied corpus.","Workflow nodes require receipts before completion.","Exhausted budgets and inaccessible providers must be reported as blockers."]}
        report["cycle_sha256"]=hashlib.sha256(canonical_json(report).encode()).hexdigest()
        return report
