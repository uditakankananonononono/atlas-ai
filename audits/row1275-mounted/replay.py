"""Trusted local app-level arbitration route mutation probes; no external calls."""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
ROUTE='backend/app/modules/m20_general_cognitive_worker/arbitration_routes1275.py'
MOUNT='backend/app/modules/m20_general_cognitive_worker/routes.py'
TEST='tests/modules/test_m20_arbitration1275_mounted.py'
OPS=[('A1275-M1',MOUNT,'router.include_router(arbitration_router1275)',''),('A1275-M2',ROUTE,"if media!='application/json':","if False:"),('A1275-M3',ROUTE,'if len(body)+len(chunk)>MAX_BODY_BYTES:','if False:'),('A1275-M4',ROUTE,'if key in result:','if False:'),('A1275-M5',ROUTE,"def _reject_constant(value):raise ValueError('non-finite JSON number')",'def _reject_constant(value):return 0'),('A1275-M6',ROUTE,'HTTPException(422,str(exc))','HTTPException(400,str(exc))'),('A1275-M7',ROUTE,"'tenant_id':principal.tenant_id","'tenant_id':'wrong'"),('A1275-M8',ROUTE,"'actor_id':principal.actor_id","'actor_id':'wrong'")]
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    private=Path(tempfile.mkdtemp(prefix='arb1275-raw-'))
    cmd=[sys.executable,'-B','-m','pytest',TEST,'-q','-rf','--tb=short']
    def run(label):
        p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        raw=(p.stdout+p.stderr).encode();(private/(label+'.log')).write_bytes(raw)
        lines=[];changes=[]
        for n,l in enumerate(raw.decode().splitlines(keepends=True),1):
            clean=l.rstrip('\r\n').rstrip()+'\n'
            # Stable logical labels: private raw path remains only in private original.
            for prefix in [str(ROOT),str(Path(sys.executable).parent.parent),'../atlas-ai/.venv']:
                clean=clean.replace(prefix,'<private-workspace>')
            if clean!=l:changes.append(dict(line=n,operations=['whitespace/path-portable-normalization']))
            lines.append(clean)
        delivered=''.join(lines).encode();(OUT/(label+'.log')).write_bytes(delivered)
        text=raw.decode();failed=[l[7:].split(' - ')[0] for l in text.splitlines() if l.startswith('FAILED ')]
        return dict(rc=p.returncode,failed_ids=failed,caught=p.returncode==1 and bool(failed) and 'ERROR ' not in text,log=label+'.log',original_sha256=sha(raw),delivered_sha256=sha(delivered),normalized_lines=changes)
    files=[ROUTE,MOUNT,TEST,'backend/app/modules/m20_general_cognitive_worker/arbitration1275.py']
    r=dict(base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),file_sha256={p:sha((ROOT/p).read_bytes()) for p in files},command=['python',*cmd[1:]],normalization='Interpreter normalized to python, private workspace prefixes to logical label, trailing whitespace trimmed. Raw originals private; listed changed lines and raw/delivered hashes.',baseline=run('baseline'),mutants=[])
    assert r['baseline']['rc']==0
    for ident,file,old,new in OPS:
        path=ROOT/file;raw=path.read_bytes();src=raw.decode();assert src.count(old)==1
        changed=src.replace(old,new,1).encode()
        try:path.write_bytes(changed);item=run(ident)
        finally:path.write_bytes(raw)
        item.update(id=ident,target=file,old=old,new=new,before_sha256=sha(raw),mutant_sha256=sha(changed),restored_sha256=sha(path.read_bytes()))
        assert raw==path.read_bytes(),item;r['mutants'].append(item)
    r['restored_baseline']=run('restored-baseline');assert r['restored_baseline']['rc']==0
    (OUT/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');print('8caught; originals',private)
if __name__=='__main__':main()
