from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .capability_audit_13 import audit,load_ledger,verify_row
router=APIRouter(prefix='/capability-audit-13',tags=['capability-audit'])
class Attestations(BaseModel):production_attestations:list[str]=Field(default_factory=list)
@router.get('/ledger')
def ledger():return load_ledger()
@router.post('/verify')
def verify(body:Attestations):return audit(body.production_attestations)
@router.get('/rows/{row_id}')
def row(row_id:int):
 rows=load_ledger()['rows']
 if not 1<=row_id<=len(rows):raise HTTPException(404,'unknown capability row')
 return verify_row(rows[row_id-1])
