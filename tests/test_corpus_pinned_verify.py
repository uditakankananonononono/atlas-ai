from pathlib import Path
import shutil,sqlite3,json,pytest

def fixture(tmp_path):
 root=Path('/tmp/archive-store-review');db=tmp_path/'live.sqlite';out=tmp_path/'live.jsonl'
 assert root.joinpath('live.sqlite').is_file(),'real CC0 fixture required'
 for name in ('live.sqlite','live.jsonl','live.jsonl.manifest.json'):shutil.copyfile(root/name,tmp_path/name)
 shutil.copytree(root/'live.jsonl.source',tmp_path/'live.jsonl.source')
 return db,out

def test_real_offline_attestation_and_db_tamper(tmp_path):
 from app.core.corpus_pinned_verify import attest
 db,out=fixture(tmp_path);report=attest(db,out)
 assert report['rows_verified']==100 and report['network_requests']==0 and report['training_verified'] is False
 with sqlite3.connect(db) as conn:conn.execute("UPDATE pinned_rows SET text='corrupt' WHERE ordinal=0")
 with pytest.raises(ValueError):attest(db,out)

def test_stored_manifest_revision_and_export_tamper(tmp_path):
 from app.core.corpus_pinned_verify import attest
 db,out=fixture(tmp_path)
 with sqlite3.connect(db) as conn:
  raw=json.loads(conn.execute('SELECT manifest_json FROM pinned_manifest').fetchone()[0]);raw['publisher_revision']='forged';conn.execute('UPDATE pinned_manifest SET manifest_json=?',(json.dumps(raw),))
 with pytest.raises(ValueError):attest(db,out)

def test_cli_real_receipt(tmp_path):
 from app.core.corpus_pinned_verify import main
 db,out=fixture(tmp_path)
 assert main(['--db',str(db),'--export',str(out)])==0
