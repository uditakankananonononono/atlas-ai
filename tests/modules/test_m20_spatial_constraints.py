import pytest
from app.modules.m20_general_cognitive_worker.spatial_constraints import solve_spatial
O=[{'id':id,'bounds':[[-10,10],[-10,10]]} for id in 'abc']
def rel(a,b,gap=1):return {'subject':a,'reference':b,'direction':'east','minimum_gap':gap}
def run(relations,queries=[]):return solve_spatial({'frame_of_reference':'Cartesian x east/y north','spatial_objects':O,'spatial_relations':relations,'spatial_queries':queries})

def test_actual_transitive_spatial_entailment_with_separation_certificate():
 r=run([rel('a','b',2),rel('b','c',3)],[rel('a','c',5)])
 q=r['queries'][0];assert q['guaranteed'] and q['minimum_signed_separation']==pytest.approx(5)
 assert q['counterexample'] is None


def test_unconstrained_query_has_real_counterexample_not_copied_relation():
 q=run([],[rel('a','b')])['queries'][0]
 assert not q['guaranteed'] and q['possible']
 assert q['counterexample']['a']['x']-q['counterexample']['b']['x']<1
 assert q['supporting_layout']['a']['x']-q['supporting_layout']['b']['x']>=1


def test_impossible_positive_cycle_reports_no_layout():
 r=run([rel('a','b'),rel('b','c'),rel('c','a')])
 assert r['status']=='inconsistent' and r['layout'] is None


def test_zero_gap_cycle_is_feasible_not_assumed_strict():
 assert run([rel('a','b',0),rel('b','a',0)])['status']=='feasible'


def test_bad_reference_or_missing_frame_rejected():
 with pytest.raises(ValueError):run([rel('a','z')])
 with pytest.raises(ValueError):solve_spatial({'spatial_objects':O,'spatial_relations':[]})


def test_spatial_conflict_identifies_input_cycle_and_drops_unrelated_relation():
 r=run([rel('a','b'),rel('b','a'),rel('b','c',0)])
 witness=r['conflict_witness']
 assert witness['verified_infeasible'] and witness['irreducible']
 assert {c['relation_index'] for c in witness['constraints'] if c['source']=='relation'}=={0,1}
 assert all(c['source']=='relation' for c in witness['constraints'])
 assert witness['solver_checks']<=64


def test_spatial_conflict_retains_box_origin_when_relation_exceeds_available_bounds():
 objects=[{'id':'a','bounds':[[0,0],[0,0]]},{'id':'b','bounds':[[0,0],[0,0]]}]
 r=solve_spatial({'frame_of_reference':'test','spatial_objects':objects,'spatial_relations':[rel('a','b')]})
 constraints=r['conflict_witness']['constraints']
 assert any(c['source']=='relation' and c['relation_index']==0 for c in constraints)
 assert {(c['object_id'],c['axis'],c['bound']) for c in constraints if c['source']=='box'}=={('a','x','upper'),('b','x','lower')}


def test_bounded_spatial_conflict_does_not_claim_minimal_when_checks_exhausted():
 r=solve_spatial({'frame_of_reference':'test','spatial_objects':O,'spatial_relations':[rel('a','b'),rel('b','a')],'conflict_max_checks':1})
 witness=r['conflict_witness']
 assert witness['verified_infeasible'] and not witness['irreducible']
 assert witness['solver_checks']==1 and witness['stopped_by']=='check_budget'


def test_reported_spatial_subset_independently_infeasible_and_each_deletion_feasible():
 import numpy as np
 from scipy.optimize import linprog
 r=run([rel('a','b',3),rel('b','a',2),rel('b','c',0)])
 constraints=r['conflict_witness']['constraints']; names=['a','b','c']
 def status(selected):
  A=[];b=[]
  for c in selected:
   row=np.zeros(6)
   if c['source']=='relation':
    relation=c['relation'];row[2*names.index(relation['subject'])]=-1;row[2*names.index(relation['reference'])]=1;bound=-relation['minimum_gap']
   else:
    sign=1 if c['bound']=='upper' else -1;row[2*names.index(c['object_id'])+(c['axis']=='y')]=sign;bound=sign*c['value']
   A.append(row);b.append(bound)
  return linprog(np.zeros(6),A_ub=A or None,b_ub=b or None,bounds=[(None,None)]*6).status
 assert status(constraints)==2
 assert all(status(constraints[:i]+constraints[i+1:])==0 for i in range(len(constraints)))
