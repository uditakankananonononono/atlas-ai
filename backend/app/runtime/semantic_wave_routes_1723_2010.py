import json
from pathlib import Path
from fastapi import APIRouter
from .semantic_wave_1723_2010 import report
router=APIRouter(prefix='/semantic-wave-1723-2010',tags=['semantic-verification'])
@router.get('/report')
def verification_report():
 path=Path(__file__).resolve().parents[3]/'audits'/'additional-2000-features.json'
 return report(json.loads(path.read_text())['rows'])
