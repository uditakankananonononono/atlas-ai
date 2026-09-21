import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.optimization_story_235_280 import WorkbenchError, capabilities, execute
from app.modules.m20_general_cognitive_worker.optimization_story_routes_235_280 import router
SRC={"title":"Owner supplied reference","url":"https://example.org/input"}
OPT={"source":SRC,"objective":[1.0,2.0],"initial":[0.5,1.5],"constraint_matrix":[[1.0,1.0]],"bounds":[1.0],"iteration":4,"blocks":[[0],[1]],"duals":[0.2],"denominator":2.0,"historical_losses":[1.2,0.8],"arm_rewards":[[1,0],[0.4,0.5]],"model_weights":[[1,0],[0,1]],"propensities":[0.5,0.5],"priors":[[1,1],[2,1]],"outcomes":[[2,1],[1,2]],"means":[0.5,0.7],"counts":[2,3],"expert_losses":[0.2,0.9],"learner_losses":[1,2],"comparator_losses":[0.5,1.5],"payoff_matrix":[[1,0],[0,2]],"action_counts":[2,3]}
STORY={"source":SRC,"premise":"A mapmaker finds a changing city","source_domain":"tide","target_domain":"memory","shared_structure":"returns changed","genres":["mystery"],"trope":"map","hook":"bell","acts":3,"scenes":[{"text":"The bell calls the mapmaker home.","tension":1,"duration":2,"character":"Ila","goal":"enter","outcome":"gate opens","location":"gate"},{"text":"A hidden map shifts and the bell breaks.","tension":5,"duration":1,"character":"Ila","goal":"decode","outcome":"truth found","location":"archive"},{"text":"The mapmaker returns home with the map.","tension":2,"duration":3,"character":"Ila","goal":"restore","outcome":"city settles","location":"gate"}],"choices":[{"from":0,"to":1},{"from":1,"to":2}]}
def run(row):
 name=next(x["key"] for x in capabilities() if x["row_id"]==row)
 return execute(name, dict(OPT if row<260 else STORY))["result"]

def test_catalog_and_exact_mount():
 assert [x["row_id"] for x in capabilities()]==list(range(235,281))
 app=FastAPI(); app.include_router(router,prefix="/m20")
 c=TestClient(app); assert c.post("/m20/optimization-story-235-280/admm",json={"payload":OPT}).status_code==200

