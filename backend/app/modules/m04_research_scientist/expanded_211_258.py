"""Expanded owner-spec research capabilities M4 rows 211-258."""
from __future__ import annotations
from collections import Counter
from typing import Any
ROWS={
211:'continuous_pubmed_surveillance',212:'continuous_arxiv_surveillance',213:'continuous_biorxiv_surveillance',214:'continuous_nature_surveillance',215:'continuous_science_surveillance',216:'custom_journal_surveillance',217:'paper_summarization',218:'paper_embeddings',219:'paper_clustering',220:'research_gap_finder',221:'under_researched_intersection_detection',222:'hypothesis_suggestions',223:'react_hypothesis_generation_loop',224:'methods_findings_extraction',225:'novel_combination_extension_proposals',226:'public_huggingface_dataset_experiments',227:'public_kaggle_dataset_experiments',228:'python_code_generation',229:'r_code_generation',230:'scverse_scanpy_support',231:'sandboxed_docker_execution',232:'result_interpretation',233:'plot_generation',234:'latex_manuscript_drafting',235:'journal_finder_api',236:'nature_inspired_idea_generation',237:'customer_care_problem_inspiration',238:'scientific_paper_problem_inspiration',239:'question_then_research_loop',240:'simulation_planning_execution_seam',241:'molecular_docking_tool_seam',242:'experiment_planning_execution_seam',243:'research_prize_tracking',244:'past_research_winner_analysis',245:'high_impact_implementable_idea_scoring',246:'automatic_cross_field_topic_exploration',247:'google_docs_research_compilation',248:'alphafold_colabfold_adapter',249:'galaxy_adapter',250:'pymol_adapter',251:'open_source_research_tool_registry',252:'legal_books_literature_sources',253:'oceanofpdf_excluded_legal_replacement',254:'universal_scraper_excluded_allowlisted_adapters',255:'billion_researcher_equivalence_excluded_measurable_worker_scale',256:'forty_page_research_specification_target',257:'research_competition_submission_curation',258:'social_advice_collection_for_research'}
SURVEILLANCE={211:'PubMed',212:'arXiv',213:'bioRxiv',214:'Nature',215:'Science',216:'custom journal'}

def _need(d,*keys):
 m=[k for k in keys if k not in d or d[k] in ('',None)];
 if m:raise ValueError('missing required fields: '+', '.join(m))
def _papers(d):
 _need(d,'papers');return [{'id':p.get('id'),'title':p.get('title'),'doi':p.get('doi'),'url':p.get('url'),'published_at':p.get('published_at'),'source':p.get('source'),'provenance_complete':bool(p.get('title') and (p.get('doi') or p.get('url')) and p.get('source'))} for p in d['papers']]
def _surveil(row,d):
 _need(d,'query','papers');ps=_papers(d);seen=set(d.get('seen_ids',[]));new=[p for p in ps if (p['doi'] or p['id'] or p['url']) not in seen]
 return {'provider':SURVEILLANCE[row],'query':d['query'],'new_papers':new,'deduplicated_count':len(ps)-len(new),'cursor':d.get('cursor'),'network_fetch_performed':False}
def _summary(d):
 _need(d,'paper','sections');return {'paper_id':d['paper'].get('id'),'objective':d['sections'].get('objective'),'methods':d['sections'].get('methods'),'findings':d['sections'].get('findings'),'limitations':d['sections'].get('limitations'),'claims_need_source_check':True}
def _embedding(d):
 _need(d,'papers','vectors');
 if len(d['papers'])!=len(d['vectors']):raise ValueError('papers and vectors length mismatch')
 dims={len(v) for v in d['vectors']};
 if len(dims)!=1:raise ValueError('embedding dimension mismatch')
 return {'items':len(d['papers']),'dimensions':next(iter(dims)),'model':d.get('model'),'normalized':d.get('normalized',False)}
