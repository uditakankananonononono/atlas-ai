"""Evidence-led history, philosophy, and literature workbench (rows 1810-1859)."""
from __future__ import annotations
import re
from collections import Counter
from datetime import date
from typing import Any

METHODS=['historical_analysis','historiography','archival_research','primary_sources','secondary_sources','oral_history','public_history','digital_history','comparative_history','world_history','microhistory','macrohistory','biography','prosopography','genealogy','chronology','periodization','historical_causation','historical_contingency','counterfactual_history','philosophy','metaphysics','epistemology','ethics','aesthetics','logic','political_philosophy','social_philosophy','philosophy_of_mind','philosophy_of_language','philosophy_of_science','philosophy_of_religion','existentialism','phenomenology','pragmatism','analytic_philosophy','continental_philosophy','eastern_philosophy','african_philosophy','indigenous_philosophy','literature','literary_criticism','literary_theory','comparative_literature','world_literature','poetry','drama','fiction','non_fiction','genre_studies']
NAMES=[x.replace('_',' ').title() for x in METHODS]
PROFILES=dict(zip(METHODS,NAMES))
HISTORY=set(METHODS[:20]); PHILOSOPHY=set(METHODS[20:40]); LITERATURE=set(METHODS[40:])

QUESTIONS={
'historical_analysis':['What changed, persisted, and for whom?','Which sources support each claim?','Which silences and rival explanations remain?'],
'historiography':['How have interpretations changed?','Which schools, archives, and contexts shaped them?','What dispute remains unresolved?'],
'archival_research':['Which repository, fonds, series, box, and folder?','What restrictions and finding aids apply?','How will original order and provenance be preserved?'],
'primary_sources':['Who created this, when, where, for whom, and why?','How was it transmitted?','What can and cannot be inferred?'],
'secondary_sources':['What thesis, method, evidence, and scholarly context?','How was it reviewed?','What primary record supports it?'],
'oral_history':['Is consent informed and ongoing?','How will narrator authority and access restrictions work?','How will memory, transcription, and trauma be handled?'],
'public_history':['Who are the publics and stakeholders?','Whose voices and harms are represented?','How will accessibility and corrections work?'],
'digital_history':['What corpus and metadata decisions shape the result?','What OCR/data gaps and biases exist?','Is the method reproducible?'],
'comparative_history':['Are units and concepts genuinely comparable?','What common questions and asymmetries apply?','What transfer or connection links cases?'],
'world_history':['Which connections, scales, and power relations cross regions?','Does the framing avoid a single civilizational center?','Which local evidence anchors the synthesis?'],
'microhistory':['Why is this small case analytically revealing?','What exceptional-normal evidence exists?','How are scale jumps justified?'],
'macrohistory':['What long-run units and mechanisms are proposed?','Do aggregates hide regional variation?','Which evidence can falsify the pattern?'],
'biography':['Which life stages, relationships, contexts, and archives?','How are interiority and gaps marked?','How are living-person privacy and myth handled?'],
'prosopography':['What defines group membership?','Which common variables and missingness rules?','Do patterns avoid ecological inference?'],
'genealogy':['What identity standard links each generation?','Which civil, religious, census, and DNA claims conflict?','Are living-person privacy and uncertainty protected?'],
'chronology':['Which calendar, timezone, precision, and dating convention?','Which dates are disputed?','Are event order and causal order separated?'],
'periodization':['What boundary criteria define each period?','Whose experience does the boundary fit or erase?','Which continuities cross it?'],
'historical_causation':['What mechanism links cause to outcome?','What temporal, comparative, and counterevidence tests it?','Are conditions distinguished from triggers?'],
'historical_contingency':['Which decision points had live alternatives?','What constraints bounded agency?','Which outcomes were unforeseeable then?'],
'counterfactual_history':['Is the antecedent plausible and minimally changed?','Which background conditions remain fixed?','How does the exercise test an explicit causal claim?'],
'philosophy':['What question, concepts, thesis, argument, and objection?','Are terms used consistently?','What would revise the conclusion?'],
'metaphysics':['Which ontology, identity, modality, time, or causation commitments?','Are possibility and actuality distinguished?','What explanatory cost follows?'],
'epistemology':['What is believed, known, or justified?','Which evidence and defeaters apply?','Are reliability, testimony, and uncertainty explicit?'],
'ethics':['Who is affected and what duties, rights, virtues, care, and consequences apply?','Which facts and values are disputed?','What conflicts or moral residue remain?'],
'aesthetics':['Which aesthetic object, experience, value, and interpretation?','How do form, context, convention, and audience interact?','Are taste claims universalized without warrant?'],
'logic':['What are the premises and conclusion?','Is the inference deductive, inductive, or abductive?','Is validity separated from premise truth?'],
'political_philosophy':['How are authority, legitimacy, liberty, equality, justice, and coercion framed?','Who is included?','What institutional tradeoffs follow?'],
'social_philosophy':['How do norms, institutions, identity, recognition, and power interact?','Which social ontology is assumed?','Are structural and individual explanations separated?'],
'philosophy_of_mind':['Which account of consciousness, intentionality, self, or mental causation?','What explanatory gap remains?','Which empirical claims need evidence?'],
'philosophy_of_language':['How are meaning, reference, truth, use, and context related?','What speech act or pragmatic inference occurs?','Which examples test the account?'],
'philosophy_of_science':['What demarcation, explanation, confirmation, model, and realism claims?','How do values enter inquiry?','Which history or practice of science constrains the view?'],
'philosophy_of_religion':['Which concept of divinity, faith, reason, evil, experience, or pluralism?','Are traditions represented from sources?','Are theological and philosophical claims distinguished?'],
'existentialism':['How are freedom, responsibility, anxiety, authenticity, absurdity, and situatedness related?','Which thinker and text?','Are differences among thinkers preserved?'],
'phenomenology':['What experience is described in first-person structure?','How do intentionality, embodiment, temporality, and world appear?','What is bracketed rather than denied?'],
'pragmatism':['What practical difference does the claim make?','How does inquiry revise belief?','Which consequences, habits, and community tests matter?'],
'analytic_philosophy':['Can the argument be reconstructed precisely?','Which distinctions and counterexamples matter?','Is formal clarity masking substantive assumptions?'],
'continental_philosophy':['Which text, genealogy, dialectic, interpretation, power, or lived condition?','Is terminology historically situated?','Are traditions flattened?'],
'eastern_philosophy':['Which specific Asian tradition, language, period, and lineage?','Are endogenous categories centered?','Are translation and “East/West” generalizations challenged?'],
'african_philosophy':['Which African language, region, period, and debate?','How do oral, sage, ethnophilosophical, nationalist, and professional traditions differ?','Are colonial frames resisted?'],
'indigenous_philosophy':['Which nation/community and knowledge authority?','What protocols govern access, attribution, and use?','Are relational ontology, land, and language represented without extraction?'],
'literature':['How do form, language, voice, context, and reception produce meaning?','Which edition and passages?','Which ambiguities resist closure?'],
'literary_criticism':['What arguable reading is supported by close textual evidence?','Which critical conversation does it enter?','What counterreading tests it?'],
'literary_theory':['Which theory’s concepts and assumptions guide reading?','What does the lens reveal and obscure?','Is theory applied rather than name-dropped?'],
'comparative_literature':['What justifies comparing texts across languages/cultures/media?','Are originals and translations distinguished?','Do influence, circulation, and asymmetry matter?'],
'world_literature':['How does the work circulate, translate, and change across systems?','Is world status treated as mode of reading, not a canon label?','Are center-periphery dynamics explicit?'],
'poetry':['How do line, meter, rhythm, sound, syntax, image, and form interact?','Who speaks to whom?','Which quoted words anchor the reading?'],
'drama':['How do dialogue, stage directions, embodiment, space, performance, and audience interact?','Is performance history considered?','What changes between page and stage?'],
'fiction':['How do narration, focalization, plot, character, time, setting, and style work?','How reliable is narration?','What textual pattern supports the reading?'],
'non_fiction':['What truth claim, genre, evidence, voice, structure, and ethical relation to subjects?','How are fact, memory, reconstruction, and argument marked?','Which claims need verification?'],
'genre_studies':['Which conventions, expectations, institutions, and historical changes define the genre?','How does the work mix or revise genres?','Who gains from classification?']}

