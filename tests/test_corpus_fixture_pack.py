from pathlib import Path
import io,json,tarfile,pytest

def test_actual_cc0_relocation_and_attestation(tmp_path):
 from app.core.corpus_fixture_pack import extract_checked
 from app.core.corpus_pinned_verify import attest
 root=tmp_path/'relocated';r=extract_checked('/tmp/cc0-offline-pack/fixtures.tar.gz','/tmp/cc0-offline-pack/CONTENTS.json',root)
 assert r['status']=='verified' and r['files_verified']==len(json.loads(Path('/tmp/cc0-offline-pack/CONTENTS.json').read_text()))
 assert attest(root/'archive-store-review/live.sqlite',root/'archive-store-review/live.jsonl')['rows_verified']==100
 with pytest.raises(FileExistsError):extract_checked('/tmp/cc0-offline-pack/fixtures.tar.gz','/tmp/cc0-offline-pack/CONTENTS.json',root)

def test_traversal_symlink_and_corruption_refuse(tmp_path):
 from app.core.corpus_fixture_pack import extract_checked
 manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps([{'path':'cc0-review/x','bytes':1,'sha256':'0'*64}]))
 for kind in ['traversal','symlink','corrupt']:
  archive=tmp_path/(kind+'.tar.gz')
  with tarfile.open(archive,'w:gz') as t:
   i=tarfile.TarInfo('../outside' if kind=='traversal' else 'cc0-review/x')
   if kind=='symlink':i.type=tarfile.SYMTYPE;i.linkname='/etc/passwd';t.addfile(i)
   else:i.size=1;t.addfile(i,io.BytesIO(b'x'))
  out=tmp_path/kind
  with pytest.raises(ValueError):extract_checked(archive,manifest,out)
  assert not out.exists() and not (tmp_path/'outside').exists()

def test_manifest_rights_scope_and_limits(tmp_path):
 from app.core.corpus_fixture_pack import extract_checked
 manifest=tmp_path/'manifest.json';manifest.write_text('[{"path":"wikitext/x","bytes":1,"sha256":"'+'0'*64+'"}]')
 with pytest.raises(ValueError):extract_checked('/tmp/cc0-offline-pack/fixtures.tar.gz',manifest,tmp_path/'out')
 with pytest.raises(ValueError):extract_checked('/tmp/cc0-offline-pack/fixtures.tar.gz','/tmp/cc0-offline-pack/CONTENTS.json',tmp_path/'out',max_total_bytes=1)
 assert not (tmp_path/'out').exists()
