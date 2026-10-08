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
