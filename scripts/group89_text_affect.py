"""Classify reviewed local English passages; never infer an individual's mind."""
import argparse,json
from pathlib import Path
from app.modules.c32.learned_affect import LearnedAffect

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--field',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('output exists; choose a new receipt file')
    if args.input.stat().st_size>40000:raise ValueError('input exceeds 40KB')
    result=LearnedAffect().analyze(args.input.read_text(encoding='utf-8'),args.field)
    with args.output.open('x',encoding='utf-8') as output:json.dump(result,output,indent=2)
if __name__=='__main__':main()
