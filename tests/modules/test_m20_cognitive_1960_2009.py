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
