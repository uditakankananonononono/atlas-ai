"""V1-V8 deterministic, supplied-data engines. No external side effects."""
from __future__ import annotations
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from .policy import Refusal, guard, number, text, citation, validate_url
from .transforms import validate_behavior, transform, generate


def bounded_list(value,code='PLAN_REFUSED_INPUT',maximum=1000,allow_empty=False):
    if not isinstance(value,list) or len(value)>maximum or (not value and not allow_empty): raise Refusal(code)
    return value


def hustles(p,s):
    catalog=[]; ids=set()
    for occupation in bounded_list(p.get('occupations')):
        code=text(occupation.get('code')); title=text(occupation.get('title'))
        for task in bounded_list(occupation.get('tasks')):
            tid=text(task.get('id')); task_text=text(task.get('text')); sid=citation(task,s)
            if tid in ids: raise Refusal('MONEY_REFUSED_DUPLICATE')
            ids.add(tid)
            if len(ids)>1000: raise Refusal('MONEY_REFUSED_OVERSIZE')
            catalog.append({'task_id':tid,'occupation_code':code,'career':title,'source_id':sid,
                'test_plan':{'budget':0,'human_execution_required':True,'steps':['Use an owner-supplied anonymized sample',f'Produce a sample: {task_text}','Have the owner score correctness and usefulness','Record attempts, successes, minutes and observed revenue'], 'success_criteria':'Owner review approves useful deliverable; no income claim'},
                'deliverable':{'title':f'{title}: {task_text}','body':f'Work brief\nTask: {task_text}\nAudience: owner review only\nInput: owner supplies lawful anonymized sample\nAcceptance: accuracy and usefulness measured by owner\nSource: {s[sid]["url"]}'}})
    results=[]
    for row in bounded_list(p.get('results',[]),allow_empty=True):
        if row.get('task_id') not in ids: raise Refusal('MONEY_REFUSED_RESULT')
        attempts=number(row.get('attempts'),minimum=1); successes=number(row.get('successes'),minimum=0)
        if not isinstance(attempts,int) or not isinstance(successes,int) or successes>attempts: raise Refusal('MONEY_REFUSED_RESULT')
        cost=number(row.get('cost',0),minimum=0)
        if cost!=0: raise Refusal('MONEY_REFUSED_SPEND')
        revenue=number(row.get('revenue',0),minimum=0); minutes=number(row.get('minutes',0),minimum=0)
        results.append(dict(row,success_rate=successes/attempts,net_revenue=revenue-cost,minutes=minutes,evidence_status='supplied_not_independently_verified'))
    return {'catalog':catalog,'catalog_count':len(catalog),'occupation_count':len(set(x['occupation_code'] for x in catalog)),'results':results,'income_guaranteed':False}, 'O*NET-shaped supplied occupation/task catalog and no-spend experiment briefs', 'No exhaustive O*NET import, live tests, outreach, employment impersonation or income guarantee'


def patents(p,s):
    if p.get('inventor')!='owner': raise Refusal('INTEL_REFUSED_INVENTOR')
    invention=p.get('invention',{}); title=text(invention.get('title'))
    features=[text(f,limit=2000) for f in bounded_list(invention.get('features'),maximum=100)]
    rows=[]
    for art in bounded_list(p.get('prior_art'),code='INTEL_REFUSED_PRIORART_MISSING'):
        sid=citation(art,s); body=text(art.get('text')).casefold(); shared=[f for f in features if f.casefold() in body]
        rows.append({'id':text(art.get('id')),'title':art.get('title',''),'source_id':sid,'source_url':s[sid]['url'],'shared_features':shared,'feature_overlap':len(shared)/len(features)})
    rows.sort(key=lambda r:(-r['feature_overlap'],r['id']))
    claims=[{'number':1,'type':'independent','text':f'A {title} comprising: '+ '; '.join(features)+'.','basis':features}]
    claims.extend({'number':i+2,'type':'dependent','text':f'The {title} of claim 1, wherein the {f} is configured as described by the owner.','basis':[f],'requires_owner_detail':True} for i,f in enumerate(features))
    seen=set(f for a in rows for f in a['shared_features'])
    return {'title':title,'inventor':'owner','claims':claims,'sections':{'abstract':f'{title} uses '+', '.join(features)+'.','description':{'features':features,'missing':['drawings','specific embodiments','enablement details']}},'prior_art':rows,'novelty_report':{'not_matched_in_supplied_corpus':[f for f in features if f not in seen],'legal_novelty_determined':False,'method':'literal feature overlap; not semantic or exhaustive search'},'search_queries':{'google_patents':' '.join(features),'patentsview':{'feature_terms':features},'epo_ops':{'title_terms':title}},'filing_performed':False}, 'Prior-art corpus ranking and owner-invention claim draft with source mapping', 'No live patent-provider search, legal novelty opinion, application completeness or filing'


