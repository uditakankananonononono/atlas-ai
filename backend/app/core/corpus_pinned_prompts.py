"""Fixed CC0 publisher snapshot. No stamping commits onto mutable API rows."""
import argparse,csv,hashlib,io,json,re,tempfile,os
from pathlib import Path
import httpx
from urllib.parse import urljoin,urlsplit
DATASET='fka/prompts.chat'
REVISION='fbea17f2045d053d27f1de9f099e9bfdbe55bf47'
EXPECTED_HASHES={'README.md':'5e8b91b0c80be0af464727e1aca8eabb1dc63a1545dc03f36b9f94ef4d96f145','prompts.csv':'c506bbf29106058a021e5cf85271bb97c9856c2b7fcc9f337421cdc8b00964c6'}
API='https://huggingface.co/api/datasets/fka/prompts.chat'
LICENSE='https://creativecommons.org/publicdomain/zero/1.0/'
def download(output,max_rows=100):
 if isinstance(max_rows,bool) or not isinstance(max_rows,int) or not 1<=max_rows<=1000:raise ValueError('bounded integer rows 1..1000')
 out=Path(output);manifest=out.with_suffix(out.suffix+'.manifest.json')
 if out.exists() or manifest.exists():raise FileExistsError('new artifacts required')
 urls={name:f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{name}' for name in ('README.md','prompts.csv')}
 blobs={}
 with httpx.Client(timeout=30,follow_redirects=False) as client:
  for name,url in urls.items():
   with client.stream('GET',url) as initial:
    status=initial.status_code;location=initial.headers.get('location','')
   if status in (301,302,303,307,308):
    target=urljoin(url,location)
    parsed_url=urlsplit(target)
    expected=f'/api/resolve-cache/datasets/{DATASET}/{REVISION}/{name}'
    if parsed_url.scheme!='https' or parsed_url.netloc!='huggingface.co' or parsed_url.path!=expected:raise ValueError('unapproved publisher redirect')
    url=target
   elif status!=200:raise ValueError('publisher file unavailable')
   with client.stream('GET',url) as response:
    response.raise_for_status()
    data=bytearray()
    for chunk in response.iter_bytes():
     data.extend(chunk)
     if len(data)>8_000_000:raise ValueError('publisher response exceeds bounded 8MB')
    blobs[name]=bytes(data)
 for name,data in blobs.items():
  if hashlib.sha256(data).hexdigest()!=EXPECTED_HASHES[name]:raise ValueError('publisher file checksum mismatch')
 card=blobs['README.md'].decode()
 if not re.search(r'^license:\s*cc0-1.0\s*$',card,re.M):raise ValueError('pinned publisher card does not identify CC0')
 parsed=csv.DictReader(io.StringIO(blobs['prompts.csv'].decode('utf-8-sig')))
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
  record={'dataset':DATASET,'publisher_revision':REVISION,'revision_discovery_api':API,'license':'CC0-1.0','license_url':LICENSE,'rows_exported':rows,'requested_max_rows':max_rows,'source_urls':urls,'publisher_file_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()},'publisher_bytes_downloaded':sum(len(v) for v in blobs.values()),'export_sha256':hashlib.sha256(stage.read_bytes()).hexdigest(),'training_performed':False}
  stage_manifest=Path(directory)/'manifest.json';stage_manifest.write_text(json.dumps(record,indent=2)+'\n')
  os.link(stage,out)
  try:os.link(stage_manifest,manifest)
  except Exception:out.unlink();raise
 return record
def verify_snapshot(path):
 path=Path(path);m=json.loads(path.with_suffix(path.suffix+'.manifest.json').read_text())
 if m['publisher_revision']!=REVISION:raise ValueError('wrong publisher commit')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=m['export_sha256']:raise ValueError('export checksum mismatch')
 rows=0
 for line in path.read_text().splitlines():
  r=json.loads(line)
  if r['publisher_revision']!=REVISION or r['source']!=f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/prompts.csv':raise ValueError('row commit/source mismatch')
  if r['sha256']!=hashlib.sha256(r['text'].encode()).hexdigest():raise ValueError('text checksum mismatch')
  if r['row_index']!=rows:raise ValueError('ordinal mismatch')
  rows+=1
 if rows!=m['rows_exported']:raise ValueError('row count mismatch')
 return rows
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--export',required=True);parser.add_argument('--max-rows',type=int,default=100);args=parser.parse_args();print(json.dumps(download(args.export,args.max_rows),indent=2))
