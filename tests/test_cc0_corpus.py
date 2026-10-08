"""CC0 contract and actual public source evidence; no simulated ingestion."""
from pathlib import Path
import json,pytest
from app.core.public_corpus import collect
from app.core.corpus_verify import verify
from app.core.corpus_stream_verify import verify as stream_verify

def test_cc0_fixed_source_contract():
 from app.core.public_corpus import source_spec
 dataset,card,config,field,license_note=source_spec('cc0-prompts')
 assert dataset=='fka/prompts.chat' and config=='default' and field=='prompt'
 assert card=='https://huggingface.co/datasets/fka/prompts.chat'
 assert license_note=='CC0-1.0 https://creativecommons.org/publicdomain/zero/1.0/'

def test_actual_cc0_corpus_and_license():
 p=Path('/tmp/cc0-review/live.jsonl')
 if not p.exists():pytest.skip('requires real CC0 public collector run')
 report=verify(p.with_name('live.sqlite'),p);assert report['stored_rows_verified']>=100
 assert report['stored_rows_verified']==len(p.read_text().splitlines())
 assert stream_verify(p.with_name('live.sqlite'),p)['export_sha256']==report['export_sha256']
 manifest=json.loads(p.with_suffix('.jsonl.manifest.json').read_text())
 assert manifest['dataset']=='fka/prompts.chat' and manifest['license_url']=='https://creativecommons.org/publicdomain/zero/1.0/'
 for line in p.read_text().splitlines():
  row=json.loads(line);assert row['license']=='CC0-1.0 https://creativecommons.org/publicdomain/zero/1.0/'
def test_existing_ordinal_conflict_refuses_page_and_keeps_cursor(tmp_path,monkeypatch):
 import sqlite3,hashlib,httpx
 import app.core.public_corpus as module
 real=httpx.Client;db=tmp_path/'corpus.sqlite';out=tmp_path/'out.jsonl'
 # Conflicting existing ordinal with cursor at zero models interrupted or
 # noncooperating-writer state. Real DB, injected page only for kill test.
 with sqlite3.connect(db) as conn:
  conn.executescript('CREATE TABLE rows(selection TEXT,ordinal INTEGER,text TEXT,sha256 TEXT,source TEXT,fetched_at TEXT,PRIMARY KEY(selection,ordinal));CREATE TABLE cursors(selection TEXT PRIMARY KEY,next_offset INTEGER)')
  conn.execute('INSERT INTO rows VALUES (?,?,?,?,?,?)',('cc0-prompts/train',0,'old text',hashlib.sha256(b'old text').hexdigest(),'old source','old timestamp'))
  conn.execute('INSERT INTO cursors VALUES (?,?)',('cc0-prompts/train',0))
 def handle(request):return httpx.Response(200,json={'rows':[{'row_idx':0,'row':{'prompt':'new conflicting text'},'truncated_cells':[]}],'num_rows_total':1,'partial':False},request=request)
 monkeypatch.setattr(module.httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handle),**kwargs))
 with pytest.raises(ValueError,match='ordinal conflict'):module.collect(db,out,config='cc0-prompts',max_rows=1)
 with sqlite3.connect(db) as conn:
  assert conn.execute('SELECT text FROM rows').fetchone()[0]=='old text'
  assert conn.execute('SELECT next_offset FROM cursors').fetchone()[0]==0
 assert not out.exists()
def test_conflict_after_precheck_readback_refuses_and_rolls_page_back(tmp_path,monkeypatch):
 import sqlite3,hashlib,httpx
 import app.core.public_corpus as module
 real_client=httpx.Client;real_connect=sqlite3.connect;fired=[]
 class BarrierConnection(sqlite3.Connection):
  def execute(self,sql,parameters=()):
   if sql.startswith('INSERT OR IGNORE INTO rows') and not fired:
    fired.append(True)
    super().execute('INSERT INTO rows VALUES (?,?,?,?,?,?)',(parameters[0],parameters[1],'competing text',hashlib.sha256(b'competing text').hexdigest(),'competing source','barrier'))
   return super().execute(sql,parameters)
 monkeypatch.setattr(module.sqlite3,'connect',lambda *args,**kwargs:real_connect(*args,**kwargs,factory=BarrierConnection))
 def handle(request):return httpx.Response(200,json={'rows':[{'row_idx':0,'row':{'prompt':'incoming text'},'truncated_cells':[]}],'num_rows_total':1,'partial':False},request=request)
 monkeypatch.setattr(module.httpx,'Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handle),**kwargs))
 db=tmp_path/'corpus.sqlite';out=tmp_path/'out.jsonl'
 with pytest.raises(ValueError,match='ordinal conflict'):module.collect(db,out,config='cc0-prompts',max_rows=1)
 with real_connect(db) as conn:
  assert conn.execute('SELECT count(*) FROM rows').fetchone()[0]==0
  assert conn.execute('SELECT count(*) FROM cursors').fetchone()[0]==0
 assert fired==[True] and not out.exists()
