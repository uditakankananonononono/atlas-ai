import pytest
from app.modules.m20_general_cognitive_worker.temporal_network import temporal

def run(constraints,queries=[],events=['a','b','c']):return temporal({'temporal_events':events,'time_unit':'hours','time_constraints':constraints,'time_queries':queries})
def bound(a,b,lo,hi):return {'from':a,'to':b,'minimum_gap':lo,'maximum_gap':hi}

def test_transitive_time_gap_bounds_not_merely_ordered_input():
 r=run([bound('a','b',2,4),bound('b','c',3,5)],[{'from':'a','to':'c','at_least':5}])
 assert r['queries'][0]['minimum_implied_gap']==5 and r['queries'][0]['maximum_implied_gap']==9
 assert r['queries'][0]['guaranteed_at_least'] and r['constraint_violation']==0
 t=r['witness_relative_times'];assert 2<=t['b']-t['a']<=4 and 3<=t['c']-t['b']<=5


def test_contradictory_cycle_rejected_and_zero_cycle_allowed():
 assert run([bound('a','b',1,None),bound('b','a',1,None)])['status']=='inconsistent'
 assert run([bound('a','b',0,0),bound('b','a',0,0)])['status']=='consistent'


def test_unknown_order_unbounded_and_possible_not_guaranteed():
 q=run([],[{'from':'a','to':'b','at_least':1}])['queries'][0]
 assert q['minimum_implied_gap'] is None and q['maximum_implied_gap'] is None
 assert not q['guaranteed_at_least'] and q['possible_at_least']


def test_negative_gaps_model_precedence_reverse_without_discarding():
 q=run([bound('a','b',-5,-2)],[{'from':'b','to':'a','at_least':2}])['queries'][0]
 assert q['guaranteed_at_least'] and q['minimum_implied_gap']==2 and q['maximum_implied_gap']==5


def test_bad_or_nonfinite_bound_rejected():
 with pytest.raises(ValueError):run([bound('a','z',1,2)])
 with pytest.raises(ValueError):run([bound('a','b',3,2)])
 with pytest.raises(ValueError):run([bound('a','b',0,float('inf'))])
