import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m20_general_cognitive_worker.cognitive_1960_2009 import ROWS,run
C={
"graph_of_thought":{"nodes":["a","b","c"],"edges":[["a","b",1],["b","c",1],["a","c",5]],"start":"a","goal":"c"},"self_consistency":{"answers":["x","x","y"]},"retrieval_augmented_generation":{"query_embedding":[1,0],"documents":[{"id":"a","text":"A","embedding":[1,0]},{"id":"b","text":"B","embedding":[0,1]}]},"vector_databases":{"query":[1,0],"vectors":{"a":[1,0],"b":[0,1]}},"embeddings":{"tokens":["cat","dog"]},"semantic_search":{"query_embedding":[1,0],"items":[{"id":"a","embedding":[1,0]},{"id":"b","embedding":[0,1]}]},"knowledge_graphs":{"triples":[["a","is","b"]]},"ontologies":{"parent_map":{"dog":"mammal","mammal":"animal","animal":None},"concept":"dog"},"linked_data":{"triples":[["urn:a","type","urn:b"]]},"knowledge_representation":{"facts":["a"],"rules":[{"if":["a"],"then":"b"}]},"automated_reasoning":{"clauses":[["p"],["q"]],"query":"q"},"theorem_proving":{"clauses":[["p"]],"query":"p"},"symbolic_ai":{"facts":["a"],"rules":[{"if":["a"],"then":"b"}]},"neuro_symbolic_ai":{"probabilities":{"a":.9},"rules":[{"if":["a"],"then":"b"}]},"hybrid_ai":{"probabilities":{"a":.9},"rules":[{"if":["a"],"then":"b"}]},
"cognitive_computing":{"tasks":[{"task":"a","confidence":.8,"correct":True}]},"affective_computing":{"signals":{"arousal":.8,"valence":.7}},"emotion_recognition":{"signals":{"arousal":.2,"valence":-.7}},"sentiment_analysis":{"texts":["good great","bad"]},"opinion_mining":{"texts":["love it"]},"social_computing":{"edges":[["a","b"],["a","c"]]},
"genetic_programming":{"candidate_coefficients":[[0,1],[1,2]],"x":[1,2],"y":[1,2]},"digital_twins":{"observed":[1,2,3],"simulated":[1,2,2]},"simulation":{"initial":1,"rate":.1},"modeling":{"initial":1,"rate":.1},"optimization":{"values":[10,8],"costs":[5,3],"budget":5},"operations_research":{"values":[10,8],"costs":[5,3],"budget":5},"decision_science":{"weights":[.6,.4],"options":[{"name":"a","criteria":[1,.5]},{"name":"b","criteria":[.5,1]}]},"systems_science":{"nodes":["a","b","c"],"edges":[["a","b"],["b","c"]]},"complexity_science":{"nodes":["a","b","c"],"edges":[["a","b"],["b","c"]]},"network_science":{"nodes":["a","b","c"],"edges":[["a","b"],["b","c"]]},"chaos_theory":{"initial":.2},"fractal_geometry":{"scales":[.5,.25,.125],"box_counts":[2,4,8]},"cybernetics":{"target":1,"state":0},"second_order_cybernetics":{"target":1,"state":0},"metacognition":{"tasks":[{"task":"a","confidence":.8,"correct":True},{"task":"b","confidence":.3,"correct":False}]}}
for m in ["crowdsourcing","human_computation","collective_intelligence"]:C[m]={"responses":[{"answer":"a"},{"answer":"a"},{"answer":"b"}]}
for m in ["swarm_intelligence","evolutionary_computation","genetic_algorithms"]:C[m]={"population":[0,5,10],"target":4,"generations":3}
for m in ["artificial_life","self_organization","emergence","adaptation","evolution","co_evolution","symbiosis","autopoiesis"]:C[m]={"state":[.1,.5,.9],"steps":3}

def test_all_50_rows_have_specific_deterministic_evidence():
 assert set(C)==set(ROWS) and sorted(ROWS.values())==list(range(1960,2010))
 for m,d in C.items():
  r=run(m,d,7);assert r["feature_row"]==ROWS[m] and r["inputs"]==d and r["output"]["method_limits"] and r==run(m,d,7)

