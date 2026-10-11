"""A limited declarative record language with no eval, imports or arbitrary code.

Generated Python runs the same interpreter and includes pinned attribution.
"""
import json
from .policy import Refusal, number, text

COMPARATORS={'eq':lambda a,b:a==b,'ne':lambda a,b:a!=b,'gt':lambda a,b:a>b,'gte':lambda a,b:a>=b,'lt':lambda a,b:a<b,'lte':lambda a,b:a<=b}

def validate_behavior(behavior):
    ops=behavior.get('operations') if isinstance(behavior,dict) else None
    if not isinstance(ops,list) or not ops or len(ops)>20: raise Refusal('PROTO_REFUSED_BEHAVIOR')
    for i,op in enumerate(ops):
        if not isinstance(op,dict) or op.get('op') not in {'filter','project','sort','aggregate'}: raise Refusal('PROTO_REFUSED_BEHAVIOR')
        kind=op['op']
        if kind=='project':
            if not isinstance(op.get('fields'),list) or not op['fields'] or len(op['fields'])>100: raise Refusal('PROTO_REFUSED_BEHAVIOR')
            for field in op['fields']: text(field,limit=100)
        else: text(op.get('field'),limit=100)
        if kind=='filter' and (op.get('cmp') not in COMPARATORS or 'value' not in op): raise Refusal('PROTO_REFUSED_BEHAVIOR')
        if kind=='aggregate' and (i!=len(ops)-1 or op.get('function') not in {'sum','mean','count','min','max'}): raise Refusal('PROTO_REFUSED_BEHAVIOR')
    return ops

def transform(records,ops):
    if not isinstance(records,list) or len(records)>10000 or any(not isinstance(r,dict) for r in records): raise Refusal('PROTO_REFUSED_RECORDS')
    rows=[dict(r) for r in records]
    try:
        for op in ops:
            kind=op['op']
            if kind=='filter': rows=[r for r in rows if COMPARATORS[op['cmp']](r[op['field']],op['value'])]
            elif kind=='project': rows=[{f:r[f] for f in op['fields']} for r in rows]
            elif kind=='sort': rows=sorted(rows,key=lambda r:r[op['field']])
            elif kind=='aggregate':
                values=[number(r[op['field']]) for r in rows]; fn=op['function']
                if fn=='count': value=len(values)
                elif fn=='sum': value=sum(values)
                elif not values: raise Refusal('PROTO_REFUSED_EMPTY')
                elif fn=='mean': value=sum(values)/len(values)
                elif fn=='min': value=min(values)
                else: value=max(values)
                number(value)
                return {fn:value}
        return rows
    except (KeyError,TypeError,OverflowError) as exc:
        raise Refusal('PROTO_REFUSED_RECORDS',str(exc)) from exc


def generate(ops):
    # JSON encoded as a Python string literal, never interpolated executable text.
    return ("import json\nfrom app.modules.m20_general_cognitive_worker.venture_v2.transforms import transform as _run\n"
            + 'OPERATIONS = json.loads(' + repr(json.dumps(ops,allow_nan=False)) + ')\n'
            + 'def transform(records):\n    return _run(records, OPERATIONS)\n'
            + "if __name__ == '__main__':\n    import sys\n    print(json.dumps(transform(json.load(sys.stdin)), allow_nan=False))\n")