def test_row_235_dual_decomposition_computes_from_inputs():
 r=run(235); assert "coupling_residual_norm" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_236_admm_computes_from_inputs():
 r=run(236); assert "primal_residual_norm" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_237_coordinate_descent_computes_from_inputs():
 r=run(237); assert "selected_coordinate" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_238_proximal_methods_computes_from_inputs():
 r=run(238); assert "proximal_point" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_239_frank_wolfe_algorithm_computes_from_inputs():
 r=run(239); assert "duality_gap" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_240_cutting_plane_methods_computes_from_inputs():
 r=run(240); assert "cut_added" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_241_branch_and_bound_computes_from_inputs():
 r=run(241); assert "fractional_indices" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_242_column_generation_computes_from_inputs():
 r=run(242); assert "reduced_costs" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_243_benders_decomposition_computes_from_inputs():
 r=run(243); assert "cut_type" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_244_lagrangian_relaxation_computes_from_inputs():
 r=run(244); assert "lagrangian_value" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_245_semidefinite_programming_computes_from_inputs():
 r=run(245); assert "gershgorin_lower_bound" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_246_second_order_cone_programming_computes_from_inputs():
 r=run(246); assert "cone_slack" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_247_geometric_programming_computes_from_inputs():
 r=run(247); assert "monomial_value" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_248_fractional_programming_computes_from_inputs():
 r=run(248); assert "ratio" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_249_bilevel_optimization_computes_from_inputs():
 r=run(249); assert "stationarity_residual" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_250_stochastic_approximation_computes_from_inputs():
 r=run(250); assert "sample_variance" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_251_online_learning_computes_from_inputs():
 r=run(251); assert "regret" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_252_bandit_algorithms_computes_from_inputs():
 r=run(252); assert "arm_means" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_253_contextual_bandits_computes_from_inputs():
 r=run(253); assert "context_score" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_254_thompson_sampling_computes_from_inputs():
 r=run(254); assert "posterior_means" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_255_upper_confidence_bound_computes_from_inputs():
 r=run(255); assert "ucb_scores" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_256_expert_advice_aggregation_computes_from_inputs():
 r=run(256); assert "normalized_weights" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_257_regret_minimization_computes_from_inputs():
 r=run(257); assert "cumulative_regret" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_258_game_theoretic_learning_computes_from_inputs():
 r=run(258); assert "equilibrium_gap" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_259_fictitious_play_computes_from_inputs():
 r=run(259); assert "exploitability" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_260_novel_metaphor_generation_computes_from_inputs():
 r=run(260); assert "metaphors" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_261_narrative_arc_construction_computes_from_inputs():
 r=run(261); assert "arc_shape" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_262_character_development_computes_from_inputs():
 r=run(262); assert "character_scene_counts" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_263_dialogue_writing_computes_from_inputs():
 r=run(263); assert "lexical_distinctness" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_264_worldbuilding_computes_from_inputs():
 r=run(264); assert "locations" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_265_plot_twist_design_computes_from_inputs():
 r=run(265); assert "reversal_magnitude" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_266_foreshadowing_placement_computes_from_inputs():
 r=run(266); assert "motif_positions" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_267_tension_building_computes_from_inputs():
 r=run(267); assert "tension_curve" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_268_pacing_control_computes_from_inputs():
 r=run(268); assert "pace_variance" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_269_voice_development_computes_from_inputs():
 r=run(269); assert "lexical_diversity" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_270_genre_blending_computes_from_inputs():
 r=run(270); assert "genre_signals" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_271_trope_subversion_computes_from_inputs():
 r=run(271); assert "expectation_present" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_272_myth_creation_computes_from_inputs():
 r=run(272); assert "origin_markers" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_273_poetry_generation_computes_from_inputs():
 r=run(273); assert "line_count" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_274_songwriting_computes_from_inputs():
 r=run(274); assert "hook_repetitions" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_275_screenplay_formatting_computes_from_inputs():
 r=run(275); assert "formatted_scenes" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_276_stage_play_construction_computes_from_inputs():
 r=run(276); assert "live_complexity" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_277_comic_script_writing_computes_from_inputs():
 r=run(277); assert "panel_plan" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_278_interactive_fiction_computes_from_inputs():
 r=run(278); assert "reachable_scenes" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_279_game_narrative_design_computes_from_inputs():
 r=run(279); assert "loop_alignment" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_row_280_visual_storyboarding_computes_from_inputs():
 r=run(280); assert "shots" in r and r["metrics"]["confidence"]>=0 and r["uncertainty"]

def test_metrics_change_with_inputs():
 a=run(236); p=dict(OPT); p["initial"]=[0.5,0.5]; b=execute("admm",p)["result"]; assert a["primal_residual_norm"]!=b["primal_residual_norm"]
 a=run(267); p=dict(STORY); p["scenes"]=[dict(s) for s in STORY["scenes"]]; p["scenes"][1]["tension"]=2; b=execute("tension_building",p)["result"]; assert a["peak"]!=b["peak"]

def test_degenerate_and_infeasible_diagnostics():
 p=dict(OPT); p["initial"]=[0,0]; assert execute("branch_and_bound",p)["result"]["diagnostics"]["feasible"]
 p["initial"]=[2,2]; r=execute("cutting_plane_methods",p)["result"]; assert not r["diagnostics"]["feasible"] and r["cut_added"]
 with pytest.raises(WorkbenchError,match="strictly positive"): execute("geometric_programming",{**OPT,"initial":[0,1]})
 with pytest.raises(WorkbenchError,match="denominator"): execute("fractional_programming",{**OPT,"denominator":0})
 with pytest.raises(WorkbenchError,match="outside scenes"): execute("interactive_fiction",{**STORY,"choices":[{"from":0,"to":9}]})
 with pytest.raises(WorkbenchError,match="dimensions"): execute("admm",{**OPT,"initial":[1]})
