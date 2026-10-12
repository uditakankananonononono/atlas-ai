"""Mock pipeline metadata/refusal tests, not a new image inference run."""
import hashlib
from pathlib import Path
import sys
import types
from PIL import Image
import pytest
from app.modules.c32.product_images import LocalProductImages,ImageUnavailable

@pytest.fixture
def engine(tmp_path,monkeypatch):
    root=tmp_path/'model';root.mkdir();(root/'model_index.json').write_text('{}');(root/'weights').write_bytes(b'fixture weights')
    obj=LocalProductImages(root)
    class Generator:
        def __init__(self,device):pass
        def manual_seed(self,seed):return self
    monkeypatch.setitem(sys.modules,'torch',types.SimpleNamespace(Generator=Generator,float32='float32'))
    monkeypatch.setitem(sys.modules,'diffusers',types.SimpleNamespace(DiffusionPipeline=object))
    obj._pipeline=lambda **kw:types.SimpleNamespace(images=[Image.new('RGB',(kw['width'],kw['height']))],nsfw_content_detected=[False])
    return obj

def concept():return {'subject':'Perfume bottle','style':'soft-pastel','audience':'adults'}

def test_fake_pipeline_png_metadata_hash_and_honest_review(engine,tmp_path):
    c=concept()
    result=engine.generate(c,tmp_path/'fake.png',steps=1)
    assert result['sha256']==hashlib.sha256((tmp_path/'fake.png').read_bytes()).hexdigest()
    assert result['model_sha256']==engine.identity
    assert result['realism_validated'] is False and result['visual_review']=='required'
    with Image.open(tmp_path/'fake.png') as im:
        assert im.info['AI-generated']=='true' and im.info['Model-SHA256']==engine.identity

def test_model_drift_and_safety_refuse_before_write(engine,tmp_path):
    c=concept()
    engine._pipeline=lambda **kw:types.SimpleNamespace(images=[Image.new('RGB',(kw['width'],kw['height']))],nsfw_content_detected=[True])
    with pytest.raises(ImageUnavailable,match='safety'):engine.generate(c,tmp_path/'no.png',steps=1)
    assert not (tmp_path/'no.png').exists()
    (engine.root/'weights').write_bytes(b'changed')
    with pytest.raises(ImageUnavailable,match='identity'):engine.generate(c,tmp_path/'no.png',steps=1)
