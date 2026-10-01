from app.modules.m17_narrative_architect.wiring import build_narrative_collectors
from app.modules.m22_tools_hub.collectors import default_collectors
def test_m17_default_and_optional_legal_sources():
 assert 'reddit' in build_narrative_collectors({})
 configured=build_narrative_collectors({'ATLAS_YOUTUBE_API_KEY':'y','ATLAS_PINTEREST_ACCESS_TOKEN':'p','ATLAS_M18_PUBLIC_URLS':'https://example.com'})
 assert {'reddit','youtube','pinterest','public_web'} <= set(configured)
def test_m22_ships_free_official_discovery_sources():
 c=default_collectors(); names=[x.name for x in c]
 assert names == ['github','pypi','npm','devto','wordpress','hackernews','medium','itunes','itunes-episodes','gitlab','codeberg']
 assert len(names) == len(set(names))
 assert {x.kind for x in c} == {'repository','package','blog','article','podcast','podcast-episode'}
 assert all(getattr(x, 'url', getattr(x, 'url_template', '')).startswith('https://') for x in c)
