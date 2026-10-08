"""Actual pinned snapshot, corrupt artifact pins and transport fault injection."""
import json,shutil
from pathlib import Path
import pytest,httpx
import app.core.corpus_pinned_prompts as module
@pytest.fixture
def snapshot(tmp_path):
 p=Path('/tmp/archive-review/live.jsonl')
 if not p.exists():pytest.skip('real publisher snapshot required')
 out=tmp_path/'copy.jsonl'
 shutil.copyfile(p,out);shutil.copyfile(p.with_suffix('.jsonl.manifest.json'),out.with_suffix('.jsonl.manifest.json'))
 shutil.copytree(Path(str(p)+'.source'),Path(str(out)+'.source'))
 m=json.loads(out.with_suffix('.jsonl.manifest.json').read_text());m['source_archive']=out.name+'.source';out.with_suffix('.jsonl.manifest.json').write_text(json.dumps(m));return out
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
def test_csv_closed_on_parse_failure(tmp_path,monkeypatch):
 import hashlib
 real_client=httpx.Client;real_open=Path.open;opened=[]
 card=b'---\nlicense: cc0-1.0\n---\n';csv=b'act,prompt\nx,\n'
 monkeypatch.setattr(module,'sleep',lambda seconds:None)
 monkeypatch.setattr(module,'EXPECTED_HASHES',{'README.md':hashlib.sha256(card).hexdigest(),'prompts.csv':hashlib.sha256(csv).hexdigest()})
 def handle(request):return httpx.Response(200,content=card if 'README.md' in str(request.url) else csv,request=request)
 monkeypatch.setattr(module.httpx,'Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handle),**kwargs))
 def track(path,*args,**kwargs):
  stream=real_open(path,*args,**kwargs)
  if path.name=='prompts.csv' and kwargs.get('encoding')=='utf-8-sig':opened.append(stream)
  return stream
 monkeypatch.setattr(Path,'open',track)
 with pytest.raises(ValueError,match='empty publisher prompt'):module.download(tmp_path/'out')
 assert opened and all(stream.closed for stream in opened)
 assert not (tmp_path/'out').exists()
def test_coordinated_export_rehash_cannot_claim_publisher_text(snapshot):
 import hashlib
 lines=snapshot.read_text().splitlines();row=json.loads(lines[0]);row['text']='invented text absent from publisher';row['sha256']=hashlib.sha256(row['text'].encode()).hexdigest();lines[0]=json.dumps(row)
 snapshot.write_text('\n'.join(lines)+'\n')
 p=snapshot.with_suffix('.jsonl.manifest.json');m=json.loads(p.read_text());m['export_sha256']=hashlib.sha256(snapshot.read_bytes()).hexdigest();p.write_text(json.dumps(m))
 with pytest.raises(ValueError):module.verify_snapshot(snapshot)
