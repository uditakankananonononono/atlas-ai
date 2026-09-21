"""Row-specific reference implementations for emerging-capability feature rows 910-959.

Each of the fifty owner rows maps to its own method: a distinctive research/design
calculation or seeded algorithm with caller-supplied evidence, stated assumptions,
explicit method limits and a hard physical/biological non-execution boundary.
Nothing in this module fabricates hardware results, executes lab procedures,
actuates robots, authorizes self-replication or permits clinical use.
"""
from __future__ import annotations
import math, random

NAMES=['quantum_computing_application','quantum_algorithm_design','quantum_error_correction','quantum_machine_learning','quantum_simulation','quantum_cryptography','quantum_sensing','quantum_networking','neuromorphic_computing','spiking_neural_networks','memristor_computing','optical_computing','dna_computing','molecular_computing','biological_computing','swarm_intelligence','ant_colony_optimization','bee_algorithm','firefly_algorithm','cuckoo_search','bat_algorithm','wolf_pack_algorithm','whale_optimization','artificial_immune_systems','artificial_life','genetic_programming','grammatical_evolution','gene_expression_programming','evolutionary_strategies','neuroevolution','developmental_robotics','epigenetic_robotics','morphological_computation','soft_robotics','swarm_robotics','modular_robotics','self_reconfiguring_robots','self_replicating_robots','molecular_nanotechnology','programmable_matter','metamaterials','negative_index_materials','cloaking_technology','acoustic_metamaterials','thermal_metamaterials','mechanical_metamaterials','4d_printing','bioprinting','organ_printing','tissue_engineering']
ROWS={n:910+i for i,n in enumerate(NAMES)}
SUMMARIES={n:n.replace('_',' ').title() for n in NAMES}

class EmergingError(ValueError):
    """Invalid caller-supplied evidence for an emerging-capability method."""

def _f(x,name):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise EmergingError(f'{name} must be a finite number')
    return float(x)
def _pos(data,key,allow_zero=False):
    v=_f(data.get(key),key)
    if allow_zero:
        if v<0:raise EmergingError(f'{key} must be nonnegative')
    elif v<=0:raise EmergingError(f'{key} must be positive')
    return v
def _prob(data,key,default=None):
    raw=data.get(key,default)
    if raw is None:raise EmergingError(f'{key} is required')
    v=_f(raw,key)
    if not 0<=v<=1:raise EmergingError(f'{key} must be within 0..1')
    return v
def _int(data,key,lo=1,default=None):
    raw=data.get(key,default)
    if raw is None:raise EmergingError(f'{key} is required')
    if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not float(raw).is_integer():raise EmergingError(f'{key} must be an integer')
    v=int(raw)
    if v<lo:raise EmergingError(f'{key} must be at least {lo}')
    return v
def _vec(data,key,n=1):
    x=data.get(key)
    if not isinstance(x,list) or len(x)<n:raise EmergingError(f'{key} needs at least {n} finite numbers')
    return [_f(v,key) for v in x]
def _pairs(data,key,n=2):
    x=data.get(key)
    if not isinstance(x,list) or len(x)<n or any(not isinstance(p,(list,tuple)) or len(p)!=2 for p in x):raise EmergingError(f'{key} needs at least {n} [x, y] pairs')
    return [(_f(a,key),_f(b,key)) for a,b in x]
def _h2(x):
    if x<=0 or x>=1:return 0.0
    return -x*math.log2(x)-(1-x)*math.log2(1-x)

# ---- shared benchmark objectives for the seeded metaheuristic rows (925-939) ----
def _objective(name,x):
    if name=='sphere':return sum(v*v for v in x)
    if name=='rastrigin':return 10*len(x)+sum(v*v-10*math.cos(2*math.pi*v) for v in x)
    if name=='rosenbrock':return sum(100*(x[i+1]-x[i]*x[i])**2+(1-x[i])**2 for i in range(len(x)-1))
    raise EmergingError(f'unsupported objective {name}')
def _bounds(data):
    b=data.get('bounds')
    if not isinstance(b,list) or not b or any(not isinstance(r,(list,tuple)) or len(r)!=2 for r in b):raise EmergingError('bounds must be [[lo, hi], ...] pairs')
    out=[(_f(lo,'bounds'),_f(hi,'bounds')) for lo,hi in b]
    if any(lo>=hi for lo,hi in out):raise EmergingError('each bounds entry needs lo < hi')
    return out
def _opt_setup(data,params):
    b=_bounds(data);obj=data.get('objective','sphere')
    if obj not in ('sphere','rastrigin','rosenbrock'):raise EmergingError('objective must be sphere, rastrigin or rosenbrock')
    it=int(params.get('iterations',40))
    if it<1:raise EmergingError('iterations must be positive')
    return b,obj,it
def _clip(x,b):return [min(hi,max(lo,v)) for v,(lo,hi) in zip(x,b)]

# ============================ quantum rows 910-917 ============================
def _r910_quantum_computing_application(d,p,rng):
    logical=_int(d,'logical_qubits');t_gates=_int(d,'t_gates');dist=_int(d,'code_distance',3)
    if dist%2==0:raise EmergingError('code_distance must be odd for a rotated surface code')
    classical=_pos(d,'classical_cost');quantum=_pos(d,'quantum_cost');gate_ns=_pos(d,'gate_time_ns')
    p_phys=_prob(d,'physical_error_rate');th=_prob(d,'threshold')
    if not 0<p_phys<1 or not 0<th<1:raise EmergingError('error rates must be within (0,1)')
    physical=logical*2*dist*dist
    logical_error=(p_phys/th)**((dist+1)/2)
    runtime_s=t_gates*dist*gate_ns*1e-9
    overhead=physical/logical
    effective_speedup=(classical/quantum)/(1+overhead*logical_error)
    out={'physical_qubit_estimate':physical,'logical_error_rate_bound':logical_error,'runtime_seconds_estimate':runtime_s,'error_correction_overhead':overhead,'ideal_speedup':classical/quantum,'effective_speedup_estimate':effective_speedup,'advantage_expected':effective_speedup>1}
    a=['Surface-code-style overhead model; gate times uniform; classical and quantum costs are caller-supplied resource proxies.']
    lim=['Resource estimate only; no quantum hardware is invoked and no exponential speedup is claimed for arbitrary problems.']
    return out,a,lim

def _r911_quantum_algorithm_design(d,p,rng):
    n=_int(d,'search_space_size');m=_int(d,'solutions')
    if m>n:raise EmergingError('solutions cannot exceed search_space_size')
    theta=math.asin(math.sqrt(m/n))
    k_opt=max(0,math.floor(math.pi/(4*theta)))
    success=math.sin((2*k_opt+1)*theta)**2
    classical=n/m
    out={'optimal_grover_iterations':k_opt,'iteration_bound':math.pi/4*math.sqrt(n/m),'success_probability':success,'classical_expected_queries':classical,'quadratic_query_ratio':classical/max(1,k_opt)}
    a=['Uniform superposition oracle; single marked-subspace Grover amplitude amplification; ideal noiseless gates.']
    lim=['Design arithmetic only; the oracle circuit is not synthesized and no device run is performed.']
    return out,a,lim

def _r912_quantum_error_correction(d,p,rng):
    phys=_prob(d,'physical_error_rate');th=_prob(d,'threshold');dist=_int(d,'code_distance')
    if not 0<phys<1 or not 0<th<1:raise EmergingError('rates must be within (0,1)')
    if dist%2==0:raise EmergingError('code_distance must be odd for majority-vote decoding')
    logical=(phys/th)**((dist+1)/2)
    out={'logical_error_rate_bound':logical,'below_threshold':phys<th,'code_distance':dist,'data_qubits':dist*dist,'ancilla_qubits':dist*dist-1,'total_physical_qubits':2*dist*dist-1,'syndrome_rounds_per_logical_op':dist}
    a=['Rotated surface code with phenomenological scaling (p/p_th)^((d+1)/2); independent circuit-level noise.']
    lim=['Scaling bound, not a decoded Monte-Carlo estimate; correlated noise, leakage and fabrication yield are not modeled.']
    return out,a,lim

def _r913_quantum_machine_learning(d,p,rng):
    coeffs=_vec(d,'hamiltonian_coefficients');theta=_vec(d,'ansatz_parameters',len(coeffs))
    if len(theta)!=len(coeffs):raise EmergingError('ansatz_parameters must align with hamiltonian_coefficients')
    lr=_f(p.get('learning_rate',.3),'learning_rate');steps=_int(p,'steps',1,25)
    if not 0<lr<=2:raise EmergingError('learning_rate must be within (0,2]')
    def energy(t):return sum(c*math.cos(v) for c,v in zip(coeffs,t))
    def grad(t):return [-c*math.sin(v) for c,v in zip(coeffs,t)]
    hist=[energy(theta)]
    for _ in range(steps):
        g=grad(theta);theta=[v-lr*gv for v,gv in zip(theta,g)];hist.append(energy(theta))
    lower=-sum(abs(c) for c in coeffs)
    out={'initial_energy':hist[0],'final_energy':hist[-1],'energy_history':hist,'theoretical_ground_energy_bound':lower,'reached_bound':hist[-1]<=lower+1e-6,'gradient_norm_final':math.sqrt(sum(g*g for g in grad(theta)))}
    a=['Product-state toy ansatz with exact parameter-shift gradients dE/dt_i = -c_i sin(t_i); noiseless evaluation.']
    lim=['Classical reference simulation of a VQE loop; no quantum processor is used and barren-plateau effects are not modeled.']
    return out,a,lim

def _r914_quantum_simulation(d,p,rng):
    coeffs=[abs(c) for c in _vec(d,'term_coefficients')];t=_pos(d,'evolution_time');eps=_pos(d,'target_error')
    order=_int(p,'trotter_order',1,1)
    if order not in (1,2):raise EmergingError('trotter_order must be 1 or 2')
    lam=sum(coeffs)
    if order==1:steps=(lam*t)**2/(2*eps)
    else:steps=((lam*t)**3/(12*eps))**.5
    steps=max(1,math.ceil(steps))
    gates=steps*len(coeffs)*_int(p,'gates_per_term',1,10)
    out={'spectral_range':lam,'trotter_steps_required':steps,'trotter_order':order,'gate_estimate':gates}
    a=['Worst-case product-formula error scaling with all terms treated as non-commuting; unitary circuit per term.']
    lim=['Upper-bound resource arithmetic; commutator structure and symmetry reductions would lower the bound and are not inferred.']
    return out,a,lim

def _r915_quantum_cryptography(d,p,rng):
    sifted=_f(d.get('sifted_bits'),'sifted_bits')
    if sifted<0:raise EmergingError('sifted_bits must be nonnegative')
    qber=_prob(d,'qber')
    if qber>.5:raise EmergingError('qber above 0.5 carries no key fraction')
    leak=_f(d.get('error_correction_leak',0),'error_correction_leak')
    if leak<0:raise EmergingError('error_correction_leak must be nonnegative')
    abort_th=_f(p.get('abort_threshold',.11),'abort_threshold')
    sample=_int(p,'eve_sample_size',1,64)
    h=_h2(qber)
    out={'secret_key_bits_bound':max(0.0,sifted*(1-2*h)-leak),'qber':qber,'binary_entropy':h,'abort':qber>abort_th,'intercept_resend_detection_probability':1-.75**sample,'asymptotic_key_rate':max(0.0,1-2*h)}
    a=['Asymptotic BB84 key rate 1-2h(QBER) with caller-supplied error-correction leakage; intercept-resend probe over eve_sample_size test bits.']
    lim=['Not a composable finite-key proof; decoy-state, device imperfections and side channels require a full security analysis.']
    return out,a,lim

