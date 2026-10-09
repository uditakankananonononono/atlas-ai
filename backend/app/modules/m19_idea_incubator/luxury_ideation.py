"""Evidence-driven idea generation for a luxury brand brief.

Ideas are derived from the brief's own signals and sources, not from a fixed
list. A lever (a reusable value mechanism) is proposed only when the supplied
evidence matches it; the idea quotes the evidence it came from, so two brands
with different evidence get different ideas. Lever pairs are also combined.
No model call is made. Scores are reproducible heuristics, not market facts.
Limit: matching is lexical, so synonyms outside the lever vocabulary are missed.
"""
from __future__ import annotations
import re
from itertools import combinations
from .luxury_venture import VentureBrief

# lever -> (keywords that evidence must contain, mechanism template, capability words it needs, sectors)
LEVERS: dict[str, dict] = {
 "provenance": {"kw": {"craft","heritage","provenance","origin","handmade","artisan","atelier","archive","authentic","counterfeit","resale"},
   "mechanism": "verifiable item or experience history that {brand} customers can inspect and transfer", "needs": {"records","catalog","database","data","ledger"}},
 "ownership_care": {"kw": {"servicing","maintenance","ownership","warranty","repair","restoration","aftercare","owner","owners","dealer","clubs"},
   "mechanism": "owner lifecycle care that anticipates service needs for {brand} owners", "needs": {"service","telemetry","crm","data","scheduling"}},
 "personalization": {"kw": {"personal","bespoke","custom","tailor","preferences","concierge","private","loyalty","returning","guest"},
   "mechanism": "consent-based personalization that explains each recommendation to the {brand} customer", "needs": {"crm","preferences","data","profiles","consent"}},
 "scarcity_access": {"kw": {"limited","waitlist","allocation","allocations","exclusive","edition","drop","queue","demand","sold","collector"},
   "mechanism": "transparent, fair allocation of limited {brand} offerings with an auditable queue", "needs": {"queue","inventory","identity","scheduling"}},
 "sustainability_proof": {"kw": {"sustainable","sustainability","emissions","recycled","traceability","esg","carbon","responsible","circular"},
   "mechanism": "customer-visible proof of sustainability claims for {brand} products", "needs": {"supply","records","data","reporting"}},
 "digital_world": {"kw": {"game","virtual","metaverse","fans","character","licensing","collab","collaboration","kids","merchandise","entertainment"},
   "mechanism": "fan-facing digital extension of the {brand} world with safe licensing hooks", "needs": {"content","design","engineering","platform"}},
 "operations_quality": {"kw": {"staff","staffing","shortages","understaffed","operations","occupancy","reviews","complaints","labor","yield"},
   "mechanism": "operations decision support that surfaces service gaps early for {brand}", "needs": {"operations","reviews","data","analytics"}},
 "pricing_demand": {"kw": {"price","pricing","margin","revenue","demand","inflation","tariff","discount","growth","decline","slowdown"},
   "mechanism": "demand and price-sensitivity monitor tuned to {brand}'s published results", "needs": {"analytics","data","finance","forecast"}},
}
_WORD = re.compile(r"[a-z][a-z\-']+")

def tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))

def _match(brief: VentureBrief) -> dict[str, list[dict]]:
    src = {s.source_id: s for s in brief.sources}
    out: dict[str, list[dict]] = {}
    for sig in brief.signals:
        toks = tokens(sig.statement)
        for sid in sig.source_ids:
            if sid in src: toks |= tokens(src[sid].finding)
        for name, lever in LEVERS.items():
            hit = toks & lever["kw"]
            if hit:
                out.setdefault(name, []).append({"signal_id": sig.signal_id, "importance": sig.importance,
                    "matched_terms": sorted(hit), "statement": sig.statement, "source_ids": sig.source_ids})
    return out

def _readiness(brief: VentureBrief, needs: set[str]) -> tuple[float, list[str]]:
    hits = [(c.capability_id, c.readiness) for c in brief.capabilities if tokens(c.description) & needs]
    if not hits: return 0.0, []
    return round(sum(r for _, r in hits) / len(hits), 3), [c for c, _ in hits]

def generate_ideas(brief: VentureBrief, max_ideas: int = 8) -> dict:
    """Return evidence-cited ideas plus an explicit coverage report."""
    if max_ideas < 1: raise ValueError("max_ideas must be positive")
    matches = _match(brief)
    ideas = []
    def make(key: str, parts: list[str]) -> dict:
        ev = [e for p in parts for e in matches[p]]
        strength = sum(e["importance"] * len(e["matched_terms"]) for e in ev)
        needs = set().union(*(LEVERS[p]["needs"] for p in parts))
        ready, cap_refs = _readiness(brief, needs)
        mech = " combined with ".join(LEVERS[p]["mechanism"].format(brand=brief.brand_or_segment) for p in parts)
        return {"idea_id": key, "levers": parts, "mechanism": mech,
                "customer_job": brief.customer_job,
                "evidence": [{"signal_id": e["signal_id"], "source_ids": e["source_ids"], "matched_terms": e["matched_terms"],
                              "quote": e["statement"]} for e in ev],
                "capability_refs": cap_refs, "capability_readiness": ready,
                "scores": {"evidence_strength": round(strength, 3), "readiness": ready,
                           "combination_bonus": 0.15 if len(parts) > 1 else 0.0}}
    for p in matches: ideas.append(make(p, [p]))
    for a, b in combinations(sorted(matches), 2): ideas.append(make(a + "+" + b, [a, b]))
    for i in ideas:
        s = i["scores"]; s["total"] = round(s["evidence_strength"] * (0.5 + 0.5 * s["readiness"]) * (1 + s["combination_bonus"]), 3)
    ideas.sort(key=lambda x: (-x["scores"]["total"], x["idea_id"]))
    unmatched = [s.signal_id for s in brief.signals if not any(e["signal_id"] == s.signal_id for v in matches.values() for e in v)]
    return {"brand_or_segment": brief.brand_or_segment, "ideas": ideas[:max_ideas],
            "levers_matched": sorted(matches), "unmatched_signals": unmatched,
            "coverage_note": "no idea generated for signals outside the lever vocabulary" if unmatched else "all signals matched at least one lever",
            "limits": ["lexical matching only", "scores are heuristics, not market facts", "no brand validation"]}
