from typing import Any, Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .humanities_1810_1859 import humanities_support_1810_1859
Method=Literal['historical_analysis','historiography','archival_research','primary_sources','secondary_sources','oral_history','public_history','digital_history','comparative_history','world_history','microhistory','macrohistory','biography','prosopography','genealogy','chronology','periodization','historical_causation','historical_contingency','counterfactual_history','philosophy','metaphysics','epistemology','ethics','aesthetics','logic','political_philosophy','social_philosophy','philosophy_of_mind','philosophy_of_language','philosophy_of_science','philosophy_of_religion','existentialism','phenomenology','pragmatism','analytic_philosophy','continental_philosophy','eastern_philosophy','african_philosophy','indigenous_philosophy','literature','literary_criticism','literary_theory','comparative_literature','world_literature','poetry','drama','fiction','non_fiction','genre_studies']
class Request1810_1859(BaseModel): method:Method; data:dict[str,Any]=Field(default_factory=dict)
router=APIRouter(prefix='/humanities/1810-1859',tags=['humanities-1810-1859'])
@router.post('/analyze')
def analyze(body:Request1810_1859):
 try:return humanities_support_1810_1859(body.method,body.data)
 except (ValueError,TypeError,KeyError) as e:raise HTTPException(422,str(e)) from e
