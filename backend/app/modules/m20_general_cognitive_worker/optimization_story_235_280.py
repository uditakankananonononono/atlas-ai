"""Executable optimization and narrative analysis for ledger rows 235-280.

The rebuilt numerical operators run actual restricted algorithms and free solvers.
Observed learning uses caller feedback; narrative branches remain supplied-text
analysis/templates, not generated-model breadth. No invented observation evidence.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from math import exp, log, sqrt
import re
from typing import Any, Callable
from .admm import solve_quadratic_l1
from .strategic_learning import hedge, regret_matching, game_regret_matching, fictitious_play
from .bandits import epsilon_greedy, contextual_ucb, thompson, ucb
from .learning_optimization import bilevel, stochastic_approximation, online_regression
from .conic_solvers import semidefinite, second_order, geometric
from .lp_solvers import cutting_planes, branch_and_bound, column_generation, benders, lagrangian_binary_knapsack, fractional_linear
from .convex_solvers import dual_decomposition, coordinate_descent, proximal_gradient, frank_wolfe

class WorkbenchError(ValueError):
    pass

ROWS={235:'Dual Decomposition',236:'ADMM',237:'Coordinate Descent',238:'Proximal Methods',239:'Frank-Wolfe Algorithm',240:'Cutting Plane Methods',241:'Branch and Bound',242:'Column Generation',243:'Benders Decomposition',244:'Lagrangian Relaxation',245:'Semidefinite Programming',246:'Second-Order Cone Programming',247:'Geometric Programming',248:'Fractional Programming',249:'Bilevel Optimization',250:'Stochastic Approximation',251:'Online Learning',252:'Bandit Algorithms',253:'Contextual Bandits',254:'Thompson Sampling',255:'Upper Confidence Bound',256:'Expert Advice Aggregation',257:'Regret Minimization',258:'Game-Theoretic Learning',259:'Fictitious Play',260:'Novel Metaphor Generation',261:'Narrative Arc Construction',262:'Character Development',263:'Dialogue Writing',264:'Worldbuilding',265:'Plot Twist Design',266:'Foreshadowing Placement',267:'Tension Building',268:'Pacing Control',269:'Voice Development',270:'Genre Blending',271:'Trope Subversion',272:'Myth Creation',273:'Poetry Generation',274:'Songwriting',275:'Screenplay Formatting',276:'Stage Play Construction',277:'Comic Script Writing',278:'Interactive Fiction',279:'Game Narrative Design',280:'Visual Storyboarding'}
FAMILY={i:('optimization' if i<260 else 'story') for i in ROWS}
def slug(s:str)->str:return re.sub(r'[^a-z0-9]+','_',s.lower()).strip('_')
KEYS={slug(v):k for k,v in ROWS.items()}
def capabilities():return [{'row_id':i,'key':slug(n),'name':n,'family':FAMILY[i],'execution_kind':'restricted_optimization' if i<260 else 'supplied_text_diagnostics'} for i,n in ROWS.items()]

def _source(p):
    s=p.get('source')
    if not isinstance(s,dict) or not isinstance(s.get('title'),str) or not s['title'].strip() or not isinstance(s.get('url'),str) or not s['url'].startswith(('http://','https://')):
        raise WorkbenchError('source requires non-empty title and http(s) url')
    return {'title':s['title'].strip(),'url':s['url']}
def _nums(value,name,*,nonempty=True):
    if not isinstance(value,list) or (nonempty and not value):raise WorkbenchError(f'{name} must be a non-empty list')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) for x in value):raise WorkbenchError(f'{name} must contain numbers')
    return [float(x) for x in value]
def _matrix(value,name):
    if not isinstance(value,list) or not value or any(not isinstance(r,list) or not r for r in value):raise WorkbenchError(f'{name} must be a non-empty numeric matrix')
    rows=[_nums(r,name) for r in value]
    if len({len(r) for r in rows})!=1:raise WorkbenchError(f'{name} rows must have equal length')
    return rows
def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _mean(x):return sum(x)/len(x) if x else 0.0
def _variance(x):
    m=_mean(x);return _mean([(v-m)**2 for v in x])
def _confidence(values):return 1.0/(1.0+sqrt(_variance(values))) if values else 0.0

def _problem(p):
    c=_nums(p.get('objective'),'objective');x=_nums(p.get('initial'),'initial')
    if len(c)!=len(x):raise WorkbenchError('objective and initial dimensions differ')
    A=p.get('constraint_matrix',[]);b=p.get('bounds',[])
    if A:
        A=_matrix(A,'constraint_matrix');b=_nums(b,'bounds')
        if len(A)!=len(b) or any(len(r)!=len(x) for r in A):raise WorkbenchError('constraint dimensions differ')
    elif b:raise WorkbenchError('bounds require constraint_matrix')
    sense=p.get('constraint_sense',['<=']*len(A))
    if not isinstance(sense,list) or len(sense)!=len(A) or any(s not in ('<=','>=','=') for s in sense):raise WorkbenchError('constraint_sense must align and use <=, >=, or =')
    residual=[]
    for r,z,s in zip(A,b,sense):
        raw=_dot(r,x)-z; residual.append(raw if s=='<=' else -raw if s=='>=' else abs(raw))
    violations=[max(0.0,v) for v in residual]
    return c,x,A,b,sense,{'objective_value':_dot(c,x),'max_violation':max(violations,default=0.0),'violation_count':sum(v>1e-9 for v in violations),'feasible':not any(v>1e-9 for v in violations),'constraint_residuals':residual}

def _opt(row,p):
    solvers={235:dual_decomposition,237:coordinate_descent,238:proximal_gradient,239:frank_wolfe,240:cutting_planes,241:branch_and_bound,242:column_generation,243:benders,244:lagrangian_binary_knapsack,245:semidefinite,246:second_order,247:geometric,248:fractional_linear,249:bilevel,250:stochastic_approximation,251:online_regression,252:epsilon_greedy,253:contextual_ucb,254:thompson,255:ucb,256:hedge,257:regret_matching,258:game_regret_matching,259:fictitious_play}
    if row in solvers:
        try:return solvers[row](p)
        except (ValueError,KeyError,TypeError) as exc:raise WorkbenchError(str(exc)) from exc
    if row==236:
        try:return solve_quadratic_l1(p)
        except ValueError as exc:raise WorkbenchError(str(exc)) from exc
    raise WorkbenchError('unsupported optimizer row')

def _scenes(p):
    premise=p.get('premise')
    if not isinstance(premise,str) or not premise.strip():raise WorkbenchError('premise must be a non-empty string')
    raw=p.get('scenes')
    if not isinstance(raw,list) or not raw:raise WorkbenchError('scenes must be a non-empty list')
    out=[]
    for i,s in enumerate(raw):
        if not isinstance(s,dict) or not isinstance(s.get('text'),str) or not s['text'].strip():raise WorkbenchError(f'scenes[{i}].text must be non-empty')
        out.append({'text':s['text'].strip(),'tension':float(s.get('tension',0)),'duration':float(s.get('duration',1)),'character':s.get('character',''),'goal':s.get('goal',''),'outcome':s.get('outcome',''),'location':s.get('location','')})
    if any(s['duration']<=0 for s in out):raise WorkbenchError('scene duration must be positive')
    return premise.strip(),out

def _story(row,p):
    premise,ss=_scenes(p); words=[re.findall(r"[A-Za-z']+",s['text'].lower()) for s in ss]; flat=[w for z in words for w in z]
    tensions=[s['tension'] for s in ss]; durations=[s['duration'] for s in ss]; chars=[s['character'] for s in ss if s['character']]
    transitions=[tensions[i+1]-tensions[i] for i in range(len(ss)-1)]
    common={'metrics':{'scene_count':len(ss),'word_count':len(flat),'mean_tension':_mean(tensions),'scene_sample_count_is_not_confidence':True},'uncertainty':{'kind':'structural_heuristic','requires_human_editorial_review':True}}
    motifs=Counter(flat)
    H={
260:lambda:{'metaphors':[f"{p.get('target_domain','the premise')} is {p.get('source_domain','a tide')} because both {p.get('shared_structure','change under pressure')}"] ,'novelty_score':1/(1+sum(motifs[w] for w in set(re.findall(r'\w+',str(p.get('source_domain','')).lower()))))},
261:lambda:{'arc_shape':tensions,'peak_scene':tensions.index(max(tensions))+1,'resolution_drop':tensions[-2]-tensions[-1] if len(ss)>1 else 0,'causal_links':sum(bool(s['outcome'] and ss[i+1]['goal']) for i,s in enumerate(ss[:-1]))},
262:lambda:{'character_scene_counts':dict(Counter(chars)),'goal_changes':sum(ss[i]['goal']!=ss[i-1]['goal'] for i in range(1,len(ss))),'arc_delta':tensions[-1]-tensions[0]},
263:lambda:{'speaker_turns':dict(Counter(chars)),'question_rate':sum(s['text'].count('?') for s in ss)/max(1,len(flat)),'lexical_distinctness':len(set(flat))/max(1,len(flat))},
264:lambda:{'locations':sorted({s['location'] for s in ss if s['location']}),'location_continuity_breaks':sum(ss[i]['location']!=ss[i-1]['location'] for i in range(1,len(ss))),'repeated_world_terms':[w for w,n in motifs.items() if n>=2 and len(w)>5]},
265:lambda:{'reversal_scene':max(range(len(transitions)),key=lambda i:abs(transitions[i]))+2 if transitions else 1,'reversal_magnitude':max(map(abs,transitions),default=0),'seed_terms':[w for w,n in motifs.items() if n>1]},
266:lambda:{'motif_positions':{w:[i+1 for i,z in enumerate(words) if w in z] for w,n in motifs.items() if n>1},'payoff_candidates':[w for w,n in motifs.items() if n>1 and w in words[-1]]},
267:lambda:{'tension_curve':tensions,'escalation_ratio':sum(v>0 for v in transitions)/max(1,len(transitions)),'release_count':sum(v<0 for v in transitions),'peak':max(tensions)},
268:lambda:{'words_per_duration':[len(w)/d for w,d in zip(words,durations)],'pace_variance':_variance([len(w)/d for w,d in zip(words,durations)]),'slowest_scene':min(range(len(ss)),key=lambda i:len(words[i])/durations[i])+1},
269:lambda:{'lexical_diversity':len(set(flat))/max(1,len(flat)),'mean_sentence_words':len(flat)/max(1,sum(s['text'].count('.')+s['text'].count('!')+s['text'].count('?') for s in ss)),'dominant_words':motifs.most_common(5)},
270:lambda:{'genre_signals':{g:sum(str(g).lower() in s['text'].lower() for s in ss) for g in p.get('genres',[])},'transition_smoothness':1/(1+_mean(list(map(abs,transitions))))},
271:lambda:{'expectation_present':str(p.get('trope','')).lower() in ' '.join(flat),'subversion_scene':max(range(len(transitions)),key=lambda i:abs(transitions[i]))+2 if transitions else None,'retained_motif_count':sum(n>1 for n in motifs.values())},
272:lambda:{'origin_markers':sum(w in {'first','origin','born','created','before'} for w in flat),'ritual_markers':sum(w in {'ritual','sacred','offering','festival'} for w in flat),'variant_count':len(set(chars))},
273:lambda:{'line_count':sum(s['text'].count('\n')+1 for s in ss),'alliteration_pairs':sum(a[:1]==b[:1] for a,b in zip(flat,flat[1:])),'image_repetition':sum(n-1 for w,n in motifs.items() if len(w)>4 and n>1)},
274:lambda:{'section_labels':[s['goal'] for s in ss],'hook_repetitions':sum(' '.join(flat).count(str(p.get('hook','')).lower()) for _ in [0]) if p.get('hook') else 0,'rhyme_proxy':sum(a[-2:]==b[-2:] for a,b in zip(flat,flat[1:]))},
275:lambda:{'formatted_scenes':[{'heading':f"INT. {s['location'].upper() or 'UNSPECIFIED'} - DAY",'action':s['text'],'character':s['character'].upper()} for s in ss],'estimated_pages':round(len(flat)/180,2)},
276:lambda:{'acts':max(1,int(p.get('acts',3))),'location_changes':sum(ss[i]['location']!=ss[i-1]['location'] for i in range(1,len(ss))),'cast_size':len(set(chars)),'live_complexity':len(set(chars))*len(set(s['location'] for s in ss))},
277:lambda:{'panel_plan':[{'panel':i+1,'action':s['text'],'caption_words':len(words[i])} for i,s in enumerate(ss)],'overloaded_panels':[i+1 for i,w in enumerate(words) if len(w)>35],'page_turn_candidate':tensions.index(max(tensions))+1},
278:lambda:_interactive(ss,p),
279:lambda:{'quest_threads':dict(Counter(s['goal'] for s in ss if s['goal'])),'fail_forward_count':sum(bool(s['outcome']) for s in ss),'loop_alignment':sum(bool(s['goal'] and s['outcome']) for s in ss)/len(ss)},
280:lambda:{'shots':[{'shot_number':i+1,'framing':'close' if s['tension']>=_mean(tensions) else 'wide','action':s['text'],'duration':s['duration'],'location':s['location']} for i,s in enumerate(ss)],'continuity_breaks':sum(ss[i]['location']!=ss[i-1]['location'] and not p.get('allow_location_cuts',True) for i in range(1,len(ss))),'total_duration':sum(durations)},
    }
    out=H[row]();out.update(common);return out

def _interactive(ss,p):
    edges=p.get('choices',[])
    if not isinstance(edges,list) or any(not isinstance(e,dict) or not isinstance(e.get('from'),int) or not isinstance(e.get('to'),int) for e in edges):raise WorkbenchError('choices must contain integer from/to edges')
    n=len(ss)
    if any(e['from']<0 or e['from']>=n or e['to']<0 or e['to']>=n for e in edges):raise WorkbenchError('choice endpoint outside scenes')
    g=defaultdict(list)
    for e in edges:g[e['from']].append(e['to'])
    seen={0};q=deque([0])
    while q:
        for v in g[q.popleft()]:
            if v not in seen:seen.add(v);q.append(v)
    return {'reachable_scenes':sorted(i+1 for i in seen),'unreachable_scenes':sorted(i+1 for i in set(range(n))-seen),'dead_ends':sorted(i+1 for i in seen if not g[i]),'branch_count':sum(len(v)>1 for v in g.values())}

def execute(method,payload):
    row=KEYS.get(slug(str(method)))
    if row is None:raise WorkbenchError(f'unknown method: {method}')
    if not isinstance(payload,dict):raise WorkbenchError('payload must be object')
    result=_opt(row,payload) if row<260 else _story(row,payload)
    return {'row_id':row,'capability':ROWS[row],'family':FAMILY[row],'source':_source(payload),'result':result,'evaluation':{'algorithm_executed':row<260,'diagnostics_executed':row>=260,'named_generation_capability_executed':False if row>=260 else None,'review_checks':['convergence','feasibility','sensitivity'] if row<260 else ['continuity','pacing','originality']},'uncertainty':{'human_review_required':True,'drivers':['caller-supplied data','model assumptions','heuristic diagnostics']},'boundary':('Restricted optimization on supplied mathematical inputs; no universal optimizer claim.' if row<260 else 'Supplied-text diagnostics and template formatting only. Named story generation/development capability not executed. Lexical proxies are not novelty, originality or quality validation; no model-backed creative generation or rendered visual storyboard.')}
