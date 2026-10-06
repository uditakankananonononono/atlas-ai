from app.modules.m20_general_cognitive_worker.optimization_story_235_280 import execute,capabilities
P={'source':{'title':'fixture','url':'https://example.org'},'premise':'A supplied scene','scenes':[{'text':'Existing text','character':'A','goal':'read','location':'room','tension':1,'duration':1}]}


def test_every_story_branch_discloses_diagnostics_not_generation():
 for cap in capabilities():
  if cap['row_id']<260:continue
  r=execute(cap['key'],P)
  assert not r['evaluation']['algorithm_executed']
  assert not r['evaluation']['named_generation_capability_executed']
  assert r['evaluation']['diagnostics_executed']
  assert 'not executed' in r['boundary']
  assert 'confidence' not in r['result']['metrics']
  assert cap['execution_kind']=='supplied_text_diagnostics'


def test_storyboard_is_data_not_rendered_visual_asset():
 r=execute('visual_storyboarding',P)
 assert r['result']['shots'][0]['action']=='Existing text'
 assert 'no model-backed creative generation or rendered visual storyboard' in r['boundary']
