"""Identity and numerical boundaries for stateless owner computation endpoints.

Payload references are metadata only; these endpoints retrieve no resources.
Matching a label is not an access grant. Actual resource resolvers must apply
source permissions separately before using private material.
"""
from __future__ import annotations
import math
from fastapi import HTTPException
from app.auth.context import TenantContext


def owner_payload(payload,tenant:TenantContext):
    claimed=payload.get('tenant_id')
    if claimed is not None and str(claimed)!=tenant.tenant_id:raise HTTPException(403,'payload tenant does not match authenticated owner')
    actor=payload.get('actor_id')
    if actor is not None and str(actor)!=tenant.actor_id:raise HTTPException(403,'payload actor does not match authenticated actor')
    refs=payload.get('resource_refs',[])
    if not isinstance(refs,list):raise HTTPException(422,'resource_refs must be a list')
    for ref in refs:
        if not isinstance(ref,dict):raise HTTPException(422,'resource references must be objects')
        if ref.get('tenant_id')!=tenant.tenant_id:raise HTTPException(403,'cross-owner reference rejected')
        if ref.get('actor_id') is not None and ref['actor_id']!=tenant.actor_id:raise HTTPException(403,'cross-actor reference rejected')
    # Prevent nonfinite output serialization and basic unbounded-input attacks.
    nodes=0
    def check(value,depth=0):
        nonlocal nodes
        nodes+=1
        if depth>60 or nodes>200000:raise HTTPException(422,'computation input exceeds size/depth boundary')
        if isinstance(value,float) and not math.isfinite(value):raise HTTPException(422,'nonfinite numerical input rejected')
        if isinstance(value,dict):
            for v in value.values():check(v,depth+1)
        elif isinstance(value,list):
            for v in value:check(v,depth+1)
    check(payload)
    return {**payload,'tenant_id':tenant.tenant_id,'actor_id':tenant.actor_id}
