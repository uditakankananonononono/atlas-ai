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


def test_tool_history_reports_manual_prior_not_connected_runtime_history():
 import pytest
 from app.modules.m20_general_cognitive_worker.tool_selection import ToolSelector
 from app.modules.m20_general_cognitive_worker.tools import ToolRegistry
 from app.modules.m20_general_cognitive_worker.schemas import ToolSpec
 registry=ToolRegistry()
 async def fixture(args):return {}
 registry.register(ToolSpec(name='read',description='read fixture'),fixture)
 selector=ToolSelector(registry)
 report=selector.select('read fixture').as_dict()
 assert report['runtime_dispatch_history_connected'] is False
 assert report['candidates'][0]['historical_success']==.5
 assert report['candidates'][0]['supplied_successes']==0
 selector.record_outcome('read',False)
 candidate=selector.select('read fixture').as_dict()['candidates'][0]
 assert candidate['supplied_failures']==1 and candidate['historical_success']==.3333
 with pytest.raises(ValueError):selector.record_outcome('read','false')
