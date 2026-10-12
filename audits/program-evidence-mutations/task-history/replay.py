"""Task-history sensitivity replay, trusted checkout only. Not a sandbox.
rc1 plus FAILED is crash-inclusive; ERROR-space/ERROR-at and timeout uncredited.
Mixed FAILED+SKIP is not rejected. Private raw bytes are retained separately;
delivered formatting changes and per-file original/delivered SHA pairs recorded.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
CONFIG=OUT.parent/'task-history.json'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    config=json.loads(CONFIG.read_text());private=Path(tempfile.mkdtemp(prefix='task-history-raw-'))
    env=dict(os.environ,PYTHONPATH='backend',PYTHONDONTWRITEBYTECODE='1')
    command=[sys.executable,'-B','-m','pytest','--noconftest','-p','no:cacheprovider',*config['tests'],'-q','-rf','--tb=short']
    def invoke(label):
        p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=90)
        raw=(p.stdout+p.stderr).encode();(private/(label+'.log')).write_bytes(raw)
        changes=[];lines=[]
        for n,line in enumerate(raw.decode().splitlines(keepends=True),1):
            clean=line.rstrip('\r\n').rstrip()+'\n'
            paths=re.findall(r'/(?:home/sandbox|tmp|workspace)(?:/[^\s\"\'<>:]*)?',clean)
            for path in paths:clean=clean.replace(path,'<workspace-path>')
            if clean!=line:changes.append({'line':n,'trailing_whitespace_removed':line.rstrip('\r\n')!=line.rstrip('\r\n').rstrip(),'path_pairs':[{'original':path,'delivered':'<workspace-path>'} for path in paths]})
            lines.append(clean)
        data=''.join(lines).encode();(OUT/(label+'.log')).write_bytes(data)
        text=raw.decode();failed=[l[7:].split(' - ')[0] for l in text.splitlines() if l.startswith('FAILED ')]
        verdict='SURVIVED' if p.returncode==0 else 'CAUGHT' if p.returncode==1 and failed and 'ERROR ' not in text and 'ERROR at' not in text else 'INVALID'
        return dict(returncode=p.returncode,verdict=verdict,failed_ids=failed,log=label+'.log',original_sha256=sha(raw),delivered_sha256=sha(data),normalizations=changes)
    report=dict(base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),config_sha256=sha(CONFIG.read_bytes()),command=['python',*command[1:]],portable_path_normalization='interpreter normalized to python; delivered logs strip whitespace and replace listed private paths only',baseline=invoke('baseline'),mutants=[])
    assert report['baseline']['returncode']==0
    for m in config['mutants']:
        path=ROOT/m['file'];raw=path.read_bytes();text=raw.decode();assert text.count(m['old'])==1,m
        try:
            path.write_text(text.replace(m['old'],m['new'],1))
            result=invoke(m['id'])
        finally:path.write_bytes(raw)
        result.update(id=m['id'],target=m['file'],before_sha256=sha(raw),restored_sha256=sha(path.read_bytes()),restore_verified=path.read_bytes()==raw)
        assert result['restore_verified'];report['mutants'].append(result)
    report['restored_baseline']=invoke('restored-baseline');assert report['restored_baseline']['returncode']==0
    report['counts']={s:sum(x['verdict']==s for x in report['mutants']) for s in ['CAUGHT','SURVIVED','INVALID']}
    (OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'counts':report['counts'],'private_raw_directory':str(private),'baseline':report['baseline']['returncode'],'restored':report['restored_baseline']['returncode']}))
if __name__=='__main__':main()
