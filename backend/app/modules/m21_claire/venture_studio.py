"""Evidence-linked venture and content hypotheses from supplied signal records.

This is structured ideation, not a market-research substitute. It never claims a
market exists merely because keywords recur and never publishes content.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any, Sequence
from urllib.parse import urlparse

STOP = {"the","and","for","with","from","that","this","into","are","was","were","have","has","new","how","why","what","when","where","your","their","about","using","use","can","will","its","not","but","our","you","they","them","than","more","less","very","make","made","based","research","study","studies","method","methods","tool","tools"}

def _tokens(text: Any) -> list[str]:
    return [x.lower() for x in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", str(text or "")) if x.lower() not in STOP]

def _https(value: Any) -> bool:
    try:
        p=urlparse(str(value or "")); return p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
    except ValueError: return False

def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

def generate_venture_hypotheses(signals: Sequence[dict[str,Any]], profile: dict[str,Any] | None = None, *, limit: int = 30) -> dict[str,Any]:
    """Generate bounded, testable concept briefs grounded in supplied signals."""
    if not 1 <= limit <= 200: raise ValueError("limit must be in [1, 200]")
    profile = profile or {}
    if not isinstance(profile, dict): raise ValueError("profile must be an object")
    valid=[]; term_docs=Counter(); source_refs={}
    for i,s in enumerate(signals[:2000]):
        if not isinstance(s,dict): continue
        title=str(s.get("title","")).strip(); summary=str(s.get("summary",s.get("description",""))).strip()
        url=str(s.get("link",s.get("official_url",""))).strip()
        tokens=set(_tokens(title+" "+summary))
        if not title or not _https(url): continue
        row={"id":str(s.get("id") or s.get("content_hash") or _hash([title,url])[:16]),"title":title,"url":url,
             "source_domain":str(s.get("source_domain") or urlparse(url).hostname),"tokens":tokens}
        valid.append(row)
        for t in sorted(tokens): term_docs[t]+=1; source_refs.setdefault(t,[]).append(row)
    sectors=[str(x).strip() for x in profile.get("sectors",[]) if str(x).strip()][:40]
    interests=[str(x).strip() for x in profile.get("interests",[]) if str(x).strip()][:40]
    audiences=[str(x).strip() for x in profile.get("audiences",[]) if str(x).strip()][:20] or ["students and early practitioners"]
    constraints=[str(x).strip() for x in profile.get("constraints",[]) if str(x).strip()][:30] or ["low-cost prototype", "use public or permissioned data"]
    if not sectors: sectors = interests or ["digital services", "education", "research workflows"]
    ranked_terms=[t for t,n in sorted(term_docs.items(),key=lambda kv:(-kv[1],kv[0]))[:60] if n>=1]
    if not ranked_terms: ranked_terms=["workflow gap"]
    out=[]; seen=set()
    for sector in sectors:
        for term in ranked_terms:
            refs=source_refs.get(term,[])
            if not refs: continue
            best=refs[:5]
            idea={
                "title": f"{sector.title()} {term.replace('-', ' ').title()} Explorer",
                "sector": sector,
                "signal_pattern": term,
                "audience_hypothesis": audiences[(len(out)) % len(audiences)],
                "problem_hypothesis": f"People working in {sector} may need a clearer way to evaluate or act on the recurring theme '{term}'.",
                "solution_hypothesis": f"Prototype a narrow tool that organizes evidence about '{term}' for {sector}, exposes source provenance, and helps the target user complete one measurable workflow.",
                "why_this_is_only_a_hypothesis": "Keyword recurrence is a discovery cue, not proof of demand, trend growth, willingness to pay, or causality.",
                "evidence": [{"title":r["title"],"url":r["url"],"source_domain":r["source_domain"],"signal_id":r["id"]} for r in best],
                "source_count": len(refs), "distinct_source_domains": len({r["source_domain"] for r in refs}),
                "prototype_scope": ["one user group", "one workflow", "one measurable outcome", *constraints[:3]],
                "validation_plan": [
                    "Interview 5-10 target users without pitching the solution first.",
                    "Write down the current workaround and measure its time/cost/error rate.",
                    "Build the smallest clickable or scripted prototype.",
                    "Compare task completion against the current workflow on held-out users.",
                    "Abandon or revise the idea if independent users show no meaningful pain or measurable improvement."
                ],
                "primary_metric": "task completion time or error rate against a predeclared baseline",
                "disconfirming_evidence": "Target users do not report the problem or the prototype fails to beat the baseline.",
                "status": "unvalidated_hypothesis",
                "creation_mode": "rule-based synthesis from supplied public-source records; no model training occurred",
            }
            key=_hash([idea["sector"],idea["signal_pattern"],idea["audience_hypothesis"]])
            if key in seen: continue
            seen.add(key); idea["id"]=key[:20]; idea["evidence_hash"]=_hash(idea["evidence"]); out.append(idea)
            if len(out)>=limit: break
        if len(out)>=limit: break
    return {"count":len(out),"items":out,"input_signal_count":len(valid),
            "unrepresented_signal_count":max(0,len(signals)-len(valid)),
            "limits":["Only supplied signals were analyzed; this does not scan all internet content.",
                      "No market demand, originality, legal clearance, safety, or business success was established.",
                      "A human must validate the need before investment, outreach, or launch."],
            "generation_hash":_hash([out,[r["id"] for r in valid]])}

def build_content_calendar(signals: Sequence[dict[str,Any]], *, audience: str, voice: str="curious, specific, evidence-led", items: int=14) -> dict[str,Any]:
    """Build a source-attributed content plan; drafts are not published."""
    if not audience.strip(): raise ValueError("audience is required")
    if not 1<=items<=60: raise ValueError("items must be in [1, 60]")
    valid=[]; seen=set()
    for s in signals:
        if not isinstance(s,dict): continue
        title=str(s.get("title","")).strip(); url=str(s.get("link",s.get("official_url",""))).strip()
        if not title or not _https(url) or url in seen: continue
        seen.add(url); valid.append((title,url,str(s.get("summary",s.get("description",""))).strip()))
    rows=[]
    for i,(title,url,summary) in enumerate(valid[:items]):
        rows.append({"slot":i+1,"working_title":f"What {title} does—and what it does not show",
                     "audience":audience,"voice":voice,"source":{"title":title,"url":url,"excerpt":summary[:600]},
                     "structure":["state the question", "summarize only what the source supports", "state limitations and missing evidence", "ask a useful question"],
                     "status":"outline_only_not_published"})
    return {"items":rows,"count":len(rows),"publish_action":"not_performed",
            "warning":"A source-linked outline is not a verified factual post. Check source context, rights, and accuracy before publication."}