def _r916_quantum_sensing(d,p,rng):
    n=_pos(d,'resources');contrast=_prob(d,'readout_contrast',1.0)
    if contrast<=0:raise EmergingError('readout_contrast must be positive')
    t2=_pos(d,'coherence_time_s');total=_pos(d,'measurement_time_s')
    sql=1/math.sqrt(n);hl=1/n
    shots=max(1.0,total/t2)
    phase_floor=1/(contrast*math.sqrt(shots))
    out={'standard_quantum_limit':sql,'heisenberg_limit':hl,'ideal_advantage':sql/hl,'coherence_limited_phase_floor':phase_floor,'independent_shots':shots}
    a=['n independent probe resources; Ramsey-style readout with caller-stated contrast and T2 coherence; averaging over measurement_time_s.']
    lim=['Ideal sensitivity bounds; decoherence during interrogation, readout loss and systematics are not modeled.']
    return out,a,lim

def _r917_quantum_networking(d,p,rng):
    fids=_vec(d,'link_fidelities');succ=_vec(d,'link_success_probabilities',len(fids))
    if len(fids)!=len(succ):raise EmergingError('link fidelity and probability arrays must align')
    if any(not 0<s<=1 for s in succ):raise EmergingError('link success probabilities must be within (0,1]')
    if any(not .25<f<=1 for f in fids):raise EmergingError('link fidelities must exceed the 0.25 classical threshold')
    werner=[(4*f-1)/3 for f in fids]
    w_e2e=math.prod(werner)
    f_worst=min(fids);q=(1-f_worst)/3
    f_distilled=(f_worst**2+q**2)/(f_worst**2+2*f_worst*q+5*q**2)
    out={'end_to_end_success':math.prod(succ),'end_to_end_fidelity_lower_bound':math.prod(fids),'links':len(succ),'repeater_levels':max(0,math.ceil(math.log2(len(succ)))),'werner_end_to_end':w_e2e,'bbpssw_distilled_worst_link':f_distilled,'distillation_gain':f_distilled-f_worst}
    a=['Independent links; Werner-state decay under ideal entanglement swapping; one BBPSSW distillation round on the worst link.']
    lim=['Reference protocol arithmetic; no photons, memories or network hardware are operated.']
    return out,a,lim

# ===================== alternative-computing rows 918-924 =====================
def _r918_neuromorphic_computing(d,p,rng):
    tau=_pos(d,'membrane_tau_ms');dt=_pos(d,'dt_ms');steps=_int(d,'steps')
    if dt>tau:raise EmergingError('dt_ms must not exceed membrane_tau_ms for a stable Euler step')
    v_rest=_f(d.get('v_rest_mv',-65),'v_rest_mv');v_th=_f(d.get('v_threshold_mv',-50),'v_threshold_mv');v_reset=_f(d.get('v_reset_mv',-65),'v_reset_mv')
    if not v_reset<=v_rest<v_th:raise EmergingError('expected v_reset <= v_rest < v_threshold')
    current=_pos(d,'input_current_na');r_m=_pos(d,'membrane_resistance_mohm')
    drive=r_m*current
    v=v_rest;spikes=[];trace=[]
    for i in range(steps):
        v+=dt*(-(v-v_rest)+drive)/tau
        if v>=v_th:spikes.append(i*dt);v=v_reset
        trace.append(v)
    isi=[b-a for a,b in zip(spikes,spikes[1:])]
    analytic=0.0
    if drive>v_th-v_rest:analytic=1000.0/(tau*math.log((drive-(v_reset-v_rest))/(drive-(v_th-v_rest))))
    energy= len(spikes)*_f(p.get('energy_per_spike_j',1e-12),'energy_per_spike_j')
    out={'spike_count':len(spikes),'mean_isi_ms':(sum(isi)/len(isi) if isi else 0.0),'simulated_rate_hz':(len(spikes)/(steps*dt/1000.0)),'analytic_rate_hz':analytic,'final_membrane_mv':trace[-1],'spike_energy_joules':energy}
    a=['Single leaky integrate-and-fire neuron, exact-forward Euler; constant drive current; no synaptic noise.']
    lim=['Point-neuron reference simulation; no silicon or wetware is programmed and network effects are absent.']
    return out,a,lim

def _r919_spiking_neural_networks(d,p,rng):
    pre=sorted(_vec(d,'pre_spike_times_ms'));post=sorted(_vec(d,'post_spike_times_ms'))
    a_plus=_pos(d,'a_plus');a_minus=_pos(d,'a_minus');tau_plus=_pos(d,'tau_plus_ms');tau_minus=_pos(d,'tau_minus_ms')
    if max(a_plus,a_minus)>1:raise EmergingError('STDP amplitudes are bounded by 1 in this reference')
    pot=dep=0.0
    for tp in pre:
        for tq in post:
            dt=tq-tp
            if dt>0:pot+=a_plus*math.exp(-dt/tau_plus)
            elif dt<0:dep+=a_minus*math.exp(dt/tau_minus)
    out={'weight_change':pot-dep,'potentiation':pot,'depression':dep,'spike_pairs_evaluated':len(pre)*len(post),'net_direction':'potentiation' if pot>dep else 'depression' if dep>pot else 'neutral'}
    a=['Additive all-pair STDP rule; times in milliseconds on a common clock; weights unclipped.']
    lim=['Two-neuron plasticity kernel only; no network training, hardware mapping or behavioral claim is made.']
    return out,a,lim

def _r920_memristor_computing(d,p,rng):
    g=d.get('conductance_matrix')
    if not isinstance(g,list) or not g or any(not isinstance(r,list) or len(r)!=len(g[0]) or not r for r in g):raise EmergingError('conductance_matrix must be a non-empty rectangular array')
    g=[[_f(x,'conductance_matrix') for x in r] for r in g]
    v=_vec(d,'input_vector',len(g[0]))
    if len(v)!=len(g[0]):raise EmergingError('input_vector must match matrix width')
    g_lo=_f(p.get('g_min_s',1e-6),'g_min_s');g_hi=_f(p.get('g_max_s',1e-3),'g_max_s')
    if not 0<g_lo<g_hi:raise EmergingError('expected 0 < g_min_s < g_max_s')
    if any(not g_lo<=x<=g_hi for r in g for x in r):raise EmergingError('conductances must be programmed within [g_min_s, g_max_s]')
    noise=_f(d.get('device_noise_std',0.0),'device_noise_std')
    if noise<0:raise EmergingError('device_noise_std must be nonnegative')
    bits=_int(d,'adc_bits',1,8)
    y=[sum(gv*vv for gv,vv in zip(r,v)) for r in g]
    sigma_mac=noise*(g_hi-g_lo)*math.sqrt(sum(x*x for x in v))
    noisy=[val+rng.gauss(0,sigma_mac) for val in y]
    full=g_hi*sum(abs(x) for x in v);lsb=full/((1<<bits)-1)
    quant=[round(val/lsb)*lsb for val in noisy]
    mse=sum((a-b)**2 for a,b in zip(y,quant))/len(y)
    var=sum((val-sum(y)/len(y))**2 for val in y)/len(y)
    out={'ideal_output':y,'noisy_quantized_output':quant,'mse_vs_ideal':mse,'snr_db':(10*math.log10(var/mse) if mse>0 and var>0 else None),'mac_count':len(g)*len(v),'energy_estimate_joules':len(g)*len(v)*_f(p.get('energy_per_mac_j',1e-12),'energy_per_mac_j'),'seed_note':'reproducible for fixed seed'}
    a=['Ohmic crossbar with Kirchhoff summation; per-MAC Gaussian conductance noise scaled by input norm; mid-tread ADC quantization.']
    lim=['Reference VMM model; no crossbar is written or read and sneak-path/IR-drop effects are excluded.']
    return out,a,lim

def _r921_optical_computing(d,p,rng):
    n=_int(d,'dimension',2);il=_f(d.get('insertion_loss_db_per_mzi',.2),'insertion_loss_db_per_mzi')
    if il<0:raise EmergingError('insertion loss must be nonnegative')
    heater=_pos(d,'phase_shifter_power_mw');wl=_pos(d,'wavelength_nm')
    mzi=n*(n-1)//2;worst_path=2*n-3
    loss=worst_path*il
    out={'mzi_count':mzi,'worst_path_mzis':worst_path,'worst_path_loss_db':loss,'worst_path_transmission':10**(-loss/10),'static_heater_power_mw':mzi*heater,'phase_shifter_count':n*(n-1)}
    a=['Clements-style rectangular mesh; uniform per-MZI insertion loss; worst path scales as 2n-3 couplers.']
    lim=['Photonic design estimate; no mesh is configured, thermal crosstalk and fabrication variation are not modeled.']
    return out,a,lim

def _r922_dna_computing(d,p,rng):
    n=_int(d,'vertex_count',2);e=_int(d,'edge_count',0);wl=_int(d,'word_length',4)
    if wl%2:raise EmergingError('word_length must be even so vertices split into half-words')
    strands=n+2*e
    tm=3.0*wl
    library=4**wl
    paths=math.factorial(n-1)
    out={'strands_required':strands,'wallace_tm_celsius_estimate':tm,'distinct_library_sequences':library if library<10**15 else f'{library:.3e}','classical_path_enumerations':paths,'molecular_parallelism_note':'a micromole-scale library holds ~6e17 copies per sequence'}
    a=['Adleman-style vertex/edge encoding; Wallace rule Tm at 50% GC; perfect hybridization specificity assumed.']
    lim=['Design arithmetic only; no oligos are synthesized, and wet-lab error rates (mis-hybridization, extraction loss) dominate practice.']
    return out,a,lim

def _r923_molecular_computing(d,p,rng):
    init=d.get('species_initial')
    if not isinstance(init,dict) or not init:raise EmergingError('species_initial must be a non-empty object')
    conc={k:_f(v,k) for k,v in init.items()}
    if any(v<0 for v in conc.values()):raise EmergingError('initial concentrations must be nonnegative')
    rxns=d.get('reactions')
    if not isinstance(rxns,list) or not rxns:raise EmergingError('reactions must be a non-empty list')
    parsed=[]
    for r in rxns:
        if not isinstance(r,dict) or not isinstance(r.get('reactants'),dict) or not isinstance(r.get('products'),dict):raise EmergingError('each reaction needs reactants and products objects')
        rate=_f(r.get('rate'),'rate')
        if rate<=0:raise EmergingError('reaction rates must be positive')
        parsed.append(({k:_f(v,'reactants') for k,v in r['reactants'].items()},{k:_f(v,'products') for k,v in r['products'].items()},rate))
    dt=_pos(d,'dt');steps=_int(d,'steps')
    traj=[dict(conc)]
    for _ in range(steps):
        delta={k:0.0 for k in conc}
        for re,pr,rate in parsed:
            flux=rate
            for s,c in re.items():flux*=conc.get(s,0.0)**c
            for s,c in re.items():delta[s]=delta.get(s,0.0)-c*flux
            for s,c in pr.items():delta[s]=delta.get(s,0.0)+c*flux
        conc={k:v+dt*delta.get(k,0.0) for k,v in conc.items()}
        if any(v<-1e-12 for v in conc.values()):raise EmergingError('dt too large: a concentration went negative; reduce dt')
        conc={k:max(0.0,v) for k,v in conc.items()}
        traj.append(dict(conc))
    out={'final_concentrations':traj[-1],'trajectory_length':len(traj),'stable':all(abs(traj[-1][k]-traj[-2][k])<1e-9 for k in traj[-1]),'species':sorted(conc)}
    a=['Deterministic mass-action kinetics integrated by explicit Euler; well-mixed reactor; stoichiometric coefficients as supplied.']
    lim=['Reference ODE integration; stochastic low-copy chemistry and actual wetware execution are out of scope.']
    return out,a,lim