def test_concept_specific_results():
 assert run("graph_of_thought",C["graph_of_thought"])["output"]["best_path"]==["a","b","c"]
 assert run("retrieval_augmented_generation",C["retrieval_augmented_generation"])["output"]["retrieved"][0]["id"]=="a"
 assert run("knowledge_representation",C["knowledge_representation"])["output"]["closure"]==["a","b"]
 assert run("fractal_geometry",C["fractal_geometry"])["output"]["box_counting_dimension"]==pytest.approx(1)
 assert run("cybernetics",C["cybernetics"])["output"]["final_error"]<.01

def test_validation_and_mounted_surface():
 with pytest.raises(ValueError):run("vector_databases",{"query":[1],"vectors":{}})
 c=TestClient(app);h={"X-Tenant-ID":"cog","X-Actor-ID":"tester"}
 assert len(c.get("/api/v1/api/modules/20/cognitive-1960-2009/methods",headers=h).json())==50
 r=c.post("/api/v1/api/modules/20/cognitive-1960-2009/analyze",headers=h,json={"method":"metacognition","data":C["metacognition"]});assert r.status_code==200 and r.json()["feature_row"]==2009
 assert c.post("/api/v1/api/modules/20/cognitive-1960-2009/analyze",headers=h,json={"method":"bad"}).status_code==422

# --- audit family D: distinctive per-row value assertions, failure paths, tenant boundary
def _out(m):return run(m,C[m],7)["output"]
def test_distinctive_value_per_row():
 assert _out("graph_of_thought")["cost"]==2 and _out("graph_of_thought")["reachable"] is True
 assert _out("self_consistency")["consensus"]=="x" and _out("self_consistency")["vote_share"]==pytest.approx(2/3)
 assert _out("retrieval_augmented_generation")["retrieved"][0]["score"]==pytest.approx(1)
 assert _out("vector_databases")["nearest"][0]["id"]=="a"
 e=_out("embeddings");assert e["dimensions"]==8 and all(abs(sum(v*v for v in x)**.5-1)<1e-9 for x in e["embeddings"])
 assert _out("semantic_search")["results"][0]["id"]=="a"
 assert _out("knowledge_graphs")["entity_count"]==2 and _out("knowledge_graphs")["predicate_count"]==1
 assert _out("ontologies")["ancestor_chain"]==["mammal","animal"] and _out("ontologies")["depth"]==2
 assert _out("linked_data")["triples"][0]["predicate"]=="type"
 assert _out("knowledge_representation")["inferred_count"]==1 and _out("knowledge_representation")["closure"]==["a","b"]
 assert _out("automated_reasoning")["proved"] is True and _out("theorem_proving")["proved"] is True
 assert _out("symbolic_ai")["closure"]==["a","b"]
 assert _out("neuro_symbolic_ai")["accepted"]==["a","b"] and _out("hybrid_ai")["combined_scores"]["b"]==pytest.approx(.9)
 assert _out("cognitive_computing")["calibration_brier"]==pytest.approx(.04)
 assert _out("affective_computing")["quadrant"]=="excited" and _out("emotion_recognition")["quadrant"]=="sad"
 s=_out("sentiment_analysis");assert s["net_sentiment"]==1 and [x["label"] for x in s["opinions"]]==["positive","negative"]
 assert _out("opinion_mining")["opinions"][0]["label"]=="positive"
 assert _out("social_computing")["most_connected"]=="a" and _out("social_computing")["edge_count"]==2
 for m in ["crowdsourcing","human_computation","collective_intelligence"]:
  o=_out(m);assert o["aggregate_answer"]=="a" and o["weighted_support"]==pytest.approx(2/3) and o["contributors"]==3
 for m in ["swarm_intelligence","evolutionary_computation","genetic_algorithms"]:
  o=_out(m);assert o["best_distance"]<=1 and len(o["history"])==3
 assert _out("genetic_programming")["best_coefficients"]==[0,1] and _out("genetic_programming")["mse"]==pytest.approx(0)
 d=_out("digital_twins");assert d["rmse"]==pytest.approx((1/3)**.5) and d["bias"]==pytest.approx(1/3)
 assert _out("simulation")["terminal"]==pytest.approx(1.1**10) and _out("modeling")["terminal"]==pytest.approx(1.1**10)
 o=_out("optimization");assert o["chosen_indices"]==[1] and o["objective_value"]==8 and o["used_budget"]==3
 assert _out("operations_research")["objective_value"]==8
 r=_out("decision_science")["ranked"];assert r[0]["name"]=="a" and r[0]["score"]==pytest.approx(.8)
 for m in ["systems_science","complexity_science","network_science"]:
  o=_out(m);assert o["density"]==pytest.approx(2/3) and o["degree_distribution"]=={"a":1,"b":2,"c":1}
 assert len(_out("chaos_theory")["trajectory_separation"])==50
 assert _out("fractal_geometry")["box_counting_dimension"]==pytest.approx(1)
 assert _out("cybernetics")["final_error"]<.01 and len(_out("second_order_cybernetics")["trajectory"])==10
 m=_out("metacognition");assert m["review_tasks"]==["b"] and m["accuracy"]==pytest.approx(.5) and m["calibration_brier"]==pytest.approx(.065)
 for m in ["artificial_life","self_organization","emergence","adaptation","evolution","co_evolution","symbiosis","autopoiesis"]:
  o=_out(m);assert len(o["trajectory"])==4 and 0<=o["order_parameter"]<=1
