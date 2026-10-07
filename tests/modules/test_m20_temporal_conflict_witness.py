from app.modules.m20_general_cognitive_worker.temporal_network import temporal


def test_temporal_conflict_reports_constraint_cycle_not_all_constraints():
    result = temporal({'temporal_events': ['start','review','finish','other'], 'time_unit':'hours',
        'time_constraints': [
            {'from':'start','to':'review','minimum_gap':3},
            {'from':'review','to':'finish','minimum_gap':4},
            {'from':'start','to':'finish','maximum_gap':5},
            {'from':'start','to':'other','minimum_gap':0}], 'time_queries':[]})
    assert result['status']=='inconsistent'
    witness = result['conflict_witness']
    assert {edge['constraint_index'] for edge in witness['edges']} == {0,1,2}
    assert witness['total_upper_bound'] == -2
    edges = witness['edges']
    assert all(edge['to'] == edges[(i+1)%len(edges)]['from'] for i,edge in enumerate(edges))
    assert witness['minimal_conflict_claimed'] is False


def test_consistent_temporal_network_has_no_conflict_witness():
    result=temporal({'temporal_events':['a','b'],'time_unit':'hours',
        'time_constraints':[{'from':'a','to':'b','minimum_gap':1,'maximum_gap':2}]})
    assert result['conflict_witness'] is None


def test_disconnected_self_conflict_points_to_exact_constraint():
    result=temporal({'temporal_events':['a','b','c'],'time_unit':'hours','time_constraints':[
        {'from':'a','to':'b','minimum_gap':1},
        {'from':'c','to':'c','maximum_gap':-1}]})
    witness=result['conflict_witness']
    assert witness['edges']==[{'from':'c','to':'c','upper_bound':-1.0,'constraint_index':1,'bound':'maximum_gap'}]
    assert witness['total_upper_bound']==-1
