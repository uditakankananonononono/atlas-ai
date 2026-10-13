# Knowledge organization and semantic-network computation

Rows873 and876 formerly echoed supplied grouping/one-hop adjacency. New optional
row873 knowledge_items+facet_queries inputs build an actual multi-valued facet
index and evaluate OR-within-facet, AND-across-facet and exclusions. New row876
graph_queries inputs compute typed directed multi-hop BFS paths, with bounded
hop limits, cycle handling and exact edge witnesses. Existing default outputs
remain compatible. No new route.117 tests passed with original row suite.

PARTIAL: labels and edges are supplied, not discovered or learned; paths do not
prove causality or unstated relation truth. No persistent graph ingestion, semantic
embedding discovery or UI. Existing full-row capability_executed=False retained.
