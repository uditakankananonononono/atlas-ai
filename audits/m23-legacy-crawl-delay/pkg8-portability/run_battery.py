from pathlib import Path
import hashlib,json,subprocess,os,tempfile
root=Path.cwd();out=root/'audits/m23-legacy-crawl-delay/pkg8-portability';private=Path(tempfile.mkdtemp(prefix='pkg8-portability-raw-'))
target=root/'audits/m23-legacy-crawl-delay/pkg8-followup/replay.py';raw=target.read_bytes();text=raw.decode();sha=lambda b:hashlib.sha256(b).hexdigest()
import sys
cmd=[sys.executable,'-B','-m','pytest','--noconftest','-p','no:cacheprovider','tests/release/test_pkg8_retained_body.py','-q','-rf','--tb=short']
def run(label):
 p=subprocess.run(cmd,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'));b=(p.stdout+p.stderr).encode();(private/(label+'.log')).write_bytes(b);ls=b.decode().splitlines(keepends=True);clean=''.join(l.rstrip('\r\n').rstrip()+'\n' for l in ls).encode();(out/(label+'.log')).write_bytes(clean)
 return dict(log=label+'.log',rc=p.returncode,failed_ids=[l[7:].split(' - ')[0] for l in b.decode().splitlines() if l.startswith('FAILED ')],original_sha256=sha(b),delivered_sha256=sha(clean),normalized_lines=[i for i,l in enumerate(ls,1) if l!=l.rstrip('\r\n').rstrip()+'\n'])
ops=[('P8-M1','if sha(raw)!=BODY_SHA256:', 'if False:'),('P8-M2',"return body,comparison","return '',comparison"),('P8-M3',"if derived!=body:","if False:"),('P8-M4','if src.count(old)!=1:','if False:'),('P8-M5',"comparison='matched'","comparison='unavailable'")]
r=dict(base=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),command=['python',*cmd[1:]],normalization='Interpreter portable-normalized; trailing whitespace removed at listed lines; original raw logs privately retained. No path replacements.',baseline=run('baseline'),mutants=[])
assert r['baseline']['rc']==0
for ident,old,new in ops:
 assert text.count(old)==1
 changed=text.replace(old,new,1).encode()
 try:target.write_bytes(changed);x=run(ident)
 finally:target.write_bytes(raw)
 x.update(id=ident,old=old,new=new,before_sha256=sha(raw),mutant_sha256=sha(changed),restored_sha256=sha(target.read_bytes()),caught=x['rc']==1 and bool(x['failed_ids']))
 assert x['caught'] and sha(target.read_bytes())==sha(raw);r['mutants'].append(x)
r['restored_baseline']=run('restored-baseline');assert r['restored_baseline']['rc']==0
(out/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');print('private originals:',private);print('5 caught; baseline/restored7passed')