def linear(p):
    matrix=bounded_list(p.get('matrix'),maximum=32); rhs=bounded_list(p.get('rhs'),maximum=32)
    if len(matrix)!=len(rhs): raise Refusal('SOLVE_REFUSED_DIMENSION')
    n=len(matrix)
    def frac(v):
        number(v); f=Fraction(str(v))
        if abs(f.numerator).bit_length()>256 or f.denominator.bit_length()>256: raise Refusal('SOLVE_REFUSED_LIMIT')
        return f
    a=[]
    for row,b in zip(matrix,rhs):
        if not isinstance(row,list) or len(row)!=n: raise Refusal('SOLVE_REFUSED_DIMENSION')
        a.append([frac(v) for v in row]+[frac(b)])
    original=[r[:] for r in a]; pivot_row=0; pivots=[]
    for col in range(n):
        pivot=next((r for r in range(pivot_row,n) if a[r][col]),None)
        if pivot is None: continue
        a[pivot_row],a[pivot]=a[pivot],a[pivot_row]
        divisor=a[pivot_row][col]; a[pivot_row]=[v/divisor for v in a[pivot_row]]
        for r in range(n):
            if r!=pivot_row:
                factor=a[r][col]; a[r]=[x-factor*y for x,y in zip(a[r],a[pivot_row])]
        pivots.append(col); pivot_row+=1
    if any(all(v==0 for v in r[:-1]) and r[-1]!=0 for r in a):
        return {'status':'unsolved','reason':'inconsistent','verified':False}
    if len(pivots)<n: return {'status':'unsolved','reason':'underdetermined','verified':False}
    solution=[a[i][-1] for i in range(n)]
    residual=[sum(r[j]*solution[j] for j in range(n))-r[-1] for r in original]
    verified=all(v==0 for v in residual)
    return {'status':'solved' if verified else 'unsolved','solution':[str(v) for v in solution],'residual':[str(v) for v in residual],'verified':verified,'method':'exact rational Gaussian elimination'}


def problems(p,s):
    mode=p.get('mode')
    if mode=='linear': result=linear(p)
    elif mode=='trends':
        ranked=[]
        for row in bounded_list(p.get('series'),maximum=100):
            values=[number(v) for v in bounded_list(row.get('values'),maximum=10000)]
            if len(values)<2: raise Refusal('SOLVE_REFUSED_SERIES')
            n=len(values); mean_x=(n-1)/2; mean_y=sum(values)/n
            slope=sum((i-mean_x)*(v-mean_y) for i,v in enumerate(values))/sum((i-mean_x)**2 for i in range(n))
            number(slope)
            ranked.append({'name':text(row.get('name')),'slope':slope,'observations':n,'last':values[-1],'horizon':'input cadence unspecified; no forecast'})
        result={'ranked':sorted(ranked,key=lambda r:(-r['slope'],r['name'])),'status':'measured_not_predicted','verified':False}
    elif mode in {'research','strategy'}:
        question=text(p.get('question')); constraints=[text(c) for c in bounded_list(p.get('constraints',[]),allow_empty=True)]
        evidence=bounded_list(p.get('evidence'))
        for row in evidence: citation(row,s); text(row.get('claim'))
        result={'status':'decomposed_not_solved','verified':False,'question':question,'constraints':constraints,'steps':[
            {'goal':'Define measurable target','deliverable':{'question':question,'constraints':constraints}},
            {'goal':'Reproduce observed evidence','deliverable':{'evidence':evidence,'test':'independent reproduction'}},
            {'goal':'Compare bounded alternatives','deliverable':{'options':['change method','reduce one constraint with owner decision','collect missing evidence'],'score_axes':['correctness','cost','feasibility']}},
            {'goal':'Falsify proposed solution','deliverable':{'test':'holdout acceptance check','required':'predeclared criterion and measured result'}}]}
    else: raise Refusal('SOLVE_REFUSED_MODE')
    return result,'Exact rational linear solver, least-squares trend measures, research/strategy decomposition','No universal solver, unsourced factual solution, or predictive certainty'


