"""Manifest-locked bounded CC0 fixture relocation, no extractall or overwrite.

Manifest is trusted input, not publisher attestation. Only allowlisted CC0
review roots accepted. No symlinks/devices/traversal. Cooperative parent
assumed; no hostile-directory or power-loss atomicity guarantee.
"""
import argparse,hashlib,json,os,re,shutil,tarfile,tempfile
from pathlib import Path,PurePosixPath
ROOTS={'cc0-review','archive-review','archive-store-review'}

def _path(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] not in ROOTS or '\\' in name:raise ValueError('unsafe or non-CC0 fixture path')
    return p

def extract_checked(archive,manifest,destination,*,max_total_bytes=32_000_000,max_file_bytes=8_000_000,max_files=100):
    for limit in (max_total_bytes,max_file_bytes,max_files):
        if type(limit) is not int or limit<=0:raise ValueError('positive integer caps required')
    out=Path(destination)
    if out.exists() or out.is_symlink():raise FileExistsError('new destination required')
    records=json.loads(Path(manifest).read_text());expected={};total=0
    if not isinstance(records,list) or not records or len(records)>max_files:raise ValueError('manifest count cap')
    for row in records:
        if not isinstance(row,dict) or set(row)!={'path','bytes','sha256'} or not isinstance(row['path'],str):raise ValueError('invalid manifest row shape')
        name=str(_path(row['path']))
        if name in expected or type(row['bytes']) is not int or not 0<=row['bytes']<=max_file_bytes or not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('invalid manifest record')
        expected[name]=row;total+=row['bytes']
    if total>max_total_bytes:raise ValueError('manifest total cap')
    out.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.fixture-stage-',dir=out.parent));seen=set();members=0
    try:
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar:
                members+=1
                if members>max_files*4:raise ValueError('archive member cap')
                if member.name in {'.','./'} and member.isdir():continue
                name=str(_path(member.name))
                if member.isdir():
                    if not any(n==name or n.startswith(name+'/') for n in expected):raise ValueError('unexpected directory')
                    continue
                if not member.isfile() or name not in expected or name in seen or member.size!=expected[name]['bytes']:raise ValueError('unexpected/duplicate/nonregular member')
                target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256();written=0
                source=tar.extractfile(member)
                with source,target.open('xb') as dest:
                    while True:
                        chunk=source.read(65536)
                        if not chunk:break
                        written+=len(chunk)
                        if written>expected[name]['bytes']:raise ValueError('member size overrun')
                        digest.update(chunk);dest.write(chunk)
                    dest.flush();os.fsync(dest.fileno())
                if written!=member.size or digest.hexdigest()!=expected[name]['sha256']:raise ValueError('member checksum mismatch')
                seen.add(name)
        if seen!=set(expected):raise ValueError('missing manifested files')
        if out.exists() or out.is_symlink():raise FileExistsError('destination changed')
        os.rename(stage,out)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {'status':'verified','files_verified':len(seen),'bytes_verified':total,'roots':sorted(ROOTS),'network_requests':0}

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--manifest',required=True);p.add_argument('--destination',required=True);a=p.parse_args(argv)
    print(json.dumps(extract_checked(a.archive,a.manifest,a.destination),indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
