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

@pytest.mark.parametrize("execute,Request,row",[(execute_1,Request_1,1),(execute_2,Request_2,58),(execute_3,Request_3,76),(execute_4,Request_4,103)])
def test_core_spec_rows_are_labelled_plan_only_not_executed(execute,Request,row):
    """These rows validate input and record a hash; they do not perform the named capability (no source call, no draft,
    no export). The result must say so, never 'ready'/'done'."""
    r=execute(row,Request(objective="label check",inputs={"batch_limit":1}))
    assert r.status in {"plan_only","approval_required","configuration_required"} and r.status!="ready"
    assert r.executed is False

def _rates():
    return [{"code":"gpu","label":"GPU hour","unit":"hour","amount":"2.50","currency":"USD","effective_from":"2026-01-01",
             "source_url":"https://example.test/rates","observed_at":"2026-09-01T00:00:00+00:00"}]

def test_row_93_budget_table_really_computes_from_sourced_rates():
    r=execute_3(93,Request_3(objective="budget",inputs={"rates":_rates(),"lines":[{"rate_code":"gpu","quantity":"100","description":"training"}],
                                                     "as_of":"2026-10-04","indirect_rate":"0.1"}))
    b=r.artifact["budget"]
    assert r.executed is True and r.status=="executed"
    assert (b["direct_total"],b["indirect_total"],b["grand_total"])==("250.00","25.00","275.00")
    assert b["lines"][0]["source_url"]=="https://example.test/rates"

def test_row_93_budget_refuses_unsourced_or_expired_rates_and_never_invents_one():
    with pytest.raises(ValueError,match="no current, observed rate"):
        execute_3(93,Request_3(objective="budget",inputs={"rates":_rates(),"lines":[{"rate_code":"tpu","quantity":"1","description":"x"}],"as_of":"2026-10-04"}))
    with pytest.raises(ValueError,match="invalid|http"):
        execute_3(93,Request_3(objective="budget",inputs={"rates":[{"code":"gpu"}],"lines":[],"as_of":"2026-10-04"}))

def _call(**over):
    r=_rates()[0]; r.update(over.pop("rate",{}))
    inp={"rates":[r],"lines":[{"rate_code":"gpu","quantity":"1","description":"x"}],"as_of":"2026-10-04"}; inp.update(over)
    return execute_3(93,Request_3(objective="budget",inputs=inp))

@pytest.mark.parametrize("over,match",[
    ({"rate":{"source_url":"javascript:alert(1)"}},"http"),({"rate":{"source_url":""}},"http"),({"rate":{"source_url":"https://"}},"http"),({"rate":{"source_url":"https:///x"}},"http"),
    ({"rate":{"source_url":"https://user:pw@example.test/r"}},"http"),({"rate":{"source_url":"https://exa mple.test/r"}},"http"),
    ({"rate":{"source_url":"https://example.test/r\n"}},"http"),({"rate":{"source_url":"https://example.test:99999/r"}},"http"),({"rate":{"source_url":None}},"http"),
    ({"rate":{"effective_to":"not-a-date"}},"invalid"),
    ({"rate":{"effective_to":"2026-06-30"}},"no current, observed rate"),            # expired rate
    ({"rate":{"effective_from":"2027-01-01"}},"no current, observed rate"),
    ({"rate":{"observed_at":"2026-09-01T00:00:00"}},"invalid"),                      # naive timestamp
    ({"rate":{"observed_at":"2999-01-01T00:00:00+00:00"}},"no current, observed rate"),  # observed in the future
    ({"lines":[{"rate_code":"gpu","quantity":"0","description":"x"}]},"invalid"),
    ({"lines":[{"rate_code":"gpu","quantity":"-3","description":"x"}]},"invalid"),
    ({"indirect_rate":"2"},"invalid"),
    ({"rates":[_rates()[0],{**_rates()[0],"code":"cpu","currency":"EUR"}],"lines":[{"rate_code":"gpu","quantity":"1","description":"a"},{"rate_code":"cpu","quantity":"1","description":"b"}]},"invalid"),
])
def test_row_93_refusals(over,match):
    with pytest.raises(ValueError,match=match): _call(**over)

def test_row_93_result_says_inputs_are_caller_asserted():
    assert "CALLER-ASSERTED" in _call().artifact["budget"]["provenance_note"]

