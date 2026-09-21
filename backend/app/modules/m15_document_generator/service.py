"""Template registry, immutable versioning, structural diffs and gated rendering."""
from __future__ import annotations
import json
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import uuid4
from app.core.models import ApprovalRequest
from .schemas import *
class ApprovalSink(Protocol):
    def put(self,item:ApprovalRequest)->ApprovalRequest:...
class Service:
    def __init__(self,approval_sink:ApprovalSink,repository=None):self._approvals=approval_sink;self._repository=repository;self._versions:dict[tuple[str,str],DocumentVersion]={};self._numbers:dict[tuple[str,str],int]={}
    def create_version(self,tenant_id:str,document_id:str,request:CreateVersionRequest)->DocumentVersion:
        parent=self.get(tenant_id,request.parent_version_id) if request.parent_version_id else None
        if parent and parent.document_id!=document_id:raise ValueError("parent version belongs to another document")
        key=(tenant_id,document_id);number=self._repository.next_number(document_id) if self._repository else self._numbers.get(key,0)+1
        self._numbers[key]=number
        digest=sha256(json.dumps(request.content,sort_keys=True,default=str).encode()).hexdigest()
        version=DocumentVersion(id=str(uuid4()),tenant_id=tenant_id,document_id=document_id,version_number=number,format=request.format,template_id=request.template_id,content=request.content,parent_version_id=request.parent_version_id,content_hash=digest,citations=request.citations,figures=request.figures)
        
        if self._repository:return self._repository.save(version)
        self._versions[(tenant_id,version.id)]=version;return version
    def get(self,tenant_id:str,version_id:str)->DocumentVersion:
        
        if self._repository:
            item=self._repository.get(version_id)
            if item:return item
            raise KeyError("document version not found")
        try:return self._versions[(tenant_id,version_id)]
        except KeyError as exc:raise KeyError("document version not found") from exc
    def diff(self,before:DocumentVersion,after:DocumentVersion)->DiffResponse:
        return DiffResponse(from_version_id=before.id,to_version_id=after.id,changes=self._diff(before.content,after.content))
    def _diff(self,before,after,path="$"):
        if type(before) is not type(after):return [DiffEntry(path=path,operation="replace",before=before,after=after)]
        if isinstance(before,dict):
            out=[]
            for k in sorted(before.keys()-after.keys()):out.append(DiffEntry(path=f"{path}.{k}",operation="remove",before=before[k]))
            for k in sorted(after.keys()-before.keys()):out.append(DiffEntry(path=f"{path}.{k}",operation="add",after=after[k]))
            for k in sorted(before.keys()&after.keys()):out+=self._diff(before[k],after[k],f"{path}.{k}")
            return out
        if isinstance(before,list):
            out=[]
            for i in range(max(len(before),len(after))):
                if i>=len(before):out.append(DiffEntry(path=f"{path}[{i}]",operation="add",after=after[i]))
                elif i>=len(after):out.append(DiffEntry(path=f"{path}[{i}]",operation="remove",before=before[i]))
                else:out+=self._diff(before[i],after[i],f"{path}[{i}]")
            return out
        return [] if before==after else [DiffEntry(path=path,operation="replace",before=before,after=after)]
    def preflight(self,version:DocumentVersion)->dict:
        issues=[];warnings=[]
        if not version.content:issues.append("document content is empty")
        citation_keys=[c.key for c in version.citations]
        if len(citation_keys)!=len(set(citation_keys)):issues.append("citation keys must be unique")
        missing_urls=[c.key for c in version.citations if not c.url]
        if missing_urls:warnings.append(f"citations without URLs: {', '.join(missing_urls)}")
        if version.format=="pptx":
            slides=version.content.get("slides",[])
            if not slides:issues.append("PPTX has no slides")
            for i,slide in enumerate(slides,1):
                if not slide.get("title"):issues.append(f"slide {i} has no title")
                if len(str(slide.get("body",'')))>1200:warnings.append(f"slide {i} body may overflow")
        figure_ids=[f.id for f in version.figures]
        if len(figure_ids)!=len(set(figure_ids)):issues.append("figure IDs must be unique")
        return {"version_id":version.id,"ready":not issues,"issues":issues,"warnings":warnings,"content_hash":version.content_hash,"citation_count":len(version.citations),"figure_count":len(version.figures)}
    def propose_export(self,version:DocumentVersion)->ExportProposal:
        stored=self._approvals.put(ApprovalRequest(id=str(uuid4()),module_id=15,action_type="render_document",payload={"tenant_id":version.tenant_id,"document_id":version.document_id,"version_id":version.id,"format":version.format,"template_id":version.template_id,"content_hash":version.content_hash}))
        version.status="awaiting_approval";return ExportProposal(approval_id=stored.id,version_id=version.id,status=stored.status.value)
    @staticmethod
    def render_latex(template:Path,content:dict)->bytes:
        from jinja2 import Environment,FileSystemLoader,StrictUndefined
        env=Environment(loader=FileSystemLoader(template.parent),undefined=StrictUndefined,autoescape=False)
        return env.get_template(template.name).render(**content).encode()
    @staticmethod
    def render_figure(spec:FigureSpec)->bytes:
        import io
        if spec.engine=="matplotlib":
            import matplotlib;matplotlib.use("Agg")
            from matplotlib import pyplot as plt
            fig,ax=plt.subplots();method={"line":"plot","bar":"bar","scatter":"scatter"}.get(spec.kind,"plot");getattr(ax,method)(spec.data.get("x",[]),spec.data.get("y",[]));ax.set_title(spec.options.get("title",""));out=io.BytesIO();fig.savefig(out,format="png",bbox_inches="tight");plt.close(fig);return out.getvalue()
        import plotly.graph_objects as go
        cls={"bar":go.Bar,"scatter":go.Scatter,"line":go.Scatter,"pie":go.Pie}[spec.kind]
        args={"labels":spec.data.get("labels",[]),"values":spec.data.get("values",[])} if spec.kind=="pie" else {"x":spec.data.get("x",[]),"y":spec.data.get("y",[])}
        fig=go.Figure(data=[cls(**args)]);fig.update_layout(**spec.options);return fig.to_image(format="png")
