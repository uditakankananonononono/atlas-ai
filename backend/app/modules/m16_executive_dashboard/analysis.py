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
"predictive":1010,"prescriptive":1011,"descriptive":1012,"diagnostic":1013,"eda":1014,"confirmatory":1015,"inference":1016,"hypothesis_test":1017,"confidence_interval":1018,"bootstrap":1019,"permutation_test":1020,"nonparametric":1021,"robust":1022,"outlier_detection":1023,"imputation":1024,"multiple_imputation":1025,"mle":1026,"em":1027,"mcmc":1028,"variational":1029,"gibbs":1030,"metropolis_hastings":1031,"hmc":1032,"smc":1033,"particle_filter":1034,"kalman_filter":1035,"extended_kalman_filter":1036,"unscented_kalman_filter":1037,"hidden_markov_model":1038}
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
    o["output"]["method_limits"]=limits;o["output"]["assumptions"]=a
    return o