def test_row_93_without_budget_inputs_stays_plan_only_and_route_422_on_bad_input():
    assert execute_3(93,Request_3(objective="budget")).status=="plan_only"
    app=FastAPI();app.include_router(router_3,prefix="/m3");c=TestClient(app)
    ok=c.post("/m3/core-spec/capabilities/93",json={"objective":"budget","inputs":{"rates":_rates(),"lines":[{"rate_code":"gpu","quantity":"2","description":"x"}],"as_of":"2026-10-04"}})
    assert ok.status_code==200 and ok.json()["executed"] is True and ok.json()["artifact"]["budget"]["grand_total"]=="5.00"
    bad=c.post("/m3/core-spec/capabilities/93",json={"objective":"budget","inputs":{"rates":[{**_rates()[0],"source_url":"javascript:x"}],"lines":[{"rate_code":"gpu","quantity":"2","description":"x"}],"as_of":"2026-10-04"}})
    assert bad.status_code==422

@pytest.mark.parametrize("module,rows,execute,Request",[(1,ROWS_1,execute_1,Request_1),(2,ROWS_2,execute_2,Request_2),(3,ROWS_3,execute_3,Request_3),(4,ROWS_4,execute_4,Request_4)])
def test_no_core_spec_row_in_any_module_reports_ready(module,rows,execute,Request):
    for row in rows:
        r=execute(row,Request(objective="label sweep",inputs={"batch_limit":1}))
        assert r.status!="ready", (module,row)
        assert r.executed is False, (module,row)  # sweep supplies no row-93 budget inputs, so nothing executes


@pytest.mark.parametrize("inputs",[
    {"rates":[None],"lines":[{"rate_code":"gpu","quantity":"1","description":"x"}],"as_of":"2026-10-04"},
    {"rates":["gpu"],"lines":[{"rate_code":"gpu","quantity":"1","description":"x"}],"as_of":"2026-10-04"},
    {"rates":_rates(),"lines":[None],"as_of":"2026-10-04"},
    {"rates":_rates(),"lines":["gpu"],"as_of":"2026-10-04"},
    {"rates":"gpu","lines":"x","as_of":"2026-10-04"},
    {"rates":[],"lines":[],"as_of":"2026-10-04"},
    {"rates":_rates(),"lines":[{"rate_code":"gpu","quantity":"1","description":"x"}],"as_of":"yesterday"},
    {"rates":_rates(),"lines":[{"rate_code":"gpu","quantity":"abc","description":"x"}],"as_of":"2026-10-04"},
    {"rates":_rates(),"lines":[{"rate_code":"gpu","quantity":"1","description":"x"}],"as_of":None},
])
def test_row_93_malformed_containers_are_422_over_http_never_500(inputs):
    app=FastAPI();app.include_router(router_3,prefix="/m3")
    c=TestClient(app,raise_server_exceptions=False)
    r=c.post("/m3/core-spec/capabilities/93",json={"objective":"budget","inputs":inputs})
    assert r.status_code==422,(r.status_code,r.text[:200])
    assert "invalid" in r.text

SECRET="Bearer sk-live-SECRET-0123456789"
@pytest.mark.parametrize("bad",[
    {"rate":{"observed_at":SECRET}},{"rate":{"effective_from":SECRET}},{"rate":{"effective_to":SECRET*50}},
    {"rate":{"amount":SECRET}},{"rate":{"source_url":SECRET}},{"rate":{"code":SECRET},"lines":[{"rate_code":SECRET+"x","quantity":"1","description":"d"}]},
    {"lines":[{"rate_code":SECRET,"quantity":"1","description":"d"}]},{"lines":[{"rate_code":"gpu","quantity":SECRET,"description":"d"}]},
    {"as_of":SECRET*100},{"indirect_rate":SECRET},
])
def test_row_93_errors_never_echo_caller_input_over_http(bad):
    r0=_rates()[0]; r0.update(bad.get("rate",{}))
    inp={"rates":[r0],"lines":bad.get("lines",[{"rate_code":"gpu","quantity":"1","description":"d"}]),"as_of":bad.get("as_of","2026-10-04")}
    if "indirect_rate" in bad: inp["indirect_rate"]=bad["indirect_rate"]
    app=FastAPI();app.include_router(router_3,prefix="/m3")
    r=TestClient(app,raise_server_exceptions=False).post("/m3/core-spec/capabilities/93",json={"objective":"budget","inputs":inp})
    assert r.status_code==422,(r.status_code,r.text[:200])
    assert "SECRET" not in r.text and "sk-live" not in r.text and len(r.text)<400

