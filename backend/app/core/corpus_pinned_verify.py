"""Offline pinned CC0 SQLite/export/archive consistency attestation.

Fixed publisher hashes anchor retained bytes. No live retrieval, rights
warranty, training verification, hostile-mutation or writer lease claim.
"""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from .corpus_pinned_prompts import REVISION,verify_snapshot

def attest(db_path,export_path):
    db_path=Path(db_path).resolve();export=Path(export_path)
    count=verify_snapshot(export)
    manifest=json.loads(export.with_suffix(export.suffix+'.manifest.json').read_text())
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db,export.open() as stream:
        db.execute('BEGIN')
        records=db.execute('SELECT revision,manifest_json FROM pinned_manifest').fetchall()
        if len(records)!=1 or records[0][0]!=REVISION or json.loads(records[0][1])!=manifest:raise ValueError('stored manifest identity mismatch')
        total=0
        for revision,ordinal,text,digest,source in db.execute('SELECT revision,ordinal,text,sha256,source FROM pinned_rows ORDER BY ordinal'):
            line=stream.readline()
            if not line:raise ValueError('database has extra row')
            row=json.loads(line)
            if (revision,ordinal,text,digest,source)!=(REVISION,total,row['text'],row['sha256'],row['source']):raise ValueError('database/export mismatch')
            if hashlib.sha256(text.encode()).hexdigest()!=digest:raise ValueError('stored text checksum mismatch')
            total+=1
        if stream.readline() or total!=count:raise ValueError('row count mismatch')
    digest=hashlib.sha256()
    with db_path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''):digest.update(chunk)
    return {'status':'verified','rows_verified':total,'publisher_revision':REVISION,
            'database_sha256':digest.hexdigest(),'export_sha256':manifest['export_sha256'],
            'network_requests':0,'training_verified':False,'rights_warranty':False,
            'consistency_only':True}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',required=True);p.add_argument('--export',required=True);a=p.parse_args(argv)
    print(json.dumps(attest(a.db,a.export),indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
