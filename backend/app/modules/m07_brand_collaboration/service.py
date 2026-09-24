"""Brand discovery, collateral rendering, partnership ledger, and gated reporting."""
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from io import BytesIO
from uuid import uuid4
from app.core.models import ApprovalRequest
from .schemas import *

MODULE_ID=7
class NotFoundError(LookupError): pass
class Service:
    def __init__(self, repository, approvals):
        tenant_id=getattr(repository,"tenant_id","")
        if not tenant_id.strip():raise ValueError("tenant-scoped repository is required")
        self.repo=repository; self.approvals=approvals; self.tenant_id=tenant_id.strip()
    def discover(self,data:BrandDiscoveryIn,creator_mission:str)->BrandCandidate:
        creator=set(creator_mission.lower().split()); brand=set(data.mission.lower().split()); shared=sorted(creator&brand-{"and","the","for","with"})
        score=round(min(1.0,.25+len(shared)/max(8,len(creator))),3); reasons=[f"shared mission term: {x}" for x in shared[:5]] or ["manual alignment review required"]
        out=BrandCandidate(id=str(uuid4()),alignment_score=score,alignment_reasons=reasons,created_at=datetime.now(timezone.utc),**data.model_dump())
        self.repo.add_brand(**out.model_dump(mode="json")|{"public_url":str(out.public_url),"created_at":out.created_at})
        return out
    def _brand(self,brand_id):
        row=self.repo.brand(brand_id)
        if not row: raise NotFoundError(brand_id)
        return row
    def _artifact(self,kind,brand_id,content,content_type,metadata):
        self._brand(brand_id); now=datetime.now(timezone.utc); ident=str(uuid4()); digest=sha256(content).hexdigest()
        self.repo.add_artifact(id=ident,kind=kind,brand_id=brand_id,content=content,content_type=content_type,sha256=digest,created_at=now,metadata_json=metadata)
        return ArtifactOut(id=ident,kind=kind,brand_id=brand_id,content_type=content_type,sha256=digest,created_at=now,metadata=metadata)
    @staticmethod
    def _pdf(html:str)->tuple[bytes,str]:
        try:
            from weasyprint import HTML
            return HTML(string=html).write_pdf(),"application/pdf"
        except ImportError:
            return html.encode(),"text/html"
    def media_kit(self,data:MediaKitIn)->ArtifactOut:
        rows="".join(f"<li>{escape(str(k))}: {escape(str(v))}</li>" for k,v in data.metrics.items())
        html=f"<html><body><h1>{escape(data.creator_name)} x Brand Partnership</h1><h2>Mission</h2><p>{escape(data.creator_mission)}</p><h2>Verified metrics</h2><ul>{rows}</ul><p>Generated from supplied data; verify before sharing.</p></body></html>"
        content,ctype=self._pdf(html); return self._artifact("media_kit",data.brand_id,content,ctype,{"creator":data.creator_name,"template":"jinja-compatible-v1"})
    def sponsorship(self,data:SponsorshipPackageIn)->ArtifactOut:
        html="<html><body><h1>Sponsorship packages</h1>"+"".join(f"<h2>{escape(str(t.get('name','Tier')))}</h2><pre>{escape(str(t))}</pre>" for t in data.tiers)+"</body></html>"
        content,ctype=self._pdf(html); return self._artifact("sponsorship_package",data.brand_id,content,ctype,{"currency":data.currency,"tier_count":len(data.tiers)})
    def invoice(self,data:InvoiceIn)->ArtifactOut:
        if data.due_on<data.issued_on: raise ValueError("due_on precedes issued_on")
        total=sum(float(x.get("quantity",1))*float(x.get("unit_price",0)) for x in data.line_items)
        html=f"<html><body><h1>Invoice {escape(data.invoice_number)}</h1><p>Due {data.due_on}</p><pre>{escape(str(data.line_items))}</pre><h2>Total {data.currency} {total:.2f}</h2></body></html>"
        content,ctype=self._pdf(html); return self._artifact("invoice",data.brand_id,content,ctype,{"invoice_number":data.invoice_number,"total":total,"currency":data.currency})
    def log_event(self,data:PartnershipEventIn)->PartnershipEventOut:
        self._brand(data.brand_id); out=PartnershipEventOut(id=str(uuid4()),created_at=datetime.now(timezone.utc),**data.model_dump()); self.repo.add_event(**out.model_dump(mode="json")); return out
    def report(self,data:ReportIn)->ArtifactOut:
        if data.period_end<data.period_start: raise ValueError("invalid reporting period")
        events=self.repo.events(data.brand_id); html=f"<html><body><h1>Brand performance report</h1><p>{data.period_start} to {data.period_end}</p><pre>{escape(str(data.metrics))}</pre><p>{len(events)} partnership ledger events.</p></body></html>"
        content,ctype=self._pdf(html); return self._artifact("performance_report",data.brand_id,content,ctype,{"period_start":str(data.period_start),"period_end":str(data.period_end),"event_count":len(events)})
    def propose_send(self,artifact_id:str,recipient:str)->ApprovalProposal:
        row=self.repo.artifact(artifact_id)
        if not row: raise NotFoundError(artifact_id)
        action={"performance_report":"send_brand_report","invoice":"send_invoice"}.get(row.kind,"send_brand_collateral")
        payload={"tenant_id":self.tenant_id,"artifact_id":artifact_id,"brand_id":row.brand_id,"recipient":recipient,"sha256":row.sha256,"content_type":row.content_type}
        approval=ApprovalRequest(id=str(uuid4()),module_id=MODULE_ID,action_type=action,payload=payload); self.approvals.put(approval,user_id=self.tenant_id)
        return ApprovalProposal(approval_id=approval.id,action_type=action,payload=payload)
