"""Bounded reference analytics for feature rows 1010-1034.

All methods are pure and consume caller-supplied numeric inputs. Stochastic
methods use a caller-visible deterministic seed. Every response includes
inputs, assumptions and method limits. These are small reference
implementations for dashboard-scale jobs, not replacements for scipy,
statsmodels, Stan/PyMC, or production forecasting systems.
"""
from __future__ import annotations
import math,random,statistics
from collections import Counter
ROWS={
"predictive":1010,"prescriptive":1011,"descriptive":1012,"diagnostic":1013,"eda":1014,"confirmatory":1015,"inference":1016,"hypothesis_test":1017,"confidence_interval":1018,"bootstrap":1019,"permutation_test":1020,"nonparametric":1021,"robust":1022,"outlier_detection":1023,"imputation":1024,"multiple_imputation":1025,"mle":1026,"em":1027,"mcmc":1028,"variational":1029,"gibbs":1030,"metropolis_hastings":1031,"hmc":1032,"smc":1033,"particle_filter":1034,"kalman_filter":1035,"extended_kalman_filter":1036,"unscented_kalman_filter":1037,"hidden_markov_model":1038,"conditional_random_field":1039,"graphical_model":1040,"bayesian_network":1041,"markov_random_field":1042,"factor_graph":1043,"belief_propagation":1044,"variational_message_passing":1045,"expectation_propagation":1046,"laplace_approximation":1047,"importance_sampling":1048,"rejection_sampling":1049,"slice_sampling":1050,"nested_sampling":1051,"approximate_bayesian_computation":1052,"synthetic_likelihood":1053,"indirect_inference":1054,"method_of_moments":1055,"generalized_method_of_moments":1056,"instrumental_variables":1057,"two_stage_least_squares":1058,"limited_information_maximum_likelihood":1059,"control_functions":1060,"regression_discontinuity":1061,"difference_in_differences":1062,"synthetic_control":1063,"matching_methods":1064,"propensity_score_matching":1065,"coarsened_exact_matching":1066,"genetic_matching":1067,"entropy_balancing":1068,"inverse_probability_weighting":1069,"doubly_robust_estimation":1070,"targeted_maximum_likelihood":1071,"machine_learning_causal_inference":1072}
def _nums(data,key="values",min_n=1):
    v=data.get(key)
    if not isinstance(v,list) or len(v)<min_n or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in v):raise ValueError(f"{key} must contain at least {min_n} finite numbers")
    return [float(x) for x in v]
def _mean(x):return sum(x)/len(x)
def _var(x,ddof=1):
    if len(x)<=ddof:return 0.0
    m=_mean(x);return sum((v-m)**2 for v in x)/(len(x)-ddof)
def _normal_cdf(z):return .5*(1+math.erf(z/math.sqrt(2)))
def _quantile(x,q):
    s=sorted(x);p=(len(s)-1)*q;lo=int(p);hi=min(lo+1,len(s)-1);return s[lo]+(s[hi]-s[lo])*(p-lo)
def _corr(x,y):
    mx,my=_mean(x),_mean(y);num=sum((a-mx)*(b-my) for a,b in zip(x,y));den=math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y));return num/den if den else 0.0
