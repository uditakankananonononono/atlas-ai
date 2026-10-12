"""Fresh scoped replay of six named S4.3 operators, not historical log recovery.

Uses the shared FAILED-only runner: rc1 plus FAILED IDs, no ERROR/SKIP;
records source SHA restore. Trusted local tests only, not a sandbox.
"""
from pathlib import Path
import argparse
import importlib.util
import json

R=Path(__file__).resolve().parents[2]



def replay(output):
    output=Path(output)
    # The old script wrote into a missing directory. Create the parent before
    # the shared runner creates a fresh run directory; never overwrite logs.
    output.parent.mkdir(parents=True,exist_ok=True)
    loader=importlib.util.spec_from_file_location('s43_scoped_runner',R/'scripts/release/scoped_mutations.py')
    runner=importlib.util.module_from_spec(loader);loader.loader.exec_module(runner)
    return runner.execute(R/'audits/s43-delta/operators.json',output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(R/'audits/s43-delta/fresh-run'))
    args=parser.parse_args()
    result=replay(args.output)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['all_caught'] else 1)
