"""Goal decomposition, specialist orchestration, quality loops and Git versioning."""
from __future__ import annotations
import base64
import json
import tempfile
from dataclasses import asdict
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from typing import Awaitable,Callable,Protocol
from uuid import uuid4
from app.core.models import ApprovalRequest
from app.core.providers import generate as byok_generate
from . import artifacts as artifact_engine
from . import engineering as engineering_engine
from . import exports as export_engine
from . import milestones as milestone_engine
from . import quality as quality_engine
from . import reports as report_engine
from . import scoping as scope_engine
from .schemas import *
GenerateFn=Callable[[str,str,str|None],Awaitable[tuple[str,str]]]
class ApprovalSink(Protocol):
    def put(self,item:ApprovalRequest)->ApprovalRequest:...

def _milestone_to_view(m:milestone_engine.Milestone)->MilestoneView:
    return MilestoneView(milestone_id=m.milestone_id,project_id=m.project_id,title=m.title,phase=m.phase,
        depends_on=list(m.depends_on),estimated_effort_hours=m.estimated_effort_hours,deliverables=list(m.deliverables),
        acceptance_criteria=list(m.acceptance_criteria),status=m.status.value,progress=m.progress,
        planned_start=m.planned_start,planned_end=m.planned_end,actual_start=m.actual_start,actual_end=m.actual_end)
def _milestone_to_domain(v:MilestoneView)->milestone_engine.Milestone:
    return milestone_engine.Milestone(milestone_id=v.milestone_id,project_id=v.project_id,title=v.title,phase=v.phase,
        depends_on=tuple(v.depends_on),estimated_effort_hours=v.estimated_effort_hours,deliverables=tuple(v.deliverables),
        acceptance_criteria=tuple(v.acceptance_criteria),status=milestone_engine.MilestoneStatus(v.status),progress=v.progress,
        planned_start=v.planned_start,planned_end=v.planned_end,actual_start=v.actual_start,actual_end=v.actual_end)
def _artifact_to_record(m:ArtifactManifest)->artifact_engine.ArtifactRecord:
    return artifact_engine.ArtifactRecord(id=m.id,project_id=m.project_id,task_id=m.task_id,kind=m.kind,uri=m.uri,sha256=m.sha256,provenance=m.provenance)

