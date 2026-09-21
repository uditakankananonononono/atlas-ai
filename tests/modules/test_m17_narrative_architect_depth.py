import json
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m17_narrative_architect.schemas import CollectIn,ConceptIn,IdentityIn,CritiqueIn
from app.modules.m17_narrative_architect.service import Service
from app.modules.m17_narrative_architect.routes import router,get_service
from app.auth.context import require_tenant,TenantContext

async def model(prompt,provider,*args):
 if "essay concepts" in prompt:
  count=int(prompt.split("exactly ")[1].split()[0]); return provider,json.dumps([{"title":f"Lens {i}","core_tension":"belonging versus change","metaphor":"a map","outline":["choose a scene","name the choice","reflect"],"opening":"Writer prompt: draft in your own words the moment the choice became visible.","evidence_urls":["https://example.edu/a"],"privacy_flags":[],"source_material_refs":["confirmed experience"],"literary_devices":[{"device":"motif","placement":"return at the reflection","purpose":"connect change"}],"student_work_questions":["What did you notice?"]} for i in range(count)])
 return provider,json.dumps({"topic":"scene","actionable_tips":["Show a choice through concrete detail."],"confidence":.8,"narrative":[{"start":0,"end":4,"replacement":None,"reason":"Open closer to the action","category":"narrative"}],"grammar":[],"admissions":[],"cliches":[],"techniques":[]})
class Collector:
 async def collect(self,q,l): return [{"url":"https://example.edu/a","text":"Writers should show a choice with concrete detail. Avoid inflated stakes.","creator":"Writing Center","published_at":"2026-01-01","author_verified":True,"citations":["x"]}]
@pytest.mark.asyncio
async def test_retrieval_scores_clusters_and_cites_source():
 s=Service(generate=model,collectors={"public_web":Collector()}); rows=await s.collect(CollectIn(query="college essay",platforms=["public_web"],owner_id=str(uuid4())))
 assert rows[0].source.credibility_score>.7 and rows[0].cluster_id=="topic-01"
 assert "example.edu" in rows[0].citation and "sha256:" in rows[0].citation
@pytest.mark.asyncio
async def test_transcript_provenance_has_time_spans():
 class T:
  async def collect(self,q,l): return [{"url":"https://youtube.com/watch?v=x","transcript":"Start with a scene and show your choice.","transcript_spans":[{"start_seconds":12,"end_seconds":18,"text":"Start with a scene"}]}]
 row=(await Service(generate=model,collectors={"youtube":T()}).collect(CollectIn(query="essay",platforms=["youtube"])))[0]
 assert row.source.transcript_spans[0].start_seconds==12
@pytest.mark.asyncio
async def test_concepts_are_tenant_isolated_and_privacy_minimized():
 a,b=str(uuid4()),str(uuid4()); s=Service(generate=model,collectors={"public_web":Collector()})
 await s.collect(CollectIn(query="essay",platforms=["public_web"],owner_id=a))
 with pytest.raises(ValueError,match="outside the retrieved tenant corpus"):
  await s.concepts(ConceptIn(owner_id=b,prompt="Who are you?",count=5,profile=IdentityIn(traits=["curious"],pivotal_experiences=["Call me at +91 99999 99999"],forbidden_topics=["medical"])))
 concepts=await s.concepts(ConceptIn(owner_id=a,prompt="Who are you?",count=5,profile=IdentityIn(traits=["curious"],pivotal_experiences=["Call me at +91 99999 99999"])))
 assert len(concepts)==5 and concepts[0].literary_devices and "student must write" in concepts[0].authorship_notice.lower()
@pytest.mark.asyncio
async def test_critique_returns_offset_diffs_voice_metrics_and_model_votes():
 s=Service(generate=model,collectors={},critique_models=[("one",None),("two",None)])
 draft="This opening begins slowly, but it contains my own specific memory and decision."
 out=await s.critique(CritiqueIn(draft=draft,target_prompt="Describe growth",voice_samples=["I write short sentences. Details matter to me. I choose plain words."]))
 assert out.narrative[0].original=="This" and out.critique_models==["one:default","two:default"]
 assert out.voice_metrics.sample_word_count>0 and out.model_agreement>0

def test_routes_are_mounted_and_validate_failure_path():
 app=FastAPI(); app.include_router(router)
 app.dependency_overrides[get_service]=lambda:Service(generate=model,collectors={})
 app.dependency_overrides[require_tenant]=lambda:TenantContext(tenant_id="tenant-a",actor_id="actor-a")
 c=TestClient(app); r=c.post("/narrative-architect/advice",json={"query":"essay","platforms":["tiktok_unofficial"]})
 assert r.status_code==422 and "unsupported" in r.json()["detail"]