def rewrite(p,s):
    tool=p.get('tool',{}); license_=tool.get('license')
    if license_ not in {'MIT','Apache-2.0','BSD-2-Clause','BSD-3-Clause'}: raise Refusal('PROTO_REFUSED_UNLICENSED','GPL needs license-specific review; no license or proprietary refused')
    sid=citation(tool,s); name=text(tool.get('name')); author=text(tool.get('author'))
    ops=validate_behavior(p.get('behavior')); results=[]
    for case in bounded_list(p.get('cases'),maximum=100):
        actual=transform(case.get('input'),ops)
        if 'expected' not in case: raise Refusal('PROTO_REFUSED_PARITY')
        passed=actual==case['expected']; results.append({'actual':actual,'expected':case['expected'],'passed':passed})
    if not all(r['passed'] for r in results): raise Refusal('PROTO_REFUSED_PARITY',json.dumps(results))
    notice=f'Behavior reimplementation of {name}\nAuthor: {author}\nLicense: {license_}\nSource: {s[sid]["url"]}\nNo upstream code copied. Upstream LICENSE/NOTICE obligations must be verified before distribution.\n'
    return {'files':{'adapter.py':generate(ops),'NOTICE.txt':notice,'parity_cases.json':json.dumps(p['cases'],sort_keys=True)},'parity':{'passed':True,'cases':results,'scope':'supplied fixtures only'},'installed':False,'license_review':'metadata supplied; provenance and distribution obligations need human verification'},'Executable declared record-transform adapter with attribution and fixture parity','No arbitrary-tool rewrite, repository fetching, upstream legal verification or installation'


def anything(p,s):
    title=text(p.get('title')); kind=p.get('kind')
    if kind=='software':
        ops=validate_behavior(p.get('behavior')); sample=p.get('sample')
        result={'title':title,'kind':kind,'files':{'prototype.py':generate(ops),'sample.json':json.dumps(sample,allow_nan=False),'README.md':f'# {title}\nRun with PYTHONPATH pointing at Atlas backend: python prototype.py < sample.json\nScope: declared record operations only. No external I/O beyond stdin/stdout.\n'},'sample_output':transform(sample,ops),'acceptance':'sample output is computed, not a generic scaffold'}
    elif kind=='device':
        requirements=[text(r) for r in bounded_list(p.get('requirements'))]; bom=[]; total=0
        for row in bounded_list(p.get('bom')):
            sid=citation(row,s); qty=number(row.get('quantity'),minimum=1); cost=number(row.get('unit_cost'),minimum=0)
            if not isinstance(qty,int): raise Refusal('PROTO_REFUSED_BOM')
            amount=number(qty*cost); total=number(total+amount)
            bom.append({'part':text(row.get('part')),'quantity':qty,'unit_cost_estimate':cost,'extended_estimate':amount,'source_url':s[sid]['url']})
        result={'title':title,'kind':kind,'requirements':requirements,'bom':bom,'bom_total_estimate':total,'manufactured':False,'engineering_review_required':True,'verification_plan':[{'requirement':r,'test':'define calibrated bench measurement before manufacturing'} for r in requirements]}
    else: raise Refusal('PROTO_REFUSED_KIND')
    return result,'Runnable record-processing software artifact or supplied-parts device BOM/spec','No arbitrary software synthesis, CAD, validated hardware safety, purchases or physical production'


