from app.modules.m17_narrative_architect.wiring import build_narrative_collectors
from app.modules.m22_tools_hub.collectors import default_collectors
def test_m17_default_and_optional_legal_sources():
 assert 'reddit' in build_narrative_collectors({})
 configured=build_narrative_collectors({'ATLAS_YOUTUBE_API_KEY':'y','ATLAS_PINTEREST_ACCESS_TOKEN':'p','ATLAS_M18_PUBLIC_URLS':'https://example.com'})
 assert {'reddit','youtube','pinterest','public_web'} <= set(configured)
def test_m22_ships_free_official_discovery_sources():
 # Updated expectation (stale since a1ef402b added sources.py): the original three come first, then exactly the
 # sources default_source_collectors() declares. Live reachability of the extras is NOT asserted here (offline test).
 from app.modules.m22_tools_hub.sources import default_source_collectors
 c=default_collectors();assert [x.name for x in c[:3]]==['github','pypi','npm']
 assert [x.name for x in c[3:]]==[x.name for x in default_source_collectors()]
 assert all((getattr(x,'url',None) or x.url_template).startswith('https://') for x in c)
