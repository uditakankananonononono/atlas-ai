import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.humanities_1810_1859 import METHODS,QUESTIONS,humanities_support_1810_1859
from app.modules.m20_general_cognitive_worker.routes import router
H=humanities_support_1810_1859
SRC={'id':'S1','kind':'letter','title':'Letter','creator':'A','locator':'Archive, box 1','date':'1900'}
BASE={'sources':[SRC],'claims':[{'claim':'x','source_ids':['S1']}],'events':[{'date':'1900','event':'x'}]}
EXPECTED=['historical_analysis','historiography','archival_research','primary_sources','secondary_sources','oral_history','public_history','digital_history','comparative_history','world_history','microhistory','macrohistory','biography','prosopography','genealogy','chronology','periodization','historical_causation','historical_contingency','counterfactual_history','philosophy','metaphysics','epistemology','ethics','aesthetics','logic','political_philosophy','social_philosophy','philosophy_of_mind','philosophy_of_language','philosophy_of_science','philosophy_of_religion','existentialism','phenomenology','pragmatism','analytic_philosophy','continental_philosophy','eastern_philosophy','african_philosophy','indigenous_philosophy','literature','literary_criticism','literary_theory','comparative_literature','world_literature','poetry','drama','fiction','non_fiction','genre_studies']

def test_all_50_rows_exact_and_each_has_specific_inquiry():
 assert METHODS==EXPECTED and set(QUESTIONS)==set(EXPECTED)
 for m in METHODS:
  o=H(m,BASE); assert o['method']==m and len(o['guiding_questions'])==3 and o['review']['human_review_required']
  assert o['claims'][0]['status']=='source_linked_not_proven'

def test_1810_historical_analysis_timeline_and_change():
 o=H('historical_analysis',{**BASE,'events':[{'date':'1902'},{'date':'1901'}],'changes':['law'],'continuities':['practice']});assert o['timeline'][0]['date']=='1901' and o['changes']==['law']
def test_1811_historiography_schools():assert H('historiography',{**BASE,'schools':['social history']})['schools']==['social history']
def test_1812_archives_preserve_provenance_and_order():assert H('archival_research',{**BASE,'fonds_series_boxes':['F/S/B1']})['archive_plan']['preserve_original_order']
def test_1813_primary_source_classification():assert H('primary_sources',BASE)['source_audit']['primary']==1
def test_1814_secondary_source_not_misclassified():assert H('secondary_sources',{'sources':[{**SRC,'kind':'book'}]})['source_audit']['primary']==0
def test_1815_oral_history_consent_and_restrictions():
 o=H('oral_history',{**BASE,'consent_recorded':True,'access_restrictions':['closed 10y']});assert o['ethics']['consent_recorded'] and o['ethics']['access_restrictions']==['closed 10y']
def test_1816_public_history_stakeholder_questions():assert 'stakeholders' in H('public_history',BASE)['guiding_questions'][0]
def test_1817_digital_history_reproducibility():assert H('digital_history',{**BASE,'method_version':'v1','ocr_error_rate':.05})['reproducibility']['ocr_error_rate']==.05
def test_1818_comparative_history_matrix():assert H('comparative_history',{**BASE,'comparison_matrix':[{'case':'A'}]})['comparison_matrix'][0]['case']=='A'
def test_1819_world_history_decenters_single_center():assert 'single civilizational center' in H('world_history',BASE)['guiding_questions'][1]
def test_1820_microhistory_scale_warning():assert 'scale jumps' in H('microhistory',BASE)['guiding_questions'][2]
def test_1821_macrohistory_aggregate_warning():assert 'aggregates hide' in H('macrohistory',BASE)['guiding_questions'][1]
def test_1822_biography_interiority_gap():assert 'interiority' in H('biography',BASE)['guiding_questions'][1]
def test_1823_prosopography_aggregate_no_individual_inference():
 o=H('prosopography',{**BASE,'people':[{'role':'x'},{'role':'x'},{'role':'y'}],'variables':['role']});assert o['group_summary']['fields']['role']=={'x':2,'y':1} and o['group_summary']['no_individual_inference_from_aggregate']
def test_1824_genealogy_uncertain_links():assert H('genealogy',{**BASE,'relationships':[{'parent':'a','child':'b'}]})['relationships'][0]['confidence']=='unverified'
def test_1825_chronology_precision_and_dispute():assert H('chronology',{**BASE,'events':[{'date':'1900','date_disputed':True}]})['timeline'][0]['date_precision']=='unknown'
def test_1826_periodization_boundaries_interpretive():assert H('periodization',{**BASE,'periods':[{'name':'modern'}]})['periods'][0]['boundary_is_interpretive']
def test_1827_causation_separates_condition_trigger_mechanism():
 o=H('historical_causation',{**BASE,'conditions':['c'],'triggers':['t'],'mechanisms':['m']})['causal_model'];assert (o['conditions'],o['triggers'],o['mechanisms'])==(['c'],['t'],['m'])
