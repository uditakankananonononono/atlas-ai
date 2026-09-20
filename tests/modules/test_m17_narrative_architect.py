import json,pytest
from app.modules.m17_narrative_architect.schemas import CollectIn
from app.modules.m17_narrative_architect.service import Service
async def gen(prompt,*args):return "mock",json.dumps({"topic":"voice","actionable_tips":["Use concrete detail"],"confidence":.8})
class C:
 async def collect(self,q,l):return [{"url":"https://example.com/a","text":"Use a scene, not a summary."}]
@pytest.mark.asyncio
async def test_collects_and_cites():
 x=await Service(generate=gen,collectors={"reddit":C()}).collect(CollectIn(query="essay",platforms=["reddit"]));assert str(x[0].source.url)=="https://example.com/a";assert x[0].actionable_tips
@pytest.mark.asyncio
async def test_rejects_unofficial_tiktok():
 with pytest.raises(ValueError):await Service(generate=gen,collectors={}).collect(CollectIn(query="essay",platforms=["tiktok_unofficial"]))
