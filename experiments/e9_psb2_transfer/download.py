"""Recreate frozen uniform 4096-line snapshot from COMPLETE official random files.
Uses no copied EPL sampler. Scans all million rows and saves sampled line indexes,
full-file SHA256, and data URLs. Data labels are unmodified official PSB2 labels.
"""
import hashlib, json, random, urllib.request
from pathlib import Path
from psb2_data import ROOT, PROBLEMS

def main():
    metadata={}
    for name in PROBLEMS:
        directory=ROOT/'data'/name
        directory.mkdir(parents=True,exist_ok=True)
        selected=set(random.Random(9371).sample(range(1000000),4096))
        rows=[]; indices=[]; digest=hashlib.sha256(); total=0
        url=f'https://psb2-datasets.s3.amazonaws.com/PSB2/datasets/{name}/{name}-random.json'
        with urllib.request.urlopen(url,timeout=120) as f:
            for i,line in enumerate(f):
                digest.update(line); total+=1
                if i in selected:rows.append(line);indices.append(i)
        assert total==1000000,(name,total)
        (directory/'random-sample.jsonl').write_bytes(b''.join(rows))
        old=directory/'random-prefix.jsonl'
        if old.exists():old.unlink()
        edge_url=url.replace('-random.json','-edge.json')
        with urllib.request.urlopen(edge_url) as f:(directory/'edge.jsonl').write_bytes(f.read())
        metadata[name]=dict(url=url,edge_url=edge_url,total_lines=total,sha256=digest.hexdigest(),
                            sample_seed=9371,indices=indices)
        print(name,total,digest.hexdigest(),flush=True)
    (ROOT/'download_manifest.json').write_text(json.dumps(metadata,sort_keys=True,indent=1)+'\n')
if __name__=='__main__':main()