def _r924_biological_computing(d,p,rng):
    a1=_pos(d,'alpha1');a2=_pos(d,'alpha2');beta=_f(d.get('beta',2),'beta');gamma=_f(d.get('gamma',2),'gamma')
    if beta<1 or gamma<1:raise EmergingError('Hill coefficients beta and gamma must be at least 1')
    dt=_f(p.get('relaxation_dt',.05),'relaxation_dt');steps=_int(p,'relaxation_steps',100,20000)
    if not 0<dt<=1:raise EmergingError('relaxation_dt must be within (0,1]')
    def settle(u,v):
        for _ in range(steps):
            u+=dt*(a1/(1+v**beta)-u);v+=dt*(a2/(1+u**gamma)-v)
        return u,v
    s1=settle(.01*a1,2*a2);s2=settle(2*a1,.01*a2)
    dist=math.hypot(s1[0]-s2[0],s1[1]-s2[1])
    bistable=dist>.1*max(a1,a2)
    out={'steady_state_a':list(s1),'steady_state_b':list(s2),'state_separation':dist,'bistable':bistable,'toggle_logic':'two stable repressor states (digital 0/1)' if bistable else 'monostable under supplied parameters'}
    a=['Gardner-style genetic toggle switch, Hill repression, equal degradation rates normalized to 1; deterministic relaxation.']
    lim=['Kinetic reference model; no organism is engineered, and biosafety containment review precedes any wet-lab analogue.']
    return out,a,lim

# ==================== seeded metaheuristic rows 925-934 ====================
def _pso(d,p,rng):
    b,obj,it=_opt_setup(d,p);n=_int(d,'particles',2)
    w=_f(p.get('inertia',.7),'inertia');c1=_f(p.get('cognitive',1.4),'cognitive');c2=_f(p.get('social',1.4),'social')
    X=[[rng.uniform(lo,hi) for lo,hi in b] for _ in range(n)]
    V=[[rng.uniform(-(hi-lo),hi-lo)*.1 for lo,hi in b] for _ in range(n)]
    P=[x[:] for x in X];pf=[_objective(obj,x) for x in X]
    gi=min(range(n),key=lambda i:pf[i]);G=P[gi][:];hist=[pf[gi]]
    for _ in range(it):
        for i in range(n):
            V[i]=[w*vv+c1*rng.random()*(pb-xv)+c2*rng.random()*(gb-xv) for vv,pb,xv,gb in zip(V[i],P[i],X[i],G)]
            X[i]=_clip([xv+vv for xv,vv in zip(X[i],V[i])],b)
            f=_objective(obj,X[i])
            if f<pf[i]:pf[i]=f;P[i]=X[i][:]
        gi=min(range(n),key=lambda i:pf[i])
        if pf[gi]<_objective(obj,G):G=P[gi][:]
        hist.append(_objective(obj,G))
    return {'best_position':G,'best_fitness':hist[-1],'fitness_history':hist,'particles':n,'seed_note':'reproducible for fixed seed'},['Particle swarm with inertia/cognitive/social constants; synchronous updates; positions clipped to bounds.'],['Bounded stochastic reference optimizer; no guarantee of global optimality.']
