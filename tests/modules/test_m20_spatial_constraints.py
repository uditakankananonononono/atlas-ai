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