@pytest.mark.parametrize('m', ['historical_contingency','counterfactual_history'])
def test_1828_1829_alternatives_guard_hindsight(m):assert H(m,{**BASE,'alternatives':[{'outcome':'z'}]})['alternatives'][0]['hindsight_warning']
def test_1830_philosophy_argument_reconstruction():assert 'arguments' in H('philosophy',{**BASE,'arguments':[{'premises':['p'],'conclusion':'q'}]})
def test_1831_metaphysics_ontology_question():assert 'ontology' in H('metaphysics',BASE)['guiding_questions'][0]
def test_1832_epistemology_defeaters():assert 'defeaters' in H('epistemology',BASE)['guiding_questions'][1]
def test_1833_ethics_does_not_infer_stakeholder_preferences():assert H('ethics',{**BASE,'stakeholders':[{'name':'x'}]})['stakeholders'][0]['do_not_infer_preferences']
def test_1834_aesthetics_context_and_audience():assert 'audience' in H('aesthetics',BASE)['guiding_questions'][1]
def test_1835_logic_validity_not_truth():
 o=H('logic',{**BASE,'arguments':[{'premises':['p'],'conclusion':'q','validity':'valid'}]});assert o['arguments'][0]['validity']=='valid' and o['arguments'][0]['soundness']=='not_established'
def test_1836_political_philosophy_inclusion():assert 'Who is included?' in H('political_philosophy',BASE)['guiding_questions']
def test_1837_social_philosophy_structure_individual():assert 'structural and individual' in H('social_philosophy',BASE)['guiding_questions'][2]
def test_1838_mind_empirical_claims():assert 'empirical' in H('philosophy_of_mind',BASE)['guiding_questions'][2]
def test_1839_language_speech_act():assert 'speech act' in H('philosophy_of_language',BASE)['guiding_questions'][1]
def test_1840_science_values_inquiry():assert 'values enter' in H('philosophy_of_science',BASE)['guiding_questions'][1]
def test_1841_religion_traditions_from_sources():assert 'traditions represented' in H('philosophy_of_religion',BASE)['guiding_questions'][1]
def test_1842_existentialism_preserves_thinker_differences():assert 'differences among thinkers' in H('existentialism',BASE)['guiding_questions'][2]
def test_1843_phenomenology_bracketing():assert 'bracketed' in H('phenomenology',BASE)['guiding_questions'][2]
def test_1844_pragmatism_practical_difference():assert 'practical difference' in H('pragmatism',BASE)['guiding_questions'][0]
def test_1845_analytic_counterexamples():assert 'counterexamples' in H('analytic_philosophy',BASE)['guiding_questions'][1]
def test_1846_continental_historical_terminology():assert 'historically situated' in H('continental_philosophy',BASE)['guiding_questions'][1]
@pytest.mark.parametrize('m', ['eastern_philosophy','african_philosophy'])
def test_1847_1848_specific_tradition_and_translation(m):
 o=H(m,{**BASE,'tradition':'specific','original_language_terms':{'x':'y'}});assert o['tradition_specificity']['tradition']=='specific'
def test_1849_indigenous_protocols_and_restricted_knowledge():
 o=H('indigenous_philosophy',{**BASE,'nation_or_community':'Named community','permissions':['public teachings']});assert o['protocols']['restricted_knowledge_excluded']
def test_1850_literature_requires_edition_and_passage_verification():
 o=H('literature',{**BASE,'edition':'E','passages':[{'locator':'p1','quotation':'q'}]});assert o['edition']=='E' and not o['passages'][0]['verified_against_edition']
def test_1851_criticism_counterreading():assert 'counterreading' in H('literary_criticism',BASE)['guiding_questions'][2]
def test_1852_theory_not_name_dropped():assert 'name-dropped' in H('literary_theory',BASE)['guiding_questions'][2]
def test_1853_comparative_lit_originals_translations():assert 'originals and translations' in H('comparative_literature',BASE)['guiding_questions'][1]
def test_1854_world_lit_circulation_translation():assert 'circulate' in H('world_literature',BASE)['guiding_questions'][0]
def test_1855_poetry_prosody():assert H('poetry',{**BASE,'prosody':{'meter':'iambic'}})['prosody']['meter']=='iambic'
def test_1856_drama_performance_history():assert H('drama',{**BASE,'performance_history':['1940 production']})['performance']['performance_history']==['1940 production']
def test_1857_fiction_story_discourse_order():
 o=H('fiction',{**BASE,'story_order':[1,2],'discourse_order':[2,1]})['narratology'];assert o['story_order']!=o['discourse_order']
