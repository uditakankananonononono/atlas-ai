"""Finite-benchmark summaries; seeds never counted as independent problems."""
import json
from psb2_data import ROOT
KEYS=('base','transfer','random','psb_lopo','within')

def main():
    rows=[json.loads(s) for s in (ROOT/'rows.jsonl').read_text().splitlines()]
    lines=[]
    for track in ('exact','extended'):
        for budget in sorted(set(r['budget'] for r in rows)):
            rs=[r for r in rows if r['track']==track and r['budget']==budget]
            target_count=len(set(r['target'] for r in rs));seed_count=len(set(r['seed'] for r in rs))
            counts={k:sum(r[k]['solved'] for r in rs) for k in KEYS}
            lines.append(f'{track} B={budget}: {target_count} distinct problems x {seed_count} split seeds; {counts}')
            # Five resamples of the same six tasks are descriptive repeats, not n=30 trials.
            assert all(r['base']['solved']==r['transfer']['solved'] for r in rs)
            lines.append('paired source-transfer minus base = 0.000 on every seed and target')
            for name in sorted(set(r['target'] for r in rs)):
                xs=[r for r in rs if r['target']==name]
                lines.append(f'  {name}: '+str({k:sum(x[k]['solved'] for x in xs) for k in KEYS}))
    (ROOT/'analysis.txt').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__':main()
