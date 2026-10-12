"""Dataset byte-reader and reference boundary sensitivity, controlled inputs."""
import pytest
from test_dataset_artifact_binding import setup
from app.modules.instinct_doc.dataset_register_p254 import bind_artifacts

@pytest.mark.parametrize('case',['count','length','duplicates'])
def test_dataset_reference_edges_refused(tmp_path,case):
    register,binding=setup(tmp_path)
    binding['row_ids']={'count':['row'+str(i) for i in range(1001)],'length':['x'*129],'duplicates':['row','row']}[case]
    with pytest.raises(ValueError):bind_artifacts(register,tmp_path,[binding])

def test_dataset_reader_exact_size_cap_not_counted_as_checked(tmp_path):
    register,binding=setup(tmp_path)
    row=bind_artifacts(register,tmp_path,[binding],source_reader=lambda *a:b'x'*8_000_001)['entries'][0]
    assert row['provenance']=='UNVERIFIED'
    assert row['source_checked'] is False
    assert row['source_sha256'] is None
