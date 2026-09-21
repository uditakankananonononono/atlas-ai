"""Deterministic cognitive/AI reference engines for owner ledger rows 1960-2009."""
from __future__ import annotations
import math,random,statistics
from collections import Counter,defaultdict
NAMES="""graph_of_thought self_consistency retrieval_augmented_generation vector_databases embeddings semantic_search knowledge_graphs ontologies linked_data knowledge_representation automated_reasoning theorem_proving symbolic_ai neuro_symbolic_ai hybrid_ai cognitive_computing affective_computing emotion_recognition sentiment_analysis opinion_mining social_computing crowdsourcing human_computation collective_intelligence swarm_intelligence evolutionary_computation genetic_algorithms genetic_programming artificial_life digital_twins simulation modeling optimization operations_research decision_science systems_science complexity_science network_science chaos_theory fractal_geometry self_organization emergence adaptation evolution co_evolution symbiosis autopoiesis cybernetics second_order_cybernetics metacognition""".split()
ROWS=dict(zip(NAMES,range(1960,2010)))
def _vec(d,k,n=1):
 v=d.get(k)
 if not isinstance(v,list) or len(v)<n or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in v):raise ValueError(f"{k} requires {n}+ finite numbers")
 return [float(x) for x in v]
def _num(d,k,default=None):
 v=d.get(k,default)
 if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v):raise ValueError(f"{k} must be finite")
 return float(v)
def _cos(a,b):
 if len(a)!=len(b) or not a:raise ValueError("vectors must be non-empty and aligned")
 den=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b));return sum(x*y for x,y in zip(a,b))/den if den else 0