def _aco(d,p,rng):
    dm=d.get('distance_matrix')
    if not isinstance(dm,list) or len(dm)<2 or any(not isinstance(r,list) or len(r)!=len(dm) for r in dm):raise EmergingError('distance_matrix must be square with at least 2 cities')
    n=len(dm);dm=[[_f(x,'distance_matrix') for x in r] for r in dm]
    for i in range(n):
        if abs(dm[i][i])>1e-12:raise EmergingError('distance_matrix diagonal must be zero')
        for j in range(n):
            if abs(dm[i][j]-dm[j][i])>1e-9:raise EmergingError('distance_matrix must be symmetric')
            if i!=j and dm[i][j]<=0:raise EmergingError('inter-city distances must be positive')
    ants=_int(d,'ants');it=_int(d,'iterations')
    alpha=_f(p.get('alpha',1.0),'alpha');beta=_f(p.get('beta',3.0),'beta');rho=_f(p.get('evaporation',.4),'evaporation');q=_f(p.get('deposit',1.0),'deposit')
    if not 0<rho<1 or alpha<=0 or beta<=0 or q<=0:raise EmergingError('need alpha,beta>0, deposit>0 and 0<evaporation<1')
    tau=[[1.0]*n for _ in range(n)];eta=[[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i!=j:eta[i][j]=1.0/dm[i][j]
    def tour():
        start=rng.randrange(n);visited={start};path=[start]
        while len(path)<n:
            cur=path[-1];cands=[j for j in range(n) if j not in visited]
            weights=[(tau[cur][j]**alpha)*(eta[cur][j]**beta) for j in cands];tot=sum(weights)
            r=rng.random()*tot;acc=0
            for j,wt in zip(cands,weights):
                acc+=wt
                if acc>=r:path.append(j);visited.add(j);break
        return path
    def length(path):return sum(dm[a][b] for a,b in zip(path,path[1:]+path[:1]))
    best=None;best_len=None;hist=[]
    for _ in range(it):
        tours=[tour() for _ in range(ants)];lens=[length(t) for t in tours]
        for i in range(n):
            for j in range(n):tau[i][j]*=(1-rho)
        for t,l in zip(tours,lens):
            for a,b in zip(t,t[1:]+t[:1]):tau[a][b]+=q/l;tau[b][a]+=q/l
        i=min(range(ants),key=lambda k:lens[k])
        if best_len is None or lens[i]<best_len:best,best_len=tours[i],lens[i]
        hist.append(best_len)
    return {'best_tour':best,'best_length':best_len,'length_history':hist,'cities':n,'seed_note':'reproducible for fixed seed'},['Standard ant system: tau^alpha * eta^beta roulette construction, global evaporation, Q/L deposition.'],['Heuristic tour construction; optimality is not certified and no logistics booking is made.']
def _abc(d,p,rng):
    b,obj,it=_opt_setup(d,p);colony=_int(d,'colony_size',4);limit=_int(p,'abandon_limit',1,20)
    half=max(2,colony//2)
    X=[[rng.uniform(lo,hi) for lo,hi in b] for _ in range(half)];F=[_objective(obj,x) for x in X]
    def fit(f):return 1/(1+f) if f>=0 else 1-f
    trial=[0]*half;hist=[min(F)];scouts=0
    def neighbor(i):
        x=X[i][:];k=rng.randrange(half)
        while k==i:k=rng.randrange(half)
        j=rng.randrange(len(b));phi=rng.uniform(-1,1);x[j]=x[j]+phi*(x[j]-X[k][j])
        return _clip(x,b)
    for _ in range(it):
        for i in range(half):
            x=neighbor(i);f=_objective(obj,x)
            if f<F[i]:X[i],F[i],trial[i]=x,f,0
            else:trial[i]+=1
        tot=sum(fit(f) for f in F);on=0
        while on<half:
            i=rng.randrange(half)
            if rng.random()<fit(F[i])/tot:
                on+=1;x=neighbor(i);f=_objective(obj,x)
                if f<F[i]:X[i],F[i],trial[i]=x,f,0
                else:trial[i]+=1
        for i in range(half):
            if trial[i]>=limit:X[i]=[rng.uniform(lo,hi) for lo,hi in b];F[i]=_objective(obj,X[i]);trial[i]=0;scouts+=1
        hist.append(min(F))
    bi=min(range(half),key=lambda i:F[i])
    return {'best_position':X[bi],'best_fitness':F[bi],'fitness_history':hist,'scouts_triggered':scouts,'seed_note':'reproducible for fixed seed'},['Artificial bee colony with employed/onlooker/scout phases; greedy selection; roulette onlooker choice.'],['Bounded stochastic reference optimizer; no hive, crop or deployment claim.']
def _firefly(d,p,rng):
    b,obj,it=_opt_setup(d,p);n=_int(d,'fireflies',2)
    beta0=_f(p.get('beta0',1.0),'beta0');gamma=_f(p.get('gamma',1.0),'gamma');alpha=_f(p.get('randomness',.2),'randomness')
    if beta0<=0 or gamma<0 or alpha<0:raise EmergingError('need beta0>0, gamma>=0, randomness>=0')
    X=[[rng.uniform(lo,hi) for lo,hi in b] for _ in range(n)];F=[_objective(obj,x) for x in X]
    scale=[hi-lo for lo,hi in b];hist=[min(F)]
    for _ in range(it):
        for i in range(n):
            for j in range(n):
                if F[j]<F[i]:
                    r=math.sqrt(sum((a-c)**2 for a,c in zip(X[i],X[j])))
                    beta=beta0*math.exp(-gamma*r*r)
                    X[i]=_clip([xi+beta*(xj-xi)+alpha*(rng.random()-.5)*s for xi,xj,s in zip(X[i],X[j],scale)],b)
                    F[i]=_objective(obj,X[i])
        hist.append(min(F))
    bi=min(range(n),key=lambda i:F[i])
    return {'best_position':X[bi],'best_fitness':F[bi],'fitness_history':hist,'seed_note':'reproducible for fixed seed'},['Brightness = inverse objective; attraction beta0*exp(-gamma r^2); minimization moves dimmer toward brighter fireflies.'],['Bounded stochastic reference optimizer; no global-optimality certificate.']
def _cuckoo(d,p,rng):
    b,obj,it=_opt_setup(d,p);n=_int(d,'nests',2);pa=_f(p.get('abandon_probability',.25),'abandon_probability')
    if not 0<pa<1:raise EmergingError('abandon_probability must be within (0,1)')
    lam=1.5
    sig=(math.gamma(1+lam)*math.sin(math.pi*lam/2)/(math.gamma((1+lam)/2)*lam*2**((lam-1)/2)))**(1/lam)
    X=[[rng.uniform(lo,hi) for lo,hi in b] for _ in range(n)];F=[_objective(obj,x) for x in X]
    hist=[min(F)]
    def levy():
        u=rng.gauss(0,sig);v=rng.gauss(0,1)
        return u/(abs(v)**(1/lam))
    for _ in range(it):
        bi=min(range(n),key=lambda i:F[i])
        for i in range(n):
            step=[.01*levy()*(X[i][k]-X[bi][k]) for k in range(len(b))]
            x=_clip([xv+sv for xv,sv in zip(X[i],step)],b);f=_objective(obj,x)
            j=rng.randrange(n)
            if f<F[j]:X[j],F[j]=x,f
        order=sorted(range(n),key=lambda i:F[i],reverse=True)
        for i in order[:max(1,int(pa*n))]:X[i]=[rng.uniform(lo,hi) for lo,hi in b];F[i]=_objective(obj,X[i])
        hist.append(min(F))
    bi=min(range(n),key=lambda i:F[i])
    return {'best_position':X[bi],'best_fitness':F[bi],'fitness_history':hist,'levy_lambda':lam,'seed_note':'reproducible for fixed seed'},['Cuckoo search with Mantegna Levy flights (lambda=1.5) and worst-nest abandonment probability pa.'],['Bounded stochastic reference optimizer; heavy-tailed steps do not guarantee coverage.']
def _bat(d,p,rng):
    b,obj,it=_opt_setup(d,p);n=_int(d,'bats',2)
    fmin=_f(p.get('fmin',0.0),'fmin');fmax=_f(p.get('fmax',1.0),'fmax')
    if not fmin<fmax:raise EmergingError('expected fmin < fmax')
    a0=_f(p.get('loudness',.9),'loudness');r0=_f(p.get('pulse_rate',.5),'pulse_rate');decay=_f(p.get('loudness_decay',.9),'loudness_decay');gam=_f(p.get('pulse_growth',.9),'pulse_growth')
    if not 0<a0<=1 or not 0<r0<1 or not 0<decay<=1 or gam<=0:raise EmergingError('invalid loudness/pulse constants')
    X=[[rng.uniform(lo,hi) for lo,hi in b] for _ in range(n)];V=[[0.0]*len(b) for _ in range(n)]
    F=[_objective(obj,x) for x in X];A=[a0]*n;R=[r0]*n;hist=[min(F)]
    for t in range(it):
        bi=min(range(n),key=lambda i:F[i]);best=X[bi]
        for i in range(n):
            fr=fmin+(fmax-fmin)*rng.random()
            V[i]=[vv+(xv-bv)*fr for vv,xv,bv in zip(V[i],X[i],best)]
            x=_clip([xv+vv for xv,vv in zip(X[i],V[i])],b)
            if rng.random()>R[i]:x=_clip([bv+.001*sum(A)/n*rng.gauss(0,1) for bv in best],b)
            f=_objective(obj,x)
            if f<=F[i] and rng.random()<A[i]:
                X[i],F[i]=x,f;A[i]*=decay;R[i]=r0*(1-math.exp(-gam*(t+1)))
        hist.append(min(F))
    bi=min(range(n),key=lambda i:F[i])
    return {'best_position':X[bi],'best_fitness':F[bi],'fitness_history':hist,'final_mean_loudness':sum(A)/n,'seed_note':'reproducible for fixed seed'},['Bat algorithm with frequency-tuned velocities, local walk around the best, loudness decay and pulse-rate growth.'],['Bounded stochastic reference optimizer; echolocation is metaphor, not acoustics.']
def _gwo(d,p,rng):
    b,obj,it=_opt_setup(d,p);n=_int(d,'wolves',4)
    X=[[rng.uniform(lo,hi) for lo,hi in b] for _ in range(n)];hist=[]
    for t in range(it):
        F=[_objective(obj,x) for x in X];order=sorted(range(n),key=lambda i:F[i]);alpha,beta,delta=(X[k] for k in order[:3])
        a=2-2*t/max(1,it-1)
        for i in range(n):
            new=[]
            for k in range(len(b)):
                xs=[]
                for lead in (alpha,beta,delta):
                    A=2*a*rng.random()-a;C=2*rng.random()
                    xs.append(lead[k]-A*abs(C*lead[k]-X[i][k]))
                new.append(sum(xs)/3)
            X[i]=_clip(new,b)
        hist.append(min(_objective(obj,x) for x in X))
    F=[_objective(obj,x) for x in X];bi=min(range(n),key=lambda i:F[i])
    return {'best_position':X[bi],'best_fitness':F[bi],'fitness_history':hist,'seed_note':'reproducible for fixed seed'},['Grey wolf optimizer: alpha/beta/delta encircling with coefficient a decreasing linearly 2 to 0.'],['Bounded stochastic reference optimizer; pack hierarchy is an algorithmic device only.']
def _woa(d,p,rng):
    b,obj,it=_opt_setup(d,p);n=_int(d,'whales',2);spiral=_f(p.get('spiral_shape',1.0),'spiral_shape')
    X=[[rng.uniform(lo,hi) for lo,hi in b] for _ in range(n)];hist=[]
    for t in range(it):
        F=[_objective(obj,x) for x in X];bi=min(range(n),key=lambda i:F[i]);best=X[bi]
        a=2-2*t/max(1,it-1)
        for i in range(n):
            if rng.random()<.5:
                A=2*a*rng.random()-a;C=2*rng.random()
                if abs(A)<1:target=best
                else:target=X[rng.randrange(n)]
                X[i]=_clip([tv-A*abs(C*tv-xv) for tv,xv in zip(target,X[i])],b)
            else:
                X[i]=_clip([abs(bv-xv)*math.exp(spiral*rng.uniform(-1,1))*math.cos(2*math.pi*rng.uniform(-1,1))+bv for bv,xv in zip(best,X[i])],b)
        hist.append(min(_objective(obj,x) for x in X))
    F=[_objective(obj,x) for x in X];bi=min(range(n),key=lambda i:F[i])
    return {'best_position':X[bi],'best_fitness':F[bi],'fitness_history':hist,'seed_note':'reproducible for fixed seed'},['Whale optimization: shrinking encirclement versus logarithmic bubble-net spiral chosen per update with p=0.5.'],['Bounded stochastic reference optimizer; no marine behavior is inferred.']
def _clonalg(d,p,rng):
    b,obj,it=_opt_setup(d,p);n=_int(d,'antibodies',2);clones=_int(p,'clones_per_antibody',1,5)
    X=[[rng.uniform(lo,hi) for lo,hi in b] for _ in range(n)];F=[_objective(obj,x) for x in X];hist=[min(F)]
    for _ in range(it):
        order=sorted(range(n),key=lambda i:F[i]);pool=[]
        span=max(F)-min(F)+1e-12
        for rank,i in enumerate(order):
            count=clones*(n-rank)
            affinity=(F[i]-min(F))/span
            for _ in range(count):
                mut=[xv+ (1-affinity)*rng.gauss(0,1)*(hi-lo)*.1 for xv,(lo,hi) in zip(X[i],b)]
                mut=_clip(mut,b);fm=_objective(obj,mut)
                if fm<F[i]:pool.append((fm,mut))
        pool+= [(F[i],X[i]) for i in range(n)]
        pool.sort(key=lambda t:t[0]);X=[x for _,x in pool[:n]];F=[f for f,_ in pool[:n]]
        hist.append(min(F))
    bi=min(range(n),key=lambda i:F[i])
    return {'best_position':X[bi],'best_fitness':F[bi],'fitness_history':hist,'seed_note':'reproducible for fixed seed'},['CLONALG clonal selection: clone count proportional to rank, hypermutation strength inversely proportional to affinity.'],['Immune metaphor only; no biological system is modeled for clinical use.']
def _game_of_life(d,p,rng):
    grid=d.get('grid')
    if grid is None:
        rows=_int(p,'rows',1,10);cols=_int(p,'cols',1,10);density=_f(p.get('density',.3),'density')
        if not 0<density<1:raise EmergingError('density must be within (0,1)')
        grid=[[1 if rng.random()<density else 0 for _ in range(cols)] for _ in range(rows)]
    if not isinstance(grid,list) or not grid or any(not isinstance(r,list) or len(r)!=len(grid[0]) or not r for r in grid):raise EmergingError('grid must be a non-empty rectangular array of 0/1')
    if any(x not in (0,1) for r in grid for x in r):raise EmergingError('grid cells must be 0 or 1')
    grid=[[int(x) for x in r] for r in grid]
    steps=_int(d,'steps');wrap=bool(p.get('wrap',True))
    R,C=len(grid),len(grid[0])
    def nxt(g):
        out=[[0]*C for _ in range(R)]
        for i in range(R):
            for j in range(C):
                s=0
                for di in (-1,0,1):
                    for dj in (-1,0,1):
                        if di==0 and dj==0:continue
                        ii,jj=i+di,j+dj
                        if wrap:ii%=R;jj%=C
                        if 0<=ii<R and 0<=jj<C:s+=g[ii][jj]
                out[i][j]=1 if (g[i][j] and s in (2,3)) or (not g[i][j] and s==3) else 0
        return out
    hist=[sum(map(sum,grid))];states=[grid]
    for _ in range(steps):grid=nxt(grid);hist.append(sum(map(sum,grid)));states.append(grid)
    period=0
    if states[-1]==states[-2]:period=1
    elif steps>=2 and states[-1]==states[-3]:period=2
    return {'population_history':hist,'final_population':hist[-1],'detected_period':period,'rows':R,'cols':C},['Conway B3/S23 rule; toroidal wrap unless disabled; seeded random fill when no grid is supplied.'],['Cellular-automaton reference run; no claim about living systems.']
_META={'swarm_intelligence':_pso,'ant_colony_optimization':_aco,'bee_algorithm':_abc,'firefly_algorithm':_firefly,'cuckoo_search':_cuckoo,'bat_algorithm':_bat,'wolf_pack_algorithm':_gwo,'whale_optimization':_woa,'artificial_immune_systems':_clonalg,'artificial_life':_game_of_life}

# ================== evolutionary-computation rows 935-939 ==================
_GP_FUNS=[('+',2),('-',2),('*',2),('/',2)]
_GP_TERMS=['x',-2.0,-1.0,-0.5,0.5,1.0,2.0]
def _gp_tree(rng,depth,maxd,full):
    if depth>=maxd or (not full and rng.random()<.3):return rng.choice(_GP_TERMS)
    f,ar=rng.choice(_GP_FUNS)
    return [f]+[_gp_tree(rng,depth+1,maxd,full) for _ in range(ar)]
def _gp_eval(t,x):
    if isinstance(t,(int,float)):return float(t)
    if t=='x':return x
    vals=[_gp_eval(s,x) for s in t[1:]]
    if t[0]=='+':return vals[0]+vals[1]
    if t[0]=='-':return vals[0]-vals[1]
    if t[0]=='*':return vals[0]*vals[1]
    return vals[0]/vals[1] if abs(vals[1])>1e-9 else 1.0
def _gp_size(t):return 1 if not isinstance(t,list) else 1+sum(_gp_size(s) for s in t[1:])
def _gp_str(t):
    if not isinstance(t,list):return 'x' if t=='x' else f'{t:g}'
    return f'({_gp_str(t[1])} {t[0]} {_gp_str(t[2])})'
def _gp_nodes(t):
    out=[t]
    if isinstance(t,list):
        for s in t[1:]:out+=_gp_nodes(s)
    return out
def _gp_paths(t,prefix=()):
    yield prefix
    if isinstance(t,list):
        for i,sub in enumerate(t[1:],1):yield from _gp_paths(sub,prefix+(i,))
def _gp_replace_path(t,path,new):
    import copy
    root=copy.deepcopy(t)
    node=root
    for i in path[:-1]:node=node[i]
    if path:node[path[-1]]=new
    else:root=new
    return root
def _gp_cross(rng,a,b):
    import copy
    pa=rng.choice(list(_gp_paths(a)));sb=copy.deepcopy(rng.choice(_gp_nodes(b)))
    return _gp_replace_path(a,pa,sb)
def _gp_mut(rng,t,maxd):
    path=rng.choice(list(_gp_paths(t)))
    return _gp_replace_path(t,path,_gp_tree(rng,0,maxd,rng.random()<.5))
def _evolve_common(d,p):
    pts=_pairs(d,'target_points');pop=_int(d,'population',4);gens=_int(d,'generations')
    return pts,pop,gens
def _gp(d,p,rng):
    pts,popn,gens=_evolve_common(d,p);maxd=_int(p,'max_depth',2,4)
    P=[_gp_tree(rng,0,maxd,i%2==0) for i in range(popn)]
    def mse(t):
        try:return sum((_gp_eval(t,x)-y)**2 for x,y in pts)/len(pts)+1e-4*_gp_size(t)
        except (OverflowError,ValueError):return 1e18
    hist=[]
    for _ in range(gens):
        F=[mse(t) for t in P];elite=min(range(popn),key=lambda i:F[i]);new=[P[elite]]
        hist.append(F[elite])
        while len(new)<popn:
            def tourney():
                k=min(3,popn);cand=rng.sample(range(popn),k)
                return P[min(cand,key=lambda i:F[i])]
            child=_gp_cross(rng,tourney(),tourney()) if rng.random()<.9 else _gp_mut(rng,tourney(),maxd)
            if _gp_size(child)>4**maxd:child=_gp_tree(rng,0,2,False)
            new.append(child)
        P=new
    F=[mse(t) for t in P];bi=min(range(popn),key=lambda i:F[i]);best=P[bi]
    return {'best_expression':_gp_str(best),'best_mse':F[bi],'mse_history':hist,'tree_nodes':_gp_size(best),'seed_note':'reproducible for fixed seed'},['Koza-style tree GP: function set {+,-,*,protected /}, terminals {x, constants}, tournament selection, subtree crossover, parsimony penalty 1e-4 per node.'],['Symbolic-regression reference run; discovered expressions are hypotheses requiring validation on held-out data.']
_GE_EXPR=['binop','var','const']
def _ge_map(codons,max_wraps=3):
    pos=0;wraps=0;out=[]
    def nxt():
        nonlocal pos,wraps
        if pos>=len(codons):
            wraps+=1;pos=0
            if wraps>max_wraps:raise EmergingError('genome exhausted')
        c=codons[pos];pos+=1;return c
    def expr(depth):
        if depth>8:out.append('x');return
        c=nxt()%3
        if c==0:
            out.append('(');expr(depth+1);out.append(nxt()%4);expr(depth+1);out.append(')')
        elif c==1:out.append('x')
        else:out.append(float(nxt()%4))
    try:expr(0)
    except EmergingError:return None
    return out
def _ge_eval(mapped,x):
    stack=list(mapped);pos=0
    def parse():
        nonlocal pos
        tok=stack[pos];pos+=1
        if tok=='(':
            a=parse();op=stack[pos];pos+=1;b=parse();pos+=1
            if op==0:return a+b
            if op==1:return a-b
            if op==2:return a*b
            return a/b if abs(b)>1e-9 else 1.0
        if tok=='x':return x
        return float(tok)
    return parse()
def _ge_str(mapped):
    pos=0
    def parse():
        nonlocal pos
        tok=mapped[pos];pos+=1
        if tok=='(':
            a=parse();op='+ - * /'.split()[mapped[pos]];pos+=1;b=parse();pos+=1
            return f'({a} {op} {b})'
        return 'x' if tok=='x' else f'{tok:g}'
    return parse()
def _ge(d,p,rng):
    pts,popn,gens=_evolve_common(d,p);glen=_int(p,'genome_length',8,32)
    P=[[rng.randrange(256) for _ in range(glen)] for _ in range(popn)]
    def mse(g):
        m=_ge_map(g)
        if m is None:return 1e18
        try:return sum((_ge_eval(m,x)-y)**2 for x,y in pts)/len(pts)
        except (OverflowError,ValueError):return 1e18
    hist=[]
    for _ in range(gens):
        F=[mse(g) for g in P];elite=min(range(popn),key=lambda i:F[i]);new=[P[elite][:]];hist.append(F[elite])
        while len(new)<popn:
            def tourney():
                cand=rng.sample(range(popn),min(3,popn))
                return P[min(cand,key=lambda i:F[i])]
            a,b=tourney(),tourney();cut=rng.randrange(1,glen)
            child=a[:cut]+b[cut:]
            child=[(c+rng.randrange(256))%256 if rng.random()<.05 else c for c in child]
            new.append(child)
        P=new
    F=[mse(g) for g in P];bi=min(range(popn),key=lambda i:F[i]);m=_ge_map(P[bi])
    used=sum(1 for _ in m) if m else 0
    return {'best_expression':_ge_str(m) if m else None,'best_mse':F[bi],'mse_history':hist,'used_codons':used,'genome_length':glen,'seed_note':'reproducible for fixed seed'},['Grammatical evolution over an expression grammar (<expr> -> <expr><op><expr> | x | const), codon-mod mapping with at most 3 wraps, one-point crossover, 5% codon mutation.'],['Evolves expressions only; fitness is in-sample MSE and no causal model is implied.']
def _gep_decode(gene,h):
    funcs={'+','-','*','/'}
    nodes=list(gene);i=1
    root=[nodes[0]];queue=[root]
    while queue and i<len(nodes):
        parent=queue.pop(0)
        if parent[0] in funcs:
            for _ in range(2):
                child=[nodes[i]];i+=1;parent.append(child);queue.append(child)
    def ev(t,x):
        v=t[0]
        if v not in funcs:return x if v=='x' else float(v)
        a,b=ev(t[1],x),ev(t[2],x)
        if v=='+':return a+b
        if v=='-':return a-b
        if v=='*':return a*b
        return a/b if abs(b)>1e-9 else 1.0
    def render(t):
        v=t[0]
        if v not in funcs:return 'x' if v=='x' else f'{v:g}'
        return f'({render(t[1])} {v} {render(t[2])})'
    return root,ev,render
def _gep(d,p,rng):
    pts,popn,gens=_evolve_common(d,p);h=_int(p,'head_length',2,6);t=h+1;gl=h+t
    head_syms=['+','-','*','/','x',0.5,1.0,2.0];tail_syms=['x',0.5,1.0,2.0]
    def rand_gene():return [rng.choice(head_syms) for _ in range(h)]+[rng.choice(tail_syms) for _ in range(t)]
    P=[rand_gene() for _ in range(popn)]
    def mse(g):
        root,ev,_=_gep_decode(g,h)
        try:return sum((ev(root,x)-y)**2 for x,y in pts)/len(pts)
        except (OverflowError,ValueError):return 1e18
    hist=[]
    for _ in range(gens):
        F=[mse(g) for g in P];elite=min(range(popn),key=lambda i:F[i]);new=[P[elite][:]];hist.append(F[elite])
        while len(new)<popn:
            def tourney():
                cand=rng.sample(range(popn),min(3,popn))
                return P[min(cand,key=lambda i:F[i])]
            a,b=tourney(),tourney();cut=rng.randrange(1,gl);child=a[:cut]+b[cut:]
            for k in range(gl):
                if rng.random()<.05:child[k]=rng.choice(head_syms if k<h else tail_syms)
            new.append(child)
        P=new
    F=[mse(g) for g in P];bi=min(range(popn),key=lambda i:F[i]);root,_,render=_gep_decode(P[bi],h)
    return {'best_expression':render(root),'best_mse':F[bi],'mse_history':hist,'head_length':h,'gene':P[bi],'seed_note':'reproducible for fixed seed'},['Gene expression programming with Karva head/tail genes (tail = head+1 for arity 2), breadth-first decoding, one-point recombination, 5% symbol mutation.'],['Expression discovery is statistical; constants and structure need out-of-sample confirmation.']
def _es_impl(d,p,rng):
    dim=_int(d,'dimension');mu=_int(d,'mu')
    lam=d.get('lambda',d.get('lambda_'))
    if lam is None:raise EmergingError('lambda (offspring count) is required')
    if isinstance(lam,bool) or not isinstance(lam,(int,float)) or not float(lam).is_integer() or int(lam)<mu:raise EmergingError('lambda must be an integer >= mu')
    lam=int(lam);gens=_int(d,'generations');sig0=_pos(d,'initial_sigma')
    obj=d.get('objective','sphere')
    if obj not in ('sphere','rastrigin'):raise EmergingError('objective must be sphere or rastrigin')
    tp=1/math.sqrt(2*math.sqrt(dim));t0=1/math.sqrt(2*dim)
    P=[([rng.uniform(-5,5) for _ in range(dim)],[sig0]*dim) for _ in range(mu)]
    hist=[min(_objective(obj,x) for x,_ in P)]
    for _ in range(gens):
        off=[]
        for _ in range(lam):
            x,s=rng.choice(P)
            common=rng.gauss(0,1)
            s2=[sv*math.exp(tp*common+t0*rng.gauss(0,1)) for sv in s]
            x2=[xv+sv*rng.gauss(0,1) for xv,sv in zip(x,s2)]
            off.append((x2,s2))
        cand=P+off;cand.sort(key=lambda t:_objective(obj,t[0]));P=cand[:mu]
        hist.append(_objective(obj,P[0][0]))
    return {'best_position':P[0][0],'best_fitness':hist[-1],'fitness_history':hist,'final_sigma_mean':sum(P[0][1])/dim,'seed_note':'reproducible for fixed seed'},['(mu+lambda) evolution strategy with log-normal self-adaptive per-coordinate step sizes, tau primes as in Schwefel.'],['Continuous black-box reference optimizer; no surrogate or constraint handling.']
def _neuroevolution(d,p,rng):
    hidden=_int(p,'hidden_units',1,4);popn=_int(d,'population',4);gens=_int(d,'generations');mstd=_pos(d,'mutation_std')
    samples=d.get('samples')
    if samples is None:samples=[([0.0,0.0],0.0),([0.0,1.0],1.0),([1.0,0.0],1.0),([1.0,1.0],0.0)]
    if not isinstance(samples,list) or len(samples)<2:raise EmergingError('samples must be [[x1, x2], y] rows')
    data=[]
    for s in samples:
        if not isinstance(s,(list,tuple)) or len(s)!=2 or not isinstance(s[0],(list,tuple)) or len(s[0])!=2:raise EmergingError('samples must be [[x1, x2], y] rows')
        data.append(([_f(s[0][0],'x'),_f(s[0][1],'x')],_f(s[1],'y')))
    wlen=2*hidden+hidden+hidden+1
    def forward(w,x):
        hs=[]
        for j in range(hidden):
            z=w[2*j]*x[0]+w[2*j+1]*x[1]+w[2*hidden+j]
            hs.append(math.tanh(z))
        z=sum(w[3*hidden+j]*hs[j] for j in range(hidden))+w[-1]
        return 1/(1+math.exp(-z))
    def mse(w):return sum((forward(w,x)-y)**2 for x,y in data)/len(data)
    P=[[rng.gauss(0,1) for _ in range(wlen)] for _ in range(popn)];hist=[]
    for _ in range(gens):
        F=[mse(w) for w in P];order=sorted(range(popn),key=lambda i:F[i]);hist.append(F[order[0]])
        elites=[P[i] for i in order[:max(1,popn//4)]];new=[P[order[0]][:]]
        while len(new)<popn:
            a,b=rng.choice(elites),rng.choice(elites)
            child=[(av+bv)/2+mstd*rng.gauss(0,1) for av,bv in zip(a,b)]
            new.append(child)
        P=new
    F=[mse(w) for w in P];bi=min(range(popn),key=lambda i:F[i])
    acc=sum(1 for x,y in data if (forward(P[bi],x)>=.5)==(y>=.5))/len(data)
    return {'best_mse':F[bi],'best_accuracy':acc,'mse_history':hist,'topology':[2,hidden,1],'weights_evolved':wlen,'seed_note':'reproducible for fixed seed'},['Fixed-topology neuroevolution (2-h-1, tanh hidden, sigmoid output) with arithmetic-weight crossover, Gaussian mutation and elitism; default task is XOR.'],['Toy-network reference; no hardware training run and no generalization claim beyond supplied samples.']
_EVO={'genetic_programming':_gp,'grammatical_evolution':_ge,'gene_expression_programming':_gep,'evolutionary_strategies':_es_impl,'neuroevolution':_neuroevolution}

# ========================= robotics rows 940-947 =========================
def _r940_developmental_robotics(d,p,rng):
    regions=d.get('regions')
    if not isinstance(regions,list) or not regions:raise EmergingError('regions must be a non-empty list')
    eps=_f(p.get('exploration_floor',.01),'exploration_floor');samples=_int(d,'samples')
    info=[]
    for r in regions:
        if not isinstance(r,dict) or not isinstance(r.get('competence_errors'),list) or len(r['competence_errors'])<4:raise EmergingError('each region needs a competence_errors list of at least 4 values')
        errs=[_f(x,'competence_errors') for x in r['competence_errors']]
        if any(x<0 for x in errs):raise EmergingError('competence errors must be nonnegative')
        half=len(errs)//2
        progress=max(0.0,sum(errs[:half])/half-sum(errs[-half:])/len(errs[-half:]))
        info.append({'name':str(r.get('name',f'region_{len(info)}')),'learning_progress':progress})
    weights=[i['learning_progress']+eps for i in info];tot=sum(weights)
    counts={i['name']:0 for i in info}
    for _ in range(samples):
        r=rng.random()*tot;acc=0
        for i,w in zip(info,weights):
            acc+=w
            if acc>=r:counts[i['name']]+=1;break
    nxt=max(info,key=lambda i:i['learning_progress'])['name']
    return {'learning_progress':info,'selection_counts':counts,'next_region_estimate':nxt,'samples':samples,'seed_note':'reproducible for fixed seed'},['SAGG-RIAC-style intrinsic motivation: learning progress = drop in mean competence error between history halves; region choice proportional to progress plus floor.'],['Curiosity signal only; no motor commands are issued and developmental stage claims require embodied studies.']
def _r941_epigenetic_robotics(d,p,rng):
    stim=_vec(d,'stimulus_intensities');decay=_f(p.get('habituation_decay',.8),'habituation_decay');thresh=_f(p.get('response_threshold',.5),'response_threshold')
    if not 0<decay<1:raise EmergingError('habituation_decay must be within (0,1)')
    if any(s<0 for s in stim):raise EmergingError('stimulus intensities must be nonnegative')
    h=0.0;resp=[]
    for s in stim:
        resp.append(s/(1+h));h=decay*h+s
    first=resp[0] if resp[0]>0 else 1.0
    hab=1-resp[-1]/first if resp[0]>0 else 0.0
    peak=max(resp);dishab=len(resp)>1 and resp[-1]>1.5*resp[-2] and resp[-2]<peak
    stage='habituated' if hab>.6 else 'sensitizing' if hab<0 else 'attentive'
    return {'response_curve':resp,'habituation_index':hab,'stage_estimate':stage,'dishabituation_detected':dishab},['Dual-process habituation model: response = intensity/(1+H) with leaky accumulator H; stages labeled from response decrement.'],['Behavioral-timescale reference model; no infant-development or robot-learning claim is made.']
def _r942_morphological_computation(d,p,rng):
    sensor=_vec(d,'sensor_series',3);action=_vec(d,'action_series',3);morph=_vec(d,'morphology_params',3)
    if not(len(sensor)==len(action)==len(morph)):raise EmergingError('series must be aligned and equal length')
    def corr(x,y):
        mx,my=sum(x)/len(x),sum(y)/len(y)
        num=sum((a-mx)*(b-my) for a,b in zip(x,y));den=math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))
        if den==0:raise EmergingError('series variance must be nonzero')
        return num/den
    r_ma=corr(morph,action);r_sa=corr(sensor,action)
    mc=max(0.0,abs(r_ma)-abs(r_sa))
    bits=-.5*math.log2(max(1e-12,1-r_ma*r_ma))
    return {'morphology_action_correlation':r_ma,'sensor_action_correlation':r_sa,'morphological_computation_index':mc,'estimated_morphology_bits':bits},['Information-theoretic proxy: morphology computes when it predicts control actions better than raw sensors do; bits estimated from Gaussian MI -0.5 log2(1-r^2).'],['Correlation proxy, not a causal decomposition; embodiment claims need physical robots.']
def _r943_soft_robotics(d,p,rng):
    press=_pos(d,'pressure_kpa');length=_pos(d,'length_mm');wall=_pos(d,'wall_thickness_mm');modulus=_pos(d,'material_modulus_kpa')
    phi=_f(d.get('fiber_angle_deg',45),'fiber_angle_deg')
    if not 0<phi<90:raise EmergingError('fiber_angle_deg must be within (0, 90)')
    burst=_pos(d,'burst_pressure_kpa');diam=_pos(d,'outer_diameter_mm')
    k=math.sin(math.radians(2*phi))
    theta=k*(press/modulus)*(length/wall)
    area=math.pi*(diam/2000)**2
    force=press*1000*area
    out={'tip_angle_deg_estimate':math.degrees(theta),'blocked_force_n_estimate':force,'geometric_coupling':k,'within_safe_pressure':press<.5*burst,'safety_margin_kpa':.5*burst-press}
    a=['Fiber-reinforced bending actuator surrogate: tip angle proportional to pressure/modulus and length/wall with sin(2phi) coupling; blocked force = P * cross-section; 50% burst derating.']
    lim=['Surrogate design model only; no pneumatic hardware is actuated, and fatigue, hysteresis and certification tests are separate.']
    return out,a,lim
def _r944_swarm_robotics(d,p,rng):
    n=_int(d,'agents',2);steps=_int(d,'steps');arena=_pos(d,'arena_size');rad=_pos(d,'perception_radius')
    wc=_f(p.get('cohesion',.01),'cohesion');wa=_f(p.get('alignment',.05),'alignment');ws=_f(p.get('separation',.1),'separation')
    pos=[[rng.uniform(0,arena),rng.uniform(0,arena)] for _ in range(n)]
    vel=[[rng.uniform(-1,1),rng.uniform(-1,1)] for _ in range(n)]
    hist=[]
    for _ in range(steps):
        for i in range(n):
            nb=[j for j in range(n) if j!=i and math.dist(pos[i],pos[j])<rad]
            if not nb:continue
            cx=sum(pos[j][0] for j in nb)/len(nb);cy=sum(pos[j][1] for j in nb)/len(nb)
            vx=sum(vel[j][0] for j in nb)/len(nb);vy=sum(vel[j][1] for j in nb)/len(nb)
            sep=[0.0,0.0]
            for j in nb:
                dij=math.dist(pos[i],pos[j])
                if dij<rad/2 and dij>0:sep[0]+=(pos[i][0]-pos[j][0])/dij;sep[1]+=(pos[i][1]-pos[j][1])/dij
            vel[i][0]+=wc*(cx-pos[i][0])+wa*(vx-vel[i][0])+ws*sep[0]
            vel[i][1]+=wc*(cy-pos[i][1])+wa*(vy-vel[i][1])+ws*sep[1]
            sp=math.hypot(*vel[i])
            if sp>1:vel[i]=[v/sp for v in vel[i]]
        for i in range(n):
            pos[i][0]=(pos[i][0]+vel[i][0])%arena;pos[i][1]=(pos[i][1]+vel[i][1])%arena
        mx=sum(v[0] for v in vel)/n;my=sum(v[1] for v in vel)/n
        hist.append(math.hypot(mx,my))
    return {'order_parameter_history':hist,'final_order_parameter':hist[-1],'agents':n,'seed_note':'reproducible for fixed seed'},['Reynolds-style boids on a torus with unit-speed cap; order parameter = magnitude of mean velocity.'],['Kinematic reference swarm; no radio, motor or safety behavior of real robots is modeled.']
def _r945_modular_robotics(d,p,rng):
    n=_int(d,'module_count',2);dof=_int(d,'dof_per_module');mass=_pos(d,'module_mass_g');strength=_pos(d,'connector_strength_n');mlen=_pos(d,'module_length_mm');reach=_pos(d,'target_reach_mm')
    total_dof=n*dof;max_reach=n*mlen
    torque=sum((mass/1000)*9.81*(i*mlen/1000) for i in range(1,n+1))
    allow=strength*mlen/1000
    sf=allow/torque if torque>0 else float('inf')
    return {'total_dof':total_dof,'max_reach_mm':max_reach,'reach_feasible':reach<=max_reach,'cantilever_torque_nm':torque,'connector_allowable_nm':allow,'static_safety_factor':sf,'assembly_ok':reach<=max_reach and sf>=1},['Serial chain of identical modules; worst-case horizontal cantilever torque against a connector force couple at one module length.'],['Static design screen; dynamic loads, backlash and connector fatigue need test evidence.']
def _r946_self_reconfiguring_robots(d,p,rng):
    def cells(key):
        raw=d.get(key)
        if not isinstance(raw,list) or not raw or any(not isinstance(c,(list,tuple)) or len(c)!=2 for c in raw):raise EmergingError(f'{key} must be [x, y] lattice cells')
        out=set()
        for a,b in raw:
            if not float(a).is_integer() or not float(b).is_integer():raise EmergingError(f'{key} cells must be integer lattice points')
            out.add((int(a),int(b)))
        return out
    start=cells('start_shape');goal=cells('goal_shape')
    if len(start)!=len(goal):raise EmergingError('start_shape and goal_shape must contain the same number of modules')
    max_steps=_int(d,'max_steps')
    def connected(shape):
        if not shape:return True
        seen={next(iter(shape))};stack=list(seen)
        while stack:
            c=stack.pop()
            for nb in ((c[0]+1,c[1]),(c[0]-1,c[1]),(c[0],c[1]+1),(c[0],c[1]-1)):
                if nb in shape and nb not in seen:seen.add(nb);stack.append(nb)
        return seen==shape
    if not connected(start):raise EmergingError('start_shape must be 4-connected')
    shape=set(start);moves=[]
    empties=set(goal)-set(shape)
    while empties and len(moves)<max_steps:
        target=min(empties,key=lambda c:rng.random())
        cands=[c for c in shape-goal if any((c[0]+dx,c[1]+dy) in shape|{target} for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))]
        moved=False
        for c in sorted(cands,key=lambda c:abs(c[0]-target[0])+abs(c[1]-target[1])):
            trial=shape-{c}
            if connected(trial|{target}):
                shape=trial|{target};moves.append([list(c),list(target)]);empties.discard(target);moved=True;break
        if not moved:break
    matched=len(shape&goal)
    return {'moves':moves,'steps_used':len(moves),'goal_match_fraction':matched/len(goal),'reconfiguration_complete':shape==goal,'plan_only':True,'hardware_commands_emitted':False},['Greedy lattice reconfiguration: boundary modules slide to empty goal cells only when 4-connectivity is preserved; seeded tie-breaking.'],['Motion plan only; module docking physics, power and control are not executed or certified.']
def _r947_self_replicating_robots(d,p,rng):
    design=d.get('design')
    if not isinstance(design,dict):raise EmergingError('design object is required')
    parts=_int(design,'parts_count');fab=_int(design,'self_fabricated_parts',0)
    if fab>parts:raise EmergingError('self_fabricated_parts cannot exceed parts_count')
    cont=d.get('containment')
    if not isinstance(cont,dict):raise EmergingError('containment object is required')
    missing=[k for k in ('physical_isolation','remote_disable','feedstock_interlock') if cont.get(k) is not True]
    closure=fab/parts
    return {'closure_index':closure,'von_neumann_closure_complete':closure>=1,'containment_ok':not missing,'missing_controls':missing,'replication_authorized':False,'evaluation_only':True,'containment_required':True},['Design-paper review arithmetic: closure index = self-fabricated parts / total parts; replication is never authorized by this evaluator regardless of inputs.'],['Hard boundary: self-replication is not authorized, enabled or planned; missing containment controls block any downstream review.']

# ===================== advanced-materials rows 948-955 =====================
def _r948_molecular_nanotechnology(d,p,rng):
    atoms=_pos(d,'atoms_per_product');rate=_pos(d,'deposition_rate_atoms_per_s');tools=_int(d,'parallel_tools')
    err=_prob(d,'error_rate_per_op')
    if err>=1:raise EmergingError('error_rate_per_op must be below 1')
    t=atoms/(rate*tools)
    defects=atoms*err
    yield_p=math.exp(-defects)
    return {'build_time_s':t,'expected_misplaced_atoms':defects,'defect_free_yield_estimate':yield_p,'products_per_day':tools*86400/max(t,1e-12)},['Drexler-style serial mechanosynthesis arithmetic; independent per-operation errors; parallel tools divide wall time.'],['Paper design estimate; no atoms are positioned, and path-dependent chemistry, tooltip wear and thermal noise are excluded.']
def _r949_programmable_matter(d,p,rng):
    vol=_pos(d,'target_volume_mm3');edge=_pos(d,'module_edge_mm');mods=_int(d,'modules_available')
    energy=_f(d.get('energy_per_move_mj',1.0),'energy_per_move_mj');moves=_pos(d,'mean_moves_per_module')
    if energy<0:raise EmergingError('energy_per_move_mj must be nonnegative')
    vox=math.ceil(vol/edge**3)
    return {'voxels_required':vox,'shape_resolution_mm':edge,'feasible_with_inventory':mods>=vox,'module_deficit':max(0,vox-mods),'estimated_moves':vox*moves,'estimated_energy_joules':vox*moves*energy/1000},['Uniform cubic catom-style modules; volume fill without internal void optimization; mean path length caller-supplied.'],['Shape-planning arithmetic; modules are not actuated and mechanical/electrical module limits are not certified.']
def _r950_metamaterials(d,p,rng):
    r=_pos(d,'ring_radius_mm')/1000;w=_pos(d,'ring_width_mm')/1000;gap=_pos(d,'split_gap_mm')/1000
    epsr=_pos(d,'substrate_permittivity');f_ghz=_pos(d,'frequency_ghz');thick=_f(p.get('metallization_m',35e-6),'metallization_m')
    mu0=4*math.pi*1e-7;eps0=8.854e-12
    if not 0<w<2*r:raise EmergingError('ring_width_mm must be within (0, 2*ring_radius_mm)')
    L=mu0*r*(math.log(8*r/w)-2)
    C=eps0*epsr*w*thick/gap
    f0=1/(2*math.pi*math.sqrt(L*C))
    F=_f(p.get('fill_factor',.5),'fill_factor');gamma=_f(p.get('damping',.05),'damping')
    if not 0<F<1 or gamma<=0:raise EmergingError('fill_factor in (0,1) and positive damping required')
    wq=2*math.pi*f_ghz*1e9;w0=2*math.pi*f0
    denom=(wq**2-w0**2)**2+(gamma*w0*wq)**2
    mu_eff=1-F*wq**2*(wq**2-w0**2)/denom
    return {'resonance_ghz':f0/1e9,'inductance_h':L,'capacitance_f':C,'mu_eff_real_at_frequency':mu_eff,'negative_mu_at_frequency':mu_eff<0},['Single-split-ring resonator: loop inductance mu0 r (ln(8r/w) - 2), parallel-plate gap capacitance, Lorentz effective permeability with caller fill factor and damping.'],['Effective-medium estimate; no structure is fabricated or measured, and spatial dispersion is ignored.']
def _r951_negative_index_materials(d,p,rng):
    eps=_f(d.get('permittivity'),'permittivity');mu=_f(d.get('permeability'),'permeability')
    if eps==0 or mu==0:raise EmergingError('permittivity and permeability must be nonzero')
    theta_i=_f(d.get('incidence_angle_deg',30),'incidence_angle_deg');n_host=_pos(d,'host_index')
    if not 0<=theta_i<90:raise EmergingError('incidence_angle_deg must be within [0, 90)')
    if eps*mu<0:raise EmergingError('opposite-signed permittivity and permeability give evanescent propagation, not refraction')
    nim=eps<0 and mu<0
    n=-math.sqrt(eps*mu) if nim else math.sqrt(eps*mu)
    sin_t=n_host/n*math.sin(math.radians(theta_i))
    if abs(sin_t)>1:raise EmergingError('total internal reflection for supplied angle and indices')
    theta_t=math.degrees(math.asin(sin_t))
    return {'refractive_index':n,'negative_index_condition':nim,'refraction_angle_deg':theta_t,'negative_refraction':theta_t<0,'veselago_slab_focus_possible':nim and abs(abs(n)-n_host)<.05},['Lossless isotropic effective medium; Veselago sign convention n < 0 when both eps and mu are negative; Snell law applied with signed index.'],['Ideal-interface calculation; real NIMs are lossy, dispersive and narrowband.']
def _r952_cloaking_technology(d,p,rng):
    a=_pos(d,'inner_radius_mm');b=_pos(d,'outer_radius_mm')
    if b<=a:raise EmergingError('outer_radius_mm must exceed inner_radius_mm')
    wl=_pos(d,'wavelength_mm');base=_pos(d,'baseline_scattering');cloak=_f(d.get('cloaked_scattering'),'cloaked_scattering')
    if cloak<0:raise EmergingError('cloaked_scattering must be nonnegative')
    r=(a+b)/2
    return {'mu_r_mid':(r-a)/r,'mu_theta_mid':r/(r-a),'epsilon_z_mid':(b/(b-a))**2*(r-a)/r,'scattering_reduction':1-cloak/base,'size_parameter':2*math.pi*b/wl,'bandwidth_note':'transformation-optics profiles are dispersive; suppression holds over a narrow band only'},['Pendry cylindrical cloak profile evaluated at mid-shell; scattering figures are caller measurements, not simulations.'],['Idealized constitutive profile; manufacturing tolerances, absorption and polarization dependence limit real cloaks.']
def _r953_acoustic_metamaterials(d,p,rng):
    vol=_pos(d,'cavity_volume_mm3');neck=_pos(d,'neck_length_mm');area=_pos(d,'neck_area_mm2');freq=_pos(d,'frequency_hz')
    c=_f(p.get('sound_speed_m_s',343),'sound_speed_m_s');q=_f(p.get('quality_factor',10),'quality_factor')
    if c<=0 or q<=0:raise EmergingError('sound speed and quality factor must be positive')
    rn=math.sqrt(area/math.pi);leff=neck+1.6*rn
    f0=c/(2*math.pi)*math.sqrt(area/(vol*leff)*1000)
    bw=f0/q
    return {'resonance_hz':f0,'effective_neck_length_mm':leff,'bandwidth_hz_estimate':bw,'negative_bulk_modulus_band':abs(freq-f0)<bw/2},['Helmholtz resonator with 1.6r end correction; Lorentzian band estimate from caller quality factor; 3D unit conversions on mm inputs.'],['Lumped-element estimate; array coupling, thermoviscous loss and nonlinear regimes are not modeled.']
def _r954_thermal_metamaterials(d,p,rng):
    a=_pos(d,'inner_radius_mm');b=_pos(d,'outer_radius_mm')
    if b<=a:raise EmergingError('outer_radius_mm must exceed inner_radius_mm')
    k0=_pos(d,'background_conductivity_w_mk');tin=_f(d.get('inner_temp_c'),'inner_temp_c');tout=_f(d.get('outer_temp_c'),'outer_temp_c')
    if tin==tout:raise EmergingError('a nonzero temperature gradient is required')
    dev=_f(d.get('cloaked_temp_deviation_c',0),'cloaked_temp_deviation_c')
    if dev<0:raise EmergingError('cloaked_temp_deviation_c must be nonnegative')
    r=(a+b)/2
    ratio=((r-a)/r)**2
    return {'k_r_over_k_theta_mid':ratio,'k_r_mid':k0*ratio,'k_theta_mid':k0/ratio,'cloaking_efficiency':1-dev/abs(tout-tin),'core_gradient_shielded':dev<.05*abs(tout-tin)},['Transformation thermotics on a cylindrical shell; anisotropy ratio ((r-a)/r)^2 evaluated at mid-shell; deviation is caller-measured.'],['Steady-state conduction only; convection, radiation and contact resistance are excluded.']
def _r955_mechanical_metamaterials(d,p,rng):
    hl=_pos(d,'length_ratio_h_over_l');theta=_f(d.get('reentrant_angle_deg',60),'reentrant_angle_deg');rho=_prob(d,'relative_density')
    if not 0<theta<90:raise EmergingError('reentrant_angle_deg must be within (0, 90)')
    if rho==0:raise EmergingError('relative_density must be positive')
    tr=math.radians(theta)
    nu=-math.cos(tr)**2/((hl+math.sin(tr))*math.sin(tr))
    modulus=rho**2/math.sin(tr)
    return {'poisson_ratio_estimate':nu,'auxetic':nu<0,'modulus_ratio_estimate':modulus,'geometric_regime':'re-entrant honeycomb, bending-dominated'},['Gibson-Ashby re-entrant honeycomb: nu = -cos^2(theta) / ((h/l + sin(theta)) sin(theta)); modulus scales with relative density squared over sin(theta).'],['Ideal-cell estimates; imperfections, plasticity and rate effects move real lattice response.']
# ======================= printing / bio rows 956-959 =======================
def _r956_4d_printing(d,p,rng):
    em=_f(d.get('programmed_strain'),'programmed_strain');ep=_f(d.get('residual_strain'),'residual_strain')
    if em<=0:raise EmergingError('programmed_strain must be positive')
    if ep<0 or ep>em:raise EmergingError('residual_strain must be within [0, programmed_strain]')
    a1=_f(d.get('cte_1_per_k'),'cte_1_per_k');a2=_f(d.get('cte_2_per_k'),'cte_2_per_k')
    if a1==a2:raise EmergingError('distinct layer expansion coefficients are required for bending')
    dt=_f(d.get('delta_temp_k'),'delta_temp_k')
    if dt<=0:raise EmergingError('delta_temp_k must be positive')
    h=_pos(d,'total_thickness_mm');n=_pos(d,'modulus_ratio');m=_f(p.get('thickness_ratio',1.0),'thickness_ratio')
    if m<=0:raise EmergingError('thickness_ratio must be positive')
    kappa=6*(a2-a1)*dt*(1+m)**2/(h*(3*(1+m)**2+(1+m*n)*(m*m+1/(m*n))))
    recovery=(em-ep)/em
    return {'recovery_ratio':recovery,'bilayer_curvature_per_mm':kappa,'fold_radius_mm':abs(1/kappa) if kappa else None,'cycles_observed':_int(d,'cycles_observed',0,0) if d.get('cycles_observed') is not None else 0},['Timoshenko bilayer curvature with caller modulus/thickness ratios; shape-memory recovery ratio (em - ep)/em from supplied strain measurements.'],['Stimulus-response arithmetic; no print is run and fatigue, biocompatibility and application safety are unverified.']
def _r957_bioprinting(d,p,rng):
    R=_pos(d,'nozzle_radius_mm')/1000;L=_pos(d,'nozzle_length_mm')/1000;dp=_pos(d,'pressure_drop_kpa')*1000;eta=_pos(d,'viscosity_pa_s')
    viab=_vec(d,'cell_viability')
    if any(not 0<=x<=1 for x in viab):raise EmergingError('cell_viability entries must be within 0..1')
    q=math.pi*R**4*dp/(8*eta*L)
    tau=R*dp/(2*L)
    speed=q/(math.pi*R*R)
    warn=_f(p.get('shear_warn_pa',5000),'shear_warn_pa')
    return {'flow_rate_mm3_s':q*1e9,'wall_shear_pa':tau,'stage_speed_mm_s':speed*1000,'mean_cell_viability':sum(viab)/len(viab),'min_cell_viability':min(viab),'shear_stress_warning':tau>warn,'clinical_use_authorized':False},['Newtonian Hagen-Poiseuille extrusion; wall shear R*dP/(2L); stage speed matched to bead cross-section; viability is caller-supplied evidence.'],['Process estimate for research only; bioinks are shear-thinning, and sterility, maturation and in-vivo function require validated studies. Clinical use is never authorized.']
def _r958_organ_printing(d,p,rng):
    thick=_pos(d,'construct_thickness_mm');diff=_pos(d,'oxygen_diffusivity_mm2_s');c0=_pos(d,'surface_oxygen_concentration');cons=_pos(d,'cell_consumption_rate')
    pen=math.sqrt(2*diff*c0/cons)
    channels=math.ceil(thick/(2*pen))
    return {'oxygen_penetration_depth_mm':pen,'avascular_thickness_viable':thick<=2*pen,'perfusion_channels_required_estimate':channels,'construct_thickness_mm':thick,'vascularization_required':thick>2*pen,'clinical_use_authorized':False},['Zero-order oxygen consumption with penetration depth sqrt(2 D C0 / q); channels spaced at twice the penetration depth; caller supplies consistent units.'],['Design screening only; organ printing is not performed and no implantable, clinical or therapeutic claim is made.']
def _r959_tissue_engineering(d,p,rng):
    por=_prob(d,'scaffold_porosity');pore=_pos(d,'pore_size_um');n0=_pos(d,'initial_cells');dt=_pos(d,'doubling_time_h')
    k=_pos(d,'carrying_capacity');t=_f(d.get('culture_time_h',0),'culture_time_h')
    if t<0:raise EmergingError('culture_time_h must be nonnegative')
    if k<=n0:raise EmergingError('carrying_capacity must exceed initial_cells')
    if por==0:raise EmergingError('scaffold_porosity must be positive')
    r=math.log(2)/dt;A=(k-n0)/n0
    n_t=k/(1+A*math.exp(-r*t))
    diff=_f(p.get('oxygen_diffusivity_m2_s',2e-9),'oxygen_diffusivity_m2_s')
    half=_pos(d,'scaffold_half_thickness_mm')
    length=math.sqrt(2*diff*t*3600)*1000 if t>0 else 0.0
    return {'cells_at_culture_time':n_t,'doublings_elapsed':t/dt,'logistic_r_per_h':r,'oxygen_diffusion_length_mm':length,'nutrient_limited':length<half,'research_use_only':True},['Logistic growth with caller doubling time and carrying capacity; oxygen diffusion length sqrt(2 D t); porosity/pore size recorded as scaffold evidence.'],['In-vitro design arithmetic; sterility, differentiation, immunogenicity and long-term function are unestablished; never a clinical product.']
# ============================= dispatch surface =============================
_QUANTUM={'quantum_computing_application':_r910_quantum_computing_application,'quantum_algorithm_design':_r911_quantum_algorithm_design,'quantum_error_correction':_r912_quantum_error_correction,'quantum_machine_learning':_r913_quantum_machine_learning,'quantum_simulation':_r914_quantum_simulation,'quantum_cryptography':_r915_quantum_cryptography,'quantum_sensing':_r916_quantum_sensing,'quantum_networking':_r917_quantum_networking}
_ALT={'neuromorphic_computing':_r918_neuromorphic_computing,'spiking_neural_networks':_r919_spiking_neural_networks,'memristor_computing':_r920_memristor_computing,'optical_computing':_r921_optical_computing,'dna_computing':_r922_dna_computing,'molecular_computing':_r923_molecular_computing,'biological_computing':_r924_biological_computing}
_MAT={'molecular_nanotechnology':_r948_molecular_nanotechnology,'programmable_matter':_r949_programmable_matter,'metamaterials':_r950_metamaterials,'negative_index_materials':_r951_negative_index_materials,'cloaking_technology':_r952_cloaking_technology,'acoustic_metamaterials':_r953_acoustic_metamaterials,'thermal_metamaterials':_r954_thermal_metamaterials,'mechanical_metamaterials':_r955_mechanical_metamaterials}
_BIO={'4d_printing':_r956_4d_printing,'bioprinting':_r957_bioprinting,'organ_printing':_r958_organ_printing,'tissue_engineering':_r959_tissue_engineering}
_ROB={'developmental_robotics':_r940_developmental_robotics,'epigenetic_robotics':_r941_epigenetic_robotics,'morphological_computation':_r942_morphological_computation,'soft_robotics':_r943_soft_robotics,'swarm_robotics':_r944_swarm_robotics,'modular_robotics':_r945_modular_robotics,'self_reconfiguring_robots':_r946_self_reconfiguring_robots,'self_replicating_robots':_r947_self_replicating_robots}
REGISTRY={**_QUANTUM,**_ALT,**_META,**_EVO,**_ROB,**_MAT,**_BIO}
INPUTS={
'quantum_computing_application':['logical_qubits, t_gates, odd code_distance','classical_cost and quantum_cost resource proxies','gate_time_ns, physical_error_rate, threshold'],
'quantum_algorithm_design':['search_space_size and marked solutions count'],
'quantum_error_correction':['physical_error_rate, threshold and odd code_distance'],
'quantum_machine_learning':['hamiltonian_coefficients and aligned ansatz_parameters'],
'quantum_simulation':['term_coefficients, evolution_time, target_error and trotter_order'],
'quantum_cryptography':['sifted_bits, qber and error_correction_leak'],
'quantum_sensing':['resource count, readout_contrast, coherence_time_s, measurement_time_s'],
'quantum_networking':['aligned link_fidelities (>0.25) and link_success_probabilities'],
'neuromorphic_computing':['membrane_tau_ms, dt_ms, steps, input_current_na, membrane_resistance_mohm'],
'spiking_neural_networks':['pre_spike_times_ms and post_spike_times_ms with STDP amplitudes and time constants'],
'memristor_computing':['conductance_matrix within [g_min_s, g_max_s], aligned input_vector, device_noise_std, adc_bits'],
'optical_computing':['mesh dimension, insertion_loss_db_per_mzi, phase_shifter_power_mw, wavelength_nm'],
'dna_computing':['vertex_count, edge_count and even word_length'],
'molecular_computing':['species_initial concentrations, mass-action reactions, dt and steps'],
'biological_computing':['alpha1, alpha2 production rates and Hill coefficients beta, gamma'],
'swarm_intelligence':['bounds, objective, particles (PSO constants optional)'],
'ant_colony_optimization':['symmetric positive distance_matrix, ants, iterations'],
'bee_algorithm':['bounds, objective, colony_size, optional abandon_limit'],
'firefly_algorithm':['bounds, objective, fireflies, optional beta0/gamma/randomness'],
'cuckoo_search':['bounds, objective, nests, abandon_probability in (0,1)'],
'bat_algorithm':['bounds, objective, bats, optional frequency/loudness/pulse constants'],
'wolf_pack_algorithm':['bounds, objective, at least 4 wolves'],
'whale_optimization':['bounds, objective, whales, optional spiral_shape'],
'artificial_immune_systems':['bounds, objective, antibodies, optional clones_per_antibody'],
'artificial_life':['0/1 grid and steps (or seeded random fill via rows/cols/density)'],
'genetic_programming':['target_points [x, y] pairs, population, generations'],
'grammatical_evolution':['target_points pairs, population, generations, optional genome_length'],
'gene_expression_programming':['target_points pairs, population, generations, optional head_length'],
'evolutionary_strategies':['dimension, mu, lambda, generations, initial_sigma'],
'neuroevolution':['population, generations, mutation_std, optional 2-input samples'],
'developmental_robotics':['regions with competence_errors histories and sample count'],
'epigenetic_robotics':['stimulus_intensities series with habituation_decay'],
'morphological_computation':['aligned sensor_series, action_series and morphology_params with nonzero variance'],
'soft_robotics':['pressure_kpa, geometry, material_modulus_kpa, fiber_angle_deg, burst_pressure_kpa'],
'swarm_robotics':['agents, steps, arena_size, perception_radius and boid weights'],
'modular_robotics':['module_count, dof_per_module, masses, connector strength, module length, target reach'],
'self_reconfiguring_robots':['equal-size 4-connected start_shape and goal_shape lattice cells, max_steps'],
'self_replicating_robots':['design parts counts and containment flags; replication is never authorized'],
'molecular_nanotechnology':['atoms_per_product, deposition_rate_atoms_per_s, parallel_tools, error_rate_per_op'],
'programmable_matter':['target_volume_mm3, module_edge_mm, modules_available, mean_moves_per_module'],
'metamaterials':['split-ring geometry, substrate_permittivity, frequency_ghz'],
'negative_index_materials':['signed permittivity and permeability, incidence_angle_deg, host_index'],
'cloaking_technology':['inner/outer radii, wavelength_mm, baseline and cloaked scattering'],
'acoustic_metamaterials':['cavity_volume_mm3, neck geometry, frequency_hz'],
'thermal_metamaterials':['inner/outer radii, background_conductivity_w_mk, temperatures, deviation'],
'mechanical_metamaterials':['length_ratio_h_over_l, reentrant_angle_deg, relative_density'],
'4d_printing':['programmed_strain, residual_strain, layer CTEs, delta_temp_k, total_thickness_mm, modulus_ratio'],
'bioprinting':['nozzle geometry, pressure_drop_kpa, viscosity_pa_s, cell_viability evidence'],
'organ_printing':['construct_thickness_mm, oxygen diffusivity/concentration/consumption in consistent units'],
'tissue_engineering':['scaffold_porosity, pore_size_um, initial_cells, doubling_time_h, carrying_capacity, scaffold_half_thickness_mm']}
_BOUNDARY={'quantum':'Reference quantum design/evaluation arithmetic; no quantum device is invoked.','alternative':'Reference computing model; no unconventional hardware or wetware is programmed.','metaheuristic':'Seeded reference optimizer; no global-optimality certificate.','evolutionary':'Seeded evolutionary reference run; outputs are hypotheses requiring held-out validation.','robotics':'Kinematic/design reference; no robot is actuated or commanded.','materials':'Effective-property design estimate; nothing is fabricated, and manufacturability, bandwidth, toxicity and safety need qualified review.','bio':'Research-use-only calculation; no printing, culturing or clinical use is performed or authorized.'}
_FAMILY={**{k:'quantum' for k in _QUANTUM},**{k:'alternative' for k in _ALT},**{k:'metaheuristic' for k in _META if k!='artificial_life'},'artificial_life':'alternative',**{k:'evolutionary' for k in _EVO},**{k:'robotics' for k in _ROB},**{k:'materials' for k in _MAT},**{k:'bio' for k in _BIO}}
def run(method,data,params=None,seed=0):
    if method not in ROWS:raise EmergingError(f'unsupported emerging method {method}')
    if not isinstance(data,dict):raise EmergingError('data must be an object')
    p=params or {}
    if not isinstance(p,dict):raise EmergingError('params must be an object')
    rng=random.Random(seed)
    out,a,lim=REGISTRY[method](data,p,rng)
    return {'method':method,'feature_row':ROWS[method],'inputs':{'data':data,'params':p,'seed':seed},'assumptions':a,'method_limits':lim,'execution_boundary':_BOUNDARY[_FAMILY[method]],'physical_execution':'not_performed','output':out}
def catalog():return [{'method':m,'feature_row':r,'summary':SUMMARIES[m],'family':_FAMILY[m],'required_evidence':INPUTS[m]} for m,r in ROWS.items()]