def worldclass(p,s):
    suite=text(p.get('suite_id')); tasks=bounded_list(p.get('tasks'),maximum=10000); ids=[]
    for task in tasks:
        tid=text(task.get('id'))
        if tid in ids or 'expected' not in task: raise Refusal('BENCH_REFUSED_TASK')
        ids.append(tid)
    fingerprint=hashlib.sha256(json.dumps(tasks,sort_keys=True,allow_nan=False).encode()).hexdigest()
    def score(row):
        name=text(row.get('name')); outputs=row.get('outputs')
        if not isinstance(outputs,dict) or set(outputs)!=set(ids): raise Refusal('BENCH_REFUSED_COVERAGE')
        results=[{'id':t['id'],'passed':outputs[t['id']]==t['expected']} for t in tasks]; correct=sum(r['passed'] for r in results)
        return {'name':name,'correct':correct,'accuracy':correct/len(tasks),'results':results,'suite_fingerprint':fingerprint}
    candidate=score(p.get('candidate',{})); baselines=[]
    for baseline in bounded_list(p.get('baselines',[]),maximum=100,allow_empty=True):
        sid=citation(baseline,s); baselines.append(dict(score(baseline),source_id=sid,source_url=s[sid]['url'],evidence_status='supplied_outputs_not_independently_verified'))
    return {'suite_id':suite,'suite_size':len(tasks),'suite_fingerprint':fingerprint,'candidate':candidate,'baselines':baselines,'comparisons':[{'baseline':b['name'],'accuracy_delta':candidate['accuracy']-b['accuracy'],'claim_scope':'this supplied task suite only'} for b in baselines],'world_class_established':False},'Exact-match reproducible task-suite scores and same-suite baseline comparisons','No live model runs, external benchmark certification, leakage audit or global world-class claim'


def redirect(p,s):
    project=text(p.get('project')); failures=bounded_list(p.get('failures')); ids=set()
    for f in failures:
        fid=text(f.get('id')); citation(f,s)
        if fid in ids: raise Refusal('FLEET_REFUSED_DUPLICATE')
        ids.add(fid)
        for key in ['expected','observed','reproduce']: text(f.get(key))
    files=p.get('files',{})
    if not isinstance(files,dict) or len(files)>100: raise Refusal('FLEET_REFUSED_FILES')
    packet_files={}
    for name,body in files.items():
        text(name,limit=200); text(body,limit=100000)
        packet_files[name]={'content':body,'sha256':hashlib.sha256(body.encode()).hexdigest()}
    reviews=[]; tickets=[]
    for row in bounded_list(p.get('reviews',[]),allow_empty=True):
        citation(row,s); text(row.get('model')); text(row.get('response'))
        if row.get('failure_id') not in ids: raise Refusal('FLEET_REFUSED_REVIEW')
        reviews.append(dict(row,trust='untrusted opinion; never executed'))
        tickets.append({'failure_id':row['failure_id'],'review_index':len(reviews)-1,'status':'requires_code_verification','acceptance':'reproduce failure, inspect criticism against pinned code, implement bounded alternative, run regression','proposed_alternatives':['isolate smallest reproduction','replace failing dependency with a tested local mechanism','change hypothesis and run counterexample']})
    return {'packet':{'project':project,'failures':failures,'files':packet_files,'review_request':'Review measured failures vs supplied code; suggest falsifiable alternatives. Do not claim success without passing reproduction.'},'reviews':reviews,'tickets':tickets,'external_validation_completed':False},'Failure packet with code hashes, verbatim review storage and verification tickets','No external-model contact, automatic execution of reviews, or validation verdict based on opinion'


