#!/usr/bin/env python3
import json,subprocess
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'audits/coverage-register.json').read_text())
rows=data['rows']; head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();counts=Counter(x['depth_sweep_status'] for x in rows)
lines=['# Atlas AI implementation audit','',f'Generated from `audits/coverage-register.json` at `{head}`. Do not edit by hand.','',f'Coverage: **{len(rows)}/{len(rows)}** rows. '+', '.join(f'`{k}`: {v}' for k,v in sorted(counts.items())), '', '| Row | Requirement | Status | Implementation | Test | Evidence |','|---:|---|---|---|---|---|']
for r in rows:
 esc=lambda x:str(x or '').replace('|','\\|').replace('\n',' ')
 lines.append(f"| {r['row']} | {esc(r['requirement'])} | {esc(r['depth_sweep_status'])} | `{esc(r.get('implementation_path'))}` | `{esc(r.get('test_path'))}` | {esc(r.get('depth_evidence') or r.get('implementation_details'))} |")
(root/'docs/IMPLEMENTATION_AUDIT.md').write_text('\n'.join(lines)+'\n')
print(f'wrote {len(rows)} rows at {head}')