def _clusters(d):
 _need(d,'assignments');groups={}
 for x in d['assignments']:groups.setdefault(str(x['cluster']),[]).append(x['paper_id'])
 return {'clusters':groups,'noise_ids':groups.get('-1',[]),'algorithm':d.get('algorithm','provided_assignments')}
def _gaps(d):
 _need(d,'topics');return {'candidate_gaps':[{'topic':x['topic'],'evidence_count':int(x.get('evidence_count',0)),'recent_count':int(x.get('recent_count',0)),'gap_candidate':int(x.get('evidence_count',0))<=int(d.get('max_evidence_for_gap',3)),'absence_not_proven':True} for x in d['topics']]}
def _hyp(d):
 _need(d,'observations');return {'hypotheses':[{'statement':x.get('hypothesis'),'grounding_ids':x.get('grounding_ids',[]),'falsifier':x.get('falsifier'),'test':x.get('test'),'testable':bool(x.get('falsifier') and x.get('test'))} for x in d['observations']],'suggestions_not_findings':True}
def _code(d,lang):
 _need(d,'task','code');return {'language':lang,'task':d['task'],'code':d['code'],'dependencies':d.get('dependencies',[]),'tests':d.get('tests',[]),'executed':False,'sandbox_required':True}
def _adapter(name,d):
 _need(d,'operation','inputs');return {'adapter':name,'operation':d['operation'],'inputs':d['inputs'],'outputs_expected':d.get('outputs_expected',[]),'version':d.get('version'),'credentials_present':False,'executed':False}
