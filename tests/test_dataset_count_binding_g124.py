from app.modules.instinct_doc.dataset_register_p254 import create_register,add_entry,bind_artifacts
import pytest


def run(tmp_path,data,fmt,declared=1,reader=True):
 (tmp_path/'data').write_bytes(data)
 r=add_entry(create_register(),dict(id='a',project_id='p',dataset='d',records=declared,source='observed',source_ref='ref'))
 b={'entry_id':'a','artifact_path':'data','row_ids':[],'project_ids':[]}
 if fmt is not None:b['format']=fmt
 return bind_artifacts(r,tmp_path,[b],source_reader=(lambda *a:data) if reader else None)['entries'][0]


@pytest.mark.parametrize('data,fmt,count',[(b'a\n1\n','csv',1),(b'{"a":1}\n','jsonl',1),(b'[1,2]','json',2)])
def test_count_match_requires_actual_parser(tmp_path,data,fmt,count):
 r=run(tmp_path,data,fmt,count)
 assert r['counted_records']==count and r['record_count_status']=='COUNT_MATCH'
 assert r['provenance']=='VERIFIED' and r['source_bytes_match'] is True


def test_equal_bytes_wrong_count_is_unverified(tmp_path):
 r=run(tmp_path,b'a\n1\n','csv',999)
 assert r['source_bytes_match'] is True
 assert r['provenance']=='UNVERIFIED' and r['record_count_status']=='COUNT_MISMATCH'
 assert r['counted_records']==1


@pytest.mark.parametrize('data,fmt',[(b'x','parquet'),(b'[NaN]','json'),(b'bad','jsonl'),(b'', 'csv'),(b'a\n1\n',None)])
def test_unsupported_malformed_or_missing_format_unverified(tmp_path,data,fmt):
 r=run(tmp_path,data,fmt)
 assert r['provenance']=='UNVERIFIED'
 assert r['counted_records'] is None


def test_local_count_without_source_not_source_verified(tmp_path):
 r=run(tmp_path,b'a\n1\n','csv',reader=False)
 assert r['record_count_status']=='COUNT_MATCH'
 assert r['provenance']=='DECLARED-ONLY' and not r['source_checked']


def test_count_match_does_not_upgrade_source_mismatch(tmp_path):
 data=b'a\n1\n';(tmp_path/'data').write_bytes(data)
 r=add_entry(create_register(),dict(id='a',project_id='p',dataset='d',records=1,source='source',source_ref='ref'))
 b={'entry_id':'a','artifact_path':'data','row_ids':[],'project_ids':[],'format':'csv'}
 row=bind_artifacts(r,tmp_path,[b],source_reader=lambda *a:b'a\n2\n')['entries'][0]
 assert row['record_count_status']=='COUNT_MATCH' and row['provenance']=='UNVERIFIED'
 assert row['source_bytes_match'] is False


def test_oversized_artifact_never_count_verified(tmp_path):
 row=run(tmp_path,b'x'*8_000_001,'csv',1)
 assert row['provenance']=='UNVERIFIED' and row['counted_records'] is None


def test_declared_only_supported_count_and_matching_source_aggregation(tmp_path):
 from app.modules.instinct_doc.dataset_register_p254 import bind_artifacts
 (tmp_path/'data').write_bytes(b'a\n1\n')
 reg=create_register();bindings=[]
 for ident,n,fmt in [('ok',1,'csv'),('wrong',999,'csv'),('legacy',1,None)]:
  reg=add_entry(reg,dict(id=ident,project_id='p',dataset='d',records=n,source='s',source_ref='ref'))
  b={'entry_id':ident,'artifact_path':'data','row_ids':[],'project_ids':[]}
  if fmt:b['format']=fmt
  bindings.append(b)
 result=bind_artifacts(reg,tmp_path,bindings,source_reader=lambda *a:b'a\n1\n')
 assert result['counts']=={'VERIFIED':1,'DECLARED-ONLY':0,'UNVERIFIED':2}


def test_json_object_is_not_array_count(tmp_path):
 row=run(tmp_path,b'{"one":1}','json',1)
 assert row['provenance']=='UNVERIFIED' and row['counted_records'] is None


def test_sparse_oversize_file_refused_before_read(tmp_path,monkeypatch):
 from pathlib import Path
 from app.modules.instinct_doc import repo_evidence
 sparse=tmp_path/'data'
 with sparse.open('wb') as handle:handle.truncate(8_000_001)
 reg=add_entry(create_register(),dict(id='a',project_id='p',dataset='d',records=1,source='s',source_ref='r'))
 binding={'entry_id':'a','artifact_path':'data','row_ids':[],'project_ids':[],'format':'csv'}
 # Exercise this API's own cap even if safe_file's independent stat gate changes.
 monkeypatch.setattr(repo_evidence,'safe_file',lambda *a:sparse)
 original_open=Path.open;opened=[]
 def guard_open(path,*a,**kw):
  if path==sparse:
   opened.append(True)
   raise AssertionError('oversized artifact must not be opened')
  return original_open(path,*a,**kw)
 monkeypatch.setattr(Path,'open',guard_open)
 row=bind_artifacts(reg,tmp_path,[binding])['entries'][0]
 assert row['provenance']=='UNVERIFIED' and row['counted_records'] is None
 assert row['artifact_sha256'] is None
 assert opened==[]


def test_local_read_is_bounded_even_when_file_grows_after_stat(tmp_path,monkeypatch):
 import io
 from app.modules.instinct_doc import repo_evidence
 requests=[]
 class Handle(io.BytesIO):
  def read(self,n=-1):requests.append(n);return super().read(n)
 class RacingArtifact:
  def stat(self):
   class Stat:st_size=5
   return Stat()
  def open(self,mode):return Handle(b'x'*8_000_002)
  def read_bytes(self):requests.append(-1);return b'x'*8_000_002
 monkeypatch.setattr(repo_evidence,'safe_file',lambda *a:RacingArtifact())
 reg=add_entry(create_register(),dict(id='a',project_id='p',dataset='d',records=1,source='s',source_ref='r'))
 row=bind_artifacts(reg,tmp_path,[{'entry_id':'a','artifact_path':'data','row_ids':[],'project_ids':[],'format':'csv'}])['entries'][0]
 assert requests==[8_000_001]
 assert row['provenance']=='UNVERIFIED' and row['counted_records'] is None
