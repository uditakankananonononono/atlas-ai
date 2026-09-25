"""Luxury venture service: real evidence collection plus review-only concept scoring.

Collection fetches live public data through sources.py (SEC EDGAR XBRL, Stooq,
Wikipedia/Wikidata, trade-press RSS, Google News RSS - all free, no keys).
Concept scoring reuses Module 19's deterministic studio; this service never
invents evidence, never claims brand affiliation, and never contacts a brand.
"""
from __future__ import annotations
from pydantic import BaseModel,Field
from .luxury_venture import Capability,VentureBrief,build_luxury_venture
from .luxury_sources import LuxuryDataService

class GroundedStudioRequest(BaseModel):
 brand_or_segment:str=Field(min_length=2,max_length=200)
 sector:str=Field(default='other',pattern=r'^(automotive|character_ip|hotel|luxury_hospitality|fashion|jewelry|other)$')
 customer_job:str=Field(min_length=10,max_length=1000)
 constraints:list[str]=Field(min_length=1,max_length=30)
 capabilities:list[Capability]=Field(min_length=1,max_length=30)
 ticker:str|None=Field(default=None,pattern=r'^[A-Za-z]{1,6}$')
 limit:int=Field(default=12,ge=1,le=30)

class LuxuryVentureService:
 def __init__(self,data:LuxuryDataService|None=None):self.data=data or LuxuryDataService()
 async def collect(self,brand_or_segment:str,sector:str='other',ticker:str|None=None,limit:int=12)->dict:
  return await self.data.collect_evidence(brand_or_segment,sector,ticker,limit)
 async def grounded_studio(self,request:GroundedStudioRequest)->dict:
  evidence=await self.collect(request.brand_or_segment,request.sector,request.ticker,request.limit)
  signals=[{k:s[k] for k in ('signal_id','statement','source_ids','importance')} for s in evidence['signals']]
  if len(evidence['sources'])<2 or len(signals)<2:
   raise ValueError('insufficient live evidence collected to ground a brief ('+str(len(evidence['sources']))+' sources, '+str(len(signals))+' signals); check fetch_report and retry or widen the query')
  brief=VentureBrief(brand_or_segment=request.brand_or_segment,sector=request.sector,customer_job=request.customer_job,constraints=request.constraints,sources=[{k:s[k] for k in ('source_id','url','title','observed_at','finding')} for s in evidence['sources']],signals=signals,capabilities=request.capabilities)
  studio=build_luxury_venture(brief)
  return {'studio':studio,'evidence':{'collected_on':evidence['collected_on'],'sources':evidence['sources'],'coverage_notes':evidence['coverage_notes'],'fetch_report':evidence['fetch_report'],'fetch_summary':evidence['fetch_summary']},'review_required':evidence['review_required'],'boundary':'Real public data grounds every source; concepts remain review-only. No affiliation claim, outreach, publication, sale, contract, purchase, or spend occurs.'}
