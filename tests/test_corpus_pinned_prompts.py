"""Actual pinned snapshot, corrupt artifact pins and transport fault injection."""
import json,shutil
from pathlib import Path
import pytest,httpx
import app.core.corpus_pinned_prompts as module
@pytest.fixture
def snapshot(tmp_path):
 p=Path('/tmp/pinned-review/live.jsonl')
 if not p.exists():pytest.skip('real publisher snapshot required')
 out=tmp_path/'copy.jsonl'
 shutil.copyfile(p,out);shutil.copyfile(p.with_suffix('.jsonl.manifest.json'),out.with_suffix('.jsonl.manifest.json'));return out
def test_actual_pinned_snapshot(snapshot):assert module.verify_snapshot(snapshot)==100
@pytest.mark.parametrize('fault',['hash','commit'])
def test_actual_tamper_refused(snapshot,fault):
 p=snapshot.with_suffix('.jsonl.manifest.json');m=json.loads(p.read_text());m['export_sha256' if fault=='hash' else 'publisher_revision']='0'*40;p.write_text(json.dumps(m))
 with pytest.raises(ValueError):module.verify_snapshot(snapshot)
@pytest.mark.parametrize('fault',['oversized','wrong_commit_redirect','wrong_hash'])
def test_transport_tamper_refused_without_output(tmp_path,monkeypatch,fault):
 real=httpx.Client
 def handle(request):
  if fault=='wrong_commit_redirect':return httpx.Response(307,headers={'location':'/api/resolve-cache/datasets/fka/prompts.chat/'+'0'*40+'/README.md'},request=request)
  return httpx.Response(200,content=(b'x'*8_000_001 if fault=='oversized' else b'wrong hash'),request=request)
 monkeypatch.setattr(module.httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
 with pytest.raises(ValueError):module.download(tmp_path/'out.jsonl')
 assert list(tmp_path.iterdir())==[]
def test_request_starts_paced_on_pinned_fetch(tmp_path,monkeypatch):
 real=httpx.Client;clock=[0.0];starts=[]
 monkeypatch.setattr(module,'monotonic',lambda:clock[0],raising=False)
 monkeypatch.setattr(module,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds),raising=False)
 def handle(request):starts.append(clock[0]);return httpx.Response(200,content=b'incorrect fixed file hash',request=request)
 monkeypatch.setattr(module.httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
 with pytest.raises(ValueError):module.download(tmp_path/'out.jsonl')
 assert len(starts)>=2 and all(b-a>=3 for a,b in zip(starts,starts[1:]))
@pytest.mark.parametrize('fault',['publisher_hash','source_url','license_url'])
def test_actual_snapshot_manifest_identity_tamper(snapshot,fault):
 p=snapshot.with_suffix('.jsonl.manifest.json');m=json.loads(p.read_text())
 if fault=='publisher_hash':m['publisher_file_sha256']['prompts.csv']='0'*64
 elif fault=='source_url':m['source_urls']['prompts.csv']='https://example.invalid/file'
 else:m['license_url']='https://example.invalid/license'
 p.write_text(json.dumps(m))
 with pytest.raises(ValueError):module.verify_snapshot(snapshot)
def test_file_cap_never_writes_above_bound(tmp_path):
 path=tmp_path/'bounded'
 response=httpx.Response(200,content=b'x'*100000)
 total,sha=module.stream_capped(response,path,100000)
 assert total==path.stat().st_size==100000
 with pytest.raises(ValueError):module.stream_capped(response,path,1000)
 assert path.stat().st_size<=1000
