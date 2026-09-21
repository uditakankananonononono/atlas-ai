import io,json,zipfile
from app.modules.m04_research_scientist.reproducibility_bundle import build_bundle
def test_bundle_is_content_addressed_complete_and_truthful():
 blob,m=build_bundle(title='Cell model',code='print(1)',language='python',inputs={'counts':[1,2]},parameters={'alpha':.05},seed=7,expected_outputs=['result.csv'],dependencies=['numpy'],source_urls=['https://doi.org/x'])
 assert m['execution_performed'] is False and m['input_hashes']['counts'].startswith('sha256:') and m['bundle_sha256'].startswith('sha256:')
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  assert set(z.namelist())=={'manifest.json','analysis.py','parameters.json','inputs.json','README.md'}
  assert json.loads(z.read('manifest.json'))['seed']==7
