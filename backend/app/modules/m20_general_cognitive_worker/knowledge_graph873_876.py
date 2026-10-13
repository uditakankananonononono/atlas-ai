"""Actual finite facet intersection and typed graph reachability, no semantics model.

These computations operate on supplied labels/relations only. They never prove
that a graph edge is factually true or infer an unstated relationship.
"""
from collections import deque


def label(value, name):
    if not isinstance(value,str) or not value.strip() or len(value)>200:
        raise ValueError(name+' requires nonblank label up to200 characters')
    try:value.encode('utf-8')
    except UnicodeEncodeError as exc:raise ValueError(name+' invalid Unicode')from exc
    return value


def facet_retrieval(inputs):
    items=inputs.get('knowledge_items');queries=inputs.get('facet_queries')
    if not isinstance(items,list) or not 1<=len(items)<=1000:
        raise ValueError('knowledge_items requires1..1000 objects')
    if not isinstance(queries,list) or len(queries)>100:
        raise ValueError('facet_queries requires0..100 objects')
    index={};ids=set();records={}
    for row in items:
        if not isinstance(row,dict):raise ValueError('knowledge item object required')
        key=label(row.get('id'),'item id');facets=row.get('facets')
        if key in ids:raise ValueError('duplicate item id')
        ids.add(key)
        if not isinstance(facets,dict) or not 1<=len(facets)<=32:raise ValueError('1..32 item facets required')
        for name,values in facets.items():
            label(name,'facet name')
            if not isinstance(values,list) or not 1<=len(values)<=32:raise ValueError('1..32 facet values required')
            for value in values:
                label(value,'facet value');index.setdefault(name,{}).setdefault(value,set()).add(key)
        records[key]=row
    answers=[]
    for q in queries:
        if not isinstance(q,dict):raise ValueError('facet query object required')
        ident=label(q.get('id'),'query id');filters=q.get('filters');exclude=q.get('exclude',{})
        if not isinstance(filters,dict) or len(filters)>32 or not isinstance(exclude,dict) or len(exclude)>32:
            raise ValueError('bounded query filters and exclusion dictionaries required')
        matches=set(ids)
        # Within one facet, alternatives are OR; across facets, intersection.
        for name,values in filters.items():
            label(name,'query facet')
            if not isinstance(values,list) or not 1<=len(values)<=32:raise ValueError('bounded nonempty filter values required')
            union=set()
            for value in values:
                label(value,'query value');union.update(index.get(name,{}).get(value,set()))
            matches &= union
        for name,values in exclude.items():
            label(name,'exclude facet')
            if not isinstance(values,list) or len(values)>32:raise ValueError('bounded exclusions required')
            for value in values:
                label(value,'exclude value');matches-=index.get(name,{}).get(value,set())
        answers.append({'query_id':ident,'matching_item_ids':sorted(matches),'matching_count':len(matches)})
    return {'kind':'exact_supplied_facet_index','item_count':len(ids),'queries':answers,
            'facet_index':{name:{value:sorted(keys)for value,keys in sorted(values.items())}
                           for name,values in sorted(index.items())},
            'source_truth_verified':False,'semantic_labels_learned':False}


def graph_paths(inputs):
    nodes=inputs.get('nodes');edges=inputs.get('typed_edges');queries=inputs.get('graph_queries')
    if not isinstance(nodes,list) or not 1<=len(nodes)<=256 or len(set(nodes))!=len(nodes):raise ValueError('1..256 unique graph nodes required')
    for node in nodes:label(node,'node')
    if not isinstance(edges,list) or len(edges)>2048 or not isinstance(queries,list) or len(queries)>100:
        raise ValueError('bounded edges and queries required')
    adjacency={n:[]for n in nodes};edge_ids=set()
    for i,edge in enumerate(edges):
        if not isinstance(edge,dict):raise ValueError('edge object required')
        a=edge.get('from');b=edge.get('to');kind=label(edge.get('type'),'edge type');key=edge.get('id',str(i))
        label(key,'edge id')
        if a not in adjacency or b not in adjacency or key in edge_ids:raise ValueError('known endpoints and unique edge ids required')
        edge_ids.add(key);adjacency[a].append({'from':a,'to':b,'type':kind,'id':key})
    answers=[]
    for q in queries:
        if not isinstance(q,dict):raise ValueError('graph query object required')
        start=q.get('from');target=q.get('to');allowed=q.get('types');limit=q.get('max_hops',len(nodes)-1)
        if start not in adjacency or target not in adjacency or type(limit)is not int or not 0<=limit<=255:
            raise ValueError('known query endpoints and max_hops integer0..255 required')
        if allowed is not None:
            if not isinstance(allowed,list) or len(allowed)>32:raise ValueError('bounded edge type filter required')
            for kind in allowed:label(kind,'query edge type')
            allowed=set(allowed)
        queue=deque([(start,[])]);seen={start};found=None
        while queue:
            node,path=queue.popleft()
            if node==target:found=path;break
            if len(path)>=limit:continue
            for edge in sorted(adjacency[node],key=lambda e:(e['to'],e['type'],e['id'])):
                if edge['to']in seen or allowed is not None and edge['type']not in allowed:continue
                seen.add(edge['to']);queue.append((edge['to'],[*path,edge]))
        answers.append({'from':start,'to':target,'reachable':found is not None,'shortest_hops':None if found is None else len(found),
                        'edge_path':found,'max_hops':limit,'direct_relation_inferred':False})
    return {'kind':'typed_directed_graph_breadth_first_paths','queries':answers,
            'source_truth_verified':False,'unstated_relation_inference':False,
            'path_is_causality_proof':False}
