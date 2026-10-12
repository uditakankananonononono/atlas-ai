"""Actual educational public digits split, no best-tool/breakthrough claims.

Requires optional learning-evaluation deps. CLI writes a fresh JSON receipt.
"""
import hashlib,json
from pathlib import Path
from app.modules.c37.learning_experiment import experiment

def run():
    import sklearn
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    data=load_digits()
    # Drop exact repeated feature vectors globally, even across different labels,
    # before split, so no vector repeats cross split. Keep first indexed record.
    unique={}
    for index,(features,label) in enumerate(zip(data.data,data.target)):
        unique.setdefault(tuple(features),{'id':str(index),'features':features.tolist(),'label':str(label)})
    rows=list(unique.values())
    train,test=train_test_split(rows,test_size=.25,random_state=42,stratify=[r['label'] for r in rows])
    scaler=StandardScaler().fit([r['features'] for r in train])
    def transform(split):
        values=scaler.transform([r['features'] for r in split]).tolist()
        return [dict(r,features=v) for r,v in zip(split,values)]
    train,test=transform(train),transform(test)
    report=experiment(train,test)
    logistic=LogisticRegression(max_iter=2000,random_state=42).fit([r['features'] for r in train],[r['label'] for r in train])
    score=logistic.score([r['features'] for r in test],[r['label'] for r in test])
    raw=json.dumps(rows,sort_keys=True,separators=(',',':'))
    return {'dataset':{'name':'sklearn bundled UCI handwritten digits','original_count':len(data.data),
                      'unique_vector_count':len(rows),'deduplicated_sha256':hashlib.sha256(raw.encode()).hexdigest()},
            'sklearn_version':sklearn.__version__,'scaling':'fit on training only','split_seed':42,
            'experiment':report,'comparison':{'standardized_logistic_accuracy':float(score),
                                             'same_split':True,'tuned_on_heldout':False},
            'scope':'One fixed public educational split, not sector-wide superiority.'}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with args.output.open('x') as stream:json.dump(run(),stream,indent=2,allow_nan=False)
