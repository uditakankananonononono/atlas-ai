"""Reviewable cognitive and learning designs for audit rows 860-909."""
from __future__ import annotations
import re
from typing import Any
ROWS=dict(enumerate('''Historical Thinking|Critical Thinking|Creative Thinking|Lateral Thinking|Divergent Thinking|Convergent Thinking|Associative Thinking|Reframing|Perspective Shifting|Paradigm Shifting|Concept Formation|Concept Mapping|Mind Mapping|Knowledge Organization|Taxonomy Creation|Ontology Development|Semantic Networks|Schema Development|Mental Model Construction|Model Updating|Belief Revision|Theory Change|Conceptual Change|Learning by Teaching|Learning by Doing|Learning by Observing|Learning by Imitating|Learning by Trial and Error|Learning by Insight|Learning by Association|Classical Conditioning|Operant Conditioning|Observational Learning|Social Learning|Vicarious Learning|Experiential Learning|Reflective Practice|Action Learning|Project-Based Learning|Problem-Based Learning|Inquiry-Based Learning|Discovery Learning|Guided Discovery|Direct Instruction|Explicit Instruction|Implicit Learning|Incidental Learning|Intentional Learning|Formal Learning|Informal Learning'''.split('|'),860))
class CognitiveLearningError(ValueError):pass
def slug(s):return re.sub('[^a-z0-9]+','_',s.lower()).strip('_')
KEYS={i:slug(n) for i,n in ROWS.items()}
STAGES={
860:['source','contextualize','corroborate','continuity_change','causal_claim'],861:['claim','evidence','assumptions','alternatives','judgment'],862:['prepare','incubate','ideate','elaborate','evaluate'],863:['dominant_pattern','provocation','random_entry','movement','candidate'],864:['prompt','fluency','flexibility','originality','defer_judgment'],865:['criteria','screen','compare','select_for_review'],866:['seed','retrieve_associations','remote_connection','explain_link'],867:['current_frame','alternative_frame','changed_implications'],868:['stakeholders','situated_perspectives','agreements','differences','unknowns'],869:['current_paradigm','anomalies','alternative_paradigm','predictions','transition_costs'],870:['examples','non_examples','attributes','rule','boundary_cases'],871:['concepts','typed_links','cross_links','propositions'],872:['central_topic','branches','subbranches','cross_links'],873:['items','facets','grouping_rules','retrieval_paths'],874:['scope','terms','hierarchy','definitions','polyhierarchy_review'],875:['scope','classes','relations','constraints','competency_questions'],876:['nodes','typed_edges','paths','unsupported_edges'],877:['prior_schema','new_information','assimilation','accommodation'],878:['purpose','entities','relationships','assumptions','predictions'],879:['prior_model','evidence','prediction_error','revised_model'],880:['prior_beliefs','evidence','reliability','conflicts','revised_confidence'],881:['current_theory','anomalies','rivals','comparative_fit','research_needed'],882:['initial_conception','elicitation','discrepant_evidence','reconstruction','transfer_check'],883:['topic','learner_explanation','audience_questions','knowledge_gaps','revision'],884:['objective','authentic_task','attempt','feedback','next_attempt'],885:['model','attention_cues','observations','inference_check'],886:['model','target_sequence','guided_rehearsal','fidelity_check','adaptation'],887:['goal','attempts','outcomes','error_pattern','next_experiment'],888:['impasse','representation','restructuring_prompt','insight','verification'],889:['cues','associations','strength','context','retrieval_test'],890:['neutral_stimulus','unconditioned_stimulus','pairings','conditioned_response','extinction_plan'],891:['target_behavior','antecedent','consequence','schedule','ethical_review'],892:['model','attention','retention','reproduction','motivation'],893:['community','participation','interaction','shared_artifacts','identity_safety'],894:['model_outcome','observer_inference','similarity_limits','direct_practice'],895:['concrete_experience','reflective_observation','abstract_conceptualization','active_experimentation'],896:['experience','description','feelings','evaluation','analysis','action_plan'],897:['real_problem','set_members','questions','action','reflection'],898:['driving_question','milestones','inquiry','critique_revision','public_product'],899:['ill_structured_problem','knowns','unknowns','self_directed_inquiry','solution','debrief'],900:['question','hypothesis','investigation','evidence','explanation','new_questions'],901:['environment','exploration','pattern','learner_rule','verification'],902:['target','exploration_space','hints','fading','transfer'],903:['objective','review','model','guided_practice','independent_practice','check'],904:['objective','explanation','think_aloud','guided_practice','feedback','independent_practice'],905:['exposure','patterns','performance_change','awareness_check','alternative_explanations'],906:['primary_activity','unplanned_learning','evidence','reflection','transfer'],907:['goal','strategy','practice','monitoring','evaluation'],908:['provider','curriculum','schedule','assessment','credential_boundary'],909:['setting','activity','community','self_direction','evidence_of_learning']}
FAMILY={**{i:'thinking' for i in range(860,870)},**{i:'knowledge_representation' for i in range(870,879)},**{i:'model_and_belief_change' for i in range(879,883)},**{i:'learning_mechanism' for i in range(883,896)},**{i:'practice_and_pedagogy' for i in range(896,910)}}
def _need(p,k):
 v=p.get(k)
 if v in (None,[],{}):raise CognitiveLearningError(f'{k} is required')
 return v
