import pytest
from app.modules.m20_general_cognitive_worker.knowledge_graph873_876 import facet_retrieval,graph_paths
from app.modules.m20_general_cognitive_worker.cognitive_learning_860_909 import execute


def test_real_facet_and_or_exclusion_queries():
    out=facet_retrieval({'knowledge_items':[
        {'id':'a','facets':{'topic':['biology'],'format':['paper']}},
        {'id':'b','facets':{'topic':['biology','cs'],'format':['code']}},
        {'id':'c','facets':{'topic':['physics'],'format':['paper']}},
    ],'facet_queries':[
        {'id':'allbio','filters':{'topic':['biology']}},
        {'id':'biopaper','filters':{'topic':['biology'],'format':['paper']}},
        {'id':'or','filters':{'topic':['biology','physics']},'exclude':{'format':['code']}},
        {'id':'unknown','filters':{'topic':['absent']}},
    ]})
    assert [r['matching_item_ids']for r in out['queries']]==[['a','b'],['a'],['a','c'],[]]
    assert not out['semantic_labels_learned'] and not out['source_truth_verified']


def graph():
    return {'nodes':['a','b','c','d'],'typed_edges':[
        {'id':'ab','from':'a','to':'b','type':'supports'},
        {'id':'bc','from':'b','to':'c','type':'supports'},
        {'id':'ac','from':'a','to':'c','type':'contradicts'},
        {'id':'ca','from':'c','to':'a','type':'related'},
    ],'graph_queries':[{'from':'a','to':'c','types':['supports']},
                        {'from':'a','to':'c'}, {'from':'c','to':'b'},
                        {'from':'a','to':'c','types':['supports'],'max_hops':1},
                        {'from':'d','to':'a'}, {'from':'a','to':'a','max_hops':0}]}


def test_actual_multihop_graph_queries_cycles_and_filters():
    out=graph_paths(graph());q=out['queries']
    assert [x['shortest_hops']for x in q]==[2,1,2,None,None,0]
    assert [x['id']for x in q[0]['edge_path']]==['ab','bc']
    assert not out['unstated_relation_inference'] and not out['path_is_causality_proof']


def test_unknown_edge_and_duplicate_refused():
    p=graph();p['typed_edges'][0]['to']='missing'
    with pytest.raises(ValueError):graph_paths(p)
    p=graph();p['typed_edges'][1]['id']='ab'
    with pytest.raises(ValueError):graph_paths(p)


def test_duplicate_knowledge_item_id_refused():
    p={'knowledge_items':[{'id':'a','facets':{'topic':['biology']}},{'id':'a','facets':{'topic':['cs']}}],'facet_queries':[]}
    with pytest.raises(ValueError):facet_retrieval(p)


def test_facet_count_boundary_32_accepted_33_refused():
    ok={'knowledge_items':[{'id':'a','facets':{('f%02d'%i):['v'] for i in range(32)}}],'facet_queries':[]}
    out=facet_retrieval(ok)
    assert out['queries']==[]
    over={'knowledge_items':[{'id':'a','facets':{('f%02d'%i):['v'] for i in range(33)}}],'facet_queries':[]}
    with pytest.raises(ValueError):facet_retrieval(over)


def test_existing_row_dispatches_without_new_route():
    p={'tenant_id':'t','actor_id':'a','sources':[{'source_id':'s','observed_at':'2026-10-13'}],'inputs':graph()}
    out=execute(876,p)
    assert out['result']['queries'][0]['shortest_hops']==2
    assert not out['complete'] and not out['capability_executed']