def news_create(p,s):
    interests=set(w.casefold() for w in p.get('interests',[])); prior=set(w.casefold() for w in p.get('prior_concepts',[]))
    limit=p.get('limit',10)
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100: raise Refusal('INTEL_REFUSED_LIMIT')
    articles={}
    for feed in bounded_list(p.get('feeds'),maximum=100):
        sid=citation(feed,s); xml=text(feed.get('xml'),limit=1000000)
        if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper(): raise Refusal('INTEL_REFUSED_XML')
        try: root=ET.fromstring(xml)
        except ET.ParseError as exc: raise Refusal('INTEL_REFUSED_XML') from exc
        for element in root.iter():
            if element.tag.split('}')[-1] not in {'item','entry'}: continue
            fields={}; links=[]
            for child in element:
                tag=child.tag.split('}')[-1]; fields[tag]=''.join(child.itertext())
                if tag=='link': links.append(child.get('href') or fields[tag])
            if not links: continue
            url=validate_url(links[0]); title=text(fields.get('title')); body=fields.get('description',fields.get('summary',fields.get('content','')))
            words=set(re.findall(r'[a-z0-9]+',(title+' '+body).casefold()))
            article={'title':title,'url':url,'summary':body[:2000],'source_id':sid,'interest_matches':sorted(words&interests),'new_concepts':sorted(words-prior-interests)[:20]}
            article['score']=len(words&interests)*3+min(10,len(words-prior-interests))
            articles.setdefault(url,article)
            if len(articles)>1000: raise Refusal('INTEL_REFUSED_OVERSIZE')
    ranked=sorted(articles.values(),key=lambda r:(-r['score'],r['url']))[:limit]
    briefs=[{'title':a['title'],'source_urls':[a['url']],'supplied_summary':a['summary'],'research_questions':[f'Can the reported mechanism in {a["title"]} be reproduced?', 'What independently sourced prior work exists?', 'What falsifies the proposed application?'],'evidence_status':'Unverified supplied feed text, not an established scientific result'} for a in ranked]
    tickets=[{'title':f'Test an application of: {a["title"]}','source_urls':[a['url']],'idea':{'seed':a['title'],'connection':sorted(interests)[:5],'hypothesis':'Transfer the reported mechanism to one owner-selected use case'},'acceptance':['verify primary paper or source','find counterexamples and prior art','build smallest reproducible software experiment','compare measured outcome to predeclared baseline'],'status':'research_required_not_built'} for a in ranked]
    return {'ingested_count':len(articles),'selected_count':len(ranked),'ranked':ranked,'briefs':briefs,'tickets':tickets},'RSS/Atom intake, URL dedupe, interest/novelty heuristic, research briefs and experiment tickets','No live news fetch, peer-review verification, autonomous invention or hardware creation'

UNITS={'hustles':('V1','c36',hustles),'patents':('V2','c37',patents),'problems':('V3','c32',problems),'rewrite':('V4','c34',rewrite),'anything':('V5','c34',anything),'worldclass':('V6','c30',worldclass),'redirect':('V7','c31',redirect),'news-create':('V8','c37',news_create)}

def run(name,payload,shared_guard=None):
    if name not in UNITS: raise Refusal('PLAN_REFUSED_UNIT')
    if not isinstance(payload,dict): raise Refusal('PLAN_REFUSED_INPUT')
    try:
        encoded=json.dumps(payload,allow_nan=False)
    except (ValueError,TypeError) as exc: raise Refusal('PLAN_REFUSED_INPUT') from exc
    if len(encoded)>2000000: raise Refusal('PLAN_REFUSED_OVERSIZE')
    sources=guard(payload)
    if shared_guard is not None: shared_guard(payload)
    unit,module,fn=UNITS[name]
    try: result,implemented,not_implemented=fn(payload,sources)
    except (KeyError,TypeError,AttributeError,OverflowError) as exc: raise Refusal('PLAN_REFUSED_INPUT',type(exc).__name__) from exc
    result.update(unit=unit,module=module,status_label=('SUBSTITUTE' if unit in {'V1','V2','V4','V5','V6'} else 'IMPLEMENTED-BOUNDED'),scope={'implemented':implemented,'not_implemented':not_implemented,'data_source':list(sources.values()),'as_of':payload['as_of']})
    return result
