#!/usr/bin/env python3
"""Validate that audit evidence names an actual pytest node, not merely a file."""
from __future__ import annotations
import argparse,ast,json
from pathlib import Path


def functions(path:Path)->set[str]:
    try: tree=ast.parse(path.read_text())
    except (OSError,SyntaxError,UnicodeDecodeError): return set()
    return {node.name for node in ast.walk(tree)
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_')}


def validate(path:Path)->dict:
    data=json.loads(path.read_text());rows=data.get('rows',[]);cache={};results=[]
    for row in rows:
        raw=row.get('test_evidence') or (row.get('evidence') or {}).get('test_path') or row.get('test_path')
        reason=None;resolved=False
        if not raw: reason='no test evidence'
        elif '::' not in raw: reason='shared file only; no pytest node'
        else:
            filename,node=raw.split('::',1);test_path=Path(filename);node=node.split('[',1)[0]
            if not test_path.is_file(): reason='test file missing'
            else:
                cache.setdefault(filename,functions(test_path));resolved=node in cache[filename]
                if not resolved: reason='pytest node not found'
        results.append({'row':row.get('requirement_id',row.get('id',row.get('row'))),
                        'evidence':raw,'resolved':resolved,'reason':reason})
    resolved=sum(x['resolved'] for x in results)
    return {'ledger':str(path),'total':len(results),'resolvable_nodes':resolved,
            'unresolved':len(results)-resolved,'results':results}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('ledgers',nargs='+');parser.add_argument('--output')
    args=parser.parse_args();reports=[validate(Path(x)) for x in args.ledgers]
    text=json.dumps({'schema_version':1,'reports':reports},indent=2)
    Path(args.output).write_text(text+'\n') if args.output else print(text)
    raise SystemExit(1 if any(r['unresolved'] for r in reports) else 0)
if __name__=='__main__':main()
