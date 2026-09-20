from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .google_grounding import GoogleWorkspaceGrounder
router=APIRouter(prefix="/google-grounding",tags=["google-grounding"])
class GroundRequest(BaseModel):
    kind:Literal["doc","sheet"]
    resource_id:str=Field(min_length=5,max_length=500)
    ranges:list[str]=Field(default_factory=list,max_length=50)
@router.post("/read")
async def read_grounding(request:GroundRequest):
    client=GoogleWorkspaceGrounder()
    try:
        data=[await client.document(request.resource_id)] if request.kind=="doc" else await client.sheet(request.resource_id,request.ranges)
        return [{**x.__dict__,"read_only":True} for x in data]
    except RuntimeError as exc:raise HTTPException(503,str(exc)) from exc
    finally:await client.close()