def run(method,data,seed=0):
 if method not in ROWS:raise ValueError(f"unsupported cognitive method {method}")
 rng=random.Random(seed); limits=["Reference-scale, deterministic decision support on supplied data; no external retrieval, execution, or claim of human cognition."]
 if method=="graph_of_thought":
  nodes=data.get("nodes");edges=data.get("edges");start=data.get("start");goal=data.get("goal")
  if not isinstance(nodes,list) or not nodes or start not in nodes or goal not in nodes:raise ValueError("nodes/start/goal required")
  if not isinstance(edges,list):raise ValueError("edges must be a list")
  known=set(nodes);adj=defaultdict(list)
  for e in edges:
   if not isinstance(e,(list,tuple)) or len(e)!=3:raise ValueError("each edge must be [from,to,cost]")
   a,b,c=e
   if a not in known or b not in known:raise ValueError("edge references undeclared node")
   c=float(c)
   if not math.isfinite(c) or c<0:raise ValueError("edge costs must be finite and non-negative for shortest-path search")
   adj[a].append((b,c))
  dist={start:0.0};prev={};todo=set(nodes)
  while todo:
   u=min(todo,key=lambda x:dist.get(x,math.inf))
   if dist.get(u,math.inf)==math.inf:break
   todo.remove(u)
   for v,c in adj[u]:
    if v in todo and dist[u]+c<dist.get(v,math.inf):dist[v]=dist[u]+c;prev[v]=u
  if goal in dist:
   path=[];u=goal
   while u in prev:path.append(u);u=prev[u]
   path.append(start);path=path[::-1];cost=dist[goal]
  else:path=None;cost=math.inf
  out={"best_path":path,"cost":cost,"reachable":goal in dist,"evaluated_nodes":len(dist)}
 elif method=="self_consistency":
  answers=data.get("answers")
  if not isinstance(answers,list) or not answers:raise ValueError("answers required")
  c=Counter(map(str,answers));answer,votes=c.most_common(1)[0];out={"consensus":answer,"vote_share":votes/len(answers),"distribution":dict(c)}
 elif method=="retrieval_augmented_generation":
  q=_vec(data,"query_embedding");docs=data.get("documents");k=int(_num(data,"top_k",3))
  if not isinstance(docs,list) or not docs:raise ValueError("documents required")
  ranked=sorted([{"id":d["id"],"text":d.get("text",""),"score":_cos(q,list(map(float,d["embedding"])))} for d in docs],key=lambda x:x["score"],reverse=True)[:k];out={"retrieved":ranked,"grounding_context":"\n".join(x["text"] for x in ranked)};limits += ["Returns context, not an ungrounded generated answer."]
 elif method=="vector_databases":
  q=_vec(data,"query");vectors=data.get("vectors")
  if not isinstance(vectors,dict) or not vectors:raise ValueError("vectors mapping required")
  out={"nearest":sorted(({"id":k,"cosine":_cos(q,list(map(float,v))) } for k,v in vectors.items()),key=lambda x:x["cosine"],reverse=True)}
 elif method=="embeddings":
  tokens=data.get("tokens");dim=int(_num(data,"dimensions",8))
  if not isinstance(tokens,list) or not tokens or dim<1:raise ValueError("tokens and positive dimensions required")
  vals=[]
  for token in tokens:
   v=[0.0]*dim
   for i,ch in enumerate(str(token).lower()):v[(ord(ch)+i)%dim]+=1
   z=math.sqrt(sum(x*x for x in v)) or 1;vals.append([x/z for x in v])
  out={"embeddings":vals,"dimensions":dim,"model":"deterministic_character_hash"};limits += ["Hash embedding is transparent and local, not a pretrained semantic model."]
 elif method=="semantic_search":
  q=_vec(data,"query_embedding");items=data.get("items");ranked=sorted([{"id":x["id"],"score":_cos(q,list(map(float,x["embedding"])))} for x in items],key=lambda x:x["score"],reverse=True);out={"results":ranked}
 elif method in {"knowledge_graphs","linked_data"}:
  triples=data.get("triples");subject=data.get("subject")
  if not isinstance(triples,list) or any(not isinstance(t,(list,tuple)) or len(t)!=3 for t in triples):raise ValueError("triples must be [subject,predicate,object] lists")
  matched=[{"subject":s,"predicate":p,"object":o} for s,p,o in triples if subject is None or s==subject];out={"triples":matched,"entity_count":len(set(x for t in triples for x in (t[0],t[2]))),"predicate_count":len(set(t[1] for t in triples))}
 elif method=="ontologies":
  parent=data.get("parent_map");concept=data.get("concept")
  if not isinstance(parent,dict) or concept not in parent:raise ValueError("parent_map and concept required")
  chain=[concept];seen=set()
  while chain[-1] in parent and parent[chain[-1]] is not None:
   if chain[-1] in seen:raise ValueError("ontology cycle")
   seen.add(chain[-1]);chain.append(parent[chain[-1]])
  out={"concept":concept,"ancestor_chain":chain[1:],"depth":len(chain)-1}
 elif method in {"knowledge_representation","symbolic_ai"}:
  facts=set(data.get("facts",[]));rules=data.get("rules",[]);changed=True
  while changed:
   changed=False
   for r in rules:
    if set(r["if"])<=facts and r["then"] not in facts:facts.add(r["then"]);changed=True
  out={"closure":sorted(facts),"inferred_count":len(facts)-len(data.get("facts",[]))}
 elif method in {"automated_reasoning","theorem_proving"}:
  clauses=[set(x) for x in data.get("clauses",[])];query=data.get("query")
  if not clauses or not query:raise ValueError("clauses and query required")
  known=set().union(*clauses);out={"query":query,"proved":query in known or any({"if","then"}<=set(r) and query in r for r in data.get("rules",[])),"proof_basis":[sorted(x) for x in clauses]};limits += ["Finite propositional proof check, not complete first-order theorem proving."]
 elif method in {"neuro_symbolic_ai","hybrid_ai"}:
  probs=data.get("probabilities");rules=data.get("rules")
  if not isinstance(probs,dict) or not isinstance(rules,list):raise ValueError("probabilities and rules required")
  scores=dict((k,float(v)) for k,v in probs.items())
  for r in rules:scores[r["then"]]=max(scores.get(r["then"],0),min(scores.get(x,0) for x in r["if"]))
  out={"combined_scores":scores,"accepted":[k for k,v in scores.items() if v>=_num(data,"threshold",.5)]}
 elif method in {"cognitive_computing","metacognition"}:
  tasks=data.get("tasks")
  if not isinstance(tasks,list) or not tasks:raise ValueError("tasks required")
  rows=[{"task":x["task"],"confidence":float(x["confidence"]),"correct":bool(x.get("correct"))} for x in tasks];brier=sum((r["confidence"]-int(r["correct"]))**2 for r in rows)/len(rows);out={"calibration_brier":brier,"mean_confidence":statistics.mean(x["confidence"] for x in rows),"accuracy":statistics.mean(x["correct"] for x in rows),"review_tasks":[x["task"] for x in rows if x["confidence"]<_num(data,"review_threshold",.6)]}
 elif method in {"affective_computing","emotion_recognition"}:
  signals=data.get("signals")
  if not isinstance(signals,dict):raise ValueError("signals required")
  arousal=float(signals.get("arousal",0));valence=float(signals.get("valence",0));label=("excited" if valence>=0 else "distressed") if arousal>=.5 else ("content" if valence>=0 else "sad");out={"valence":valence,"arousal":arousal,"quadrant":label,"confidence":min(1,(abs(valence)+abs(arousal-.5))/1.5)};limits += ["Signal quadrant is not a diagnosis or certain reading of emotion."]
 elif method in {"sentiment_analysis","opinion_mining"}:
  texts=data.get("texts");pos=set(data.get("positive_words",["good","love","great"]));neg=set(data.get("negative_words",["bad","hate","poor"]))
  if not isinstance(texts,list):raise ValueError("texts required")
  scored=[]
  for t in texts:
   words=str(t).lower().split();s=sum(w.strip(".,!") in pos for w in words)-sum(w.strip(".,!") in neg for w in words);scored.append({"text":t,"score":s,"label":"positive" if s>0 else "negative" if s<0 else "neutral"})
  out={"opinions":scored,"net_sentiment":sum(x["score"] for x in scored)}
 elif method=="social_computing":
  edges=data.get("edges")
  if not isinstance(edges,list) or any(not isinstance(e,(list,tuple)) or len(e)!=2 for e in edges):raise ValueError("edges must be a list of [a,b] pairs")
  degree=Counter()
  for a,b in edges:degree[a]+=1;degree[b]+=1
  out={"degree_centrality":dict(degree),"most_connected":degree.most_common(1)[0][0] if degree else None,"edge_count":len(edges)}
 elif method in {"crowdsourcing","human_computation","collective_intelligence"}:
  responses=data.get("responses")
  if not isinstance(responses,list) or not responses:raise ValueError("responses required")
  if any(not isinstance(x,dict) or "answer" not in x for x in responses):raise ValueError("each response requires an answer")
  tally=defaultdict(float)
  for x in responses:tally[str(x["answer"])]+=float(x.get("weight",1))
  total=sum(tally.values());winner=max(tally,key=tally.get);out={"aggregate_answer":winner,"weighted_support":tally[winner]/total,"weighted_tally":dict(tally),"contributors":len(responses)}
 elif method in {"swarm_intelligence","evolutionary_computation","genetic_algorithms"}:
  population=_vec(data,"population",2);target=_num(data,"target");generations=int(_num(data,"generations",5));sigma=_num(data,"mutation_sigma",1)
  history=[]
  for _ in range(generations):
   population=sorted(population,key=lambda x:abs(x-target));best=population[0];history.append(best);population=[best]+[best+rng.gauss(0,sigma) for _ in population[1:]]
  out={"best_candidate":min(population,key=lambda x:abs(x-target)),"best_distance":min(abs(x-target) for x in population),"history":history}
 elif method=="genetic_programming":
  candidates=data.get("candidate_coefficients");x=_vec(data,"x");y=_vec(data,"y")
  if not isinstance(candidates,list) or not candidates or len(x)!=len(y):raise ValueError("non-empty candidate coefficients and aligned data required")
  scored=[]
  for c in candidates:
   pred=[sum(float(a)*z**i for i,a in enumerate(c)) for z in x];scored.append((sum((a-b)**2 for a,b in zip(pred,y))/len(y),c))
  best=min(scored,key=lambda t:t[0]);out={"best_coefficients":best[1],"mse":best[0]}
 elif method in {"artificial_life","self_organization","emergence","adaptation","evolution","co_evolution","symbiosis","autopoiesis"}:
  state=_vec(data,"state",2);steps=int(_num(data,"steps",10));coupling=_num(data,"coupling",.2);trajectory=[state[:]]
  for _ in range(steps):
   mean=statistics.mean(state);state=[min(1,max(0,x+coupling*(mean-x)+(_num(data,"growth",.05)*x*(1-x) if method in {"adaptation","evolution","co_evolution","autopoiesis"} else 0))) for x in state];trajectory.append(state[:])
  out={"final_state":state,"variance_reduction":statistics.pvariance(trajectory[0])-statistics.pvariance(state),"order_parameter":1-statistics.pvariance(state),"trajectory":trajectory}
 elif method=="digital_twins":
  observed=_vec(data,"observed");simulated=_vec(data,"simulated")
  if len(observed)!=len(simulated):raise ValueError("aligned series required")
  residual=[a-b for a,b in zip(observed,simulated)];out={"residuals":residual,"rmse":math.sqrt(statistics.mean(x*x for x in residual)),"bias":statistics.mean(residual),"synchronized_state":observed[-1]}
 elif method in {"simulation","modeling"}:
  initial=_num(data,"initial");rate=_num(data,"rate");steps=int(_num(data,"steps",10));vals=[initial]
  for _ in range(steps):vals.append(vals[-1]*(1+rate))
  out={"trajectory":vals,"terminal":vals[-1],"model":"discrete_exponential"}
 elif method in {"optimization","operations_research"}:
  values=_vec(data,"values");costs=_vec(data,"costs");budget=_num(data,"budget")
  if len(values)!=len(costs):raise ValueError("values and costs align")
  chosen=[];remaining=budget
  for i in sorted(range(len(values)),key=lambda i:values[i]/costs[i],reverse=True):
   if costs[i]<=remaining:chosen.append(i);remaining-=costs[i]
  out={"chosen_indices":chosen,"objective_value":sum(values[i] for i in chosen),"used_budget":budget-remaining,"method":"greedy_integer_knapsack"};limits += ["Greedy solution is feasible but not guaranteed globally optimal."]
 elif method=="decision_science":
  options=data.get("options");weights=_vec(data,"weights")
  if not isinstance(options,list) or not options or any(not isinstance(x,dict) or "name" not in x or not isinstance(x.get("criteria"),list) for x in options):raise ValueError("options require name and criteria list")
  if any(len(x["criteria"])!=len(weights) for x in options):raise ValueError("each option's criteria must align with weights")
  scored=[{"name":x["name"],"score":sum(float(a)*b for a,b in zip(x["criteria"],weights))} for x in options];out={"ranked":sorted(scored,key=lambda x:x["score"],reverse=True)}
 elif method in {"systems_science","complexity_science","network_science"}:
  nodes=data.get("nodes");edges=data.get("edges");deg=Counter()
  for a,b in edges:deg[a]+=1;deg[b]+=1
  n=len(nodes);out={"nodes":n,"edges":len(edges),"density":2*len(edges)/(n*(n-1)) if n>1 else 0,"degree_distribution":dict(deg),"degree_variance":statistics.pvariance([deg[x] for x in nodes]) if nodes else 0}
 elif method=="chaos_theory":
  x=_num(data,"initial");r=_num(data,"r",3.9);steps=int(_num(data,"steps",50));eps=_num(data,"epsilon",1e-8);y=x+eps;sep=[]
  for _ in range(steps):x=r*x*(1-x);y=r*y*(1-y);sep.append(abs(y-x))
  valid=[math.log(s/eps) for s in sep if s>0];out={"trajectory_separation":sep,"finite_time_lyapunov_proxy":statistics.mean(valid)/steps if valid else -math.inf}
 elif method=="fractal_geometry":
  scales=_vec(data,"scales",2);counts=_vec(data,"box_counts",2)
  if len(scales)!=len(counts) or any(x<=0 for x in scales+counts):raise ValueError("positive aligned scales/counts required")
  x=[math.log(1/s) for s in scales];y=[math.log(c) for c in counts];mx,my=statistics.mean(x),statistics.mean(y);slope=sum((a-mx)*(b-my) for a,b in zip(x,y))/sum((a-mx)**2 for a in x);out={"box_counting_dimension":slope,"points":len(x)}
 elif method=="cybernetics":
  target=_num(data,"target");state=_num(data,"state");gain=_num(data,"gain",.5);steps=int(_num(data,"steps",10));traj=[state]
  for _ in range(steps):state+=gain*(target-state);traj.append(state)
  out={"trajectory":traj,"final_error":target-state,"feedback_gain":gain}
 elif method=="second_order_cybernetics":
  target=_num(data,"target");state=_num(data,"state");gain=_num(data,"gain",.2);learn=_num(data,"learning_rate",.1);traj=[]
  for _ in range(int(_num(data,"steps",10))):
   err=target-state;state+=gain*err;gain=max(0,min(1,gain+learn*abs(err)/(1+abs(err))));traj.append({"state":state,"gain":gain,"error":target-state})
  out={"trajectory":traj,"observer_adjusted_gain":gain,"final_error":target-state};limits += ["Adaptive controller is a second-order cybernetics illustration, not evidence of consciousness."]
 else:raise AssertionError(method)
 out["method_limits"]=limits
 return {"method":method,"feature_row":ROWS[method],"inputs":data,"seed":seed,"output":out}
