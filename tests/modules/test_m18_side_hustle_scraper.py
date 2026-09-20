import json,pytest
from app.modules.m18_side_hustle_scraper.schemas import DiscoverIn
from app.modules.m18_side_hustle_scraper.service import Service
async def gen(prompt,*args):return "mock",json.dumps([{"title":"Tutoring","steps":["Interview 5 students"],"tools":["calendar"],"complexity":2,"time_to_first_dollar_days":14,"automation_level":10,"monetisation":["sessions"],"source_urls":["https://example.com/a"],"scam_signals":[],"assumptions":["demand"]}])
class C:
 async def collect(self,q,l):return [{"url":"https://example.com/a","text":"Interview students before offering tutoring."}]
@pytest.mark.asyncio
async def test_blueprint_keeps_sources():
 x=await Service(generate=gen,collectors={"youtube":C()}).discover(DiscoverIn(query="student business",platforms=["youtube"]));assert str(x[0].source_urls[0])=="https://example.com/a"
@pytest.mark.asyncio
async def test_rejects_login_instagram():
 with pytest.raises(ValueError):await Service(generate=gen,collectors={}).discover(DiscoverIn(query="student business",platforms=["instagram_login"]))
