from fastapi import APIRouter,HTTPException
from .semantic_verification_1149_1435 import report,rows,verify_evidence
router=APIRouter(prefix='/semantic-verification-1149-1435',tags=['semantic-verification'])
@router.get('/report')
def get_report():return report()
@router.get('/rows/{row_id}')
def get_row(row_id:int):
 found=next((r for r in rows() if r['id']==row_id),None)
 if not found:raise HTTPException(404,'row outside block')
 return verify_evidence(found)