@pytest.mark.parametrize("over",[
    {"rate":{"currency":"sk-live-C"}},{"rate":{"currency":"usd"}},{"rate":{"currency":"USDX"}},{"rate":{"currency":1}},
    {"rate":{"unit":["hour"]}},{"rate":{"unit":""}},{"rate":{"unit":"u"*41}},{"rate":{"label":{"a":1}}},{"rate":{"label":"l"*121}},
    {"rate":{"code":"has space"}},{"rate":{"code":"c"*65}},{"rate":{"amount":"NaN"}},{"rate":{"amount":"Infinity"}},{"rate":{"amount":True}},{"rate":{"amount":"1e13"}},
    {"lines":[{"rate_code":"gpu","quantity":"1","description":"d"*501}]},{"lines":[{"rate_code":"gpu","quantity":"1","description":"bad\x00ctl"}]},
    {"lines":[{"rate_code":"gpu","quantity":"1","description":["x"]}]},{"lines":[{"rate_code":"gpu","quantity":"NaN","description":"d"}]},
    {"lines":[{"rate_code":"gpu","quantity":"1","description":"d"}]*201},{"indirect_rate":"NaN"},
])
def test_row_93_field_type_length_currency_validation(over):
    with pytest.raises(ValueError,match="invalid"): _call(**over)

def test_row_93_legitimate_content_passes_unchanged():
    r=_call(lines=[{"rate_code":"gpu","quantity":"2.5","description":"Training run, 4×A100 (phase 1)"}],rate={"currency":"EUR","label":"GPU hour (A100)"})
    b=r.artifact["budget"]; assert b["currency"]=="EUR" and b["lines"][0]["description"]=="Training run, 4×A100 (phase 1)" and b["direct_total"]=="6.25"

def test_row_93_flags_lines_that_round_to_zero_instead_of_hiding_them():
    r=_call(lines=[{"rate_code":"gpu","quantity":"0.000001","description":"tiny"}])
    b=r.artifact["budget"]
    assert b["lines"][0]["total"]=="0.00" and b["warnings"][0]["code"]=="line_rounds_to_zero" and b["warnings"][0]["rate_codes"]==["gpu"]
    assert "warnings" not in _call().artifact["budget"]

def test_row_85_is_plan_only_and_points_at_the_real_corpus_operations():
    r=execute_3(85,Request_3(objective="find funded proposals",inputs={"batch_limit":10}))
    assert r.status=="plan_only" and r.executed is False and "corpus/ingest" in r.artifact["real_operation"]["ingest"]

def _doc(n):  return "\n\n".join(f"Section {k}\nBody paragraph {k} " + ("lorem ipsum "*(k%7+1)) for k in range(n))

@pytest.mark.parametrize("n,mp",[(1,20),(5,20),(20,20),(57,20),(57,7),(300,20),(3,1),(40,13)])
def test_row_95_splits_into_at_most_20_parts_losslessly(n,mp):
    t=_doc(n); r=execute_3(95,Request_3(objective="multipart",inputs={"text":t,"max_parts":mp,"batch_limit":1}))
    m=r.artifact["multipart"]
    assert r.executed is True and 1<=m["part_count"]<=min(mp,20,n)
    assert "\n\n".join(p["text"] for p in m["parts"])==t
    assert [p["order"] for p in m["parts"]]==list(range(1,m["part_count"]+1))
    if n>=mp and mp<=20: assert m["part_count"]>=max(1,mp//2)

@pytest.mark.parametrize("inputs",[{"text":""},{"text":None},{"text":["x"]},{"text":"x"*2_000_001},{"text":"a","max_parts":0},{"text":"a","max_parts":21},{"text":"a","max_parts":True},{"text":"a","max_parts":"5"}])
def test_row_95_refusals_are_422_over_http(inputs):
    app=FastAPI();app.include_router(router_3,prefix="/m3")
    r=TestClient(app,raise_server_exceptions=False).post("/m3/core-spec/capabilities/95",json={"objective":"multipart","inputs":inputs})
    assert r.status_code==422 and "invalid" in r.text and len(r.text)<300

def test_row_95_without_text_stays_plan_only():
    assert execute_3(95,Request_3(objective="multipart")).executed is False