class Service:
    def __init__(self,approval_sink:ApprovalSink,generate_fn:GenerateFn=byok_generate,repository=None):self._approvals=approval_sink;self._generate=generate_fn;self._repository=repository;self._projects:dict[tuple[str,str],ProjectView]={};self._milestones:dict[tuple[str,str],list[MilestoneView]]={};self._artifacts:dict[tuple[str,str],list[ArtifactManifest]]={};self._artifact_payloads:dict[tuple[str,str],dict[str,bytes]]={}
    def create(self,tenant_id:str,request:CreateProjectRequest)->ProjectView:
        item=ProjectView(id=str(uuid4()),tenant_id=tenant_id,goal=request.goal,brief=request.brief,budget=request.budget,status="draft")

        if self._repository: return self._repository.save(item)
        self._projects[(tenant_id,item.id)]=item;return item
    def get(self,tenant_id:str,project_id:str)->ProjectView:

        if self._repository:
            item=self._repository.get(project_id)
            if item:return item
            raise KeyError("project not found")
        try:return self._projects[(tenant_id,project_id)]
        except KeyError as exc:raise KeyError("project not found") from exc
    def list(self,tenant_id:str,limit:int=100)->list[ProjectView]:
        if self._repository:return self._repository.list(limit=limit)
        return [p for (t,_),p in self._projects.items() if t==tenant_id][-limit:]
    async def plan(self,project:ProjectView,provider:str="openai")->PlanResponse:
        prompt=("Return JSON only with tasks, assumptions, risks, quality_gates. Decompose the goal into a dependency DAG. "
                "Every task uses exactly one specialist: literature, data, coder, analyst, writer. Include measurable acceptance criteria. "
                f"Goal: {project.goal}\nBrief: {json.dumps(project.brief,sort_keys=True)}")
        _,text=await self._generate(prompt,provider,None)
        try:raw=json.loads(text)
        except json.JSONDecodeError as exc:raise ValueError("planner returned invalid JSON") from exc
        plan=ProjectPlan(goal=project.goal,**raw)
        roots={t.id for t in plan.tasks if not t.dependencies}
        for task in plan.tasks:task.status="ready" if task.id in roots else "blocked"
        project.plan=plan;project.status="planned";old=project.revision;project.revision+=1
        if self._repository: project=self._repository.save(project,expected_revision=old)
        return PlanResponse(project=project)
    def propose_execution(self,project:ProjectView)->ExecutionProposal:
        if project.status!="planned" or not project.plan:raise ValueError("project must be planned first")
        stored=self._approvals.put(ApprovalRequest(id=str(uuid4()),module_id=14,action_type="execute_project_plan",payload={"project_id":project.id,"tenant_id":project.tenant_id,"budget":project.budget.model_dump(),"task_count":len(project.plan.tasks)}))
        project.status="awaiting_approval";old=project.revision;project.revision+=1
        if self._repository:self._repository.save(project,expected_revision=old)
        return ExecutionProposal(approval_id=stored.id,project_id=project.id,status=stored.status.value)
    @staticmethod
    def ready_tasks(plan:ProjectPlan)->list[ProjectTask]:
        complete={t.id for t in plan.tasks if t.status=="completed"}
        return [t for t in plan.tasks if t.status in {"blocked","ready"} and set(t.dependencies)<=complete]
    @staticmethod
    def artifact(project_id:str,task_id:str,kind:str,uri:str,payload:bytes,provenance:dict)->ArtifactManifest:
        return ArtifactManifest(id=str(uuid4()),project_id=project_id,task_id=task_id,kind=kind,uri=uri,sha256=sha256(payload).hexdigest(),provenance=provenance)
    @staticmethod
    def commit(working_tree:Path,message:str,relative_paths:list[str])->str:
        root=working_tree.resolve();paths=[]
        for item in relative_paths:
            path=(root/item).resolve()
            if root not in path.parents:raise ValueError("versioned path escapes project workspace")
            paths.append(item)
        try:
            from git import Actor,Repo
        except ImportError as exc:raise RuntimeError("GitPython is required for repository versioning") from exc
        repo=Repo(root);repo.index.add(paths);actor=Actor("Atlas Project Builder","atlas@localhost")
        return repo.index.commit(message,author=actor,committer=actor).hexsha

    # --- Scoped project generation -------------------------------------------
    def scope_project(self,project:ProjectView,request:ScopeRequest)->ScopeView:
        constraints=scope_engine.ScopeConstraints(deadline=request.constraints.deadline,
            max_effort_hours=request.constraints.max_effort_hours,max_budget_usd=request.constraints.max_budget_usd,
            hours_per_day=request.constraints.hours_per_day,deliverable_requirements=tuple(request.constraints.deliverable_requirements),
            excluded_activities=tuple(request.constraints.excluded_activities))
        scope=scope_engine.generate_scope(project.id,project.goal,constraints=constraints,kind=request.kind,
            brief_keywords=request.brief_keywords)
        markdown=scope_engine.render_scope_markdown(scope)
        project.brief=dict(project.brief);project.brief["scope"]={"kind":scope.kind,"feasible":scope.feasibility.feasible,"markdown":markdown}
        project.status="scoped";old=project.revision;project.revision+=1
        if self._repository:self._repository.save(project,expected_revision=old)
        return ScopeView(project_id=project.id,kind=scope.kind,kind_confidence=scope.kind_confidence,
            feasible=scope.feasibility.feasible,issues=list(scope.feasibility.issues),
            estimated_effort_hours=scope.feasibility.estimated_effort_hours,estimated_finish=scope.feasibility.estimated_finish,
            in_scope=list(scope.in_scope),out_of_scope=list(scope.out_of_scope),assumptions=list(scope.assumptions),
            risks=list(scope.risks),markdown=markdown)

    # --- Milestones ------------------------------------------------------------
    def plan_milestones(self,project:ProjectView,request:MilestonePlanRequest)->list[MilestoneView]:
        plan=milestone_engine.instantiate_template(request.kind,project.id,request.start,hours_per_day=request.hours_per_day)
        views=[_milestone_to_view(m) for m in plan]
        if self._repository:self._repository.save_milestones(project.id,views)
        else:self._milestones[(project.tenant_id,project.id)]=views
        return views
    def list_milestones(self,project:ProjectView)->list[MilestoneView]:
        if self._repository:return self._repository.list_milestones(project.id)
        return list(self._milestones.get((project.tenant_id,project.id),[]))
    def milestone_progress(self,project:ProjectView)->MilestoneProgressView:
        domain=[_milestone_to_domain(v) for v in self.list_milestones(project)]
        report=milestone_engine.compute_progress(domain)
        return MilestoneProgressView(overall_progress=report.overall_progress,total_effort_hours=report.total_effort_hours,
            completed_effort_hours=report.completed_effort_hours,per_phase=dict(report.per_phase),counts_by_status=dict(report.counts_by_status))
    def advance_milestone(self,project:ProjectView,milestone_id:str,request:MilestoneAdvanceRequest)->MilestoneView:
        views=self.list_milestones(project);by_id={v.milestone_id:v for v in views}
        if milestone_id not in by_id:raise KeyError("milestone not found")
        at=request.at or datetime.now(timezone.utc)
        domain=[_milestone_to_domain(v) for v in views];target=by_id[milestone_id]
        new_status=milestone_engine.MilestoneStatus(request.status)
        if new_status==milestone_engine.MilestoneStatus.COMPLETED:
            ok,reason=milestone_engine.can_complete(_milestone_to_domain(target),domain,request.evidence or {})
            if not ok:raise ValueError(reason)
        updated=milestone_engine.advance_status(_milestone_to_domain(target),new_status,at)
        if request.progress is not None and new_status not in milestone_engine.TERMINAL_STATUSES:
            from dataclasses import replace as dc_replace
            updated=dc_replace(updated,progress=request.progress)
        out=[_milestone_to_view(updated if v.milestone_id==milestone_id else _milestone_to_domain(v)) for v in views]
        if self._repository:self._repository.save_milestones(project.id,out)
        else:self._milestones[(project.tenant_id,project.id)]=out
        return _milestone_to_view(updated)
    def milestone_slippage(self,project:ProjectView,as_of:datetime|None=None)->list[SlippageView]:
        domain=[_milestone_to_domain(v) for v in self.list_milestones(project)]
        findings=milestone_engine.detect_slippage(domain,as_of or datetime.now(timezone.utc))
        return [SlippageView(milestone_id=f.milestone_id,kind=f.kind,detail=f.detail,
            overdue_by_seconds=f.overdue_by.total_seconds() if f.overdue_by else None,progress_gap=f.progress_gap) for f in findings]
    def replan_milestones(self,project:ProjectView,as_of:datetime|None=None,hours_per_day:float=8.0)->list[MilestoneView]:
        domain=[_milestone_to_domain(v) for v in self.list_milestones(project)]
        if not domain:raise ValueError("no milestones to replan")
        result=milestone_engine.replan(domain,as_of or datetime.now(timezone.utc),hours_per_day=hours_per_day)
        views=[_milestone_to_view(m) for m in result.milestones]
        if self._repository:self._repository.save_milestones(project.id,views)
        else:self._milestones[(project.tenant_id,project.id)]=views
        return views

    # --- Artifacts -------------------------------------------------------------
    def register_artifact(self,project:ProjectView,request:ArtifactRegisterRequest)->ArtifactManifest:
        try:payload=base64.b64decode(request.content_base64,validate=True)
        except Exception as exc:raise ValueError("content_base64 is not valid base64") from exc
        record=artifact_engine.build_manifest(project.id,request.task_id,request.kind,request.uri,payload,request.provenance)
        report=artifact_engine.validate_artifact(record,payload=payload)
        if not report.passed:
            raise ValueError("artifact failed validation: "+"; ".join(f.message for f in report.findings if f.severity=="error"))
        manifest=ArtifactManifest(id=record.id,project_id=record.project_id,task_id=record.task_id,kind=record.kind,uri=record.uri,sha256=record.sha256,provenance=dict(record.provenance))
        if self._repository:self._repository.save_artifact(project.id,manifest,payload)
        else:
            self._artifacts.setdefault((project.tenant_id,project.id),[]).append(manifest)
            self._artifact_payloads.setdefault((project.tenant_id,project.id),{})[manifest.id]=payload
        return manifest
    def list_artifacts(self,project:ProjectView)->list[ArtifactManifest]:
        if self._repository:return self._repository.list_artifacts(project.id)
        return list(self._artifacts.get((project.tenant_id,project.id),[]))
    def validate_artifacts(self,project:ProjectView)->ArtifactSetValidationView:
        manifests=self.list_artifacts(project)
        if self._repository:payloads=self._repository.artifact_payloads(project.id)
        else:payloads=self._artifact_payloads.get((project.tenant_id,project.id),{})
        records=tuple(_artifact_to_record(m) for m in manifests)
        report=artifact_engine.validate_manifest_set(records,project.id,payloads=payloads)
        return ArtifactSetValidationView(project_id=project.id,passed=report.passed,score=report.score,
            artifacts=[ArtifactValidationView(artifact_id=r.artifact_id,passed=r.passed,score=r.score,
                findings=[asdict(f) for f in r.findings],remediation=list(r.remediation)) for r in report.artifact_reports],
            findings=[asdict(f) for f in report.findings])

    # --- Plan quality -----------------------------------------------------------
    def evaluate_plan(self,project:ProjectView)->QualityResult:
        if not project.plan:raise ValueError("project must be planned before quality evaluation")
        report=quality_engine.evaluate_plan(project.plan,budget=project.budget)
        return QualityResult(passed=report.passed,score=report.score,
            findings=[f.message for f in report.findings],remediation=list(report.remediation))

    # --- Engineering design artifacts (rows 510-534) ------------------------------
    def generate_design(self,project:ProjectView,request:DesignRequest)->DesignDocView:
        document=engineering_engine.generate_design(request.kind,project.goal,context=request.context)
        report=engineering_engine.validate_design(document)
        if not report.passed:
            raise ValueError("generated design failed validation: "+"; ".join(f.message for f in report.findings if f.severity=="error"))
        payload=document.markdown.encode("utf-8")
        provenance={"generator":"m14-engineering","created_at":document.generated_at,
            "design_kind":document.kind,"feature_row":str(document.row)}
        record=artifact_engine.build_manifest(project.id,f"design:{document.kind}","design_document",
            f"workspace://{project.id}/designs/{document.kind}.md",payload,provenance)
        manifest=ArtifactManifest(id=record.id,project_id=record.project_id,task_id=record.task_id,kind=record.kind,uri=record.uri,sha256=record.sha256,provenance=dict(record.provenance))
        if self._repository:self._repository.save_artifact(project.id,manifest,payload)
        else:
            self._artifacts.setdefault((project.tenant_id,project.id),[]).append(manifest)
            self._artifact_payloads.setdefault((project.tenant_id,project.id),{})[manifest.id]=payload
        return DesignDocView(kind=document.kind,row=document.row,title=document.title,
            markdown=document.markdown,generated_at=datetime.fromisoformat(document.generated_at),
            validation=DesignValidationView(passed=report.passed,score=report.score,
                findings=[asdict(f) for f in report.findings],remediation=list(report.remediation)),
            artifact_id=manifest.id)
    def list_designs(self,project:ProjectView)->list[DesignListItem]:
        out=[]
        for m in self.list_artifacts(project):
            if m.kind!="design_document":continue
            spec=engineering_engine.spec_for_kind(str(m.provenance.get("design_kind","")))
            out.append(DesignListItem(artifact_id=m.id,kind=spec.kind,row=spec.row,title=spec.title,
                generated_at=datetime.fromisoformat(str(m.provenance.get("created_at")))))
        return out

    # --- Status report -----------------------------------------------------------
    def status_report(self,project:ProjectView,as_of:datetime|None=None)->StatusReportView:
        milestones=tuple(_milestone_to_domain(v) for v in self.list_milestones(project))
        progress=milestone_engine.compute_progress(list(milestones)) if milestones else None
        slippage=tuple(milestone_engine.detect_slippage(list(milestones),as_of or datetime.now(timezone.utc))) if milestones else ()
        manifests=self.list_artifacts(project)
        validation=None
        if manifests:
            if self._repository:payloads=self._repository.artifact_payloads(project.id)
            else:payloads=self._artifact_payloads.get((project.tenant_id,project.id),{})
            records=tuple(_artifact_to_record(m) for m in manifests)
            validation=artifact_engine.validate_manifest_set(records,project.id,payloads=payloads)
        generated=datetime.now(timezone.utc)
        markdown=report_engine.render_status_report(report_engine.StatusReportContext(
            project_id=project.id,goal=project.goal,status=project.status,progress=progress,
            milestones=milestones,slippage=slippage,artifact_validation=validation,generated_at=generated))
        return StatusReportView(project_id=project.id,markdown=markdown,generated_at=generated)

    # --- Feedback and exports --------------------------------------------------
    async def apply_feedback(self,project:ProjectView,request:FeedbackRequest)->FeedbackResponse:
        if not project.plan:raise ValueError("project must be planned before feedback")
        prompt=("Return JSON only with tasks, assumptions, risks, quality_gates. Revise the existing plan to address the feedback. "
                "Every task uses exactly one specialist: literature, data, coder, analyst, writer. Keep measurable acceptance criteria. "
                f"Goal: {project.goal}\nCurrent plan: {project.plan.model_dump_json()}\nFeedback: {request.feedback}")
        _,text=await self._generate(prompt,request.provider,None)
        try:raw=json.loads(text)
        except json.JSONDecodeError as exc:raise ValueError("planner returned invalid JSON") from exc
        plan=ProjectPlan(goal=project.goal,**raw)
        roots={t.id for t in plan.tasks if not t.dependencies}
        for task in plan.tasks:task.status="ready" if task.id in roots else "blocked"
        project.plan=plan;project.status="planned";old=project.revision;project.revision+=1
        if self._repository:project=self._repository.save(project,expected_revision=old)
        return FeedbackResponse(project=project,revision_applied=True)
    def export_project(self,project:ProjectView,base_dir:Path|None=None)->ExportView:
        manifests=self.list_artifacts(project)
        if self._repository:payloads=self._repository.artifact_payloads(project.id)
        else:payloads=self._artifact_payloads.get((project.tenant_id,project.id),{})
        records=[_artifact_to_record(m) for m in manifests]
        files={}
        warnings=[]
        for record in records:
            payload=payloads.get(record.id)
            if payload is None:
                warnings.append(f"artifact {record.id} ({record.kind}) excluded from export: payload unavailable")
                continue
            files[artifact_engine.storage_path(record)]=payload
        root=(Path(base_dir) if base_dir else Path(tempfile.mkdtemp(prefix=f"atlas-m14-{project.id}-")))/project.id
        root.mkdir(parents=True,exist_ok=True)
        entries=export_engine.write_project_files(root,files,overwrite=True)
        milestones=tuple(_milestone_to_domain(v) for v in self.list_milestones(project))
        progress=None
        if milestones:
            progress=milestone_engine.compute_progress(list(milestones)).overall_progress
        readme=export_engine.render_readme(export_engine.ReadmeContext(project_id=project.id,goal=project.goal,status=project.status,
            milestones=milestones,artifacts=tuple(records),overall_progress=progress,
            assumptions=tuple(project.plan.assumptions) if project.plan else (),risks=tuple(project.plan.risks) if project.plan else ()))
        readme_bytes=readme.encode("utf-8")
        extra_entries=export_engine.write_project_files(root,{"README.md":readme_bytes},overwrite=True)
        status_md=self.status_report(project).markdown
        extra_entries+=export_engine.write_project_files(root,{"STATUS.md":status_md.encode("utf-8")},overwrite=True)
        scope_md=(project.brief.get("scope") or {}).get("markdown")
        if scope_md:
            extra_entries+=export_engine.write_project_files(root,{"SCOPE.md":scope_md.encode("utf-8")},overwrite=True)
        manifest=export_engine.build_manifest(project.id,tuple(entries)+tuple(extra_entries))
        (root/"export_manifest.json").write_text(json.dumps(manifest.to_dict(),indent=2))
        verification=export_engine.verify_export(root,manifest)
        zip_entry=export_engine.create_zip(root,root.parent/f"{project.id}-export.zip")
        return ExportView(project_id=project.id,readme=readme,manifest=manifest.to_dict(),
            verification=asdict(verification),zip_sha256=zip_entry.sha256,warnings=warnings)