def _source(s:dict,i:int)->dict:
    if not isinstance(s,dict): raise ValueError(f'sources[{i-1}] must be an object')
    kind=str(s.get('kind','unknown')); return {'id':str(s.get('id') or f'S{i}'),'kind':kind,'title':s.get('title'),'creator':s.get('creator'),'date':s.get('date'),'repository_or_publisher':s.get('repository_or_publisher'),'locator':s.get('locator'),'language':s.get('language'),'translation_by':s.get('translation_by'),'accessed':s.get('accessed'),'rights':s.get('rights'),'primary':kind in {'manuscript','letter','diary','artifact','oral_history','contemporary_record','literary_text'},'complete_citation':all(s.get(k) for k in ('title','creator','locator'))}

def _claims(data,sources):
    ids={x['id'] for x in sources}; out=[]
    for ci,c in enumerate(data.get('claims',[])):
        if not isinstance(c,dict): raise ValueError(f'claims[{ci}] must be an object')
        support=[str(x) for x in c.get('source_ids',[])]; missing=[x for x in support if x not in ids]
        out.append({'claim':c.get('claim'),'source_ids':support,'missing_source_ids':missing,'counterevidence':c.get('counterevidence',[]),'qualification':c.get('qualification'),'status':'unsupported' if not support or missing else 'source_linked_not_proven'})
    return out

