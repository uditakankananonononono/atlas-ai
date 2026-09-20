from app.modules.m04_research_scientist.lane_api import ExperimentPlan, Paper, execute_experiment, render_manuscript


def test_manuscript_links_evidence_and_run():
    paper = Paper("p1", "Title", authors=("Ada",), doi="10.1/x")
    result = execute_experiment(ExperimentPlan("e1", "h", "effect", {}, 7, "mean", "commit"),
                                lambda params, seed: {"effect": 1.5, "sample_size": 4})
    manuscript = render_manuscript("Report", [paper], [result])
    assert "[p1] Ada. Title. https://doi.org/10.1/x" in manuscript.markdown
    assert result.manifest.run_id in manuscript.markdown
    assert manuscript.cited_paper_ids == ("p1",)