def run(row:int,d:dict[str,Any])->dict[str,Any]:
 if row not in ROWS:raise ValueError('unsupported expanded row')
 if row in SURVEILLANCE:r=_surveil(row,d)
 elif row==217:r=_summary(d)
 elif row==218:r=_embedding(d)
 elif row==219:r=_clusters(d)
 elif row in {220,221}:r=_gaps(d)
 elif row in {222,223}:r=_hyp(d)|({'iterations':d.get('iterations',[]),'max_iterations':int(d.get('max_iterations',5))} if row==223 else {})
 elif row==224:_need(d,'paper');r={'methods':d['paper'].get('methods'),'findings':d['paper'].get('findings'),'limitations':d['paper'].get('limitations'),'verbatim_evidence':d.get('verbatim_evidence',[])}
 elif row==225:_need(d,'components');r={'proposals':[{'components':x.get('components',[]),'novelty_search_required':True,'mechanism':x.get('mechanism'),'test':x.get('test')} for x in d['components']]}
 elif row in {226,227}:_need(d,'dataset','experiment');r={'registry':'Hugging Face' if row==226 else 'Kaggle','dataset':d['dataset'],'license':d.get('license'),'experiment':d['experiment'],'public_access_verified':bool(d.get('public_access_verified')),'executed':False}
 elif row in {228,229}:r=_code(d,'python' if row==228 else 'r')
 elif row==230:r=_adapter('scanpy/scverse',d)
 elif row==231:_need(d,'image_digest','command','resource_limits');r={'image_digest':d['image_digest'],'command':d['command'],'resource_limits':d['resource_limits'],'network':d.get('network','disabled'),'mounts':d.get('mounts',[]),'executed':False,'approval_required':True}
 elif row==232:_need(d,'results');r={'results':d['results'],'interpretations':d.get('interpretations',[]),'alternative_explanations':d.get('alternative_explanations',[]),'limitations':d.get('limitations',[]),'causality_not_inferred':True}
 elif row==233:_need(d,'data','plot_spec');r={'plot_spec':d['plot_spec'],'data_columns':list(d['data'].keys()) if isinstance(d['data'],dict) else [],'alt_text':d.get('alt_text'),'rendered':False}
 elif row==234:_need(d,'sections','citations');r={'latex_sections':d['sections'],'citations':d['citations'],'unresolved_citation_keys':d.get('unresolved_citation_keys',[]),'compiled':False}
 elif row==235:_need(d,'manuscript','journals');r={'ranked':[dict(x,score=sum(float(x.get(k,0)) for k in ('scope_fit','method_fit','audience_fit'))) for x in d['journals']],'manuscript':d['manuscript'],'submission_guaranteed':False}
 elif row in {236,237,238}:_need(d,'source_observations');r={'source_kind':{236:'nature',237:'customer_care',238:'scientific_papers'}[row],'ideas':[{'observation':x.get('observation'),'mechanism':x.get('mechanism'),'research_question':x.get('research_question')} for x in d['source_observations']]}
 elif row==239:_need(d,'question','search_steps');r={'question':d['question'],'search_steps':d['search_steps'],'evidence':d.get('evidence',[]),'next_questions':d.get('next_questions',[]),'loop_complete':bool(d.get('stop_criteria_met'))}
 elif row in {240,241,242}:r=_adapter({240:'simulation',241:'molecular_docking',242:'experiment'}[row],d)
 elif row==243:_need(d,'prizes');r={'prizes':[dict(x,deadline_verified=bool(x.get('deadline') and x.get('source_url'))) for x in d['prizes']]}
 elif row==244:_need(d,'winners');r={'patterns':dict(Counter(y for x in d['winners'] for y in x.get('attributes',[]))),'winner_count':len(d['winners']),'selection_bias_warning':True}
 elif row==245:_need(d,'ideas','weights');r={'scored':[dict(x,score=sum(float(d['weights'].get(k,0))*float(x.get('scores',{}).get(k,0)) for k in d['weights'])) for x in d['ideas']],'weights':d['weights']}
 elif row==246:_need(d,'fields');r={'pairs':[{'a':a,'b':b} for i,a in enumerate(d['fields']) for b in d['fields'][i+1:]],'automatic_claims_forbidden':True}
 elif row==247:_need(d,'sections','sources');r={'document_title':d.get('title','Research compilation'),'sections':d['sections'],'sources':d['sources'],'google_doc_created':False}
 elif row in {248,249,250}:r=_adapter({248:'AlphaFold/ColabFold',249:'Galaxy',250:'PyMOL'}[row],d)
 elif row==251:_need(d,'tools');r={'tools':[dict(x,acceptable=bool(x.get('source_url') and x.get('license') and x.get('version'))) for x in d['tools']]}
 elif row==252:_need(d,'sources');r={'sources':[dict(x,legal=bool(x.get('license_or_access_basis') and x.get('url'))) for x in d['sources']]}
 elif row==253:_need(d,'requested_work');r={'excluded_source':'OceanofPDF','requested_work':d['requested_work'],'legal_replacements':d.get('legal_replacements',[]),'piracy_used':False}
 elif row==254:_need(d,'targets');r={'universal_scraper':False,'adapters':[x for x in d['targets'] if x.get('allowlisted') and x.get('terms_checked')],'rejected':[x for x in d['targets'] if not (x.get('allowlisted') and x.get('terms_checked'))]}
 elif row==255:_need(d,'workers','benchmarks');r={'worker_count':int(d['workers']),'benchmarks':d['benchmarks'],'billion_researcher_claim':False,'throughput_measured_not_equated_to_people':True}
 elif row==256:_need(d,'outline','page_target');r={'outline':d['outline'],'page_target':int(d['page_target']),'target_met':int(d['page_target'])>=40,'page_count_not_quality':True}
 elif row==257:_need(d,'submissions','criteria');r={'submissions':[dict(x,eligible=all(x.get('checks',{}).get(k) for k in d['criteria'])) for x in d['submissions']],'criteria':d['criteria']}
 else:_need(d,'advice','consent');r={'advice':[dict(x,anonymized=bool(x.get('anonymized'))) for x in d['advice']],'consent':d['consent'],'research_use_allowed':bool(d['consent'].get('research_use'))}
 return {'row':row,'capability':ROWS[row],'result':r,'boundary':'Prepared research artifact only. External collection, execution, publication, submission, messaging, and installs require their own authorization and live source checks.'}