def _timeline(data):
    rows=data.get('events',[])
    for ei,e in enumerate(rows):
        if not isinstance(e,dict): raise ValueError(f'events[{ei}] must be an object')
    return sorted([{**x,'date_precision':x.get('date_precision','unknown'),'date_disputed':bool(x.get('date_disputed'))} for x in rows],key=lambda x:str(x.get('date','')))

def _arguments(data):
    args=[]
    for a in data.get('arguments',[]):
        premises=a.get('premises',[]); conclusion=a.get('conclusion'); objections=a.get('objections',[])
        args.append({'id':a.get('id'),'premises':premises,'conclusion':conclusion,'inference_type':a.get('inference_type','unspecified'),'validity':a.get('validity','not_assessed'),'soundness':'not_assessed' if not conclusion or not premises else a.get('soundness','not_established'),'objections':objections,'replies':a.get('replies',[])})
    return args

def humanities_support_1810_1859(method:str,data:dict[str,Any])->dict[str,Any]:
    if method not in PROFILES: raise ValueError(f'unsupported humanities method: {method}')
    sources=[_source(s,i) for i,s in enumerate(data.get('sources',[]),1)]; claims=_claims(data,sources)
    domain='history' if method in HISTORY else 'philosophy' if method in PHILOSOPHY else 'literature'
    out={'method':method,'capability':PROFILES[method],'domain':domain,'research_question':data.get('research_question'),'scope':data.get('scope',{}),'guiding_questions':QUESTIONS[method],'sources':sources,'claims':claims,'interpretations':data.get('interpretations',[]),'uncertainties':data.get('uncertainties',[]),'counterpositions':data.get('counterpositions',[]),'source_audit':{'total':len(sources),'primary':sum(x['primary'] for x in sources),'incomplete_citation_ids':[x['id'] for x in sources if not x['complete_citation']]},'as_of':data.get('as_of') or date.today().isoformat(),'boundary':'Interpretive analysis. Sources, quotations, translations, provenance, cultural authority, and contested claims must remain visible; absence of evidence is not evidence of absence.'}
    if domain=='history': out.update({'timeline':_timeline(data),'actors':data.get('actors',[]),'contexts':data.get('contexts',[]),'continuities':data.get('continuities',[]),'changes':data.get('changes',[])})
    if domain=='philosophy': out.update({'arguments':_arguments(data),'concepts':data.get('concepts',{}),'thought_experiments':data.get('thought_experiments',[])})
    if domain=='literature': out.update({'edition':data.get('edition'),'passages':[{'locator':p.get('locator'),'quotation':p.get('quotation'),'device':p.get('device'),'interpretation':p.get('interpretation'),'verified_against_edition':bool(p.get('verified_against_edition'))} for p in data.get('passages',[])],'formal_features':data.get('formal_features',[]),'reception_contexts':data.get('reception_contexts',[])})
    if method=='historiography': out['schools']=data.get('schools',[])
    elif method=='archival_research': out['archive_plan']={'repositories':data.get('repositories',[]),'fonds_series_boxes':data.get('fonds_series_boxes',[]),'restrictions':data.get('restrictions',[]),'preserve_original_order':True}
    elif method=='oral_history': out['ethics']={'consent_recorded':bool(data.get('consent_recorded')),'withdrawal_terms':data.get('withdrawal_terms'),'access_restrictions':data.get('access_restrictions',[]),'narrator_review':data.get('narrator_review',False)}
    elif method=='digital_history': out['reproducibility']={'corpus_manifest':data.get('corpus_manifest',[]),'method_version':data.get('method_version'),'ocr_error_rate':data.get('ocr_error_rate'),'code_or_query':data.get('code_or_query')}
    elif method=='comparative_history': out['comparison_matrix']=data.get('comparison_matrix',[])
    elif method=='prosopography':
        people=data.get('people',[]); out['group_summary']={'members':len(people),'fields':{k:dict(Counter(str(p.get(k,'unknown')) for p in people)) for k in data.get('variables',[])},'no_individual_inference_from_aggregate':True}
    elif method=='genealogy': out['relationships']=[{**r,'confidence':r.get('confidence','unverified'),'evidence_ids':r.get('evidence_ids',[])} for r in data.get('relationships',[])]
    elif method=='periodization': out['periods']=[{**p,'boundary_is_interpretive':True} for p in data.get('periods',[])]
    elif method=='historical_causation': out['causal_model']={'conditions':data.get('conditions',[]),'mechanisms':data.get('mechanisms',[]),'triggers':data.get('triggers',[]),'rival_explanations':data.get('rival_explanations',[])}
    elif method in {'historical_contingency','counterfactual_history'}: out['alternatives']=[{**a,'hindsight_warning':True,'plausibility_evidence':a.get('plausibility_evidence',[])} for a in data.get('alternatives',[])]
    elif method=='logic': out['fallacy_flags']=data.get('fallacy_flags',[])
    elif method=='ethics': out['stakeholders']=[{**s,'voice_source':s.get('voice_source'),'do_not_infer_preferences':not bool(s.get('voice_source'))} for s in data.get('stakeholders',[])]
    elif method=='indigenous_philosophy': out['protocols']={'nation_or_community':data.get('nation_or_community'),'knowledge_authorities':data.get('knowledge_authorities',[]),'permissions':data.get('permissions',[]),'restricted_knowledge_excluded':True}
    elif method in {'eastern_philosophy','african_philosophy'}: out['tradition_specificity']={'tradition':data.get('tradition'),'original_language_terms':data.get('original_language_terms',{}),'translation_notes':data.get('translation_notes',[])}
    elif method=='poetry': out['prosody']=data.get('prosody',{})
    elif method=='drama': out['performance']={'stage_directions':data.get('stage_directions',[]),'performance_history':data.get('performance_history',[])}
    elif method=='fiction': out['narratology']={'narrator':data.get('narrator'),'focalization':data.get('focalization'),'story_order':data.get('story_order',[]),'discourse_order':data.get('discourse_order',[])}
    elif method=='non_fiction': out['truth_claims']=[{**c,'verification_status':c.get('verification_status','unverified')} for c in data.get('truth_claims',[])]
    elif method=='genre_studies': out['genre_map']={'claimed_genres':data.get('claimed_genres',[]),'conventions':data.get('conventions',[]),'hybridities':data.get('hybridities',[]),'institutions':data.get('institutions',[])}
    out['metrics']=_metrics(method,data,out)
    out['review']={'status':'needs_sources' if not sources else 'ready_for_scholarly_review','unsupported_claim_count':sum(x['status']=='unsupported' for x in claims),'human_review_required':True}
    return out

