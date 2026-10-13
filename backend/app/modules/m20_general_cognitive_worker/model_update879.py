"""Fit an actual bounded linear ridge model and compare explicit heldout errors.

Numeric records/provenance are supplied, not verified measurements. No automatic
promotion or general world-model learning. Holdout is used only after fitting.
"""
import hashlib
import json
import numpy as np


def fit_update(packet):
    if not isinstance(packet,dict):raise ValueError('model_update_training object required')
    names=packet.get('feature_names');train=packet.get('training');holdout=packet.get('heldout')
    if not isinstance(names,list) or not 1<=len(names)<=32 or any(not isinstance(n,str) or not n or len(n)>100 for n in names) or len(set(names))!=len(names):
        raise ValueError('1..32 unique feature names required')
    if not isinstance(train,list) or not 2<=len(train)<=1000 or not isinstance(holdout,list) or not 1<=len(holdout)<=1000:
        raise ValueError('2..1000 training and1..1000 heldout records required')
    seen=set()
    def rows(records):
        vectors=[];targets=[];ids=[]
        for row in records:
            if not isinstance(row,dict):raise ValueError('training record object required')
            ident=row.get('id');source=row.get('source');vector=row.get('features');target=row.get('target')
            if not isinstance(ident,str) or not ident or ident in seen or not isinstance(source,str) or not source:
                raise ValueError('unique disjoint record IDs and supplied sources required')
            seen.add(ident);ids.append(ident)
            if not isinstance(vector,list) or len(vector)!=len(names) or any(type(x)not in(int,float) or not np.isfinite(x) or abs(x)>1e6 for x in vector):
                raise ValueError('bounded finite aligned features required')
            if type(target)not in(int,float) or not np.isfinite(target) or abs(target)>1e6:
                raise ValueError('bounded finite target required')
            vectors.append([1.,*vector]);targets.append(target)
        return np.asarray(vectors,dtype=float),np.asarray(targets,dtype=float),ids
    x,y,train_ids=rows(train);hx,hy,heldout_ids=rows(holdout)
    penalty=packet.get('ridge',1.)
    if type(penalty)not in(int,float) or not np.isfinite(penalty) or not 1e-8<=penalty<=1e6:
        raise ValueError('ridge requires finite number[1e-8,1e6]')
    prior=packet.get('prior_parameters')
    if not isinstance(prior,list) or len(prior)!=len(names)+1 or any(type(v)not in(int,float) or not np.isfinite(v) or abs(v)>1e6 for v in prior):
        raise ValueError('bounded finite prior_parameters intercept+weights required')
    regularizer=np.sqrt(penalty)*np.eye(len(names)+1);regularizer[0,0]=0.
    # Augmented least squares, not unstable normal-equation inversion.
    fitted,_,rank,singular=np.linalg.lstsq(np.vstack([x,regularizer]),np.concatenate([y,np.zeros(len(names)+1)]),rcond=None)
    old=hx@np.asarray(prior,dtype=float);new=hx@fitted
    old_mse=float(np.mean((old-hy)**2));new_mse=float(np.mean((new-hy)**2))
    if not np.isfinite(fitted).all() or not np.isfinite([old_mse,new_mse]).all():raise ValueError('model fit or metric overflow')
    digest=hashlib.sha256(json.dumps(packet,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return {'kind':'actual_ridge_regression_fit_and_heldout_comparison','feature_names':list(names),
            'fitted_parameters':fitted.tolist(),'prior_parameters':list(prior),'rank':int(rank),
            'training_record_ids':train_ids,'heldout_record_ids':heldout_ids,'input_sha256':digest,
            'heldout_mse_prior':old_mse,'heldout_mse_fitted':new_mse,'heldout_error_reduced':new_mse<old_mse,
            'heldout_predictions':[{'record_id':ident,'prior':float(a),'fitted':float(b),'observed':float(c)}
                                   for ident,a,b,c in zip(heldout_ids,old,new,hy)],
            'model_promoted':False,'causal_model_learned':False,'source_truth_verified':False,
            'limits':'Linear regression on supplied numeric records, not autonomous model discovery. Distinct IDs do not prove independent holdout sampling. No promotion, deployment or causal interpretation.'}
