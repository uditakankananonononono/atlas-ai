from app.modules.m20_general_cognitive_worker.tool_selection import ToolSelector
from app.modules.m20_general_cognitive_worker.tools import ToolRegistry
from app.modules.m20_general_cognitive_worker.schemas import ToolSpec,Risk

class ExactEmbedding:
 dimensions=2
 def embed(self,text):return [1.,0.] if 'search' in text else [0.,1.]
async def handler(args):return {}


def test_single_unrelated_tool_cannot_win_by_prior_and_no_competition():
 registry=ToolRegistry();registry.register(ToolSpec(name='web_search',description='search documents',risk=Risk.READ,capabilities=['search']),handler)
 selector=ToolSelector(registry,embedder=ExactEmbedding())
 r=selector.select('cook dinner')
 assert r.chosen is None and r.needs_clarification and r.margin==0
 assert r.candidates[0].historical_success==.5
 assert r.as_dict()['margin_is_not_probability']


def test_relevance_not_historical_success_alone_permits_selection():
 registry=ToolRegistry();registry.register(ToolSpec(name='web_search',description='search documents',risk=Risk.READ,capabilities=['search']),handler)
 selector=ToolSelector(registry,embedder=ExactEmbedding())
 for i in range(100):selector.record_outcome('web_search',True)
 assert selector.select('cook dinner').chosen is None
 assert selector.select('search documents').chosen.tool_name=='web_search'
