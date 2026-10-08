"""Fixed CC0 publisher snapshot. No stamping commits onto mutable API rows."""
import argparse,csv,hashlib,io,json,re,tempfile,os,shutil
from pathlib import Path
from contextlib import ExitStack
from time import monotonic,sleep
import httpx
from urllib.parse import urljoin,urlsplit
DATASET='fka/prompts.chat'
REVISION='fbea17f2045d053d27f1de9f099e9bfdbe55bf47'
EXPECTED_HASHES={'README.md':'5e8b91b0c80be0af464727e1aca8eabb1dc63a1545dc03f36b9f94ef4d96f145','prompts.csv':'c506bbf29106058a021e5cf85271bb97c9856c2b7fcc9f337421cdc8b00964c6'}
API='https://huggingface.co/api/datasets/fka/prompts.chat'
LICENSE='https://creativecommons.org/publicdomain/zero/1.0/'
def download(output,max_rows=100):
 with tempfile.TemporaryDirectory(prefix='pinned-source-') as source_dir,ExitStack() as stack:
  return _download(output,max_rows,Path(source_dir),stack)

def stream_capped(response,path,cap=8_000_000):
 digest=hashlib.sha256();total=0
 with Path(path).open('wb') as stream:
  for chunk in response.iter_bytes(chunk_size=65536):
   if total+len(chunk)>cap:raise ValueError('publisher response exceeds file cap')
   stream.write(chunk);digest.update(chunk);total+=len(chunk)
 return total,digest.hexdigest()

