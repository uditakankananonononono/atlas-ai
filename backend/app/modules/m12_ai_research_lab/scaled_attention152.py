"""Bounded single-head scaled dot-product attention; no learned relevance claim."""
import math


def attend(queries,keys,values,mask=None):
    def matrix(rows):
        if type(rows) is not list or not 1<=len(rows)<=32:
            raise ValueError('1..32 matrix rows before scan')
        width=None;result=[]
        for row in rows:
            if type(row) is not list or not 1<=len(row)<=16:
                raise ValueError('1..16 matrix columns before scan')
            if width is None:width=len(row)
            if len(row)!=width:raise ValueError('rectangular matrix required')
            for cell in row:
                if type(cell) not in (int,float) or not -1000<=cell<=1000 or not math.isfinite(cell):
                    raise ValueError('strict finite matrix values within -1000..1000')
            result.append(list(row))
        return result,width
    q,d=matrix(queries);k,kd=matrix(keys);v,vd=matrix(values)
    if d!=kd:raise ValueError('query/key dimensions must match')
    if len(k)!=len(v):raise ValueError('key/value row counts must match')
    if mask is None:allowed=[[True]*len(k) for _ in q]
    else:
        if type(mask) is not list or len(mask)!=len(q):raise ValueError('mask shape must match query/key rows')
        allowed=[]
        for row in mask:
            if type(row) is not list or len(row)!=len(k):raise ValueError('mask shape must match query/key rows')
            if any(type(x) is not bool for x in row):raise ValueError('strict boolean mask cells')
            if not any(row):raise ValueError('at least one allowed key per query')
            allowed.append(list(row))
    weights=[];outputs=[]
    for query,flags in zip(q,allowed):
        scores=[sum(a*b for a,b in zip(query,key))/math.sqrt(d) for key in k]
        peak=max(score for score,flag in zip(scores,flags) if flag)
        masses=[math.exp(score-peak) if flag else 0.0 for score,flag in zip(scores,flags)]
        total=sum(masses);w=[x/total for x in masses]
        weights.append(w);outputs.append([sum(wi*row[j] for wi,row in zip(w,v)) for j in range(vd)])
    return {'weights':weights,'outputs':outputs,'scale_dimension':d,
            'mask_semantics':'True allows key; False contributes exactly zero weight',
            'learned_projection_performed':False,'semantic_relevance_verified':False,
            'attention_is_causal_explanation':False,'external_effects':[],
            'assumptions':['caller supplied query/key/value projections','dot product compatibility is not semantic relevance']}
