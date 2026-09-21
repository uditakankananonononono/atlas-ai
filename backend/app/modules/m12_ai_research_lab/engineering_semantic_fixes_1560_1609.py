"""Row-specific semantic evidence for engineering rows 1560-1609.

This layer closes the old family-level verification gap by composing the 50
named engineering analyses in engineering_support_1560_1609 (one named function
per owner row; no shared group dispatch). No label-only success: each row
validates the physical/design inputs that distinguish that capability and its
row-specific computed outputs are surfaced as the distinctive evidence.
"""
from __future__ import annotations
from typing import Any
from .engineering_support_1560_1609 import ANALYSES

def engineering_semantic_1560_1609(feature_id:int,data:dict[str,Any])->dict[str,Any]:
    analysis=ANALYSES.get(feature_id)
    if analysis is None:raise ValueError("feature_id must be 1560-1609")
    result=analysis(data)
    result["distinctive_output"]=result["analysis"]
    result["evaluation"]={"computed_outputs":sorted(result["analysis"]),"acceptance_criteria":data.get("acceptance_criteria",[]),"verification_plan":data.get("verification_plan",[]),"constraints":result["constraints"],"qualified_review_required":True}
    result["semantic_verification"]="row-specific-v1"
    return result