def _download(output,max_rows,source_dir,stack):
 if isinstance(max_rows,bool) or not isinstance(max_rows,int) or not 1<=max_rows<=1000:raise ValueError('bounded integer rows 1..1000')
 out=Path(output);manifest=out.with_suffix(out.suffix+'.manifest.json')
 archive=Path(str(out)+'.source')
 if out.exists() or manifest.exists() or archive.exists():raise FileExistsError('new artifacts required')
 urls={name:f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{name}' for name in ('README.md','prompts.csv')}
 files={};hashes={};sizes={};last_request=None
 def pace():
  nonlocal last_request
  if last_request is not None:sleep(max(0.0,3-(monotonic()-last_request)))
  last_request=monotonic()
 with httpx.Client(timeout=30,follow_redirects=False) as client:
  for name,url in urls.items():
   pace()
   with client.stream('GET',url) as initial:
    status=initial.status_code;location=initial.headers.get('location','')
   if status in (301,302,303,307,308):
    target=urljoin(url,location)
    parsed_url=urlsplit(target)
    expected=f'/api/resolve-cache/datasets/{DATASET}/{REVISION}/{name}'
    if parsed_url.scheme!='https' or parsed_url.netloc!='huggingface.co' or parsed_url.path!=expected:raise ValueError('unapproved publisher redirect')
    url=target
   elif status!=200:raise ValueError('publisher file unavailable')
   pace()
   with client.stream('GET',url) as response:
    response.raise_for_status()
    path=source_dir/name
    sizes[name],hashes[name]=stream_capped(response,path,65536 if name=='README.md' else 8_000_000)
    files[name]=path
 for name,digest in hashes.items():
  if digest!=EXPECTED_HASHES[name]:raise ValueError('publisher file checksum mismatch')
 card=files['README.md'].read_text()
 if not re.search(r'^license:\s*cc0-1.0\s*$',card,re.M):raise ValueError('pinned publisher card does not identify CC0')
 csv_stream=stack.enter_context(files['prompts.csv'].open(encoding='utf-8-sig',newline=''))
 parsed=csv.DictReader(csv_stream)
 if not parsed.fieldnames or 'prompt' not in parsed.fieldnames:raise ValueError('publisher schema lacks prompt')
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.pinned-prompts-',dir=out.parent) as directory:
  stage=Path(directory)/'rows.jsonl';rows=0
  with stage.open('w',encoding='utf-8') as stream:
   for ordinal,row in enumerate(parsed):
    if rows>=max_rows:break
    text=row['prompt']
    if not text:raise ValueError('empty publisher prompt')
    stream.write(json.dumps({'text':text,'row_index':ordinal,'source':urls['prompts.csv'],'publisher_revision':REVISION,'license':'CC0-1.0','license_url':LICENSE,'act':row.get('act'),'contributor':row.get('contributor'),'sha256':hashlib.sha256(text.encode()).hexdigest()},ensure_ascii=False)+'\n');rows+=1
  record={'dataset':DATASET,'publisher_revision':REVISION,'revision_discovery_api':API,'license':'CC0-1.0','license_url':LICENSE,'rows_exported':rows,'requested_max_rows':max_rows,'source_urls':urls,'publisher_file_sha256':hashes,'publisher_bytes_downloaded':sum(sizes.values()),'source_file_caps_bytes':{'README.md':65536,'prompts.csv':8_000_000},'download_buffer_bytes':65536,'export_sha256':hashlib.sha256(stage.read_bytes()).hexdigest(),'training_performed':False,'request_min_interval_seconds':3}
  record['source_archive']=archive.name
  stage_archive=Path(directory)/'source';stage_archive.mkdir()
  for name,path in files.items():
   os.link(path,stage_archive/name)
  os.rename(stage_archive,archive)
  linked=False
  try:
   stage_manifest=Path(directory)/'manifest.json';stage_manifest.write_text(json.dumps(record,indent=2)+'\n')
   os.link(stage,out);linked=True
   os.link(stage_manifest,manifest)
  except Exception:
   if linked:out.unlink()
   shutil.rmtree(archive)
   raise
 csv_stream.close()
 return record
def verify_snapshot(path):
 path=Path(path);m=json.loads(path.with_suffix(path.suffix+'.manifest.json').read_text())
 if m.get('training_performed') is not False:raise ValueError('training claim unsupported')
 if m['publisher_revision']!=REVISION:raise ValueError('wrong publisher commit')
 expected_urls={name:f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{name}' for name in EXPECTED_HASHES}
 if m['dataset']!=DATASET or m['publisher_file_sha256']!=EXPECTED_HASHES or m['source_urls']!=expected_urls or m['license_url']!=LICENSE or m['license']!='CC0-1.0':raise ValueError('manifest source/hash/license identity mismatch')
 archive=Path(str(path)+'.source')
 if m.get('source_archive')!=archive.name:raise ValueError('source archive identity missing')
 for name,expected in EXPECTED_HASHES.items():
  h=hashlib.sha256()
  with (archive/name).open('rb') as original:
   for chunk in iter(lambda:original.read(65536),b''):h.update(chunk)
  if h.hexdigest()!=expected:raise ValueError('archived publisher bytes mismatch')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=m['export_sha256']:raise ValueError('export checksum mismatch')
 rows=0
 with (archive/'prompts.csv').open(encoding='utf-8-sig',newline='') as original:
  publisher=csv.DictReader(original)
  for line in path.read_text().splitlines():
   r=json.loads(line)
   source_row=next(publisher,None)
   if source_row is None or r['text']!=source_row.get('prompt') or r.get('act')!=source_row.get('act') or r.get('contributor')!=source_row.get('contributor'):raise ValueError('export differs from archived publisher row')
   if r.get('license')!='CC0-1.0' or r.get('license_url')!=LICENSE:raise ValueError('row license identity mismatch')
   if r['publisher_revision']!=REVISION or r['source']!=f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/prompts.csv':raise ValueError('row commit/source mismatch')
   if r['sha256']!=hashlib.sha256(r['text'].encode()).hexdigest():raise ValueError('text checksum mismatch')
   if r['row_index']!=rows:raise ValueError('ordinal mismatch')
   rows+=1
 if rows!=m['rows_exported']:raise ValueError('row count mismatch')
 return rows
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--export',required=True);parser.add_argument('--max-rows',type=int,default=100);args=parser.parse_args();print(json.dumps(download(args.export,args.max_rows),indent=2))