def test_1858_nonfiction_truth_claim_unverified_default():assert H('non_fiction',{**BASE,'truth_claims':[{'claim':'x'}]})['truth_claims'][0]['verification_status']=='unverified'
def test_1859_genre_hybridity_and_institutions():
 o=H('genre_studies',{**BASE,'claimed_genres':['memoir'],'hybridities':['essay'],'institutions':['publisher']})['genre_map'];assert o['hybridities']==['essay'] and o['institutions']==['publisher']
def test_missing_source_link_is_explicit_and_no_sources_blocks_review():
 o=H('historical_analysis',{'claims':[{'claim':'x','source_ids':['missing']}]});assert o['claims'][0]['missing_source_ids']==['missing'] and o['review']['status']=='needs_sources'
def test_route_mounted_and_literal_validated():
 app=FastAPI();app.include_router(router);c=TestClient(app)
 assert c.post('/api/modules/20/humanities/1810-1859/analyze',json={'method':'genre_studies','data':BASE}).status_code==200
 assert c.post('/api/modules/20/humanities/1810-1859/analyze',json={'method':'fake','data':{}}).status_code==422

# --- audit family D: computed metric artifacts, failure paths, tenant boundary
def M(m,d):return H(m,{**BASE,**d})['metrics']
def test_1810_historical_analysis_metrics():
 m=M('historical_analysis',{'events':[{'date':'1850'},{'date':'1901'}],'changes':['a','b'],'continuities':['c']})
 assert m['span_years']==51 and m['change_count']==2 and m['continuity_count']==1
def test_1811_historiography_metrics():assert M('historiography',{'schools':['social','social','cultural']})['school_counts']=={'social':2,'cultural':1}
def test_1812_archival_metrics():assert M('archival_research',{'repositories':['r1'],'fonds_series_boxes':['a','b'],'restrictions':['x']})=={'repository_count':1,'holding_unit_count':2,'restriction_count':1}
def test_1813_1814_primary_linkage_metrics():
 m=M('primary_sources',{'claims':[{'claim':'x','source_ids':['S1']},{'claim':'y','source_ids':['ZZ']}]})
 assert m['claims_linked_to_primary']==1 and m['cited_source_ids']==['S1','ZZ']
def test_1815_oral_history_metrics():
 m=M('oral_history',{'consent_recorded':True,'access_restrictions':['a','b']});assert m['access_restriction_count']==2 and m['consent_recorded'] is True
def test_1816_public_history_metrics():assert M('public_history',{'scope':{'stakeholders':['a','b','c']}})['stakeholder_count']==3
def test_1817_digital_history_metrics():
 m=M('digital_history',{'corpus_manifest':['d1','d2','d3'],'ocr_error_rate':.02});assert m['corpus_document_count']==3 and m['estimated_ocr_errors_per_10k_tokens']==200
def test_1818_comparative_matrix_metrics():assert M('comparative_history',{'comparison_matrix':[{'case':'A','x':1}]})['matrix_rows']==1
def test_1819_world_history_languages():
 m=M('world_history',{'sources':[{**SRC,'language':'en','translation_by':'T'}]});assert m['languages_represented']==['en'] and m['translation_marked_sources']==1
def test_1821_macrohistory_span():assert M('macrohistory',{'events':[{'date':'-0300'},{'date':'1900'}]})['long_run_span_years']==2200
def test_1822_biography_span():
 m=M('biography',{'events':[{'date':'1880'},{'date':'1955'}]});assert m['documented_life_span_years']==75 and m['first_documented_year']==1880
def test_1823_prosopography_metrics():assert M('prosopography',{'people':[{'role':'x'}],'variables':['role']})=={'member_count':1,'variables_assessed':1}
def test_1824_genealogy_metrics():
 m=M('genealogy',{'relationships':[{'parent':'a','child':'b','confidence':'verified'},{'parent':'b','child':'c'}]});assert m['verified_count']==1 and m['unverified_count']==1
def test_1825_chronology_metrics():
 m=M('chronology',{'events':[{'date':'1899','date_disputed':True},{'date':'1901'}]});assert m['disputed_date_count']==1 and m['span_years']==2
def test_1826_periodization_durations():
 m=M('periodization',{'periods':[{'name':'modern','start':'1789','end':'1914'}]});assert m['period_durations']==[{'name':'modern','duration_years':125}]
