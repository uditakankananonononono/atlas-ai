"""Finite graph harmonic label propagation, not population generalization.

Caller-supplied symmetric similarities and evidence-linked labels are assumed,
not independently learned/validated. Predictions apply only to supplied nodes.
"""
from __future__ import annotations
import numpy as np
from .measured_learning import text
from .conic_solvers import finite


def transduce(p):
    nodes=p.get('nodes');labels=p.get('observed_labels')
    if not isinstance(nodes,list) or not 2<=len(nodes)<=128 or any(not isinstance(n,str) or not n for n in nodes) or len(set(nodes))!=len(nodes):raise ValueError('2..128 unique nonempty node ids required')
    if not isinstance(labels,list) or not labels:raise ValueError('nonempty evidence-linked observed_labels required')
    W=finite(p['similarity_matrix'],'similarity_matrix',2);n=len(nodes)
    if W.shape!=(n,n) or np.any(W<0) or not np.allclose(W,W.T,rtol=0,atol=1e-12) or np.any(np.diag(W)!=0):raise ValueError('nonnegative symmetric similarity matrix with zero diagonal required')
    index={id:i for i,id in enumerate(nodes)};seen=set();evidence=set();classes=[];known=[]
    for label in labels:
        node=label.get('node_id');cls=text(label.get('label'),'class label');ev=text(label.get('evidence_id'),'label evidence')
        if node not in index or node in seen or ev in evidence:raise ValueError('unique evidence and known labeled nodes required')
        seen.add(node);evidence.add(ev)
        if cls not in classes:classes.append(cls)
        known.append((index[node],cls,ev))
    classes.sort();labeled=[i for i,_,_ in known];unknown=[i for i in range(n) if i not in labeled]
    # Every unlabeled connected component must reach a label for unique solution.
    reachable=set(labeled);frontier=list(labeled)
    while frontier:
        i=frontier.pop()
        for j in np.flatnonzero(W[i]>0):
            if int(j) not in reachable:reachable.add(int(j));frontier.append(int(j))
    missing=[nodes[i] for i in unknown if i not in reachable]
    if missing:raise ValueError('unlabeled nodes disconnected from evidence: '+','.join(missing))
    degree=W.sum(axis=1);L=np.diag(degree)-W
    if not np.isfinite(L).all():raise ValueError('graph arithmetic overflow')
    F=np.zeros((n,len(classes)))
    for i,cls,_ in known:F[i,classes.index(cls)]=1
    influence=np.zeros((n,len(labeled)))
    influence[labeled]=np.eye(len(labeled))
    residual=0.;influence_residual=0.;condition=None
    if unknown:
        A=L[np.ix_(unknown,unknown)];B=-L[np.ix_(unknown,labeled)]@F[labeled]
        condition=float(np.linalg.cond(A))
        if not np.isfinite(condition) or condition>1e12:raise ValueError('ill-conditioned unlabeled Laplacian; no reliable unique prediction')
        try:
            influence[unknown]=np.linalg.solve(A,-L[np.ix_(unknown,labeled)])
            F[unknown]=influence[unknown]@F[labeled]
        except np.linalg.LinAlgError as exc:raise ValueError('harmonic linear solve failed') from exc
        residual=float(np.max(np.abs(A@F[unknown]-B)))
        influence_residual=float(np.max(np.abs(A@influence[unknown]+L[np.ix_(unknown,labeled)])))
    if not np.isfinite(F).all() or np.any(F < -1e-8) or np.any(F>1+1e-8) or np.max(np.abs(F.sum(axis=1)-1))>1e-8:raise ValueError('invalid harmonic class scores')
    if not np.isfinite(influence).all() or np.any(influence < -1e-8) or np.any(influence>1+1e-8) or np.max(np.abs(influence.sum(axis=1)-1))>1e-8:raise ValueError('invalid harmonic evidence influence')
    predictions=[]
    for i in unknown:
        tied=[classes[j] for j in range(len(classes)) if abs(F[i,j]-F[i].max())<=1e-10]
        predictions.append({'evidence_influence':[{'node_id':nodes[source],'evidence_id':ev,'label':cls,'weight':float(influence[i,j])} for j,(source,cls,ev) in enumerate(known)],'evidence_influence_is_not_source_reliability':True,'node_id':nodes[i],'class_scores':dict(zip(classes,F[i].tolist())),'candidate_labels':tied,'predicted_label':tied[0] if len(tied)==1 else None})
    return {'evidence_influence_residual':influence_residual,'predictions':predictions,'classes':classes,'observed_labels':labels,'harmonic_residual':residual,'laplacian_condition':condition,
            'energy':float(.5*np.sum(F*(L@F))),'scope':'supplied target instance graph only; no population rule',
            'algorithm_source':'https://aaai.org/papers/icml03-118-semi-supervised-learning-using-gaussian-fields-and-harmonic-functions/',
            'boundary':'Actual harmonic graph solve on supplied similarities and labels. Scores are harmonic weights, not calibrated outcome probabilities. Ties preserved. Graph/label correctness not independently verified; no population generalization, semantic analogy or causal inference claim.'}