def _year(v):
    m=re.match(r'\s*(-?\d{3,4})',str(v or '')); return int(m.group(1)) if m else None
def _syllables(word):
    groups=re.findall(r'[aeiouy]+',word.lower()); n=len(groups)
    if word.lower().endswith('e') and not word.lower().endswith(('le','ee','ye')) and n>1: n-=1
    return max(1,n)
def _metrics(method,data,out):
    """Distinctive computed artifacts per humanities method, derived only from supplied data."""
    if method=='historical_analysis':
        yrs=[y for y in (_year(e.get('date')) for e in data.get('events',[]) if isinstance(e,dict)) if y is not None]
        return {'event_count':len(data.get('events',[])),'span_years':(max(yrs)-min(yrs) if yrs else None),'change_count':len(data.get('changes',[])),'continuity_count':len(data.get('continuities',[]))}
    if method=='historiography': return {'school_counts':dict(Counter(str(s.get('name') if isinstance(s,dict) else s) for s in data.get('schools',[])))}
    if method=='archival_research': return {'repository_count':len(data.get('repositories',[])),'holding_unit_count':len(data.get('fonds_series_boxes',[])),'restriction_count':len(data.get('restrictions',[]))}
    if method in ('primary_sources','secondary_sources'):
        linked={sid for c in data.get('claims',[]) if isinstance(c,dict) for sid in c.get('source_ids',[])}
        primary_ids={s['id'] for s in out['sources'] if s['primary']}
        return {'claims_linked_to_primary':sum(bool({str(x) for x in c.get('source_ids',[])}&primary_ids) for c in data.get('claims',[]) if isinstance(c,dict)),'cited_source_ids':sorted(map(str,linked))}
    if method=='oral_history': return {'access_restriction_count':len(data.get('access_restrictions',[])),'consent_recorded':bool(data.get('consent_recorded')),'narrator_review':bool(data.get('narrator_review'))}
    if method=='public_history': return {'stakeholder_count':len(data.get('scope',{}).get('stakeholders',[])) if isinstance(data.get('scope'),dict) else 0}
    if method=='digital_history':
        manifest=data.get('corpus_manifest',[])
        return {'corpus_document_count':len(manifest),'ocr_error_rate':data.get('ocr_error_rate'),'estimated_ocr_errors_per_10k_tokens':(round(float(data['ocr_error_rate'])*10000,1) if isinstance(data.get('ocr_error_rate'),(int,float)) else None)}
    if method=='comparative_history':
        rows=data.get('comparison_matrix',[]);keys=sorted({k for r in rows if isinstance(r,dict) for k in r})
        return {'matrix_rows':len(rows),'matrix_fields':keys}
    if method in ('world_history','comparative_literature','world_literature'):
        srcs=out['sources'];langs={str(s.get('language')) for s in srcs if s.get('language')}
        return {'languages_represented':sorted(langs),'translation_marked_sources':sum(bool(s.get('translation_by')) for s in srcs)}
    if method=='microhistory': return {'scale_note':'small case claims require exceptional-normal evidence','evidence_item_count':len(data.get('sources',[]))}
    if method=='macrohistory':
        yrs=[y for y in (_year(e.get('date')) for e in data.get('events',[]) if isinstance(e,dict)) if y is not None]
        return {'long_run_span_years':(max(yrs)-min(yrs) if yrs else None)}
    if method=='biography':
        yrs=sorted(y for y in (_year(e.get('date')) for e in data.get('events',[]) if isinstance(e,dict)) if y is not None)
        return {'life_event_count':len(data.get('events',[])),'documented_life_span_years':(yrs[-1]-yrs[0] if yrs else None),'first_documented_year':(yrs[0] if yrs else None),'last_documented_year':(yrs[-1] if yrs else None)}
    if method=='prosopography':
        people=data.get('people',[])
        return {'member_count':len(people),'variables_assessed':len(data.get('variables',[]))}
    if method=='genealogy':
        rels=data.get('relationships',[])
        return {'relationship_count':len(rels),'verified_count':sum(r.get('confidence')=='verified' for r in rels if isinstance(r,dict)),'unverified_count':sum(not isinstance(r,dict) or r.get('confidence','unverified')!='verified' for r in rels)}
    if method=='chronology':
        evs=[e for e in data.get('events',[]) if isinstance(e,dict)];yrs=[y for y in (_year(e.get('date')) for e in evs) if y is not None]
        return {'disputed_date_count':sum(bool(e.get('date_disputed')) for e in evs),'span_years':(max(yrs)-min(yrs) if yrs else None),'events_with_year':len(yrs)}
    if method=='periodization':
        periods=data.get('periods',[]);durs=[]
        for p in periods:
            if isinstance(p,dict):
                a,b=_year(p.get('start')),_year(p.get('end'));durs.append({'name':p.get('name'),'duration_years':(b-a if a is not None and b is not None else None)})
        return {'period_durations':durs}
    if method=='historical_causation':
        cm=out.get('causal_model',{})
        return {'condition_count':len(cm.get('conditions',[])),'mechanism_count':len(cm.get('mechanisms',[])),'trigger_count':len(cm.get('triggers',[])),'rival_explanation_count':len(cm.get('rival_explanations',[]))}
    if method in ('historical_contingency','counterfactual_history'):
        alts=data.get('alternatives',[])
        return {'alternative_count':len(alts),'alternatives_with_plausibility_evidence':sum(bool(a.get('plausibility_evidence')) for a in alts if isinstance(a,dict))}
    if method in ('philosophy','analytic_philosophy','logic'):
        args=out.get('arguments',[])
        return {'argument_count':len(args),'arguments_without_objections':sum(not a['objections'] for a in args),'premise_count_total':sum(len(a['premises']) for a in args),'fallacy_flag_count':len(data.get('fallacy_flags',[]))}
    if method=='metaphysics': return {'concept_count':len(data.get('concepts',{}))}
    if method=='epistemology':
        bels=[b for b in data.get('beliefs',[]) if isinstance(b,dict)]
        return {'belief_count':len(bels),'defeater_index':{str(b.get('statement')):len(b.get('defeaters',[])) for b in bels if b.get('statement') is not None}}
    if method=='ethics':
        sts=out.get('stakeholders',[])
        return {'stakeholder_count':len(sts),'unvoiced_stakeholders':[s.get('name') for s in sts if s.get('do_not_infer_preferences')]}
    if method=='aesthetics':
        passages=data.get('passages',[])
        return {'device_counts':dict(Counter(str(p.get('device','unspecified')) for p in passages if isinstance(p,dict)))}
    if method in ('political_philosophy','social_philosophy'):
        scope=data.get('scope',{})
        return {'included_groups':scope.get('included',[]) if isinstance(scope,dict) else [],'excluded_groups':scope.get('excluded',[]) if isinstance(scope,dict) else []}
    if method in ('philosophy_of_mind','philosophy_of_language','philosophy_of_science','philosophy_of_religion','existentialism','phenomenology','pragmatism','continental_philosophy'):
        return {'concept_count':len(data.get('concepts',{})),'thought_experiment_count':len(data.get('thought_experiments',[]))}
    if method in ('eastern_philosophy','african_philosophy'):
        ts=out.get('tradition_specificity',{})
        return {'original_language_term_count':len(ts.get('original_language_terms',{})),'translation_note_count':len(ts.get('translation_notes',[]))}
    if method=='indigenous_philosophy':
        pr=out.get('protocols',{})
        return {'knowledge_authority_count':len(pr.get('knowledge_authorities',[])),'permission_count':len(pr.get('permissions',[]))}
    if method in ('literature','literary_criticism','literary_theory'):
        passages=out.get('passages',[])
        return {'passage_count':len(passages),'verified_passage_count':sum(p['verified_against_edition'] for p in passages),'unverified_passage_count':sum(not p['verified_against_edition'] for p in passages)}
    if method=='poetry':
        lines=[str(x) for x in data.get('lines',[])]
        if lines:
            syll=[sum(_syllables(w) for w in re.findall(r"[A-Za-z']+",line)) for line in lines]
            def _rhyme_key(line):
                words=re.findall(r"[A-Za-z']+",line)
                if not words: return ''
                m=re.search(r"[aeiouy][^aeiouy']*$",words[-1].lower()); return m.group(0) if m else words[-1].lower()[-2:]
            endings=[_rhyme_key(line) for line in lines]
            scheme={};letters={};next_letter='A'
            for i,e in enumerate(endings):
                if e not in letters:letters[e]=next_letter;next_letter=chr(ord(next_letter)+1)
                scheme[i]=letters[e]
            return {'line_count':len(lines),'syllables_per_line':syll,'rhyme_scheme':''.join(scheme[i] for i in sorted(scheme))}
        return {'line_count':0,'note':'supply lines to compute prosody'}
    if method=='drama':
        script=[x for x in data.get('script',[]) if isinstance(x,dict)]
        return {'turn_counts_by_speaker':dict(Counter(str(x.get('speaker')) for x in script if x.get('speaker'))),'stage_direction_count':len(data.get('stage_directions',[]))}
    if method=='fiction':
        so,do=data.get('story_order',[]),data.get('discourse_order',[])
        return {'order_disagreement_positions':sum(1 for a,b in zip(so,do) if a!=b) if len(so)==len(do) else None,'anachrony_present':so!=do}
    if method=='non_fiction':
        tcs=out.get('truth_claims',[])
        return {'verification_status_counts':dict(Counter(str(c.get('verification_status')) for c in tcs))}
    if method=='genre_studies':
        gm=out.get('genre_map',{});claimed={str(x) for x in gm.get('claimed_genres',[])};conventions={str(c.get('genre')) for c in gm.get('conventions',[]) if isinstance(c,dict) and c.get('genre')}
        return {'claimed_genres_with_documented_conventions':sorted(claimed&conventions) if conventions else [],'hybridity_count':len(gm.get('hybridities',[]))}
    return {}
