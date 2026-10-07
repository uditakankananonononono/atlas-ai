import pytest
from app.modules.m20_general_cognitive_worker import model_adapters as ma
from app.modules.m20_general_cognitive_worker.htn_planner import PlanError

@pytest.mark.parametrize('body',['{"a":1} trailing','{"a":NaN}','{"a":1,"a":2}','prose {"a":1}','[{"a":1}] []'])
def test_model_json_rejects_partial_duplicate_nonfinite_or_prose(body):
 with pytest.raises(ValueError):ma.extract_json(body)


def reply(monkeypatch,body):
 async def fake(prompt,model_name=None,*,private=False):
  assert private
  return 'local','fixture',body
 monkeypatch.setattr(ma.model_catalog,'generate_free_first',fake)

@pytest.mark.parametrize('body',['[{"title":"send","tool":"unregistered_send"}]','[1]','[]','[{"title":"x"}'+', {"title":"x"}'*8+']'])
def test_planner_rejects_unregistered_tools_or_bad_step_sets(monkeypatch,body):
 reply(monkeypatch,body)
 with pytest.raises(PlanError):ma.FreeFirstPlannerModel().decompose('goal')


def test_invalid_executive_output_not_relabelled_as_reasoning(monkeypatch):
 reply(monkeypatch,'I think it is fine')
 r=ma.FreeFirstExecutiveModel().complete('reflect',{})
 assert not r['available'] and 'invalid JSON' in r['error'] and 'text' not in r

@pytest.mark.parametrize('purpose,body',[
 ('reason','{"reason":"correct summary"}'),('reason','{"result":" "}'),('reason','{"result":12}'),
 ('reflect','{"reason":"empty fixture","fix":"check fixture","retry":false}'),
 ('reflect','{"cause":"timeout","fix":"retry","retry":"false"}'),
 ('reflect','{"cause":"","fix":"retry","retry":false}'),
 ('reflect','{"cause":"timeout","retry":false}'),
])
def test_executive_rejects_invalid_purpose_schema(monkeypatch,purpose,body):
 reply(monkeypatch,body)
 out=ma.FreeFirstExecutiveModel().complete(purpose,{})
 assert out['available'] is False and 'schema mismatch' in out['error']
 assert 'result' not in out and 'cause' not in out

@pytest.mark.parametrize('purpose,body',[('reason','{"result":"Three colors."}'),('reflect','{"cause":"timeout","fix":"retry","retry":false}')])
def test_executive_accepts_exact_purpose_schema(monkeypatch,purpose,body):
 reply(monkeypatch,body)
 out=ma.FreeFirstExecutiveModel().complete(purpose,{})
 assert out.get('available') is not False and out['route']=='local/fixture'


@pytest.mark.parametrize("body", ['{"value":1e999}', '[{"arguments":{"value":-1e999}}]'])
def test_model_json_numeric_overflow_is_rejected(body):
    with pytest.raises(ValueError):
        ma.extract_json(body)