def _source(p):
 src=_need(p,'sources')
 if any(not s.get('source_id') or not s.get('observed_at') for s in src):raise CognitiveLearningError('each source requires source_id and observed_at')
 return src
def _typed_map(row,p,stages):
 supplied=p['inputs'];artifacts=[]
 for stage in stages:
  value=supplied.get(stage)
  artifacts.append({'stage':stage,'status':'supplied' if value not in (None,[],{}) else 'evidence_gap','content':value})
 return artifacts
def execute(row:int,payload:dict[str,Any])->dict[str,Any]:
 if row not in ROWS:raise CognitiveLearningError('unsupported capability')
 sources=_source(payload);inputs=_need(payload,'inputs')
 if not isinstance(inputs,dict):raise CognitiveLearningError('inputs must be an object')
 stages=STAGES[row];artifacts=_typed_map(row,payload,stages)
 # Domain-specific validity rules that prevent nearby concepts collapsing together.
 if row==860 and not any(s.get('kind') in ('primary','secondary') for s in sources):raise CognitiveLearningError('historical thinking requires source kind primary or secondary')
 if row in (871,875,876):
  edges=inputs.get('typed_links',inputs.get('relations',inputs.get('typed_edges',[])))
  if edges and any(not e.get('type') for e in edges):raise CognitiveLearningError('knowledge edges require relation type')
 if row==880:
  for b in inputs.get('revised_confidence',[]):
   if not 0<=float(b.get('confidence',-1))<=1:raise CognitiveLearningError('belief confidence must be in [0,1]')
 if row in (890,891):
  if not payload.get('ethical_review',False):raise CognitiveLearningError('conditioning design requires ethical_review=true')
 if row==908 and inputs.get('credential_boundary') is True:raise CognitiveLearningError('credential_boundary must describe limits, not claim a credential')
 gaps=[x['stage'] for x in artifacts if x['status']=='evidence_gap']
 return {'row_id':row,'capability':ROWS[row],'key':KEYS[row],'family':FAMILY[row],'workflow':artifacts,'complete':not gaps,'evidence_gaps':gaps,'sources':sources,'learner_agency':{'opt_out':payload.get('opt_out',True),'goals':payload.get('learner_goals',[]),'access_needs':payload.get('access_needs',[])},'assessment':{'criteria':payload.get('criteria',[]),'results':payload.get('results',[]),'grade_or_credential_awarded':False},'status':'draft_for_learner_and_educator_review','actions_taken':[],'boundary':'Learning support only. Do not manipulate, condition without informed ethical oversight, diagnose, infer hidden mental states, plagiarize learner work, award grades or credentials, enroll, contact others, or change education records. Preserve accessibility, learner agency, privacy, uncertainty and human review.'}
def capabilities():return [{'row_id':i,'key':KEYS[i],'name':ROWS[i],'family':FAMILY[i],'stages':STAGES[i]} for i in ROWS]
