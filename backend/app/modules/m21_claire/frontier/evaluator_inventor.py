from __future__ import annotations
import hashlib
from typing import Any
from ._canon import canonical_json
from .representation_inventor import RepresentationInventor, TabularObservation

class EvaluationDimensionInventor:
    """Attempts to discover a missing *evaluation dimension* from past failures.

    Episodes are split by time/source before entry. The invented feature must improve
    failure prediction on validation and sealed confirmation data. Accepted outputs are
    candidates for shadow-mode evaluation, not self-awarded intelligence points.
    """
    def __init__(self, searcher: RepresentationInventor | None=None):
        self.searcher=searcher or RepresentationInventor()

    def invent(self, episodes: list[TabularObservation], *, min_validation_gain: float=0.05,
               min_confirmation_gain: float=0.03) -> dict[str,Any]:
        if any(not 0.0<=float(e.target)<=1.0 for e in episodes):
            raise ValueError("target must be a historical failure label/rate in [0,1]")
        result=self.searcher.search(episodes,min_validation_gain=min_validation_gain,min_confirmation_gain=min_confirmation_gain)
        if result["status"]!="representation_retained":
            return {"status":"no_evaluation_dimension_promoted","reason":"no candidate passed untouched confirmation",
                    "search_result":result,"self_awarded_score":False}
        repr_=result["retained_representation"]
        readout=repr_["train_fitted_readout"]
        dimension_id="evaldim-"+hashlib.sha256(canonical_json({"formula":repr_["formula"],"readout":readout}).encode()).hexdigest()[:16]
        return {"status":"candidate_dimension_created_for_shadow_evaluation","dimension_id":dimension_id,
            "name":"Historical failure-liability feature: "+repr_["formula"],"definition":repr_["formula"],
            "readout":readout,"predicted_target":"historical failure label/rate (uncalibrated score; do not display as probability)",
            "evidence":{"validation_gain":result["selected_on_validation"]["validation_gain"],
                "confirmation_gain":result["confirmation"]["relative_gain"],"confirmation_was_not_used_for_selection":True},
            "promotion_gates":["Freeze the formula and coefficients before prospective testing.",
                "Run in shadow mode on future tasks without changing agent incentives.",
                "Check calibration, subgroup performance, metric gaming and drift.",
                "Compare against existing metrics and ablate the new dimension.",
                "Require independent reviewer sign-off before using it in any policy."],
            "self_awarded_score":False,"status_meaning":"candidate metric only; not a new definition of intelligence until prospective utility is shown"}
