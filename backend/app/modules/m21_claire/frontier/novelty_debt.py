from __future__ import annotations
from typing import Any
import re


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}",text.casefold()) if t not in {"with","from","that","this","into","for","the","and","are","can"}}

def _jaccard(a: set[str],b: set[str]) -> float:
    return len(a&b)/len(a|b) if a|b else 0.0

class NoveltyDebtLedger:
    """Requires an idea to pay prior-art, mechanism, and execution-evidence debt.

    A low similarity score means only 'not similar to this provided corpus'; it never
    establishes global originality or an unprecedented invention.
    """
    def assess(self, idea: dict[str,Any], prior_art: list[dict[str,Any]], *,
               prior_art_review: dict[str,Any] | None=None,
               mechanism_test: dict[str,Any] | None=None,
               execution_test: dict[str,Any] | None=None) -> dict[str,Any]:
        title=str(idea.get("title","")).strip(); problem=str(idea.get("problem","")).strip(); mechanism=str(idea.get("mechanism","")).strip()
        if not title or not problem or not mechanism: raise ValueError("idea requires title, problem, and mechanism")
        if len(prior_art)>1000: raise ValueError("maximum 1000 prior-art records per assessment")
        keytext=title+" "+problem+" "+mechanism; kt=_tokens(keytext); matches=[]
        for source in prior_art:
            text=str(source.get("title", ""))+" "+str(source.get("abstract", ""))+" "+str(source.get("summary", ""))
            overlap=_jaccard(kt,_tokens(text))
            matches.append({"source_id":source.get("source_id"),"url":source.get("url"),"title":source.get("title"),"textual_overlap":round(overlap,4)})
        matches.sort(key=lambda x:(-x["textual_overlap"],str(x.get("source_id",""))))
        max_overlap=matches[0]["textual_overlap"] if matches else None
        prior_cleared=bool(prior_art_review and prior_art_review.get("reviewer_id") and prior_art_review.get("search_protocol") and prior_art_review.get("searched_sources"))
        mechanism_cleared=bool(mechanism_test and mechanism_test.get("preregistered") is True and mechanism_test.get("baseline") and mechanism_test.get("falsification_condition") and mechanism_test.get("result"))
        execution_cleared=bool(execution_test and execution_test.get("artifact_ref") and execution_test.get("independent_test_receipt") and execution_test.get("result"))
        debts={"prior_art":{"status":"paid_by_documented_review" if prior_cleared else "open","provided_corpus_size":len(prior_art),"maximum_textual_overlap":max_overlap,
                              "closest_matches":matches[:5],"meaning":"requires expert review across relevant sources; textual distance is not proof of originality"},
               "mechanism":{"status":"paid_by_preregistered_test" if mechanism_cleared else "open","meaning":"requires a falsifiable mechanism and recorded result"},
               "execution":{"status":"paid_by_artifact_and_independent_test" if execution_cleared else "open","meaning":"requires a real artifact and independent test receipt"}}
        cleared=all(d["status"].startswith("paid") for d in debts.values())
        return {"idea_id":str(idea.get("idea_id") or title.casefold().replace(" ","-")[:80]),"title":title,"debts":debts,
                "cleared_debt_count":sum(d["status"].startswith("paid") for d in debts.values()),"total_debts":3,
                "status":"evidence_complete_for_review" if cleared else "idea_hypothesis_with_open_debt",
                "permitted_claim":"candidate hypothesis; do not call it novel, validated, or a breakthrough until independent review supports that claim",
                "next_step":next((k for k,d in debts.items() if not d["status"].startswith("paid")),"independent replication and external review")}
