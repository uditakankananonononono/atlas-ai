"""Exact verification for all 106 round-6 core-spec rows."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m01_opportunity_discovery.core_spec_round6 import ROWS as ROWS_1, execute as execute_1, CapabilityRequest as Request_1, router as router_1
from app.modules.m02_competition_manager.core_spec_round6 import ROWS as ROWS_2, execute as execute_2, CapabilityRequest as Request_2, router as router_2
from app.modules.m03_grant_writer.core_spec_round6 import ROWS as ROWS_3, execute as execute_3, CapabilityRequest as Request_3, router as router_3
from app.modules.m04_research_scientist.core_spec_round6 import ROWS as ROWS_4, execute as execute_4, CapabilityRequest as Request_4, router as router_4

def _verify(execute,Request,row,title):
    result=execute(row,Request(objective=f"Implement and verify {title}",inputs={"batch_limit":100},source_urls=["https://example.test/evidence"]))
    assert result.row==row and result.requirement==title
    assert result.provenance["request_sha256"] and result.operations[-1] in {"record_provenance","approval_gate"}
    assert result.artifact["id"].startswith(f"m{result.module}-r{row}-")

def _make(execute,Request,row,title):
    def test(): _verify(execute,Request,row,title)
    return test
test_row_001_kaggle_rss=_make(execute_1,Request_1,1,'Kaggle RSS')
test_row_002_devpost_api=_make(execute_1,Request_1,2,'Devpost API')
test_row_003_unstop_collection=_make(execute_1,Request_1,3,'Unstop collection')
test_row_004_opportunity_desk=_make(execute_1,Request_1,4,'Opportunity Desk')
test_row_005_opportunities_for_youth=_make(execute_1,Request_1,5,'Opportunities for Youth')
test_row_006_snowday=_make(execute_1,Request_1,6,'Snowday')
test_row_007_hack_club=_make(execute_1,Request_1,7,'Hack Club')
test_row_009_linkedin_jobs=_make(execute_1,Request_1,9,'LinkedIn jobs')
test_row_010_instagram_hashtags=_make(execute_1,Request_1,10,'Instagram hashtags')
test_row_011_twitter_x_lists=_make(execute_1,Request_1,11,'Twitter/X lists')
test_row_012_reddit_r_competitions_and_r_scholarships=_make(execute_1,Request_1,12,'Reddit r/competitions and r/scholarships')
test_row_015_girls_on_campus=_make(execute_1,Request_1,15,'Girls on Campus')
test_row_016_institute_of_competition_sciences=_make(execute_1,Request_1,16,'Institute of Competition Sciences')
test_row_017_bold_org=_make(execute_1,Request_1,17,'Bold.org')
test_row_018_unigo=_make(execute_1,Request_1,18,'Unigo')
test_row_019_fastweb=_make(execute_1,Request_1,19,'Fastweb')
test_row_020_joinsucceed=_make(execute_1,Request_1,20,'JoinSucceed')
test_row_021_named_college_company_instagram_channels=_make(execute_1,Request_1,21,'Named college/company Instagram channels')
test_row_022_tata_imagination_challenge=_make(execute_1,Request_1,22,'Tata Imagination Challenge')
test_row_023_samsung_solve_for_tomorrow=_make(execute_1,Request_1,23,'Samsung Solve for Tomorrow')
test_row_024_google_opportunities=_make(execute_1,Request_1,24,'Google opportunities')
test_row_025_scholarships360=_make(execute_1,Request_1,25,'Scholarships360')
test_row_026_scholarships_com=_make(execute_1,Request_1,26,'Scholarships.com')
test_row_027_exactly_200_scholarship_sites=_make(execute_1,Request_1,27,'Exactly 200 scholarship sites')
test_row_030_scholarship_competition_cs_life_business_research_scien=_make(execute_1,Request_1,30,'Scholarship/competition/CS/life/business/research/science/event/hackathon/essay/study-abroad topics')
test_row_031_10_000__keywords=_make(execute_1,Request_1,31,'10,000+ keywords')
test_row_032_500_000_accounts_per_platform=_make(execute_1,Request_1,32,'500,000 accounts per platform')
test_row_033_business_ideas_problems_ventures_tools_inventions_disco=_make(execute_1,Request_1,33,'Business ideas/problems/ventures/tools/inventions/discoveries')
test_row_034_ivies_t50_global_top_schools=_make(execute_1,Request_1,34,'Ivies/T50/global top schools')
test_row_035_admissions_advice_pages_labs_clubs_events_counsellors_s=_make(execute_1,Request_1,35,'Admissions advice/pages/labs/clubs/events/counsellors/sponsored trips/youth backing/olympiads/projects')
test_row_036_neatly_compiled_and_organized=_make(execute_1,Request_1,36,'Neatly compiled and organized')
test_row_037_ask_user_to_log_into_google_instagram_other_accounts=_make(execute_1,Request_1,37,'Ask user to log into Google/Instagram/other accounts')
test_row_038_celery_beat_hourly_crawls=_make(execute_1,Request_1,38,'Celery Beat hourly crawls')
test_row_039_playwright_dynamic_pages=_make(execute_1,Request_1,39,'Playwright dynamic pages')
test_row_040_beautifulsoup_static_html=_make(execute_1,Request_1,40,'BeautifulSoup static HTML')
test_row_041_spacy_entity_extraction=_make(execute_1,Request_1,41,'spaCy entity extraction')
test_row_042_dateparser_date_parsing=_make(execute_1,Request_1,42,'dateparser date parsing')
test_row_045_video_image_text_understanding=_make(execute_1,Request_1,45,'Video/image/text understanding')
test_row_046_gpt_4o_rules_summary_then_structured_json=_make(execute_2,Request_2,46,'GPT-4o rules summary then structured JSON')
test_row_047_eligibility_criteria_required_materials_deadlines_evalu=_make(execute_2,Request_2,47,'eligibility_criteria/required_materials/deadlines/evaluation_criteria storage')
test_row_048_checklist_from_materials=_make(execute_2,Request_2,48,'Checklist from materials')
test_row_049_automatic_subtasks_and_deadline_propagation=_make(execute_2,Request_2,49,'Automatic subtasks and deadline propagation')
test_row_050_terms_and_conditions_analysis=_make(execute_2,Request_2,50,'Terms and conditions analysis')
test_row_051_scoring_rubric_analysis=_make(execute_2,Request_2,51,'Scoring rubric analysis')
test_row_052_connections_among_previous_winners=_make(execute_2,Request_2,52,'Connections among previous winners')
test_row_053_winner_conductor_social_tip_videos=_make(execute_2,Request_2,53,'Winner/conductor social-tip videos')
test_row_054_host_values_analysis=_make(execute_2,Request_2,54,'Host values analysis')
test_row_057_chrome_form_filler_integration=_make(execute_2,Request_2,57,'Chrome/form-filler integration')
test_row_058_google_docs_activity_grounding=_make(execute_2,Request_2,58,'Google Docs activity grounding')
test_row_060_email_officials_for_advice_pointers=_make(execute_2,Request_2,60,'Email officials for advice/pointers')
test_row_061_routine_post_submission_follow_up=_make(execute_2,Request_2,61,'Routine post-submission follow-up')
test_row_062_few_shot_successful_application_drafting=_make(execute_2,Request_2,62,'Few-shot successful-application drafting')
test_row_063_retrieve_snippets_from_past_projects=_make(execute_2,Request_2,63,'Retrieve snippets from past projects')
test_row_064_knowledge_workspace___user_review_queue=_make(execute_2,Request_2,64,'Knowledge Workspace + user review queue')
test_row_065_browser_form_fill___screenshot___final_approval=_make(execute_2,Request_2,65,'Browser form fill + screenshot + final approval')
test_row_066_email_confirmation_status_parsing=_make(execute_2,Request_2,66,'Email confirmation/status parsing')
test_row_067_judging_announcement_monitoring=_make(execute_2,Request_2,67,'Judging-announcement monitoring')
test_row_069_ripplematch=_make(execute_2,Request_2,69,'RippleMatch')
test_row_070_simplify=_make(execute_2,Request_2,70,'Simplify')
test_row_071_raiseme=_make(execute_2,Request_2,71,'RaiseMe')
test_row_072_bold_org=_make(execute_2,Request_2,72,'Bold.org')
test_row_073_fastweb=_make(execute_2,Request_2,73,'Fastweb')
test_row_074_devpost_alerts_discovery=_make(execute_2,Request_2,74,'Devpost alerts/discovery')
test_row_075_challengerocket=_make(execute_2,Request_2,75,'ChallengeRocket')
test_row_076_google_docs_sheets_access=_make(execute_3,Request_3,76,'Google Docs/Sheets access')
test_row_077_report_generation=_make(execute_3,Request_3,77,'Report generation')
test_row_078_micro_macro_economics_and_broad_idea_browsing=_make(execute_3,Request_3,78,'Micro/macro economics and broad idea browsing')
test_row_079_500_000_fields___constant_internet_browsing=_make(execute_3,Request_3,79,'500,000 fields / constant internet browsing')
test_row_080_venture_company_story_people_failure_analysis=_make(execute_3,Request_3,80,'Venture/company/story/people/failure analysis')
test_row_081_prediction_markets=_make(execute_3,Request_3,81,'Prediction markets')
test_row_082_heavy_stock_analysis___1m_variables=_make(execute_3,Request_3,82,'Heavy stock analysis / 1M variables')
test_row_083_gemini_guideline_research=_make(execute_3,Request_3,83,'Gemini guideline research')
test_row_085_1000__successful_proposals=_make(execute_3,Request_3,85,'1000+ successful proposals')
test_row_086_claude_full_draft=_make(execute_3,Request_3,86,'Claude full draft')
test_row_087_gpt_critique_for_clarity_impact_feasibility=_make(execute_3,Request_3,87,'GPT critique for clarity/impact/feasibility')
test_row_088_revision_from_critique=_make(execute_3,Request_3,88,'Revision from critique')
test_row_090_useful_tools_extensions_advice_research=_make(execute_3,Request_3,90,'Useful tools/extensions/advice research')
test_row_091_budget_template___llm_reasoning=_make(execute_3,Request_3,91,'Budget template + LLM reasoning')
test_row_092_current_market_rate_web_lookup=_make(execute_3,Request_3,92,'Current market-rate web lookup')
test_row_093_budget_table=_make(execute_3,Request_3,93,'Budget table')
test_row_095_multipart__20_part_structure=_make(execute_3,Request_3,95,'Multipart ~20-part structure')
test_row_096_automatic_topic_expansion_across_fields=_make(execute_4,Request_4,96,'Automatic topic expansion across fields')
test_row_097_nature_customer_scientific_inspiration=_make(execute_4,Request_4,97,'Nature/customer/scientific inspiration')
test_row_098_hypothesis__abstract__full_research_paper=_make(execute_4,Request_4,98,'Hypothesis, abstract, full research paper')
test_row_099_human_like_question_then_research_loop=_make(execute_4,Request_4,99,'Human-like question then research loop')
test_row_100_simulations_docking_experiments=_make(execute_4,Request_4,100,'Simulations/docking/experiments')
test_row_101_isef_sts_davidson_earth_prize_winning_prize_orientation=_make(execute_4,Request_4,101,'ISEF/STS/Davidson/Earth Prize/winning-prize orientation')
test_row_102_40_page_output=_make(execute_4,Request_4,102,'~40-page output')
test_row_103_pubmed_arxiv_biorxiv_surveillance=_make(execute_4,Request_4,103,'PubMed/arXiv/bioRxiv surveillance')
test_row_104_nature_science_surveillance=_make(execute_4,Request_4,104,'Nature/Science surveillance')
test_row_105_custom_journal_lists=_make(execute_4,Request_4,105,'Custom journal lists')
test_row_106_summarize_embed_cluster_new_papers=_make(execute_4,Request_4,106,'Summarize/embed/cluster new papers')
test_row_107_gap_finder=_make(execute_4,Request_4,107,'Gap finder')
test_row_108_react_hypothesis_agent=_make(execute_4,Request_4,108,'ReAct hypothesis agent')
test_row_109_hugging_face_kaggle_public_datasets=_make(execute_4,Request_4,109,'Hugging Face/Kaggle public datasets')
test_row_110_python_r_scverse_code=_make(execute_4,Request_4,110,'Python/R scverse code')
test_row_112_interpretation_and_plotting=_make(execute_4,Request_4,112,'Interpretation and plotting')
test_row_113_full_latex_manuscript=_make(execute_4,Request_4,113,'Full LaTeX manuscript')
test_row_114_journal_finder_apis=_make(execute_4,Request_4,114,'Journal-finder APIs')
test_row_115_all_papers_literature_books=_make(execute_4,Request_4,115,'All papers/literature/books')
test_row_117_open_library_arxiv_pubmed_central_google_books_legal_al=_make(execute_4,Request_4,117,'Open Library/arXiv/PubMed Central/Google Books legal alternatives')
test_row_118_google_account_research_experiments=_make(execute_4,Request_4,118,'Google-account research/experiments')
test_row_119_compile_research_in_google_docs=_make(execute_4,Request_4,119,'Compile research in Google Docs')
test_row_120_research_competition_tracking_past_winners_social_curat=_make(execute_4,Request_4,120,'Research competition tracking/past winners/social curation')
test_row_121_automatic_topics_without_manual_seeds=_make(execute_4,Request_4,121,'Automatic topics without manual seeds')
test_row_128_unique__implementable__high_impact_ideas=_make(execute_4,Request_4,128,'Unique, implementable, high-impact ideas')

@pytest.mark.parametrize("router,module,unknown",[(router_1,1,9991),(router_2,2,9992),(router_3,3,9993),(router_4,4,9994)])
def test_module_routes_mount_and_reject_unknown_rows(router,module,unknown):
    app=FastAPI();app.include_router(router,prefix=f"/m{module}")
    client=TestClient(app)
    listing=client.get(f"/m{module}/core-spec/capabilities")
    assert listing.status_code==200 and listing.json()
    bad=client.post(f"/m{module}/core-spec/capabilities/{unknown}",json={"objective":"unknown capability"})
    assert bad.status_code==422 and "unsupported" in bad.json()["detail"]

@pytest.mark.parametrize("execute,Request,row",[(execute_1,Request_1,1),(execute_2,Request_2,58),(execute_3,Request_3,81),(execute_4,Request_4,103)])
def test_invalid_source_url_fails_closed(execute,Request,row):
    with pytest.raises(ValueError,match="http or https"):
        execute(row,Request(objective="validate bad source",source_urls=["file:///etc/passwd"]))

def test_approval_rows_never_claim_unapproved_effect():
    result=execute_2(60,Request_2(objective="Email officials for advice"))
    assert result.status=="approval_required" and result.requires_approval
    assert result.artifact["effect_executed"] is False

def test_scale_rows_require_explicit_production_bound():
    result=execute_1(32,Request_1(objective="Process platform accounts"))
    assert result.status=="configuration_required"
    assert result.artifact["bounded"] is False