def _common(method,data,params,seed):return {"method":method,"feature_row":ROWS[method],"inputs":{"data":data,"params":params,"seed":seed},"assumptions":[],"limits":[]}
def run(method:str,data:dict,params:dict|None=None,seed:int=0)->dict:
    if method not in ROWS:raise ValueError(f"unsupported analysis method {method}")
    p=params or {};rng=random.Random(seed);o=_common(method,data,p,seed);a=o["assumptions"];limits=o["limits"]
    if method=="predictive":
        x=_nums(data,"x",2);y=_nums(data,"y",2)
        if len(x)!=len(y):raise ValueError("x and y lengths differ")
        vx=_var(x,0)
        if vx==0:raise ValueError("x has zero variance")
        slope=sum((u-_mean(x))*(v-_mean(y)) for u,v in zip(x,y))/sum((u-_mean(x))**2 for u in x);intercept=_mean(y)-slope*_mean(x);future=_nums(data,"future_x")
        o["output"]={"model":"simple_ols","intercept":intercept,"slope":slope,"predictions":[intercept+slope*z for z in future]};a+=['Linear relationship; independent errors; future inputs are caller-supplied.'];limits+=['One predictor only; no causal claim or forecast interval.']
    elif method=="prescriptive":
        options=data.get("options",[])
        if not options or any("name" not in v or "score" not in v for v in options):raise ValueError("options need name and score")
        objective=p.get("objective","max");best=(max if objective=="max" else min)(options,key=lambda v:v["score"])
        o["output"]={"recommended":best,"ranked":sorted(options,key=lambda v:v["score"],reverse=objective=="max")};a+=['Caller-defined score is the complete objective.'];limits+=['Ranks supplied options only; does not estimate effects or execute actions.']
    elif method in("descriptive","eda"):
        x=_nums(data);q1,q3=_quantile(x,.25),_quantile(x,.75)
        out={"n":len(x),"mean":_mean(x),"median":statistics.median(x),"stddev":math.sqrt(_var(x)),"min":min(x),"q1":q1,"q3":q3,"max":max(x)}
        if method=="eda":out.update({"iqr":q3-q1,"skewness":(sum((v-_mean(x))**3 for v in x)/len(x))/(math.sqrt(_var(x,0))**3) if _var(x,0)>0 else 0,"unique":len(set(x))})
        o["output"]=out;a+=['Rows supplied are the analysis population/sample.'];limits+=['Univariate summary; EDA findings are descriptive, not confirmatory.']
    elif method=="diagnostic":
        x=_nums(data,"x",3);y=_nums(data,"y",3)
        if len(x)!=len(y):raise ValueError("x and y lengths differ")
        o["output"]={"pearson_correlation":_corr(x,y),"candidate_driver":data.get("x_label","x")};a+=['Linear association is the requested diagnostic.'];limits+=['Correlation does not establish cause; omitted variables are not assessed.']
    elif method in("confirmatory","hypothesis_test"):
        x=_nums(data);mu=float(p.get("null_mean",0));alpha=float(p.get("alpha",.05));se=math.sqrt(_var(x))/math.sqrt(len(x))
        z=(_mean(x)-mu)/se if se else 0;pval=2*(1-_normal_cdf(abs(z))) if se else 1
        o["output"]={"test":"one_sample_normal_approx","estimate":_mean(x),"null_mean":mu,"z":z,"p_value":pval,"alpha":alpha,"reject":pval<alpha};a+=['Fixed-horizon two-sided test; independent observations; normal/large-sample approximation.'];limits+=['No optional-stopping correction; use an exact/domain test when approximation is unsuitable.']
    elif method in("inference","confidence_interval"):
        x=_nums(data, min_n=2);alpha=float(p.get("alpha",.05));z=float(p.get("z_critical",1.96));se=math.sqrt(_var(x))/math.sqrt(len(x));m=_mean(x)
        o["output"]={"estimate":m,"standard_error":se,"confidence_level":1-alpha,"interval":[m-z*se,m+z*se]};a+=['Independent observations; normal/large-sample interval; z-critical supplied/defaulted.'];limits+=['Not a small-sample t interval; interval coverage relies on assumptions.']
    elif method=="bootstrap":
        x=_nums(data, min_n=2);draws=int(p.get("draws",1000));draws=max(100,min(draws,10000));stats=[_mean([rng.choice(x) for _ in x]) for _ in range(draws)];alpha=float(p.get("alpha",.05))
        o["output"]={"statistic":"mean","estimate":_mean(x),"draws":draws,"percentile_interval":[_quantile(stats,alpha/2),_quantile(stats,1-alpha/2)]};a+=['Rows are exchangeable and representative; iid bootstrap.'];limits+=['Percentile interval only; capped at 10,000 draws; seed makes run reproducible.']
    elif method=="permutation_test":
        x=_nums(data,"group_a");y=_nums(data,"group_b");draws=max(100,min(int(p.get("draws",2000)),20000));observed=_mean(y)-_mean(x);pool=x+y;extreme=0
        for _ in range(draws):
            rng.shuffle(pool);d=_mean(pool[len(x):])-_mean(pool[:len(x)]);extreme+=abs(d)>=abs(observed)
        o["output"]={"difference":observed,"draws":draws,"p_value":(extreme+1)/(draws+1)};a+=['Group labels are exchangeable under the null; fixed-horizon test.'];limits+=['Monte Carlo approximation capped at 20,000 draws.']
    elif method=="nonparametric":
        x=_nums(data,"group_a");y=_nums(data,"group_b");combined=sorted([(v,0) for v in x]+[(v,1) for v in y]);ranks={}
        i=0
        while i<len(combined):
            j=i
            while j+1<len(combined) and combined[j+1][0]==combined[i][0]:j+=1
            rank=(i+j+2)/2
            for k in range(i,j+1):ranks.setdefault((combined[k][0],combined[k][1]),[]).append(rank)
            i=j+1
        ra=sum(sum(v) for (val,g),v in ranks.items() if g==0);u=ra-len(x)*(len(x)+1)/2;mu=len(x)*len(y)/2;sd=math.sqrt(len(x)*len(y)*(len(x)+len(y)+1)/12);z=(u-mu)/sd if sd else 0
        o["output"]={"test":"mann_whitney_normal_approx","u":u,"z":z,"p_value":2*(1-_normal_cdf(abs(z)))};a+=['Independent ordinal/continuous samples; equal shape if interpreted as location shift.'];limits+=['Normal approximation; tie variance correction omitted.']
    elif method=="robust":
        x=_nums(data);med=statistics.median(x);mad=statistics.median([abs(v-med) for v in x]);trim=float(p.get("trim",.1));k=int(len(x)*trim);sx=sorted(x);trimmed=sx[k:len(sx)-k] if 2*k<len(sx) else sx
        o["output"]={"median":med,"mad":mad,"trim_fraction":trim,"trimmed_mean":_mean(trimmed)};a+=['Median/MAD and symmetric trimmed mean requested.'];limits+=['MAD is unscaled; trim fraction is bounded by available rows.']
    elif method=="outlier_detection":
        x=_nums(data);q1,q3=_quantile(x,.25),_quantile(x,.75);factor=float(p.get("iqr_factor",1.5));lo,hi=q1-factor*(q3-q1),q3+factor*(q3-q1)
        o["output"]={"method":"iqr_fence","lower":lo,"upper":hi,"outliers":[{"index":i,"value":v} for i,v in enumerate(x) if v<lo or v>hi]};a+=['IQR fences suit roughly unimodal numeric data.'];limits+=['Flags are candidates, not proof of bad data.']
    elif method in("imputation","multiple_imputation"):
        vals=data.get("values")
        if not isinstance(vals,list) or not vals:raise ValueError("values must be a non-empty list")
        observed=[float(v) for v in vals if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)]
        if not observed:raise ValueError("at least one observed finite value required")
        m=_mean(observed);sd=math.sqrt(_var(observed)) if len(observed)>1 else 0
        if method=="imputation":out=[m if v is None else v for v in vals];o["output"]={"strategy":"mean","imputed":out,"fill_value":m,"missing_count":sum(v is None for v in vals)};limits+=['Single mean imputation understates uncertainty and distorts relationships.']
        else:
            datasets=max(2,min(int(p.get("datasets",5)),20));outs=[]
            for _ in range(datasets):outs.append([rng.gauss(m,sd) if v is None else v for v in vals])
            o["output"]={"strategy":"normal_draw","datasets":outs,"dataset_count":datasets,"observed_mean":m,"observed_sd":sd};limits+=['Univariate normal-draw approximation, not chained equations; capped at 20 datasets.']
        a+=['Missingness mechanism is ignorable (MCAR/MAR) for the chosen approximation.']
    elif method=="mle":
        x=_nums(data);m=_mean(x);v=_var(x,0);o["output"]={"distribution":"normal","mu_mle":m,"variance_mle":v,"log_likelihood":sum(-.5*math.log(2*math.pi*v)-((z-m)**2)/(2*v) for z in x) if v>0 else None};a+=['Independent identically distributed normal observations.'];limits+=['Normal model only; zero-variance likelihood omitted.']
    elif method=="em":
        x=_nums(data,min_n=4);iters=max(1,min(int(p.get("iterations",50)),500));means=[_quantile(x,.25),_quantile(x,.75)];vars=[max(_var(x,0),1e-6)]*2;weights=[.5,.5]
        for _ in range(iters):
            resp=[]
            for z in x:
                probs=[weights[k]/math.sqrt(2*math.pi*vars[k])*math.exp(-(z-means[k])**2/(2*vars[k])) for k in range(2)];den=sum(probs) or 1;resp.append([q/den for q in probs])
            for k in range(2):
                nk=sum(r[k] for r in resp) or 1e-12;means[k]=sum(r[k]*z for r,z in zip(resp,x))/nk;vars[k]=max(sum(r[k]*(z-means[k])**2 for r,z in zip(resp,x))/nk,1e-9);weights[k]=nk/len(x)
        o["output"]={"model":"two_normal_mixture","weights":weights,"means":means,"variances":vars,"iterations":iters};a+=['Two-component univariate Gaussian mixture.'];limits+=['Local optimum; quantile initialization; no convergence diagnostic or model selection.']
    elif method in("mcmc","metropolis_hastings"):
        x=_nums(data);draws=max(100,min(int(p.get("draws",2000)),20000));burn=min(int(p.get("burn",draws//5)),draws-1);proposal=float(p.get("proposal_sd",.5));obs_var=float(p.get("observation_variance",1));cur=_mean(x);accepted=0;samples=[]
        def logpost(mu):return -.5*mu*mu/100-sum((z-mu)**2/(2*obs_var) for z in x)
        for i in range(draws+burn):
            prop=rng.gauss(cur,proposal)
            if math.log(max(rng.random(),1e-300))<min(0,logpost(prop)-logpost(cur)):cur=prop;accepted+=1
            if i>=burn:samples.append(cur)
        o["output"]={"sampler":"random_walk_metropolis","posterior_mean":_mean(samples),"interval":[_quantile(samples,.025),_quantile(samples,.975)],"draws":draws,"acceptance_rate":accepted/(draws+burn)};a+=['Normal likelihood with known observation variance; Normal(0,100) prior.'];limits+=['Single-chain random-walk sampler; no R-hat/ESS; inspect acceptance and use production MCMC for decisions.']
    elif method=="variational":
        x=_nums(data);obs_var=float(p.get("observation_variance",1));prior_var=100;post_var=1/(1/prior_var+len(x)/obs_var);post_mean=post_var*sum(x)/obs_var
        o["output"]={"family":"normal_mean_conjugate","posterior_mean":post_mean,"posterior_variance":post_var,"elbo":None};a+=['Normal likelihood known variance; Normal(0,100) prior; exact conjugate solution represented in variational family.'];limits+=['One-parameter conjugate reference; no generic optimizer; ELBO omitted.']
    elif method=="gibbs":
        x=_nums(data);draws=max(100,min(int(p.get("draws",2000)),20000));mu=_mean(x);tau=1;mus=[];taus=[]
        for _ in range(draws):
            post_var=1/(.01+tau*len(x));post_mean=post_var*tau*sum(x);mu=rng.gauss(post_mean,math.sqrt(post_var));shape=1+len(x)/2;rate=1+sum((z-mu)**2 for z in x)/2;tau=rng.gammavariate(shape,1/rate);mus.append(mu);taus.append(tau)
        o["output"]={"model":"normal_unknown_mean_precision","mu_mean":_mean(mus),"precision_mean":_mean(taus),"draws":draws};a+=['Normal likelihood; Normal prior on mean; Gamma(1,1) precision prior.'];limits+=['Single chain; no convergence diagnostic.']
    elif method=="hmc":
        x=_nums(data);draws=max(50,min(int(p.get("draws",1000)),10000));step=float(p.get("step_size",.05));leaps=max(1,min(int(p.get("leapfrog_steps",10)),100));obs_var=float(p.get("observation_variance",1));q=_mean(x);samples=[];accepted=0
        def potential(mu):return .5*mu*mu/100+sum((z-mu)**2/(2*obs_var) for z in x)
        def grad(mu):return mu/100+sum(mu-z for z in x)/obs_var
        for _ in range(draws):
            q0=q;mom=rng.gauss(0,1);p0=mom;mom-=step*grad(q)/2
            for j in range(leaps):
                q+=step*mom
                if j<leaps-1:mom-=step*grad(q)
            mom-=step*grad(q)/2;mom=-mom
            if math.log(max(rng.random(),1e-300))<min(0,(potential(q0)+p0*p0/2)-(potential(q)+mom*mom/2)):accepted+=1
            else:q=q0
            samples.append(q)
        o["output"]={"posterior_mean":_mean(samples),"interval":[_quantile(samples,.025),_quantile(samples,.975)],"draws":draws,"acceptance_rate":accepted/draws,"step_size":step,"leapfrog_steps":leaps};a+=['One-dimensional normal-mean posterior; Euclidean unit mass.'];limits+=['1D educational HMC only; no adaptation, diagnostics, or autodiff.']
    elif method in("smc","particle_filter"):
        observations=_nums(data,"observations");particles=max(50,min(int(p.get("particles",1000)),20000));process_sd=float(p.get("process_sd",1));obs_sd=float(p.get("observation_sd",1));cloud=[float(p.get("initial_mean",0)) for _ in range(particles)];est=[];ess=[]
        for y in observations:
            cloud=[rng.gauss(v,process_sd) for v in cloud];weights=[math.exp(-.5*((y-v)/obs_sd)**2) for v in cloud];den=sum(weights) or 1;weights=[w/den for w in weights];est.append(sum(w*v for w,v in zip(weights,cloud)));ess.append(1/sum(w*w for w in weights));cdf=[];acc=0
            for w in weights:acc+=w;cdf.append(acc)
            new=[]
            for _ in cloud:
                u=rng.random();lo=0
                while lo<len(cdf)-1 and cdf[lo]<u:lo+=1
                new.append(cloud[lo])
            cloud=new
        o["output"]={"algorithm":"bootstrap_particle_filter","state_estimates":est,"effective_sample_sizes":ess,"particles":particles};a+=['1D random-walk state model and Gaussian observation model with caller-supplied standard deviations.'];limits+=['Bootstrap resampling every step; no smoothing, parameter learning, multidimensional state, or degeneracy remedy.']
    elif method=="kalman_filter":
        observations=_nums(data,"observations");transition=float(p.get("transition",1));observation=float(p.get("observation",1));q=float(p.get("process_variance",1));r=float(p.get("observation_variance",1));state=float(p.get("initial_state",0));variance=float(p.get("initial_variance",1));est=[];innovations=[];gains=[];variances=[]
        if q<0 or r<=0 or variance<0:raise ValueError("variances require process>=0, observation>0, initial>=0")
        for y in observations:
            predicted=transition*state;pred_var=transition*transition*variance+q;innovation=y-observation*predicted;s=observation*observation*pred_var+r;gain=pred_var*observation/s;state=predicted+gain*innovation;variance=(1-gain*observation)*pred_var
            est.append(state);innovations.append(innovation);gains.append(gain);variances.append(variance)
        o["output"]={"model":"scalar_linear_gaussian","filtered_states":est,"posterior_variances":variances,"innovations":innovations,"kalman_gains":gains};a += ["Scalar linear-Gaussian state-space model with caller-supplied transition and observation coefficients."];limits += ["Filtering only; scalar state; no smoothing, missing observations, control input, parameter learning, or covariance-stability square-root form."]
    elif method=="extended_kalman_filter":
        observations=_nums(data,"observations");model=p.get("observation_model","square");q=float(p.get("process_variance",.1));r=float(p.get("observation_variance",1));state=float(p.get("initial_state",1));variance=float(p.get("initial_variance",1));est=[];jacobians=[]
        if model not in {"square","exp"}:raise ValueError("observation_model must be square or exp")
        if q<0 or r<=0 or variance<0:raise ValueError("invalid variances")
        for y in observations:
            pred=state;pred_var=variance+q
            if model=="square":h=pred*pred;jac=2*pred
            else:h=math.exp(pred);jac=h
            innovation=y-h;s=jac*jac*pred_var+r;gain=pred_var*jac/s;state=pred+gain*innovation;variance=max(0,(1-gain*jac)*pred_var);est.append(state);jacobians.append(jac)
        o["output"]={"model":f"nonlinear_{model}_observation","filtered_states":est,"posterior_variance":variance,"observation_jacobians":jacobians};a += ["Identity process model and differentiable nonlinear scalar observation model; first-order local linearization."];limits += ["EKF can be biased or diverge for strong nonlinearity; scalar reference models square/exp only; inspect residuals and use domain tooling for decisions."]
    elif method=="unscented_kalman_filter":
        observations=_nums(data,"observations");model=p.get("observation_model","square");q=float(p.get("process_variance",.1));r=float(p.get("observation_variance",1));state=float(p.get("initial_state",1));variance=float(p.get("initial_variance",1));alpha=float(p.get("alpha",.5));beta=float(p.get("beta",2));kappa=float(p.get("kappa",0));est=[]
        if model not in {"square","exp"}:raise ValueError("observation_model must be square or exp")
        if q<0 or r<=0 or variance<0 or alpha<=0:raise ValueError("invalid UKF parameters")
        lam=alpha*alpha*(1+kappa)-1;c=1+lam
        if c<=0:raise ValueError("alpha/kappa yield non-positive sigma spread")
        wm=[lam/c,1/(2*c),1/(2*c)];wc=[wm[0]+(1-alpha*alpha+beta),wm[1],wm[2]]
        h=lambda x:x*x if model=="square" else math.exp(x)
        for y in observations:
            pred_var=variance+q;spread=math.sqrt(max(c*pred_var,0));sigma=[state,state+spread,state-spread];z=[h(x) for x in sigma];zmean=sum(w*v for w,v in zip(wm,z));svar=sum(w*(v-zmean)**2 for w,v in zip(wc,z))+r;cross=sum(w*(x-state)*(v-zmean) for w,x,v in zip(wc,sigma,z));gain=cross/svar;state=state+gain*(y-zmean);variance=max(0,pred_var-gain*gain*svar);est.append(state)
        o["output"]={"model":f"scaled_unscented_{model}_observation","filtered_states":est,"posterior_variance":variance,"sigma_parameters":{"alpha":alpha,"beta":beta,"kappa":kappa}};a += ["Identity scalar process and scaled unscented transform with Gaussian noise."];limits += ["Scalar square/exp observation reference; sensitive to sigma parameters; no smoothing or learned noise model."]
    elif method=="hidden_markov_model":
        obs=data.get("observations");states=data.get("states");start=data.get("start_probability");trans=data.get("transition_probability");emit=data.get("emission_probability")
        if not isinstance(obs,list) or not obs or not isinstance(states,list) or not states or not isinstance(start,dict) or not isinstance(trans,dict) or not isinstance(emit,dict):raise ValueError("observations, states, start_probability, transition_probability and emission_probability required")
        def prob(v,label):
            x=float(v)
            if x<0 or x>1:raise ValueError(f"{label} probabilities must be in [0,1]")
            return x
        for st in states:
            if st not in start or st not in trans or st not in emit:raise ValueError(f"missing parameters for state {st}")
            if abs(sum(prob(trans[st].get(t,0),"transition") for t in states)-1)>1e-6:raise ValueError(f"transition probabilities for {st} must sum to 1")
        if abs(sum(prob(start[st],"start") for st in states)-1)>1e-6:raise ValueError("start probabilities must sum to 1")
        alpha={st:prob(start[st],"start")*prob(emit[st].get(str(obs[0]),emit[st].get(obs[0],0)),"emission") for st in states};scale=sum(alpha.values())
        if scale<=0:raise ValueError("first observation has zero likelihood")
        loglik=math.log(scale);alpha={st:v/scale for st,v in alpha.items()};filtered=[dict(alpha)];viterbi={st:(math.log(max(prob(start[st],"start"),1e-300))+math.log(max(prob(emit[st].get(str(obs[0]),emit[st].get(obs[0],0)),"emission"),1e-300)),[st]) for st in states}
        for ob in obs[1:]:
            nxt={st:sum(alpha[prev]*prob(trans[prev].get(st,0),"transition") for prev in states)*prob(emit[st].get(str(ob),emit[st].get(ob,0)),"emission") for st in states};scale=sum(nxt.values())
            if scale<=0:raise ValueError(f"observation {ob!r} has zero likelihood")
            loglik+=math.log(scale);alpha={st:v/scale for st,v in nxt.items()};filtered.append(dict(alpha));nv={}
            for st in states:
                score,path=max((viterbi[prev][0]+math.log(max(prob(trans[prev].get(st,0),"transition"),1e-300)),viterbi[prev][1]) for prev in states);nv[st]=(score+math.log(max(prob(emit[st].get(str(ob),emit[st].get(ob,0)),"emission"),1e-300)),path+[st])
            viterbi=nv
        best=max(viterbi.values(),key=lambda x:x[0])
        o["output"]={"algorithm":"scaled_forward_and_viterbi","log_likelihood":loglik,"filtered_state_probabilities":filtered,"most_likely_path":best[1]};a += ["Finite first-order, time-homogeneous HMM; conditional independence of emissions given state."];limits += ["Caller supplies fixed probabilities; no Baum-Welch training, smoothing, unknown symbols, or higher-order duration model."]
    elif method=="conditional_random_field":
        tokens=data.get("tokens");labels=data.get("labels");emission=data.get("emission_scores");transition=data.get("transition_scores",{});start=data.get("start_scores",{})
        if not isinstance(tokens,list) or not tokens or not isinstance(labels,list) or not labels or not isinstance(emission,list) or len(emission)!=len(tokens):raise ValueError("tokens, labels and one emission score map per token required")
        if any(not isinstance(e,dict) or any(label not in e for label in labels) for e in emission):raise ValueError("every emission map must score every label")
        scores={label:(float(start.get(label,0))+float(emission[0][label]),[label]) for label in labels};logz_scores=dict(scores)
        for i in range(1,len(tokens)):
            nxt={};forward={}
            for label in labels:
                candidates=[(score+float(transition.get(prev,{}).get(label,0))+float(emission[i][label]),path+[label]) for prev,(score,path) in scores.items()];nxt[label]=max(candidates,key=lambda x:x[0])
                vals=[score+float(transition.get(prev,{}).get(label,0))+float(emission[i][label]) for prev,(score,_) in logz_scores.items()];m=max(vals);forward[label]=(m+math.log(sum(math.exp(v-m) for v in vals)),[])
            scores=nxt;logz_scores=forward
        best=max(scores.values(),key=lambda x:x[0]);vals=[v[0] for v in logz_scores.values()];m=max(vals);logz=m+math.log(sum(math.exp(v-m) for v in vals))
        o["output"]={"algorithm":"linear_chain_crf_viterbi","labels":best[1],"path_score":best[0],"log_partition":logz};a += ["Caller supplies log-potentials for a first-order linear-chain CRF."];limits += ["Decoding and partition function only; no feature extraction, marginals, gradient training, regularization, or higher-order dependencies."]
    elif method=="graphical_model":
        nodes=data.get("nodes");edges=data.get("edges");directed=bool(p.get("directed",True))
        if not isinstance(nodes,list) or not nodes or len(set(nodes))!=len(nodes) or not isinstance(edges,list):raise ValueError("unique nodes and edge pairs required")
        adjacency={n:[] for n in nodes};indegree={n:0 for n in nodes}
        for edge in edges:
            if not isinstance(edge,list) or len(edge)!=2 or edge[0] not in adjacency or edge[1] not in adjacency or edge[0]==edge[1]:raise ValueError("edges must connect distinct declared nodes")
            u,v=edge;adjacency[u].append(v)
            if directed:indegree[v]+=1
            else:adjacency[v].append(u)
        topo=[]
        if directed:
            queue=sorted([n for n,d in indegree.items() if d==0])
            while queue:
                n=queue.pop(0);topo.append(n)
                for v in adjacency[n]:
                    indegree[v]-=1
                    if indegree[v]==0:queue.append(v);queue.sort()
        components=[];seen=set()
        und={n:set() for n in nodes}
        for u,v in edges:und[u].add(v);und[v].add(u)
        for root in nodes:
            if root in seen:continue
            stack=[root];comp=[];seen.add(root)
            while stack:
                n=stack.pop();comp.append(n)
                for v in und[n]:
                    if v not in seen:seen.add(v);stack.append(v)
            components.append(sorted(comp))
        o["output"]={"directed":directed,"node_count":len(nodes),"edge_count":len(edges),"adjacency":adjacency,"components":components,"is_dag":(len(topo)==len(nodes)) if directed else None,"topological_order":topo if len(topo)==len(nodes) else None};a += ["Edges encode the caller's conditional-dependency structure."];limits += ["Structural diagnostics only; does not infer causal direction or learn graph structure from observations."]
    elif method=="bayesian_network":
        variables=data.get("variables");parents=data.get("parents",{});cpts=data.get("cpts",{});query=data.get("query");evidence=data.get("evidence",{})
        if not isinstance(variables,list) or not variables or query not in variables or not isinstance(evidence,dict):raise ValueError("variables and a query variable required")
        for var in variables:
            ps=parents.get(var,[])
            if any(x not in variables or variables.index(x)>=variables.index(var) for x in ps):raise ValueError("parents must precede children in topological variable order")
            if var not in cpts:raise ValueError(f"missing CPT for {var}")
        def ptrue(var,assign):
            ps=parents.get(var,[]);key=''.join('1' if assign[x] else '0' for x in ps);table=cpts[var]
            val=table.get(key,table.get('',table if isinstance(table,(int,float)) else None)) if isinstance(table,dict) else table
            if val is None:raise ValueError(f"missing CPT row for {var}:{key}")
            val=float(val)
            if not 0<=val<=1:raise ValueError("CPT probabilities must be in [0,1]")
            return val
        def enumerate_all(i,assign):
            if i==len(variables):return 1.0
            var=variables[i]
            if var in assign:
                pt=ptrue(var,assign);return (pt if assign[var] else 1-pt)*enumerate_all(i+1,assign)
            total=0
            for val in (False,True):
                assign[var]=val;pt=ptrue(var,assign);total+=(pt if val else 1-pt)*enumerate_all(i+1,assign);del assign[var]
            return total
        probs=[]
        for val in (False,True):
            assign={k:bool(v) for k,v in evidence.items()};assign[query]=val;probs.append(enumerate_all(0,assign))
        z=sum(probs)
        if z<=0:raise ValueError("evidence has zero probability")
        o["output"]={"algorithm":"exact_enumeration","query":query,"probability_false":probs[0]/z,"probability_true":probs[1]/z,"evidence":evidence};a += ["Binary discrete DAG; variables are topologically ordered; CPTs are complete."];limits += ["Exact enumeration is exponential; binary variables only; observational conditioning is not automatically causal."]
    elif method=="markov_random_field":
        variables=data.get("variables");edges=data.get("edges",[]);unary=data.get("unary_log_potentials",{});pairwise=data.get("pairwise_log_potentials",{})
        if not isinstance(variables,list) or not variables or len(variables)>20:raise ValueError("1-20 variables required for exact enumeration")
        configs=[];z=0.0
        for bits in range(1<<len(variables)):
            assign={v:bool(bits&(1<<i)) for i,v in enumerate(variables)};energy=0.0
            for v in variables:energy+=float(unary.get(v,{}).get('1' if assign[v] else '0',0))
            for edge in edges:
                u,v=edge;table=pairwise.get(f"{u}|{v}",pairwise.get(f"{v}|{u}",{}));key=('1' if assign[u] else '0')+('1' if assign[v] else '0');energy+=float(table.get(key,0))
            weight=math.exp(energy);configs.append((assign,energy,weight));z+=weight
        marginals={v:sum(w for assign,_,w in configs if assign[v])/z for v in variables};best=max(configs,key=lambda x:x[1])
        o["output"]={"algorithm":"exact_log_potential_enumeration","partition_function":z,"marginal_true":marginals,"map_assignment":best[0],"map_log_potential":best[1]};a += ["Binary undirected model; supplied values are log-potentials, not normalized probabilities."];limits += ["Exact enumeration capped at 20 variables; pairwise factors only; no structure/parameter learning."]
    elif method=="factor_graph":
        variables=data.get("variables");factors=data.get("factors")
        if not isinstance(variables,list) or not variables or len(variables)>20 or not isinstance(factors,list):raise ValueError("1-20 variables and factors required")
        configs=[];z=0.0
        for bits in range(1<<len(variables)):
            assign={v:bool(bits&(1<<i)) for i,v in enumerate(variables)};weight=1.0
            for factor in factors:
                scope=factor.get("scope",[]);table=factor.get("table",{});key=''.join('1' if assign[v] else '0' for v in scope)
                if any(v not in assign for v in scope) or key not in table:raise ValueError("factor scope/table is incomplete")
                value=float(table[key])
                if value<0:raise ValueError("factor values must be non-negative")
                weight*=value
            configs.append((assign,weight));z+=weight
        if z<=0:raise ValueError("factor graph has zero total mass")
        marginals={v:sum(w for assign,w in configs if assign[v])/z for v in variables};best=max(configs,key=lambda x:x[1])
        o["output"]={"algorithm":"exact_factor_product_enumeration","partition_function":z,"marginal_true":marginals,"map_assignment":best[0],"map_probability":best[1]/z};a += ["Binary finite factor graph with complete non-negative factor tables."];limits += ["Exact enumeration capped at 20 variables; no loopy belief propagation or continuous variables."]
    elif method=="belief_propagation":
        variables=data.get("variables");factors=data.get("factors");iterations=max(1,min(int(p.get("iterations",20)),500));damping=float(p.get("damping",0));
        if not isinstance(variables,list) or not variables or not isinstance(factors,list) or not 0<=damping<1:raise ValueError("variables, factors and damping in [0,1) required")
        neighbors={v:[] for v in variables}
        for i,f in enumerate(factors):
            for v in f.get("scope",[]):
                if v not in neighbors:raise ValueError("unknown factor variable")
                neighbors[v].append(i)
        vf={(v,i):[.5,.5] for v in variables for i in neighbors[v]};fv={(i,v):[.5,.5] for v in variables for i in neighbors[v]}
        def norm(x):
            z=sum(x)
            if z<=0:raise ValueError("zero-mass message")
            return [a/z for a in x]
        for _ in range(iterations):
            nf={}
            for i,f in enumerate(factors):
                scope=f.get("scope",[]);table=f.get("table",{})
                for target in scope:
                    vals=[0.0,0.0];others=[v for v in scope if v!=target]
                    for bits in range(1<<len(others)):
                        assign={v:bool(bits&(1<<j)) for j,v in enumerate(others)}
                        for tv in (False,True):
                            assign[target]=tv;key=''.join('1' if assign[v] else '0' for v in scope)
                            if key not in table:raise ValueError("incomplete factor table")
                            weight=float(table[key])
                            for v in others:weight*=vf[(v,i)][1 if assign[v] else 0]
                            vals[1 if tv else 0]+=weight
                    fresh=norm(vals);old=fv[(i,target)];nf[(i,target)]=norm([damping*old[j]+(1-damping)*fresh[j] for j in range(2)])
            fv=nf;nv={}
            for v in variables:
                for target in neighbors[v]:
                    vals=[1.0,1.0]
                    for i in neighbors[v]:
                        if i!=target:
                            vals[0]*=fv[(i,v)][0];vals[1]*=fv[(i,v)][1]
                    nv[(v,target)]=norm(vals)
            vf=nv
        beliefs={}
        for v in variables:
            vals=[1.0,1.0]
            for i in neighbors[v]:vals[0]*=fv[(i,v)][0];vals[1]*=fv[(i,v)][1]
            beliefs[v]=norm(vals)[1]
        o["output"]={"algorithm":"sum_product","marginal_true":beliefs,"iterations":iterations,"damping":damping,"converged_on_tree":sum(max(0,len(f.get("scope",[]))-1) for f in factors)==len(variables)-1};a += ["Binary finite factor graph and non-negative complete factor tables."];limits += ["Exact on trees after sufficient passes; loopy results are approximate and need convergence checks; fixed iteration budget."]
    elif method=="variational_message_passing":
        observations=_nums(data,"observations");prior_mean=float(p.get("prior_mean",0));prior_variance=float(p.get("prior_variance",100));observation_variance=float(p.get("observation_variance",1))
        if prior_variance<=0 or observation_variance<=0:raise ValueError("variances must be positive")
        prior_precision=1/prior_variance;likelihood_precision=len(observations)/observation_variance;posterior_precision=prior_precision+likelihood_precision;posterior_variance=1/posterior_precision;posterior_mean=posterior_variance*(prior_precision*prior_mean+sum(observations)/observation_variance)
        messages={"prior_to_mean":{"precision":prior_precision,"precision_mean":prior_precision*prior_mean},"likelihood_to_mean":{"precision":likelihood_precision,"precision_mean":sum(observations)/observation_variance}}
        o["output"]={"family":"conjugate_normal","posterior_mean":posterior_mean,"posterior_variance":posterior_variance,"natural_parameter_messages":messages,"iterations":1,"converged":True};a += ["Conjugate Normal prior and Normal likelihood with known variance; mean-field family contains the exact posterior."];limits += ["Single latent mean reference graph; no nonconjugate factors, automatic graph compiler, or generic ELBO optimizer."]
    elif method=="expectation_propagation":
        lower=float(data.get("lower"));prior_mean=float(p.get("prior_mean",0));prior_variance=float(p.get("prior_variance",1))
        if prior_variance<=0:raise ValueError("prior_variance must be positive")
        sd=math.sqrt(prior_variance);alpha=(lower-prior_mean)/sd;tail=max(1-_normal_cdf(alpha),1e-300);phi=math.exp(-alpha*alpha/2)/math.sqrt(2*math.pi);ratio=phi/tail;mean_post=prior_mean+sd*ratio;var_post=prior_variance*(1+alpha*ratio-ratio*ratio)
        site_precision=1/var_post-1/prior_variance;site_precision_mean=mean_post/var_post-prior_mean/prior_variance
        o["output"]={"model":"gaussian_prior_times_lower_truncation_factor","moment_matched_mean":mean_post,"moment_matched_variance":var_post,"site_natural_parameters":{"precision":site_precision,"precision_mean":site_precision_mean},"normalizer":tail};a += ["One-dimensional Gaussian cavity and indicator factor x>lower; EP moment match is analytic."];limits += ["Single-site reference; no iterative multi-site EP, power EP, damping, or negative-variance recovery."]
    elif method=="laplace_approximation":
        observations=_nums(data,"observations");trials=data.get("trials");successes=data.get("successes")
        if not isinstance(trials,list) or not isinstance(successes,list) or len(trials)!=len(observations) or len(successes)!=len(observations):raise ValueError("observations, trials and successes must align")
        prior_variance=float(p.get("prior_variance",100));mode=float(p.get("initial",0));tol=float(p.get("tolerance",1e-9));iters=max(1,min(int(p.get("iterations",100)),1000))
        if prior_variance<=0 or any(n<=0 or y<0 or y>n for y,n in zip(successes,trials)):raise ValueError("invalid variance or binomial counts")
        converged=False
        for i in range(iters):
            probs=[1/(1+math.exp(-max(-700,min(700,mode*x)))) for x in observations];grad=-mode/prior_variance+sum(x*(y-n*pr) for x,y,n,pr in zip(observations,successes,trials,probs));hess=-1/prior_variance-sum(n*x*x*pr*(1-pr) for x,n,pr in zip(observations,trials,probs));step=grad/hess;new=mode-step
            if abs(new-mode)<tol:mode=new;converged=True;break
            mode=new
        variance=-1/hess
        o["output"]={"model":"one_parameter_binomial_logistic","posterior_mode":mode,"gaussian_variance":variance,"iterations":i+1,"converged":converged,"interval":[mode-1.96*math.sqrt(variance),mode+1.96*math.sqrt(variance)]};a += ["Independent binomial observations, one coefficient, Normal(0, prior_variance) prior; posterior locally Gaussian near a single mode."];limits += ["Laplace can misrepresent skewed/multimodal posteriors; one parameter only; inspect convergence and use production inference for consequential decisions."]
    elif method=="importance_sampling":
        draws=max(100,min(int(p.get("draws",5000)),50000));proposal_mean=float(p.get("proposal_mean",0));proposal_sd=float(p.get("proposal_sd",2));target_mean=float(p.get("target_mean",1));target_sd=float(p.get("target_sd",1))
        if proposal_sd<=0 or target_sd<=0:raise ValueError("standard deviations must be positive")
        samples=[];weights=[]
        for _ in range(draws):
            x=rng.gauss(proposal_mean,proposal_sd);logw=-.5*((x-target_mean)/target_sd)**2-math.log(target_sd)+.5*((x-proposal_mean)/proposal_sd)**2+math.log(proposal_sd);samples.append(x);weights.append(math.exp(min(700,logw)))
        z=sum(weights);norm=[w/z for w in weights];estimate=sum(w*x for w,x in zip(norm,samples));ess=1/sum(w*w for w in norm)
        o["output"]={"target_expectation":estimate,"effective_sample_size":ess,"draws":draws,"normalized_weight_max":max(norm),"proposal":{"mean":proposal_mean,"sd":proposal_sd}};a += ["Normalized Gaussian target and Gaussian proposal with overlapping support."];limits += ["Self-normalized estimate; weight degeneracy can make nominal draws misleading; inspect ESS."]
    elif method=="rejection_sampling":
        draws=max(1,min(int(p.get("accepted_draws",1000)),20000));proposal_mean=float(p.get("proposal_mean",0));proposal_sd=float(p.get("proposal_sd",2));target_mean=float(p.get("target_mean",1));target_sd=float(p.get("target_sd",1));bound=float(p.get("bound",3));max_attempts=max(draws,min(int(p.get("max_attempts",draws*100)),2000000))
        if proposal_sd<=0 or target_sd<=0 or bound<=0:raise ValueError("scales and bound must be positive")
        accepted=[];attempts=0;violations=0
        while len(accepted)<draws and attempts<max_attempts:
            attempts+=1;x=rng.gauss(proposal_mean,proposal_sd);target=math.exp(-.5*((x-target_mean)/target_sd)**2)/target_sd;proposal=math.exp(-.5*((x-proposal_mean)/proposal_sd)**2)/proposal_sd;ratio=target/(bound*proposal)
            if ratio>1:violations+=1
            if rng.random()<min(1,ratio):accepted.append(x)
        if violations:raise ValueError("rejection bound is invalid: target exceeds bound times proposal")
        o["output"]={"accepted":len(accepted),"attempts":attempts,"acceptance_rate":len(accepted)/attempts if attempts else 0,"sample_mean":_mean(accepted) if accepted else None,"completed":len(accepted)==draws};a += ["Gaussian target/proposal and caller-supplied envelope bound valid everywhere."];limits += ["Fails on detected bound violations; finite attempts can return incomplete; Gaussian reference families only."]
    elif method=="slice_sampling":
        draws=max(50,min(int(p.get("draws",2000)),20000));width=float(p.get("width",1));steps=max(1,min(int(p.get("max_steps_out",100)),1000));target_mean=float(p.get("target_mean",1));target_sd=float(p.get("target_sd",1));x=float(p.get("initial",target_mean));samples=[]
        if width<=0 or target_sd<=0:raise ValueError("width and target_sd must be positive")
        logpdf=lambda z:-.5*((z-target_mean)/target_sd)**2
        for _ in range(draws):
            logy=logpdf(x)+math.log(max(rng.random(),1e-300));left=x-width*rng.random();right=left+width;j=int(steps*rng.random());k=steps-1-j
            while j>0 and logpdf(left)>logy:left-=width;j-=1
            while k>0 and logpdf(right)>logy:right+=width;k-=1
            while True:
                cand=rng.uniform(left,right)
                if logpdf(cand)>=logy:x=cand;break
                if cand<x:left=cand
                else:right=cand
            samples.append(x)
        o["output"]={"sample_mean":_mean(samples),"interval":[_quantile(samples,.025),_quantile(samples,.975)],"draws":draws,"width":width};a += ["Continuous one-dimensional Gaussian target known up to proportionality."];limits += ["Stepping-out univariate slice sampler; width affects efficiency; no diagnostics or multivariate adaptation."]
    elif method=="nested_sampling":
        live=max(20,min(int(p.get("live_points",200)),2000));iterations=max(10,min(int(p.get("iterations",1000)),20000));prior_low=float(p.get("prior_low",-10));prior_high=float(p.get("prior_high",10));obs=float(data.get("observation",0));likelihood_sd=float(p.get("likelihood_sd",1))
        if prior_high<=prior_low or likelihood_sd<=0:raise ValueError("invalid prior interval or likelihood scale")
        loglike=lambda x:-.5*((obs-x)/likelihood_sd)**2-math.log(math.sqrt(2*math.pi)*likelihood_sd)
        points=[(rng.uniform(prior_low,prior_high),0) for _ in range(live)];points=[(x,loglike(x)) for x,_ in points];logz=-math.inf;dead=[]
        def logadd(a,b):
            if a==-math.inf:return b
            m=max(a,b);return m+math.log(math.exp(a-m)+math.exp(b-m))
        for i in range(iterations):
            worst=min(range(live),key=lambda j:points[j][1]);x,ll=points[worst];logwidth=math.log(math.exp(-i/live)-math.exp(-(i+1)/live));logz=logadd(logz,logwidth+ll);dead.append((x,ll));tries=0
            while True:
                cand=rng.uniform(prior_low,prior_high);cl=loglike(cand);tries+=1
                if cl>ll:points[worst]=(cand,cl);break
                if tries>100000:raise ValueError("failed constrained-prior replacement")
        o["output"]={"log_evidence":logz,"live_points":live,"iterations":iterations,"dead_point_count":len(dead)};a += ["Uniform bounded prior and one-dimensional Gaussian likelihood; deterministic expected shrinkage exp(-i/live_points)."];limits += ["Reference nested sampler omits stochastic shrinkage error, posterior weights and final live-point evidence remainder."]
    elif method=="approximate_bayesian_computation":
        observed=float(data.get("observed_summary"));draws=max(100,min(int(p.get("draws",10000)),200000));epsilon=float(p.get("epsilon",.1));prior_low=float(p.get("prior_low",-10));prior_high=float(p.get("prior_high",10));simulation_sd=float(p.get("simulation_sd",1));accepted=[]
        if epsilon<=0 or prior_high<=prior_low or simulation_sd<=0:raise ValueError("invalid epsilon, prior or simulation scale")
        for _ in range(draws):
            theta=rng.uniform(prior_low,prior_high);sim=rng.gauss(theta,simulation_sd)
            if abs(sim-observed)<=epsilon:accepted.append(theta)
        o["output"]={"algorithm":"abc_rejection","accepted":len(accepted),"draws":draws,"acceptance_rate":len(accepted)/draws,"posterior_mean":_mean(accepted) if accepted else None,"posterior_interval":[_quantile(accepted,.025),_quantile(accepted,.975)] if accepted else None,"epsilon":epsilon};a += ["Observed scalar summary; uniform prior; Gaussian simulator; absolute-distance acceptance kernel."];limits += ["Posterior is epsilon-dependent and summary-limited; low acceptance or insufficient summary statistics can bias inference."]
    elif method=="synthetic_likelihood":
        observed=_nums(data,"observed_summary");simulated=data.get("simulated_summaries")
        if not isinstance(simulated,list) or len(simulated)<3 or any(not isinstance(row,list) or len(row)!=len(observed) for row in simulated):raise ValueError("at least three aligned simulated summary vectors required")
        sims=[[float(v) for v in row] for row in simulated];dim=len(observed);mu=[_mean([r[j] for r in sims]) for j in range(dim)]
        if dim==1:
            var=_var([r[0] for r in sims],0)
            if var<=0:raise ValueError("simulated summary variance must be positive")
            loglik=-.5*(math.log(2*math.pi*var)+(observed[0]-mu[0])**2/var);cov=[[var]]
        elif dim==2:
            a11=_var([r[0] for r in sims],0);a22=_var([r[1] for r in sims],0);a12=_mean([(r[0]-mu[0])*(r[1]-mu[1]) for r in sims]);det=a11*a22-a12*a12
            if det<=0:raise ValueError("simulated covariance must be positive definite")
            d0,d1=observed[0]-mu[0],observed[1]-mu[1];quad=(a22*d0*d0-2*a12*d0*d1+a11*d1*d1)/det;loglik=-.5*(2*math.log(2*math.pi)+math.log(det)+quad);cov=[[a11,a12],[a12,a22]]
        else:raise ValueError("reference implementation supports one or two summary dimensions")
        o["output"]={"synthetic_log_likelihood":loglik,"simulated_mean":mu,"simulated_covariance":cov,"simulation_count":len(sims)};a += ["Summary statistics at the candidate parameter are approximately multivariate Normal."];limits += ["One/two summary dimensions; caller supplies simulations; covariance Monte Carlo error can dominate at low simulation count."]
    elif method=="indirect_inference":
        observed=float(data.get("observed_auxiliary"));grid=_nums(data,"parameter_grid");simulated=data.get("simulated_auxiliary")
        if not isinstance(simulated,list) or len(simulated)!=len(grid) or any(not isinstance(v,list) or not v for v in simulated):raise ValueError("one non-empty simulated auxiliary list per parameter required")
        distances=[]
        for theta,vals in zip(grid,simulated):distances.append({"parameter":theta,"simulated_auxiliary_mean":_mean([float(x) for x in vals]),"distance":abs(_mean([float(x) for x in vals])-observed)})
        best=min(distances,key=lambda x:x["distance"]);o["output"]={"estimate":best["parameter"],"observed_auxiliary":observed,"binding_grid":distances};a += ["Auxiliary statistic identifies the structural parameter and simulations are comparable to observed data."];limits += ["Grid search with scalar auxiliary statistic; simulation noise and weak/non-injective binding functions can misidentify parameters."]
    elif method=="method_of_moments":
        values=_nums(data);moments=p.get("moments",["mean","variance"]);sample_mean=_mean(values);sample_variance=_var(values,0);result={}
        if "mean" in moments:result["location"]=sample_mean
        if "variance" in moments:result["scale_variance"]=sample_variance
        if not result:raise ValueError("moments must request mean and/or variance")
        o["output"]={"distribution":"normal","estimates":result,"sample_moments":{"mean":sample_mean,"variance":sample_variance},"moment_residuals":{"mean":0.0,"variance":0.0}};a += ["Selected population moments exist and identify Normal location/variance parameters."];limits += ["Normal two-moment reference; estimates can be inefficient and sensitive to high-order moment instability."]
    elif method=="generalized_method_of_moments":
        z=_nums(data,"instrument");x=_nums(data,"regressor");y=_nums(data,"outcome")
        if not len(z)==len(x)==len(y):raise ValueError("instrument, regressor and outcome lengths differ")
        zx=sum(a*b for a,b in zip(z,x))/len(z);zy=sum(a*b for a,b in zip(z,y))/len(z)
        if abs(zx)<1e-12:raise ValueError("instrument has zero sample relevance")
        beta=zy/zx;res=[yy-beta*xx for xx,yy in zip(x,y)];moment=sum(a*e for a,e in zip(z,res))/len(z);o["output"]={"estimate":beta,"moment":moment,"objective":moment*moment,"weight_matrix":[[1.0]],"iterations":1};a += ["Single exogenous instrument: E[z*(y-beta*x)]=0; observations iid."];limits += ["Just-identified scalar GMM; no overidentification test, heteroskedasticity/HAC covariance, or weak-instrument robust inference."]
    elif method=="instrumental_variables":
        z=_nums(data,"instrument");x=_nums(data,"regressor");y=_nums(data,"outcome")
        if not len(z)==len(x)==len(y) or len(z)<3:raise ValueError("aligned instrument, regressor and outcome with at least 3 rows required")
        mz,mx,my=_mean(z),_mean(x),_mean(y);covzx=sum((a-mz)*(b-mx) for a,b in zip(z,x));covzy=sum((a-mz)*(b-my) for a,b in zip(z,y))
        if abs(covzx)<1e-12:raise ValueError("instrument has zero first-stage relevance")
        beta=covzy/covzx;intercept=my-beta*mx;first_stage=covzx/sum((a-mz)**2 for a in z);xhat=[mx+first_stage*(a-mz) for a in z];r2=1-sum((b-h)**2 for b,h in zip(x,xhat))/sum((b-mx)**2 for b in x) if _var(x,0)>0 else 0;o["output"]={"estimate":beta,"intercept":intercept,"first_stage_slope":first_stage,"first_stage_r_squared":r2,"weak_instrument_warning":r2<.1};a += ["Instrument relevance, exclusion restriction, independence/exogeneity, monotonicity for a LATE interpretation."];limits += ["One instrument/regressor linear IV; validity is not testable from this data alone; no robust standard error."]
    elif method=="two_stage_least_squares":
        z=_nums(data,"instrument");x=_nums(data,"regressor");y=_nums(data,"outcome")
        if not len(z)==len(x)==len(y) or len(z)<3:raise ValueError("aligned instrument, regressor and outcome required")
        mz,mx,my=_mean(z),_mean(x),_mean(y);szz=sum((v-mz)**2 for v in z)
        if szz<=0:raise ValueError("instrument has no variation")
        first=sum((a-mz)*(b-mx) for a,b in zip(z,x))/szz;first_i=mx-first*mz;xhat=[first_i+first*v for v in z];shh=sum((h-_mean(xhat))**2 for h in xhat)
        if shh<=1e-12:raise ValueError("instrument does not identify fitted treatment variation")
        beta=sum((h-_mean(xhat))*(yy-my) for h,yy in zip(xhat,y))/shh;intercept=my-beta*_mean(xhat);res=[yy-intercept-beta*xx for xx,yy in zip(x,y)];r2=1-sum((xx-h)**2 for xx,h in zip(x,xhat))/sum((xx-mx)**2 for xx in x) if _var(x,0)>0 else 0
        o["output"]={"estimate":beta,"intercept":intercept,"first_stage":{"intercept":first_i,"slope":first,"r_squared":r2},"structural_residuals":res,"weak_instrument_warning":r2<.1};a += ["Linear first/second stages; relevance, exclusion restriction, exogeneity and correct specification."];limits += ["One excluded instrument and endogenous regressor; no controls, robust covariance or weak-IV confidence set."]
    elif method=="limited_information_maximum_likelihood":
        z=_nums(data,"instrument");x=_nums(data,"regressor");y=_nums(data,"outcome");k=float(p.get("k_class",1.0))
        if not len(z)==len(x)==len(y) or len(z)<3:raise ValueError("aligned inputs required")
        mz,mx,my=_mean(z),_mean(x),_mean(y);zc=[v-mz for v in z];xc=[v-mx for v in x];yc=[v-my for v in y];szz=sum(v*v for v in zc)
        if szz<=0:raise ValueError("instrument has no variation")
        px=[sum(a*b for a,b in zip(zc,xc))/szz*v for v in zc];py=[sum(a*b for a,b in zip(zc,yc))/szz*v for v in zc];mxv=[a-b for a,b in zip(xc,px)];myv=[a-b for a,b in zip(yc,py)];num=sum(a*b for a,b in zip(xc,yc))-k*sum(a*b for a,b in zip(mxv,myv));den=sum(a*a for a in xc)-k*sum(a*a for a in mxv)
        if abs(den)<1e-12:raise ValueError("k-class denominator is singular")
        beta=num/den;o["output"]={"estimate":beta,"intercept":my-beta*mx,"k_class":k,"note":"k=1 equals 2SLS in the just-identified single-instrument case"};a += ["Linear simultaneous-equation setup and valid excluded instrument."];limits += ["Caller supplies k-class value; this reference does not estimate the LIML eigenvalue for overidentified systems."]
    elif method=="control_functions":
        z=_nums(data,"instrument");x=_nums(data,"regressor");y=_nums(data,"outcome")
        if not len(z)==len(x)==len(y) or len(z)<4:raise ValueError("at least four aligned rows required")
        mz,mx=_mean(z),_mean(x);szz=sum((v-mz)**2 for v in z)
        if szz<=0:raise ValueError("instrument has no variation")
        pi=sum((a-mz)*(b-mx) for a,b in zip(z,x))/szz;pi0=mx-pi*mz;v=[xx-(pi0+pi*zz) for xx,zz in zip(x,z)]
        n=len(x);sx=sum(x);sv=sum(v);sxx=sum(a*a for a in x);svv=sum(a*a for a in v);sxv=sum(a*b for a,b in zip(x,v));sy=sum(y);sxy=sum(a*b for a,b in zip(x,y));svy=sum(a*b for a,b in zip(v,y));matrix=[[n,sx,sv],[sx,sxx,sxv],[sv,sxv,svv]];rhs=[sy,sxy,svy]
        for i in range(3):
            pivot=max(range(i,3),key=lambda r:abs(matrix[r][i]));matrix[i],matrix[pivot]=matrix[pivot],matrix[i];rhs[i],rhs[pivot]=rhs[pivot],rhs[i]
            if abs(matrix[i][i])<1e-12:raise ValueError("control-function regression is singular")
            d=matrix[i][i];matrix[i]=[q/d for q in matrix[i]];rhs[i]/=d
            for r in range(3):
                if r!=i:
                    f=matrix[r][i];matrix[r]=[a-f*b for a,b in zip(matrix[r],matrix[i])];rhs[r]-=f*rhs[i]
        o["output"]={"intercept":rhs[0],"treatment_effect":rhs[1],"control_residual_coefficient":rhs[2],"endogeneity_signal":abs(rhs[2])>1e-8,"first_stage_slope":pi};a += ["Linear first stage; additive control residual makes outcome conditionally exogenous; valid instrument."];limits += ["Linear scalar reference; control-residual coefficient is a diagnostic, not a formal endogeneity test without uncertainty estimates."]
    elif method=="regression_discontinuity":
        running=_nums(data,"running_variable");outcome=_nums(data,"outcome");cutoff=float(p.get("cutoff",0));bandwidth=float(p.get("bandwidth",1))
        if len(running)!=len(outcome) or bandwidth<=0:raise ValueError("aligned inputs and positive bandwidth required")
        left=[(x,y) for x,y in zip(running,outcome) if cutoff-bandwidth<=x<cutoff];right=[(x,y) for x,y in zip(running,outcome) if cutoff<=x<=cutoff+bandwidth]
        if len(left)<2 or len(right)<2:raise ValueError("need at least two observations on each side within bandwidth")
        def fit(rows):
            xs=[x-cutoff for x,_ in rows];ys=[y for _,y in rows];vx=sum((x-_mean(xs))**2 for x in xs);slope=sum((x-_mean(xs))*(y-_mean(ys)) for x,y in zip(xs,ys))/vx if vx else 0;return _mean(ys)-slope*_mean(xs),slope
        li,ls=fit(left);ri,rs=fit(right);o["output"]={"treatment_effect_at_cutoff":ri-li,"left_intercept":li,"right_intercept":ri,"left_slope":ls,"right_slope":rs,"bandwidth":bandwidth,"n_left":len(left),"n_right":len(right)};a += ["Continuity of potential outcomes at cutoff, no precise manipulation, local linear specification, sharp treatment assignment."];limits += ["No bandwidth selection, kernel weighting, manipulation test, robust bias correction or fuzzy RD."]
    elif method=="difference_in_differences":
        group=data.get("treated");period=data.get("post");outcome=_nums(data,"outcome")
        if not isinstance(group,list) or not isinstance(period,list) or not len(group)==len(period)==len(outcome):raise ValueError("aligned treated, post and outcome required")
        cells={}
        for g,t,y in zip(group,period,outcome):cells.setdefault((bool(g),bool(t)),[]).append(y)
        if any(not cells.get(k) for k in [(False,False),(False,True),(True,False),(True,True)]):raise ValueError("all four treated/post cells required")
        means={k:_mean(v) for k,v in cells.items()};effect=(means[(True,True)]-means[(True,False)])-(means[(False,True)]-means[(False,False)]);o["output"]={"effect":effect,"cell_means":{"control_pre":means[(False,False)],"control_post":means[(False,True)],"treated_pre":means[(True,False)],"treated_post":means[(True,True)]},"group_changes":{"control":means[(False,True)]-means[(False,False)],"treated":means[(True,True)]-means[(True,False)]}};a += ["Parallel untreated trends, no anticipation, stable composition and no spillovers/interference."];limits += ["Two-group/two-period unadjusted DID; no event study, clustered uncertainty, covariates or staggered adoption correction."]
    elif method=="synthetic_control":
        treated=_nums(data,"treated_pre");donors=data.get("donor_pre");post=float(data.get("treated_post"));donor_post=_nums(data,"donor_post")
        if not isinstance(donors,list) or not donors or any(not isinstance(d,list) or len(d)!=len(treated) for d in donors) or len(donors)!=len(donor_post):raise ValueError("aligned donor pre/post series required")
        donors=[[float(v) for v in d] for d in donors];weights=[1/len(donors)]*len(donors);lr=float(p.get("learning_rate",.05));iters=max(10,min(int(p.get("iterations",2000)),20000))
        for _ in range(iters):
            pred=[sum(weights[j]*donors[j][t] for j in range(len(donors))) for t in range(len(treated))];grad=[2*sum((pred[t]-treated[t])*donors[j][t] for t in range(len(treated)))/len(treated) for j in range(len(donors))];weights=[max(0,weights[j]-lr*grad[j]) for j in range(len(weights))];z=sum(weights);weights=[w/z for w in weights] if z else [1/len(weights)]*len(weights)
        synth_pre=[sum(weights[j]*donors[j][t] for j in range(len(donors))) for t in range(len(treated))];synth_post=sum(w*y for w,y in zip(weights,donor_post));rmspe=math.sqrt(_mean([(a-b)**2 for a,b in zip(treated,synth_pre)]));o["output"]={"weights":weights,"synthetic_pre":synth_pre,"synthetic_post":synth_post,"effect":post-synth_post,"pre_rmspe":rmspe};a += ["Convex donor combination reproduces untreated potential outcomes; no spillovers or donor treatment contamination."];limits += ["Projected-gradient reference; no predictor weighting, placebo inference, regularization selection or uncertainty interval."]
    elif method in ("matching_methods","propensity_score_matching","genetic_matching"):
        treated=data.get("treated");outcome=_nums(data,"outcome");covariates=data.get("covariates")
        if not isinstance(treated,list) or not isinstance(covariates,list) or not len(treated)==len(outcome)==len(covariates) or any(not isinstance(row,list) or not row for row in covariates):raise ValueError("aligned treated, outcome and covariate rows required")
        dim=len(covariates[0])
        if any(len(r)!=dim for r in covariates):raise ValueError("covariate dimensions differ")
        tx=[i for i,v in enumerate(treated) if bool(v)];ct=[i for i,v in enumerate(treated) if not bool(v)]
        if not tx or not ct:raise ValueError("both treatment groups required")
        scale=[]
        for j in range(dim):
            vals=[float(r[j]) for r in covariates];sd=math.sqrt(_var(vals,0));scale.append(sd if sd>1e-12 else 1)
        if method=="genetic_matching":
            weights=p.get("covariate_weights",[1]*dim)
            if not isinstance(weights,list) or len(weights)!=dim or any(float(w)<=0 for w in weights):raise ValueError("positive covariate_weights required")
        else:weights=[1]*dim
        def dist(i,j):return math.sqrt(sum(float(weights[k])*((float(covariates[i][k])-float(covariates[j][k]))/scale[k])**2 for k in range(dim)))
        if method=="propensity_score_matching":
            scores=[]
            mt=[_mean([float(covariates[i][j]) for i in tx]) for j in range(dim)];mc=[_mean([float(covariates[i][j]) for i in ct]) for j in range(dim)]
            for row in covariates:
                logit=sum((mt[j]-mc[j])*float(row[j])/(scale[j]**2) for j in range(dim));scores.append(1/(1+math.exp(-max(-700,min(700,logit)))))
            distance=lambda i,j:abs(scores[i]-scores[j])
        else:distance=dist;scores=None
        pairs=[];replacement=bool(p.get("replacement",True));available=set(ct)
        for i in tx:
            pool=ct if replacement else list(available)
            if not pool:break
            j=min(pool,key=lambda q:distance(i,q));pairs.append({"treated_index":i,"control_index":j,"distance":distance(i,j),"effect":outcome[i]-outcome[j]})
            if not replacement:available.remove(j)
        o["output"]={"method":method,"pairs":pairs,"att":_mean([q["effect"] for q in pairs]),"matched_count":len(pairs),"propensity_scores":scores};a += ["Conditional ignorability/no unmeasured confounding, overlap, SUTVA and correctly measured pre-treatment covariates."];limits += ["Greedy nearest-neighbor reference; no caliper/balance optimization or matching-uncertainty correction; genetic weights are caller supplied, not evolved."]
    elif method=="coarsened_exact_matching":
        treated=data.get("treated");outcome=_nums(data,"outcome");covariates=data.get("covariates");cutpoints=p.get("cutpoints")
        if not isinstance(treated,list) or not isinstance(covariates,list) or not len(treated)==len(outcome)==len(covariates) or not covariates or not isinstance(cutpoints,list) or len(cutpoints)!=len(covariates[0]):raise ValueError("aligned inputs and one cutpoint list per covariate required")
        def binval(v,cuts):return sum(float(v)>float(c) for c in cuts)
        strata={}
        for i,row in enumerate(covariates):strata.setdefault(tuple(binval(v,cutpoints[j]) for j,v in enumerate(row)),[]).append(i)
        effects=[];matched=[]
        for key,ids in strata.items():
            t=[i for i in ids if treated[i]];c=[i for i in ids if not treated[i]]
            if t and c:effects.append((_mean([outcome[i] for i in t])-_mean([outcome[i] for i in c]),len(t)));matched+=ids
        if not effects:raise ValueError("no strata contain both groups")
        att=sum(e*w for e,w in effects)/sum(w for _,w in effects);o["output"]={"att":att,"matched_indices":sorted(matched),"matched_count":len(matched),"eligible_strata":len(effects),"total_strata":len(strata)};a += ["Ignorability within coarsened strata, overlap and meaningful pre-specified cutpoints."];limits += ["Results depend on cutpoint choice; no automated monotonic imbalance tuning or uncertainty estimate."]
    elif method=="entropy_balancing":
        treated=data.get("treated");outcome=_nums(data,"outcome");covariate=_nums(data,"covariate")
        if not isinstance(treated,list) or not len(treated)==len(outcome)==len(covariate):raise ValueError("aligned treated, outcome and covariate required")
        tx=[i for i,v in enumerate(treated) if v];ct=[i for i,v in enumerate(treated) if not v]
        if not tx or not ct:raise ValueError("both groups required")
        target=_mean([covariate[i] for i in tx]);lam=0.0;converged=False
        for k in range(200):
            raw=[math.exp(max(-700,min(700,lam*covariate[i]))) for i in ct];z=sum(raw);w=[v/z for v in raw];m=sum(q*covariate[i] for q,i in zip(w,ct));var=sum(q*(covariate[i]-m)**2 for q,i in zip(w,ct))
            if abs(m-target)<1e-10:converged=True;break
            if var<1e-14:break
            lam-=(m-target)/var
        if not converged and abs(m-target)>1e-6:raise ValueError("target moment is outside feasible control support")
        effect=_mean([outcome[i] for i in tx])-sum(q*outcome[i] for q,i in zip(w,ct));entropy=-sum(q*math.log(max(q,1e-300)) for q in w);o["output"]={"att":effect,"control_indices":ct,"control_weights":w,"target_covariate_mean":target,"weighted_control_mean":m,"entropy":entropy,"converged":converged};a += ["Selection on observed covariate, overlap and feasible exact mean balance."];limits += ["One covariate/first moment reference; no higher moments/interactions, base weights or variance estimate."]
    elif method=="inverse_probability_weighting":
        treated=data.get("treated");outcome=_nums(data,"outcome");ps=_nums(data,"propensity_score")
        if not isinstance(treated,list) or not len(treated)==len(outcome)==len(ps) or any(q<=0 or q>=1 for q in ps):raise ValueError("aligned inputs and propensity scores strictly in (0,1) required")
        stabilized=bool(p.get("stabilized",False));pt=sum(bool(v) for v in treated)/len(treated);weights=[(pt/q if stabilized else 1/q) if t else ((1-pt)/(1-q) if stabilized else 1/(1-q)) for t,y,q in zip(treated,outcome,ps)];ty=[(w,y) for w,y,t in zip(weights,outcome,treated) if t];cy=[(w,y) for w,y,t in zip(weights,outcome,treated) if not t];mt=sum(w*y for w,y in ty)/sum(w for w,_ in ty);mc=sum(w*y for w,y in cy)/sum(w for w,_ in cy);ess=(sum(weights)**2)/sum(w*w for w in weights);o["output"]={"ate":mt-mc,"treated_mean":mt,"control_mean":mc,"weights":weights,"effective_sample_size":ess,"max_weight":max(weights),"stabilized":stabilized};a += ["Consistent propensity scores, exchangeability, positivity and SUTVA."];limits += ["Propensities are caller supplied; no trimming, robust variance or diagnostics beyond ESS/max weight."]
    elif method=="doubly_robust_estimation":
        treated=data.get("treated");outcome=_nums(data,"outcome");ps=_nums(data,"propensity_score");mu1=_nums(data,"outcome_model_treated");mu0=_nums(data,"outcome_model_control")
        if not isinstance(treated,list) or not len(treated)==len(outcome)==len(ps)==len(mu1)==len(mu0) or any(q<=0 or q>=1 for q in ps):raise ValueError("aligned nuisance predictions and propensities in (0,1) required")
        scores=[]
        for t,y,e,m1,m0 in zip(treated,outcome,ps,mu1,mu0):scores.append(m1-m0+(y-m1)/e if t else m1-m0-(y-m0)/(1-e))
        o["output"]={"ate":_mean(scores),"influence_scores":scores,"standard_error":math.sqrt(_var(scores)/len(scores)) if len(scores)>1 else None};a += ["At least one of propensity or outcome nuisance models is consistently estimated, plus positivity/SUTVA."];limits += ["Caller supplies in-sample nuisance predictions; production use should cross-fit to reduce overfitting bias."]
    elif method=="targeted_maximum_likelihood":
        treated=data.get("treated");outcome=_nums(data,"outcome");ps=_nums(data,"propensity_score");q1=_nums(data,"initial_q1");q0=_nums(data,"initial_q0")
        if not isinstance(treated,list) or not len(treated)==len(outcome)==len(ps)==len(q1)==len(q0) or any(not 0<e<1 for e in ps) or any(not 0<q<1 for q in q1+q0) or any(not 0<=y<=1 for y in outcome):raise ValueError("aligned binary outcomes and nuisance probabilities strictly inside bounds required")
        h=[1/e if t else -1/(1-e) for t,e in zip(treated,ps)];qobs=[a if t else b for t,a,b in zip(treated,q1,q0)];logit=lambda q:math.log(q/(1-q));eps=0
        for _ in range(50):
            probs=[1/(1+math.exp(-(logit(q)+eps*hh))) for q,hh in zip(qobs,h)];score=sum(hh*(y-pr) for hh,y,pr in zip(h,outcome,probs));info=sum(hh*hh*pr*(1-pr) for hh,pr in zip(h,probs));step=score/info if info else 0;eps+=step
            if abs(step)<1e-10:break
        expit=lambda x:1/(1+math.exp(-max(-700,min(700,x))));q1s=[expit(logit(q)+eps/e) for q,e in zip(q1,ps)];q0s=[expit(logit(q)-eps/(1-e)) for q,e in zip(q0,ps)];psi=_mean([a-b for a,b in zip(q1s,q0s)]);ic=[(a-b)-psi+((y-a)/e if t else -(y-b)/(1-e)) for t,y,e,a,b in zip(treated,outcome,ps,q1s,q0s)];o["output"]={"ate":psi,"epsilon":eps,"targeted_q1":q1s,"targeted_q0":q0s,"influence_curve_mean":_mean(ic),"standard_error":math.sqrt(_var(ic)/len(ic)) if len(ic)>1 else None};a += ["Binary bounded outcome, valid nuisance models, positivity, consistency and no unmeasured confounding."];limits += ["One-dimensional logistic fluctuation; nuisance estimates supplied and not cross-fitted; no confidence interval correction."]
    elif method=="machine_learning_causal_inference":
        treated=data.get("treated");outcome=_nums(data,"outcome");features=data.get("features")
        if not isinstance(treated,list) or not isinstance(features,list) or not len(treated)==len(outcome)==len(features) or not features or any(not isinstance(r,list) or len(r)!=len(features[0]) for r in features):raise ValueError("aligned treatment, outcome and feature matrix required")
        def predict(train_idx,test):
            groups={False:[],True:[]}
            for i in train_idx:groups[bool(treated[i])].append(i)
            if not groups[False] or not groups[True]:raise ValueError("each training fold needs both groups")
            out={}
            for g,ids in groups.items():
                d=[(sum((float(a)-float(b))**2 for a,b in zip(features[i],features[test])),outcome[i]) for i in ids];d.sort();k=min(3,len(d));out[g]=_mean([y for _,y in d[:k]])
            return out[True],out[False]
        effects=[];pred=[];fold_id={};counts={False:0,True:0}
        for i,t in enumerate(treated):g=bool(t);fold_id[i]=counts[g]%2;counts[g]+=1
        if min(counts.values())<2:raise ValueError("cross-fitting needs at least two observations per treatment group")
        for fold in (0,1):
            train=[i for i in range(len(outcome)) if fold_id[i]!=fold];test=[i for i in range(len(outcome)) if fold_id[i]==fold]
            for i in test:
                m1,m0=predict(train,i);effects.append(m1-m0);pred.append({"index":i,"mu1":m1,"mu0":m0,"cate":m1-m0})
        pred.sort(key=lambda x:x["index"]);o["output"]={"algorithm":"two-fold cross-fitted_t_learner_knn","ate":_mean(effects),"individual_effects":pred,"folds":2};a += ["Unconfoundedness conditional on features, overlap, SUTVA and local smoothness for k-nearest-neighbor outcome models."];limits += ["Small deterministic reference learner; no propensity model, tuning, uncertainty or high-dimensional safeguards."]
    o["output"]["method_limits"]=limits;o["output"]["assumptions"]=a
    return o
