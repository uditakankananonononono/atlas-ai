"""Validate actual Compose config JSON against reviewed, ordered pair fixtures.

This never merges YAML or runs containers. Snapshots pin *every* rendered key;
intentional precedence is disclosed in the companion contract, not silently
accepted. Paths normalize to the supplied repository root for portability.
"""
import json
from pathlib import Path
RECIPES={'vault+loki':['vault','loki'],'otel+loki':['otel','loki'],'rabbitmq+vault':['vault','rabbitmq'],'mtls+vault':['vault','mtls'],'grafana+otel':['grafana','otel']}

def normalized(value,root):
    if isinstance(value,str):return value.replace(str(Path(root).resolve()),'${REPOSITORY_ROOT}')
    if isinstance(value,list):return [normalized(v,root) for v in value]
    if isinstance(value,dict):return {k:normalized(v,root) for k,v in value.items()}
    return value

def validate(pair,order,model,root):
    if pair not in RECIPES or order!=RECIPES[pair]:raise ValueError('unsupported ordered recipe')
    expected=json.loads((Path(root)/'deploy/local/stacking/expected.json').read_text())[pair]
    if normalized(model,root)!=expected:raise ValueError('rendered definition drift; review every changed key before accepting')
    return True

def main():
    import argparse
    p=argparse.ArgumentParser(description='Validate config JSON rendered with documented parse-only fixture inputs, not runtime secrets')
    p.add_argument('pair',choices=RECIPES);p.add_argument('json_path');p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
    validate(a.pair,RECIPES[a.pair],json.loads(Path(a.json_path).read_text()),a.root)

if __name__=='__main__':main()
