import numpy as np
import pytest
from app.modules.m20_general_cognitive_worker.graph_transduction import transduce

def run(W,**kwargs):
 return transduce({'nodes':['a','u','b'],'similarity_matrix':W,'observed_labels':[{'node_id':'a','label':'left','evidence_id':'e1'},{'node_id':'b','label':'right','evidence_id':'e2'}],**kwargs})

def test_weighted_single_target_harmonic_solution_changes_with_edges():
 r=run([[0,3,0],[3,0,1],[0,1,0]])
 assert r['predictions'][0]['class_scores']==pytest.approx({'left':.75,'right':.25})
 assert r['predictions'][0]['predicted_label']=='left' and r['harmonic_residual']<1e-12
 assert run([[0,1,0],[1,0,3],[0,3,0]])['predictions'][0]['predicted_label']=='right'


def test_equal_evidence_preserves_tie_instead_of_arbitrary_label():
 r=run([[0,1,0],[1,0,1],[0,1,0]])
 assert r['predictions'][0]['predicted_label'] is None
 assert r['predictions'][0]['candidate_labels']==['left','right']


def test_chain_solution_matches_exact_linear_interpolation():
 W=np.zeros((5,5))
 for i in range(4):W[i,i+1]=W[i+1,i]=1
 r=transduce({'nodes':list('abcde'),'similarity_matrix':W.tolist(),'observed_labels':[{'node_id':'a','label':'0','evidence_id':'1'},{'node_id':'e','label':'1','evidence_id':'2'}]})
 assert [p['class_scores']['1'] for p in r['predictions']]==pytest.approx([.25,.5,.75])
 assert r['energy']==pytest.approx(.25)

@pytest.mark.parametrize('W',[[[0,0,0],[0,0,0],[0,0,0]],[[0,1,0],[2,0,1],[0,1,0]],[[0,-1,0],[-1,0,1],[0,1,0]]])
def test_unsupported_or_unanchored_graph_rejected(W):
 with pytest.raises(ValueError):run(W)
