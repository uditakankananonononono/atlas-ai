"""Static integration references, not authenticated external use."""
import pytest
from test_integration_evidence_binding import setup
from app.modules.instinct_doc.integrations_register_p255 import bind_local_evidence

@pytest.mark.parametrize('case',['count','length','duplicates'])
def test_integration_reference_edges_refused(tmp_path,case):
    register,binding=setup(tmp_path)
    binding['row_ids']={'count':['row'+str(i) for i in range(1001)],'length':['x'*129],'duplicates':['row','row']}[case]
    with pytest.raises(ValueError):bind_local_evidence(register,tmp_path,[binding])
