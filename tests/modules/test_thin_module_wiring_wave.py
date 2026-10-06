from app.modules.m17_narrative_architect.wiring import build_narrative_collectors
from app.modules.m22_tools_hub.collectors import default_collectors
def test_m17_default_and_optional_legal_sources():
 assert 'reddit' in build_narrative_collectors({})
 configured=build_narrative_collectors({'ATLAS_YOUTUBE_API_KEY':'y','ATLAS_PINTEREST_ACCESS_TOKEN':'p','ATLAS_M18_PUBLIC_URLS':'https://example.com'})
 assert {'reddit','youtube','pinterest','public_web'} <= set(configured)
def test_m22_ships_free_official_discovery_sources():
 c=default_collectors();names=[x.name for x in c]
 assert names[:3]==['github','pypi','npm']
 assert len(names)==len(set(names))
 from app.modules.m22_tools_hub.sources import default_source_collectors
 assert names[3:]==[x.name for x in default_source_collectors()]
 assert all(x.url.startswith('https://') for x in c[:3])