def test_graph_of_thought_unreachable_and_edge_validation():
 o=run("graph_of_thought",{"nodes":["a","b"],"edges":[],"start":"a","goal":"b"})["output"];assert o["best_path"] is None and o["reachable"] is False
 with pytest.raises(ValueError,match="undeclared"):run("graph_of_thought",{"nodes":["a","b"],"edges":[["a","z",1]],"start":"a","goal":"b"})
 with pytest.raises(ValueError,match="non-negative"):run("graph_of_thought",{"nodes":["a","b"],"edges":[["a","b",-1]],"start":"a","goal":"b"})
def test_failure_paths_raise_value_error():
 with pytest.raises(ValueError):run("self_consistency",{"answers":[]})
 with pytest.raises(ValueError,match="cycle"):run("ontologies",{"parent_map":{"a":"b","b":"a"},"concept":"a"})
 with pytest.raises(ValueError,match="align"):run("decision_science",{"weights":[1,1],"options":[{"name":"a","criteria":[1]}]})
 with pytest.raises(ValueError,match="pairs"):run("social_computing",{"edges":[["a"]]})
 with pytest.raises(ValueError,match="answer"):run("crowdsourcing",{"responses":[{"weight":1}]})
 with pytest.raises(ValueError,match="non-empty"):run("genetic_programming",{"candidate_coefficients":[],"x":[1],"y":[1]})
 with pytest.raises(ValueError,match="finite"):run("vector_databases",{"query":[float("nan"),0],"vectors":{"a":[1,0]}})
 with pytest.raises(ValueError,match="triples"):run("knowledge_graphs",{"triples":[["a","is"]]})
 with pytest.raises(ValueError,match="aligned"):run("digital_twins",{"observed":[1],"simulated":[1,2]})
 with pytest.raises(ValueError,match="unsupported"):run("not_a_method",{})
def test_tenant_boundary_enforced_on_mounted_surface(monkeypatch, oidc_auth_headers):
 from app.main import app
 monkeypatch.setenv("ATLAS_ENV","production")
 c=TestClient(app)
 assert c.get("/api/v1/api/modules/20/cognitive-1960-2009/methods").status_code==401
 assert c.post("/api/v1/api/modules/20/cognitive-1960-2009/analyze",json={"method":"self_consistency","data":{"answers":["a"]}}).status_code==401
 h=oidc_auth_headers("tenant-a", "tester")
 assert c.get("/api/v1/api/modules/20/cognitive-1960-2009/methods",headers=h).status_code==200
 assert c.post("/api/v1/api/modules/20/cognitive-1960-2009/analyze",headers=h,json={"method":"self_consistency","data":{"answers":["a","a"]}}).status_code==200
