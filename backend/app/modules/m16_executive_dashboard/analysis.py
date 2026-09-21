"""Bounded reference analytics for feature rows 1010-1034.

All methods are pure and consume caller-supplied numeric inputs. Stochastic
methods use a caller-visible deterministic seed. Every response includes
inputs, assumptions and method limits. These are small reference
implementations for dashboard-scale jobs, not replacements for scipy,
statsmodels, Stan/PyMC, or production forecasting systems.
"""
from __future__ import annotations
import math,random,statistics
from . import finance_core as finance
from collections import Counter
ROWS={
"predictive":1010,"prescriptive":1011,"descriptive":1012,"diagnostic":1013,"eda":1014,"confirmatory":1015,"inference":1016,"hypothesis_test":1017,"confidence_interval":1018,"bootstrap":1019,"permutation_test":1020,"nonparametric":1021,"robust":1022,"outlier_detection":1023,"imputation":1024,"multiple_imputation":1025,"mle":1026,"em":1027,"mcmc":1028,"variational":1029,"gibbs":1030,"metropolis_hastings":1031,"hmc":1032,"smc":1033,"particle_filter":1034,"kalman_filter":1035,"extended_kalman_filter":1036,"unscented_kalman_filter":1037,"hidden_markov_model":1038,"conditional_random_field":1039,"graphical_model":1040,"bayesian_network":1041,"markov_random_field":1042,"factor_graph":1043,"belief_propagation":1044,"variational_message_passing":1045,"expectation_propagation":1046,"laplace_approximation":1047,"importance_sampling":1048,"rejection_sampling":1049,"slice_sampling":1050,"nested_sampling":1051,"approximate_bayesian_computation":1052,"synthetic_likelihood":1053,"indirect_inference":1054,"method_of_moments":1055,"generalized_method_of_moments":1056,"instrumental_variables":1057,"two_stage_least_squares":1058,"limited_information_maximum_likelihood":1059,"control_functions":1060,"regression_discontinuity":1061,"difference_in_differences":1062,"synthetic_control":1063,"matching_methods":1064,"propensity_score_matching":1065,"coarsened_exact_matching":1066,"genetic_matching":1067,"entropy_balancing":1068,"inverse_probability_weighting":1069,"doubly_robust_estimation":1070,"targeted_maximum_likelihood":1071,"machine_learning_causal_inference":1072,"causal_forests":1073,"double_machine_learning":1074,"orthogonalized_estimation":1075,"cross_fitting":1076,"sample_splitting":1077,"post_selection_inference":1078,"selective_inference":1079,"simultaneous_inference":1080,"false_discovery_rate_control":1081,"family_wise_error_rate":1082,"bonferroni_correction":1083,"holm_bonferroni":1084,"benjamini_hochberg":1085,"storeys_method":1086,"local_fdr":1087,"permutation_based_fdr":1088,"knockoffs":1089,"stability_selection":1090,"bootstrap_aggregation":1091,"random_forests":1092,"gradient_boosting":1093,"xgboost":1094,"lightgbm":1095,"catboost":1096,"adaboost":1097,"stacking":1098,"blending":1099,"bagging":1100,"pasting":1101,"voting_classifiers":1102,"weighted_voting":1103,"bayesian_model_averaging":1104,"bayesian_model_selection":1105,"information_criteria":1106,"cross_validation":1107,"leave_one_out":1108,"k_fold_cross_validation":1109,**finance.ROWS}
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
    if method in finance.ROWS:return finance.run(method,data,params,seed)
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
    elif method=="causal_forests":
        treated=data.get("treated");outcome=_nums(data,"outcome");feature=_nums(data,"feature")
        if not isinstance(treated,list) or not len(treated)==len(outcome)==len(feature) or len(outcome)<8:raise ValueError("at least 8 aligned rows required")
        candidates=sorted(set((a+b)/2 for a,b in zip(sorted(set(feature))[:-1],sorted(set(feature))[1:])))
        leaves=[]
        for cut in candidates:
            score=0;parts=[]
            for lo,hi in ((-math.inf,cut),(cut,math.inf)):
                ids=[i for i,x in enumerate(feature) if lo<x<=hi];tx=[outcome[i] for i in ids if treated[i]];ct=[outcome[i] for i in ids if not treated[i]]
                if len(tx)<2 or len(ct)<2:score=-math.inf;break
                effect=_mean(tx)-_mean(ct);parts.append((ids,effect));score+=len(ids)*effect*effect
            if score>-math.inf:leaves.append((score,cut,parts))
        if not leaves:raise ValueError("no honest split has at least two treated and controls per leaf")
        _,cut,parts=max(leaves,key=lambda x:x[0]);effects=[0.0]*len(outcome);leafout=[]
        for ids,effect in parts:
            for i in ids:effects[i]=effect
            leafout.append({"indices":ids,"effect":effect})
        o["output"]={"algorithm":"single_honest_causal_tree_reference","split":cut,"leaves":leafout,"individual_effects":effects,"ate":_mean(effects)};a += ["Unconfoundedness given feature, overlap within leaves, SUTVA and effect heterogeneity expressible by one split."];limits += ["Single deterministic tree, not a forest; no bootstrap aggregation, honesty sample split, variance or nuisance residualization."]
    elif method in ("double_machine_learning","orthogonalized_estimation"):
        treated=_nums(data,"treatment");outcome=_nums(data,"outcome");feature=_nums(data,"feature")
        if not len(treated)==len(outcome)==len(feature) or len(outcome)<6:raise ValueError("at least six aligned rows required")
        tres=[0.0]*len(outcome);yres=[0.0]*len(outcome);folds=[i%2 for i in range(len(outcome))]
        def linefit(x,y):
            vx=sum((v-_mean(x))**2 for v in x);s=sum((a-_mean(x))*(b-_mean(y)) for a,b in zip(x,y))/vx if vx else 0;return _mean(y)-s*_mean(x),s
        for fold in (0,1):
            train=[i for i in range(len(outcome)) if folds[i]!=fold];test=[i for i in range(len(outcome)) if folds[i]==fold];ai,bi=linefit([feature[i] for i in train],[treated[i] for i in train]);aj,bj=linefit([feature[i] for i in train],[outcome[i] for i in train])
            for i in test:tres[i]=treated[i]-(ai+bi*feature[i]);yres[i]=outcome[i]-(aj+bj*feature[i])
        den=sum(v*v for v in tres)
        if den<1e-12:raise ValueError("no residualized treatment variation")
        theta=sum(a*b for a,b in zip(tres,yres))/den;psi=[tr*(yr-theta*tr)/(den/len(tres)) for tr,yr in zip(tres,yres)];o["output"]={"estimate":theta,"treatment_residuals":tres,"outcome_residuals":yres,"orthogonal_scores":psi,"standard_error":math.sqrt(_var(psi)/len(psi)),"folds":2};a += ["Partially linear model, unconfoundedness given feature, overlap and nuisance rates sufficient for orthogonal inference."];limits += ["Two-fold scalar linear nuisance models; no repeated cross-fitting, clustering or nonlinear learners."]
    elif method=="cross_fitting":
        ids=data.get("ids");predictions=_nums(data,"predictions");targets=_nums(data,"targets");folds=int(p.get("folds",2))
        if not isinstance(ids,list) or not len(ids)==len(predictions)==len(targets) or folds<2 or folds>len(ids):raise ValueError("aligned ids and valid fold count required")
        assignment=[int.from_bytes(__import__("hashlib").sha256(str(i).encode()).digest()[:8],"big")%folds for i in ids];errors=[yhat-y for yhat,y in zip(predictions,targets)];counts={f:assignment.count(f) for f in range(folds)}
        if any(v==0 for v in counts.values()):raise ValueError("hash assignment produced empty fold; use more observations or fewer folds")
        o["output"]={"fold_assignment":assignment,"fold_counts":counts,"out_of_fold_mse":_mean([e*e for e in errors]),"mean_error":_mean(errors)};a += ["Predictions are genuinely out-of-fold and ids are stable independent units."];limits += ["Validates/evaluates supplied predictions; does not train nuisance models or prevent leakage upstream."]
    elif method=="sample_splitting":
        ids=data.get("ids");train_fraction=float(p.get("train_fraction",.5));seed2=int(p.get("split_seed",seed))
        if not isinstance(ids,list) or len(ids)<2 or not 0<train_fraction<1:raise ValueError("at least two ids and train_fraction in (0,1) required")
        keyed=sorted([(random.Random(f"{seed2}:{i}").random(),i) for i in ids]);n=max(1,min(len(ids)-1,round(len(ids)*train_fraction)));train=[i for _,i in keyed[:n]];holdout=[i for _,i in keyed[n:]];o["output"]={"train_ids":train,"holdout_ids":holdout,"train_count":len(train),"holdout_count":len(holdout),"seed":seed2,"disjoint":set(train).isdisjoint(holdout)};a += ["IDs represent independent analysis units; deterministic seeded assignment occurs before outcome inspection."];limits += ["Single split can be unstable and less efficient; use repeated splits/cross-fitting when valid."]
    elif method=="post_selection_inference":
        estimates=_nums(data,"estimates");ses=_nums(data,"standard_errors");selected=data.get("selected_indices");alpha=float(p.get("alpha",.05))
        if len(estimates)!=len(ses) or not isinstance(selected,list) or not selected or any(not isinstance(i,int) or i<0 or i>=len(estimates) for i in selected) or any(v<=0 for v in ses):raise ValueError("aligned estimates/SEs and valid selected indices required")
        zcrit=float(p.get("z_critical",1.96));adjusted_alpha=alpha/len(selected);adj_z=float(p.get("adjusted_z",2.576 if adjusted_alpha<=.01 else 2.24 if adjusted_alpha<.05 else 1.96));rows=[]
        for i in selected:rows.append({"index":i,"estimate":estimates[i],"naive_interval":[estimates[i]-zcrit*ses[i],estimates[i]+zcrit*ses[i]],"selection_adjusted_interval":[estimates[i]-adj_z*ses[i],estimates[i]+adj_z*ses[i]],"adjusted_alpha":adjusted_alpha})
        o["output"]={"selected":rows,"selection_count":len(selected),"correction":"Bonferroni over selected targets"};a += ["Selected target set is caller supplied and intervals use asymptotic Normal standard errors."];limits += ["Multiplicity correction is not full conditional selective inference for a data-dependent selection event."]
    elif method=="selective_inference":
        estimate=float(data.get("estimate"));se=float(data.get("standard_error"));threshold=float(data.get("selection_threshold"));direction=p.get("direction","greater")
        if se<=0 or direction not in {"greater","less"}:raise ValueError("positive standard_error and direction greater/less required")
        z=estimate/se;t=threshold/se
        if direction=="greater":
            if estimate<threshold:raise ValueError("estimate does not satisfy selection event")
            psel=(1-_normal_cdf(z))/max(1-_normal_cdf(t),1e-300)
        else:
            if estimate>threshold:raise ValueError("estimate does not satisfy selection event")
            psel=_normal_cdf(z)/max(_normal_cdf(t),1e-300)
        o["output"]={"z":z,"selection_z":t,"conditional_one_sided_p_value":min(1,psel),"selection_event":f"estimate {direction} {threshold}"};a += ["Single Gaussian estimate selected by one-sided thresholding; known/asymptotic standard error."];limits += ["One-dimensional truncated-Normal pivot only; no lasso/polyhedral selection or confidence interval inversion."]
    elif method=="simultaneous_inference":
        estimates=_nums(data,"estimates");ses=_nums(data,"standard_errors");alpha=float(p.get("alpha",.05));method=p.get("correction","bonferroni")
        if len(estimates)!=len(ses) or any(v<=0 for v in ses) or method not in {"bonferroni","sidak"}:raise ValueError("aligned positive SEs and supported correction required")
        m=len(estimates);per=alpha/m if method=="bonferroni" else 1-(1-alpha)**(1/m);z=float(p.get("critical_value",2.576 if per<=.01 else 1.96));intervals=[[b-z*s,b+z*s] for b,s in zip(estimates,ses)];o["output"]={"intervals":intervals,"family_confidence":1-alpha,"per_comparison_alpha":per,"critical_value":z,"correction":method};a += ["Asymptotic Normal estimates; Sidak additionally relies on independence."];limits += ["Critical value uses caller override/coarse default; production should compute exact Normal quantile and account for covariance."]
    elif method=="false_discovery_rate_control":
        pvals=_nums(data,"p_values");alpha=float(p.get("alpha",.05));method=p.get("method","benjamini_hochberg")
        if any(v<0 or v>1 for v in pvals) or method not in {"benjamini_hochberg","benjamini_yekutieli"}:raise ValueError("p-values in [0,1] and supported method required")
        m=len(pvals);order=sorted(range(m),key=lambda i:pvals[i]);c=sum(1/i for i in range(1,m+1)) if method=="benjamini_yekutieli" else 1;k=-1
        for rank,i in enumerate(order,1):
            if pvals[i]<=alpha*rank/(m*c):k=rank
        rejected=sorted(order[:k]) if k>0 else [];adj=[1.0]*m;running=1.0
        for rank,i in reversed(list(enumerate(order,1))):running=min(running,pvals[i]*m*c/rank);adj[i]=min(1,running)
        o["output"]={"rejected_indices":rejected,"adjusted_p_values":adj,"discoveries":len(rejected),"method":method,"alpha":alpha};a += ["Valid p-values; BH controls FDR under independence/positive dependence, BY under arbitrary dependence."];limits += ["No adaptive pi0 estimation or hierarchical/online FDR."]
    elif method=="family_wise_error_rate":
        pvals=_nums(data,"p_values");alpha=float(p.get("alpha",.05));method=p.get("method","holm")
        if any(v<0 or v>1 for v in pvals) or method not in {"bonferroni","holm","sidak"}:raise ValueError("p-values in [0,1] and supported method required")
        m=len(pvals)
        if method=="bonferroni":adj=[min(1,v*m) for v in pvals]
        elif method=="sidak":adj=[min(1,1-(1-v)**m) for v in pvals]
        else:
            order=sorted(range(m),key=lambda i:pvals[i]);adj=[1.0]*m;running=0
            for rank,i in enumerate(order):running=max(running,(m-rank)*pvals[i]);adj[i]=min(1,running)
        rejected=[i for i,v in enumerate(adj) if v<=alpha];o["output"]={"adjusted_p_values":adj,"rejected_indices":rejected,"method":method,"alpha":alpha};a += ["Input p-values are valid; Sidak exact control relies on independence."];limits += ["Controls probability of at least one false rejection; can be conservative with many/dependent tests."]
    elif method=="bonferroni_correction":
        pvals=_nums(data,"p_values");alpha=float(p.get("alpha",.05))
        if any(v<0 or v>1 for v in pvals):raise ValueError("p-values must be in [0,1]")
        m=len(pvals);adj=[min(1,m*v) for v in pvals];o["output"]={"adjusted_p_values":adj,"rejected_indices":[i for i,v in enumerate(adj) if v<=alpha],"per_test_alpha":alpha/m,"family_alpha":alpha};a += ["Each input is a valid marginal p-value."];limits += ["Strong FWER control under arbitrary dependence but often conservative; does not exploit covariance or test hierarchy."]
    elif method=="holm_bonferroni":
        pvals=_nums(data,"p_values");alpha=float(p.get("alpha",.05))
        if any(v<0 or v>1 for v in pvals):raise ValueError("p-values must be in [0,1]")
        m=len(pvals);order=sorted(range(m),key=lambda i:pvals[i]);adj=[1.0]*m;running=0.0;steps=[];continue_reject=True
        for rank,i in enumerate(order):
            threshold=alpha/(m-rank);running=max(running,(m-rank)*pvals[i]);adj[i]=min(1,running);reject=continue_reject and pvals[i]<=threshold;continue_reject=reject;steps.append({"index":i,"rank":rank+1,"p_value":pvals[i],"threshold":threshold,"reject":reject})
        o["output"]={"steps":steps,"adjusted_p_values":adj,"rejected_indices":sorted(s["index"] for s in steps if s["reject"]),"family_alpha":alpha};a += ["Valid marginal p-values; step-down closure controls FWER under arbitrary dependence."];limits += ["Does not exploit logical constraints or dependence, and may have low power at scale."]
    elif method=="benjamini_hochberg":
        pvals=_nums(data,"p_values");alpha=float(p.get("alpha",.05))
        if any(v<0 or v>1 for v in pvals):raise ValueError("p-values must be in [0,1]")
        m=len(pvals);order=sorted(range(m),key=lambda i:pvals[i]);k=0;steps=[]
        for rank,i in enumerate(order,1):
            threshold=alpha*rank/m;passed=pvals[i]<=threshold
            if passed:k=rank
            steps.append({"index":i,"rank":rank,"p_value":pvals[i],"threshold":threshold,"passes":passed})
        rejected=sorted(order[:k]);adj=[1.0]*m;running=1.0
        for rank,i in reversed(list(enumerate(order,1))):running=min(running,pvals[i]*m/rank);adj[i]=min(1,running)
        o["output"]={"steps":steps,"largest_passing_rank":k,"rejected_indices":rejected,"adjusted_p_values":adj,"alpha":alpha};a += ["Valid p-values and independence or positive regression dependence for nominal FDR control."];limits += ["Not guaranteed under arbitrary dependence; no adaptive null-proportion estimate."]
    elif method=="storeys_method":
        pvals=_nums(data,"p_values");alpha=float(p.get("alpha",.05));lam=float(p.get("lambda",.5))
        if any(v<0 or v>1 for v in pvals) or not 0<=lam<1:raise ValueError("p-values in [0,1] and lambda in [0,1) required")
        m=len(pvals);pi0=min(1,sum(v>lam for v in pvals)/(m*(1-lam)));order=sorted(range(m),key=lambda i:pvals[i]);q=[1.0]*m;running=1.0
        for rank,i in reversed(list(enumerate(order,1))):running=min(running,pi0*m*pvals[i]/rank);q[i]=min(1,running)
        o["output"]={"pi0":pi0,"lambda":lam,"q_values":q,"rejected_indices":[i for i,v in enumerate(q) if v<=alpha],"alpha":alpha};a += ["High p-values estimate the null proportion; p-values are valid and weakly dependent."];limits += ["Single fixed lambda is unstable for small m; no bootstrap/spline tuning and pi0 bias can affect FDR control."]
    elif method=="local_fdr":
        z=_nums(data,"z_scores");null_sd=float(p.get("null_sd",1));signal_sd=float(p.get("signal_sd",3));pi0=float(p.get("pi0",.9));threshold=float(p.get("threshold",.2))
        if null_sd<=0 or signal_sd<=0 or not 0<pi0<1 or not 0<threshold<1:raise ValueError("positive scales and probabilities inside (0,1) required")
        density=lambda x,sd:math.exp(-.5*(x/sd)**2)/(math.sqrt(2*math.pi)*sd);lfdr=[]
        for x in z:
            f0=density(x,null_sd);f1=density(x,signal_sd);lfdr.append(pi0*f0/(pi0*f0+(1-pi0)*f1))
        o["output"]={"local_fdr":lfdr,"discovery_indices":[i for i,v in enumerate(lfdr) if v<=threshold],"threshold":threshold,"mixture":{"pi0":pi0,"null_sd":null_sd,"signal_sd":signal_sd}};a += ["Two-component centered Gaussian empirical-Bayes mixture with caller-supplied parameters."];limits += ["Does not estimate empirical null/mixture, model asymmetric alternatives, or guarantee tail-area FDR at the local threshold."]
    elif method=="permutation_based_fdr":
        observed=[abs(x) for x in _nums(data,"observed_statistics")];nulls=data.get("permuted_statistics");alpha=float(p.get("alpha",.1))
        if not isinstance(nulls,list) or not nulls or any(not isinstance(row,list) or len(row)!=len(observed) for row in nulls):raise ValueError("aligned permutation statistic vectors required")
        thresholds=sorted(set(observed),reverse=True);chosen=None;curve=[]
        for t in thresholds:
            discoveries=sum(v>=t for v in observed);false=sum(sum(abs(float(v))>=t for v in row) for row in nulls)/len(nulls);fdr=min(1,false/max(1,discoveries));curve.append({"threshold":t,"discoveries":discoveries,"expected_false":false,"estimated_fdr":fdr})
            if discoveries and fdr<=alpha:chosen=t
        rejected=[i for i,v in enumerate(observed) if chosen is not None and v>=chosen];o["output"]={"threshold":chosen,"rejected_indices":rejected,"estimated_fdr":next((q["estimated_fdr"] for q in curve if q["threshold"]==chosen),None),"curve":curve,"permutations":len(nulls)};a += ["Permutation scheme preserves the joint null distribution and statistics are exchangeable under the null."];limits += ["Finite permutation resolution and subset-pivotality/exchangeability assumptions; threshold scan is a reference estimator."]
    elif method=="knockoffs":
        original=_nums(data,"original_importance");knockoff=_nums(data,"knockoff_importance");q=float(p.get("fdr",.1));offset=int(p.get("offset",1))
        if len(original)!=len(knockoff) or not 0<q<1 or offset not in {0,1}:raise ValueError("aligned importances, fdr in (0,1), offset 0/1 required")
        w=[a-b for a,b in zip(original,knockoff)];candidates=sorted(set(abs(v) for v in w if v!=0));threshold=None;diagnostics=[]
        for t in candidates:
            pos=sum(v>=t for v in w);neg=sum(v<=-t for v in w);ratio=(offset+neg)/max(1,pos);diagnostics.append({"threshold":t,"positive":pos,"negative":neg,"ratio":ratio})
            if ratio<=q:threshold=t;break
        selected=[i for i,v in enumerate(w) if threshold is not None and v>=threshold];o["output"]={"w_statistics":w,"threshold":threshold,"selected_indices":selected,"diagnostics":diagnostics,"knockoff_plus":offset==1};a += ["Valid exchangeable model-X/fixed-X knockoff construction supplied upstream and antisymmetric importance statistic."];limits += ["Does not generate/validate knockoffs; FDR guarantee fails if exchangeability is violated."]
    elif method=="stability_selection":
        selections=data.get("selections");threshold=float(p.get("selection_probability",.8));feature_count=int(data.get("feature_count",0))
        if not isinstance(selections,list) or not selections or feature_count<=0 or not .5<threshold<=1:raise ValueError("selections, feature_count and probability in (.5,1] required")
        counts=[0]*feature_count
        for run in selections:
            if not isinstance(run,list) or any(not isinstance(i,int) or i<0 or i>=feature_count for i in run):raise ValueError("invalid selected index")
            for i in set(run):counts[i]+=1
        probs=[c/len(selections) for c in counts];avg_selected=_mean([len(set(run)) for run in selections]);bound=(avg_selected**2)/(feature_count*(2*threshold-1));o["output"]={"selection_probabilities":probs,"stable_indices":[i for i,v in enumerate(probs) if v>=threshold],"threshold":threshold,"average_selected":avg_selected,"expected_false_positive_bound":bound};a += ["Exchangeable noise variables and complementary/random subsampling with a stable base selector."];limits += ["Classical bound is conservative and assumptions strong; caller supplies selection runs."]
    elif method=="bootstrap_aggregation":
        values=_nums(data);draws=max(100,min(int(p.get("draws",1000)),20000));stat=p.get("statistic","mean")
        if stat not in {"mean","median"}:raise ValueError("statistic must be mean or median")
        estimates=[]
        for _ in range(draws):
            sample=[rng.choice(values) for _ in values];estimates.append(_mean(sample) if stat=="mean" else statistics.median(sample))
        o["output"]={"bagged_estimate":_mean(estimates),"base_estimate":_mean(values) if stat=="mean" else statistics.median(values),"bootstrap_variance":_var(estimates,0),"draws":draws,"statistic":stat};a += ["Observations are iid/exchangeable and empirical distribution represents the population."];limits += ["Bags scalar estimators, not predictive models; no out-of-bag performance or dependence-aware resampling."]
    elif method=="random_forests":
        features=data.get("features");targets=_nums(data,"targets");trees=max(5,min(int(p.get("trees",50)),500));max_features=max(1,int(p.get("max_features",1)))
        if not isinstance(features,list) or not features or len(features)!=len(targets) or any(not isinstance(r,list) or len(r)!=len(features[0]) for r in features):raise ValueError("aligned rectangular features and targets required")
        dim=len(features[0]);forest=[];oob_votes=[[] for _ in targets]
        for _ in range(trees):
            sample=[rng.randrange(len(targets)) for _ in targets];oob=set(range(len(targets)))-set(sample);candidate=rng.sample(range(dim),min(max_features,dim));best=None
            for j in candidate:
                vals=sorted(set(float(features[i][j]) for i in sample));cuts=[(a+b)/2 for a,b in zip(vals[:-1],vals[1:])]
                for cut in cuts:
                    left=[targets[i] for i in sample if float(features[i][j])<=cut];right=[targets[i] for i in sample if float(features[i][j])>cut]
                    if not left or not right:continue
                    loss=sum((y-_mean(left))**2 for y in left)+sum((y-_mean(right))**2 for y in right)
                    if best is None or loss<best[0]:best=(loss,j,cut,_mean(left),_mean(right))
            if best is None:best=(0,0,float(features[sample[0]][0]),_mean([targets[i] for i in sample]),_mean([targets[i] for i in sample]))
            _,j,cut,lm,rm=best;forest.append({"feature":j,"threshold":cut,"left":lm,"right":rm})
            for i in oob:oob_votes[i].append(lm if float(features[i][j])<=cut else rm)
        oob_pred=[_mean(v) if v else None for v in oob_votes];valid=[(p0,y) for p0,y in zip(oob_pred,targets) if p0 is not None];mse=_mean([(a-b)**2 for a,b in valid]) if valid else None;o["output"]={"trees":forest,"tree_count":trees,"oob_predictions":oob_pred,"oob_mse":mse,"oob_coverage":len(valid)/len(targets)};a += ["Rows are iid; bootstrap trees and random feature subsampling reduce correlated errors."];limits += ["Decision stumps only, not full trees; regression only; no missing values, tuning, importance or calibration."]
    elif method in ("gradient_boosting","xgboost","lightgbm","catboost"):
        features=data.get("features");targets=_nums(data,"targets");rounds=max(1,min(int(p.get("rounds",20)),500));lr=float(p.get("learning_rate",.1));l2=float(p.get("l2",1));
        if not isinstance(features,list) or not features or len(features)!=len(targets) or any(not isinstance(r,list) or len(r)!=len(features[0]) for r in features) or lr<=0 or l2<0:raise ValueError("aligned rectangular features, positive learning rate and nonnegative l2 required")
        dim=len(features[0]);base=_mean(targets);pred=[base]*len(targets);learners=[]
        for _ in range(rounds):
            residual=[y-yh for y,yh in zip(targets,pred)];best=None
            for j in range(dim):
                vals=sorted(set(float(r[j]) for r in features));cuts=[(a+b)/2 for a,b in zip(vals[:-1],vals[1:])]
                for cut in cuts:
                    li=[i for i,r in enumerate(features) if float(r[j])<=cut];ri=[i for i,r in enumerate(features) if float(r[j])>cut]
                    if not li or not ri:continue
                    if method=="xgboost":lm=sum(residual[i] for i in li)/(len(li)+l2);rm=sum(residual[i] for i in ri)/(len(ri)+l2)
                    else:lm=_mean([residual[i] for i in li]);rm=_mean([residual[i] for i in ri])
                    loss=sum((residual[i]-(lm if i in li else rm))**2 for i in range(len(residual)))
                    if method=="lightgbm":loss-=1e-12*abs(len(li)-len(ri))
                    if best is None or loss<best[0]:best=(loss,j,cut,lm,rm)
            if best is None:break
            _,j,cut,lm,rm=best;learners.append({"feature":j,"threshold":cut,"left":lr*lm,"right":lr*rm})
            for i,r in enumerate(features):pred[i]+=lr*(lm if float(r[j])<=cut else rm)
        rmse=math.sqrt(_mean([(y-yh)**2 for y,yh in zip(targets,pred)]));label={"gradient_boosting":"squared_error_stump_boosting","xgboost":"regularized_second_order_style_stump_boosting","lightgbm":"leafwise_style_stump_boosting","catboost":"ordered_style_numeric_stump_boosting"}[method];o["output"]={"algorithm":label,"base_prediction":base,"learners":learners,"predictions":pred,"training_rmse":rmse,"rounds_completed":len(learners)};a += ["Regression rows are iid and squared error is the target objective."];limits += [{"gradient_boosting":"Shallow numeric stumps; training fit only; no validation/early stopping.","xgboost":"XGBoost-inspired regularized leaf weights, not the native library or exact second-order tree builder.","lightgbm":"LightGBM-inspired label only; no histogram/EFB/GOSS implementation.","catboost":"CatBoost-inspired label only; numeric features, no ordered target statistics or categorical handling."}[method]]
    elif method=="adaboost":
        features=data.get("features");labels=data.get("labels");rounds=max(1,min(int(p.get("rounds",20)),500))
        if not isinstance(features,list) or not features or not isinstance(labels,list) or len(features)!=len(labels) or any(v not in (-1,1) for v in labels):raise ValueError("aligned features and labels encoded -1/+1 required")
        dim=len(features[0]);weights=[1/len(labels)]*len(labels);learners=[];scores=[0.0]*len(labels)
        for _ in range(rounds):
            best=None
            for j in range(dim):
                vals=sorted(set(float(r[j]) for r in features));cuts=[(a+b)/2 for a,b in zip(vals[:-1],vals[1:])]
                for cut in cuts:
                    for polarity in (-1,1):
                        pred=[polarity if float(r[j])>cut else -polarity for r in features];err=sum(w for w,pred0,y in zip(weights,pred,labels) if pred0!=y)
                        if best is None or err<best[0]:best=(err,j,cut,polarity,pred)
            if best is None or best[0]>=.5:break
            err,j,cut,polarity,pred=best;err=max(err,1e-12);alpha=.5*math.log((1-err)/err);learners.append({"feature":j,"threshold":cut,"polarity":polarity,"alpha":alpha,"weighted_error":err});weights=[w*math.exp(-alpha*y*ph) for w,y,ph in zip(weights,labels,pred)];z=sum(weights);weights=[w/z for w in weights];scores=[s+alpha*ph for s,ph in zip(scores,pred)]
        prediction=[1 if s>=0 else -1 for s in scores];o["output"]={"algorithm":"adaboost_m1_decision_stumps","learners":learners,"predictions":prediction,"training_error":sum(a!=b for a,b in zip(prediction,labels))/len(labels),"final_sample_weights":weights};a += ["Binary labels, weak learners better than chance and iid rows."];limits += ["Decision stumps and training diagnostics only; sensitive to mislabeled/outlier rows."]
    elif method in ("stacking","blending"):
        base=data.get("base_predictions");targets=_nums(data,"targets")
        if not isinstance(base,list) or not base or any(not isinstance(row,list) or len(row)!=len(targets) for row in base):raise ValueError("one or more aligned base prediction vectors required")
        models=[[float(v) for v in row] for row in base];m=len(models)
        if method=="blending":
            validation_fraction=float(p.get("validation_fraction",.25));start=max(1,min(len(targets)-1,round(len(targets)*(1-validation_fraction))));idx=list(range(start,len(targets)))
        else:idx=list(range(len(targets)))
        errors=[_mean([(model[i]-targets[i])**2 for i in idx]) for model in models];raw=[1/max(e,1e-12) for e in errors];z=sum(raw);weights=[v/z for v in raw];pred=[sum(w*model[i] for w,model in zip(weights,models)) for i in range(len(targets))];o["output"]={"algorithm":"weighted_oof_stacking" if method=="stacking" else "heldout_weighted_blending","weights":weights,"base_validation_mse":errors,"predictions":pred,"ensemble_mse":_mean([(a-b)**2 for a,b in zip(pred,targets)]),"validation_indices":idx};a += ["Base predictions are out-of-fold for stacking or from models fit outside the held-out blending partition."];limits += ["Inverse-MSE linear meta-learner; does not train base models or enforce upstream leakage controls."]
    elif method in ("bagging","pasting"):
        features=data.get("features");targets=_nums(data,"targets");estimators=max(2,min(int(p.get("estimators",50)),500));fraction=float(p.get("sample_fraction",.7));replacement=method=="bagging"
        if not isinstance(features,list) or len(features)!=len(targets) or not 0<fraction<=1:raise ValueError("aligned features and sample_fraction in (0,1] required")
        n=max(1,round(len(targets)*fraction));models=[];predsum=[0.0]*len(targets)
        for _ in range(estimators):
            sample=[rng.randrange(len(targets)) for _ in range(n)] if replacement else rng.sample(range(len(targets)),n);mean_target=_mean([targets[i] for i in sample]);models.append({"sample_indices":sample,"constant_prediction":mean_target});predsum=[v+mean_target for v in predsum]
        predictions=[v/estimators for v in predsum];o["output"]={"algorithm":"bootstrap_aggregation" if replacement else "pasting_without_replacement","models":models,"predictions":predictions,"ensemble_mse":_mean([(a-b)**2 for a,b in zip(predictions,targets)]),"replacement":replacement};a += ["Rows are iid and subsamples represent the same target distribution."];limits += ["Constant base learners expose sampling semantics but have little predictive power; no feature-fitting or OOB estimate."]
    elif method=="voting_classifiers":
        predictions=data.get("predictions");mode=p.get("mode","hard")
        if not isinstance(predictions,list) or not predictions or any(not isinstance(row,list) or len(row)!=len(predictions[0]) for row in predictions) or mode not in {"hard","soft"}:raise ValueError("aligned classifier predictions and hard/soft mode required")
        out=[];confidence=[]
        for i in range(len(predictions[0])):
            vals=[row[i] for row in predictions]
            if mode=="hard":
                counts=Counter(vals);winner,count=max(counts.items(),key=lambda kv:(kv[1],str(kv[0])));out.append(winner);confidence.append(count/len(vals))
            else:
                probs=[float(v) for v in vals]
                if any(not 0<=v<=1 for v in probs):raise ValueError("soft votes must be probabilities in [0,1]")
                avg=_mean(probs);out.append(1 if avg>=.5 else 0);confidence.append(avg if avg>=.5 else 1-avg)
        o["output"]={"mode":mode,"predictions":out,"vote_confidence":confidence,"classifier_count":len(predictions)};a += ["Classifiers produce comparable labels (hard) or calibrated positive-class probabilities (soft)."];limits += ["Equal voting; no correlated-error correction, calibration check or learned weights."]
    elif method=="weighted_voting":
        predictions=data.get("predictions");weights=_nums(data,"weights");threshold=float(p.get("threshold",.5))
        if not isinstance(predictions,list) or not predictions or len(predictions)!=len(weights) or any(not isinstance(row,list) or len(row)!=len(predictions[0]) for row in predictions) or any(w<0 for w in weights) or sum(weights)<=0:raise ValueError("aligned predictions and nonnegative nonzero weights required")
        z=sum(weights);weights=[w/z for w in weights];scores=[]
        for i in range(len(predictions[0])):
            vals=[float(row[i]) for row in predictions]
            if any(not 0<=v<=1 for v in vals):raise ValueError("weighted soft votes must be in [0,1]")
            scores.append(sum(w*v for w,v in zip(weights,vals)))
        o["output"]={"normalized_weights":weights,"positive_scores":scores,"predictions":[1 if v>=threshold else 0 for v in scores],"threshold":threshold};a += ["Base probabilities are calibrated/comparable and weights are fixed independently of evaluated outcomes."];limits += ["Static linear opinion pool; no learned weights, calibration or diversity penalty."]
    elif method=="bayesian_model_averaging":
        predictions=data.get("model_predictions");log_evidence=_nums(data,"log_evidence")
        if not isinstance(predictions,list) or not predictions or len(predictions)!=len(log_evidence) or any(not isinstance(row,list) or len(row)!=len(predictions[0]) for row in predictions):raise ValueError("aligned model predictions and one log evidence per model required")
        m=max(log_evidence);raw=[math.exp(v-m) for v in log_evidence];z=sum(raw);weights=[v/z for v in raw];averaged=[sum(w*float(model[i]) for w,model in zip(weights,predictions)) for i in range(len(predictions[0]))];between=[sum(w*(float(model[i])-averaged[i])**2 for w,model in zip(weights,predictions)) for i in range(len(averaged))];o["output"]={"posterior_model_probabilities":weights,"averaged_predictions":averaged,"between_model_variance":between};a += ["Candidate model set and priors are adequate; supplied log marginal likelihoods are comparable."];limits += ["No model-prior input, evidence computation or within-model predictive variance."]
    elif method=="bayesian_model_selection":
        names=data.get("model_names");log_evidence=_nums(data,"log_evidence");prior=p.get("prior_probabilities")
        if not isinstance(names,list) or len(names)!=len(log_evidence) or not names:raise ValueError("one name per model evidence required")
        priors=[1/len(names)]*len(names) if prior is None else [float(v) for v in prior]
        if len(priors)!=len(names) or any(v<=0 for v in priors):raise ValueError("positive prior per model required")
        z0=sum(priors);logs=[e+math.log(pr/z0) for e,pr in zip(log_evidence,priors)];m=max(logs);raw=[math.exp(v-m) for v in logs];z=sum(raw);post=[v/z for v in raw];winner=max(range(len(names)),key=lambda i:post[i]);o["output"]={"selected_model":names[winner],"posterior_probabilities":dict(zip(names,post)),"log_bayes_factors_vs_selected":{n:logs[i]-logs[winner] for i,n in enumerate(names)}};a += ["Models share the same observed data and marginal likelihood scale; prior probabilities are meaningful."];limits += ["Selection uncertainty remains; winner-take-all ignores model uncertainty and supplied evidence quality."]
    elif method=="information_criteria":
        models=data.get("models");n=int(data.get("sample_size",0))
        if not isinstance(models,list) or not models or n<=0 or any("name" not in m or "log_likelihood" not in m or "parameters" not in m for m in models):raise ValueError("models and positive sample_size required")
        rows=[]
        for m0 in models:
            k=int(m0["parameters"]);ll=float(m0["log_likelihood"])
            if k<0:raise ValueError("parameter count must be nonnegative")
            aic=2*k-2*ll;bic=math.log(n)*k-2*ll;aicc=aic+(2*k*(k+1)/(n-k-1) if n>k+1 else math.inf);rows.append({"name":m0["name"],"aic":aic,"aicc":aicc,"bic":bic})
        criterion=p.get("criterion","aic");
        if criterion not in {"aic","aicc","bic"}:raise ValueError("criterion must be aic/aicc/bic")
        best=min(rows,key=lambda r:r[criterion]);o["output"]={"models":rows,"criterion":criterion,"selected_model":best["name"],"deltas":{r["name"]:r[criterion]-best[criterion] for r in rows}};a += ["Maximum log likelihoods and effective parameter counts are comparable over identical observations."];limits += ["Criteria rank predictive approximation/evidence penalties; they do not test truth or account for singular models."]
    elif method=="cross_validation":
        predictions=data.get("fold_predictions");targets=data.get("fold_targets")
        if not isinstance(predictions,list) or not isinstance(targets,list) or not predictions or len(predictions)!=len(targets) or any(not isinstance(a,list) or not isinstance(b,list) or len(a)!=len(b) or not a for a,b in zip(predictions,targets)):raise ValueError("aligned non-empty fold prediction/target lists required")
        fold=[]
        for i,(a,b) in enumerate(zip(predictions,targets)):
            mse=_mean([(float(x)-float(y))**2 for x,y in zip(a,b)]);fold.append({"fold":i,"n":len(a),"mse":mse})
        total=sum(r["n"] for r in fold);weighted=sum(r["n"]*r["mse"] for r in fold)/total;o["output"]={"fold_metrics":fold,"weighted_mse":weighted,"mean_fold_mse":_mean([r["mse"] for r in fold]),"fold_count":len(fold),"total_holdout_rows":total};a += ["Every prediction was produced without training on its target row; folds reflect the deployment population."];limits += ["Evaluates supplied folds; does not create splits, tune nested models or correct selection bias after choosing by CV."]
    elif method=="leave_one_out":
        predictions=_nums(data,"predictions");targets=_nums(data,"targets");train_sizes=data.get("train_sizes")
        if len(predictions)!=len(targets) or len(targets)<2:raise ValueError("aligned predictions/targets for at least two rows required")
        if train_sizes is not None and (not isinstance(train_sizes,list) or train_sizes!=[len(targets)-1]*len(targets)):raise ValueError("each LOO model must train on n-1 rows")
        errors=[a-b for a,b in zip(predictions,targets)];o["output"]={"loo_mse":_mean([e*e for e in errors]),"loo_mae":_mean([abs(e) for e in errors]),"errors":errors,"holdout_count":len(targets),"training_size_per_fold":len(targets)-1,"standard_error_mse":math.sqrt(_var([e*e for e in errors])/len(errors)) if len(errors)>1 else None};a += ["Each prediction comes from a model trained on all other n-1 independent rows with identical preprocessing fitted inside the fold."];limits += ["Evaluates supplied LOO predictions; highly correlated folds and high compute cost; no training/leakage enforcement."]
    elif method=="k_fold_cross_validation":
        fold_ids=data.get("fold_ids");predictions=_nums(data,"predictions");targets=_nums(data,"targets");k=int(p.get("k",0) or len(set(fold_ids or [])))
        if not isinstance(fold_ids,list) or not len(fold_ids)==len(predictions)==len(targets) or k<2:raise ValueError("aligned fold_ids/predictions/targets and k>=2 required")
        unique=sorted(set(fold_ids),key=str)
        if len(unique)!=k:raise ValueError("number of unique fold ids must equal k")
        folds=[]
        for fold in unique:
            ids=[i for i,v in enumerate(fold_ids) if v==fold]
            if not ids:raise ValueError("empty fold")
            errors=[predictions[i]-targets[i] for i in ids];folds.append({"fold":fold,"n":len(ids),"mse":_mean([e*e for e in errors]),"mae":_mean([abs(e) for e in errors])})
        total=len(targets);weighted=sum(f["n"]*f["mse"] for f in folds)/total;o["output"]={"k":k,"fold_metrics":folds,"weighted_mse":weighted,"mean_fold_mse":_mean([f["mse"] for f in folds]),"fold_size_range":[min(f["n"] for f in folds),max(f["n"] for f in folds)],"every_row_held_out_once":True};a += ["Each row appears in exactly one holdout fold; preprocessing/model selection is nested inside training folds; iid rows unless grouped/time-aware splitting is used upstream."];limits += ["Evaluates supplied predictions and fold membership; does not stratify/group/order data or perform nested CV."]
    o["output"]["method_limits"]=limits;o["output"]["assumptions"]=a
    return o
