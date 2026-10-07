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


def test_harmonic_prediction_retains_actual_label_evidence_influence():
 r=run([[0,3,0],[3,0,1],[0,1,0]])
 influences=r['predictions'][0]['evidence_influence']
 assert influences==[{'node_id':'a','evidence_id':'e1','label':'left','weight':.75},
                     {'node_id':'b','evidence_id':'e2','label':'right','weight':.25}]
 assert r['evidence_influence_residual']<1e-12


def test_harmonic_same_class_sources_do_not_collapse_evidence_attribution():
 r=transduce({'nodes':['a','u','b'],'similarity_matrix':[[0,3,0],[3,0,1],[0,1,0]],
  'observed_labels':[{'node_id':'a','label':'same','evidence_id':'e1'},{'node_id':'b','label':'same','evidence_id':'e2'}]})
 pred=r['predictions'][0]
 assert pred['class_scores']=={'same':1.0}
 assert [x['weight'] for x in pred['evidence_influence']]==pytest.approx([.75,.25])
 assert pred['evidence_influence_is_not_source_reliability']


def test_harmonic_chain_source_influence_agrees_with_independent_absorption_probabilities():
 W=np.zeros((5,5))
 for i in range(4):W[i,i+1]=W[i+1,i]=1
 r=transduce({'nodes':list('abcde'),'similarity_matrix':W.tolist(),'observed_labels':[{'node_id':'a','label':'left','evidence_id':'1'},{'node_id':'e','label':'right','evidence_id':'2'}]})
 for i,pred in enumerate(r['predictions'],1):
  assert [x['weight'] for x in pred['evidence_influence']]==pytest.approx([1-i/4,i/4])


def test_harmonic_influence_tracks_reordered_evidence_and_disconnected_source_zero():
 r=transduce({'nodes':['a','u','b','isolated'],'similarity_matrix':[[0,3,0,0],[3,0,1,0],[0,1,0,0],[0,0,0,0]],
  'observed_labels':[{'node_id':'isolated','label':'other','evidence_id':'e3'}, {'node_id':'b','label':'right','evidence_id':'e2'}, {'node_id':'a','label':'left','evidence_id':'e1'}]})
 influences={x['evidence_id']:x['weight'] for x in r['predictions'][0]['evidence_influence']}
 assert influences==pytest.approx({'e3':0.,'e2':.25,'e1':.75})
 assert r['predictions'][0]['class_scores']==pytest.approx({'left':.75,'right':.25,'other':0.})