def test_1827_causation_metric_counts():
 m=M('historical_causation',{'conditions':['c'],'mechanisms':['m1','m2'],'triggers':['t'],'rival_explanations':['r']})
 assert m['condition_count']==1 and m['mechanism_count']==2 and m['rival_explanation_count']==1
def test_1828_1829_alternative_evidence_metrics():
 for m_ in ('historical_contingency','counterfactual_history'):
  m=M(m_,{'alternatives':[{'outcome':'z','plausibility_evidence':['e']},{'outcome':'y'}]});assert m['alternatives_with_plausibility_evidence']==1
def test_1830_1835_argument_metrics():
 for m_ in ('philosophy','analytic_philosophy','logic'):
  m=M(m_,{'arguments':[{'premises':['p','q'],'conclusion':'r'},{'premises':['s'],'conclusion':'t','objections':['o']}]})
  assert m['argument_count']==2 and m['arguments_without_objections']==1 and m['premise_count_total']==3
def test_1832_epistemology_defeater_index():assert M('epistemology',{'beliefs':[{'statement':'b1','defeaters':['d1','d2']}]})['defeater_index']=={'b1':2}
def test_1833_ethics_unvoiced():assert M('ethics',{'stakeholders':[{'name':'x'},{'name':'y','voice_source':'interview'}]})['unvoiced_stakeholders']==['x']
def test_1834_aesthetics_device_counts():assert M('aesthetics',{'passages':[{'locator':'1','device':'irony'},{'locator':'2','device':'irony'}]})['device_counts']=={'irony':2}
def test_1849_indigenous_protocol_metrics():
 m=M('indigenous_philosophy',{'nation_or_community':'N','knowledge_authorities':['a','b'],'permissions':['p']});assert m['knowledge_authority_count']==2 and m['permission_count']==1
def test_1850_literature_passage_metrics():
 m=M('literature',{'passages':[{'locator':'1','quotation':'q','verified_against_edition':True},{'locator':'2','quotation':'r'}]})
 assert m['verified_passage_count']==1 and m['unverified_passage_count']==1
def test_1855_poetry_prosody_computation():
 m=H('poetry',{**BASE,'lines':['The cat sat on the mat','He wore a funny hat','The dog ran fast']})['metrics']
 assert m['rhyme_scheme']=='AAB' and m['syllables_per_line']==[6,6,4]
def test_1856_drama_turn_counts():
 m=M('drama',{'script':[{'speaker':'Hamlet','line':'x'},{'speaker':'Ophelia','line':'y'},{'speaker':'Hamlet','line':'z'}]});assert m['turn_counts_by_speaker']=={'Hamlet':2,'Ophelia':1}
def test_1857_fiction_order_metrics():
 m=M('fiction',{'story_order':[1,2,3],'discourse_order':[2,1,3]});assert m['order_disagreement_positions']==2 and m['anachrony_present'] is True
def test_1858_nonfiction_verification_tally():
 m=M('non_fiction',{'truth_claims':[{'claim':'a','verification_status':'verified'},{'claim':'b'}]});assert m['verification_status_counts']=={'verified':1,'unverified':1}
def test_1859_genre_convention_metrics():
 m=M('genre_studies',{'claimed_genres':['memoir'],'conventions':[{'genre':'memoir','convention':'first person'}],'hybridities':['essay']})
 assert m['claimed_genres_with_documented_conventions']==['memoir'] and m['hybridity_count']==1
def test_humanities_failure_paths():
 with pytest.raises(ValueError,match='unsupported'):H('not_a_method',BASE)
 with pytest.raises(ValueError,match=r'sources\[0\]'):H('historical_analysis',{'sources':['not-a-dict']})
 with pytest.raises(ValueError,match=r'claims\[0\]'):H('historical_analysis',{**BASE,'claims':['x']})
 with pytest.raises(ValueError,match=r'events\[0\]'):H('chronology',{**BASE,'events':['1901']})
def test_humanities_tenant_boundary(monkeypatch):
 from app.main import app
 monkeypatch.setenv('ATLAS_ENV','production')
 c=TestClient(app)
 assert c.post('/api/v1/api/modules/20/humanities/1810-1859/analyze',json={'method':'chronology','data':BASE}).status_code==401
 h={'X-Atlas-Tenant':'tenant-a','X-Atlas-Actor':'tester'}
 r=c.post('/api/v1/api/modules/20/humanities/1810-1859/analyze',headers=h,json={'method':'chronology','data':BASE});assert r.status_code==200 and 'metrics' in r.json()
