"""Evidence-first opportunity ranking, research briefs and content draft scaffolds."""
from __future__ import annotations
import math, re
from datetime import datetime, timezone
from typing import Any, Sequence


def _tokens(value: Any) -> set[str]:
    return set(w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}",str(value or "")))


def _overlap(a:set[str],b:set[str]) -> float:
    return len(a&b)/len(a|b) if a|b else 0.0


def rank_opportunities(opportunities: Sequence[dict[str,Any]], profile: dict[str,Any], *, limit:int=50) -> dict[str,Any]:
    """Rank source-provided opportunities with transparent weights and eligibility states.

    An omitted eligibility field is UNKNOWN, never assumed eligible. This function does
    not discover listings by itself and does not claim source facts have been verified.
    """
    if not 1<=limit<=200: raise ValueError("limit must be in [1,200]")
    interests={str(x).lower() for x in profile.get("interests",[]) if str(x).strip()}
    countries={str(x).lower() for x in profile.get("countries",[]) if str(x).strip()}
    funding_priority=bool(profile.get("prioritize_funding",False))
    age=profile.get("age")
    results=[]
    now=datetime.now(timezone.utc)
    for item in opportunities:
        title=str(item.get("title","")).strip()
        url=str(item.get("official_url","")).strip()
        if not title or not url.startswith("https://"):
            continue
        item_domains=[str(x).lower() for x in item.get("domains",[]) if str(x).strip()]
        interest_score=max([_overlap(_tokens(i),_tokens(" ".join(item_domains+[str(item.get("title","")),str(item.get("description",""))]))) for i in interests] or [0.0])
        eligible="unknown"; reasons=[]; missing=[]
        countries_item={str(x).lower() for x in item.get("eligible_countries",[])}
        if countries_item:
            if countries:
                eligible="eligible" if countries.intersection(countries_item) else "ineligible"
                if eligible=="eligible": reasons.append("country eligibility matches supplied listing")
                else: reasons.append("supplied country eligibility does not match profile")
            else:
                missing.append("profile countries")
        else: missing.append("eligible_countries")
        if age is not None:
            lo=item.get("age_min"); hi=item.get("age_max")
            if lo is not None and age < lo: eligible="ineligible"; reasons.append("age below supplied minimum")
            elif hi is not None and age > hi: eligible="ineligible"; reasons.append("age above supplied maximum")
            elif lo is not None or hi is not None:
                if eligible!="ineligible": eligible="eligible" if eligible!="unknown" else "unknown"
                reasons.append("age range does not conflict with supplied bounds")
            else: missing.append("age_min/age_max")
        else: missing.append("user age (only if needed for eligibility)")
        funding=bool(item.get("full_funding",False) or item.get("funding_available",False))
        funding_score=1.0 if funding else (0.5 if item.get("funding") else 0.0)
        if funding and funding_priority: reasons.append("funding matches stated priority")
        try:
            deadline=datetime.fromisoformat(str(item["deadline"]).replace("Z","+00:00")) if item.get("deadline") else None
            if deadline and deadline.tzinfo is None: deadline=deadline.replace(tzinfo=timezone.utc)
        except Exception: deadline=None
        if deadline:
            days=(deadline.astimezone(timezone.utc)-now).total_seconds()/86400
            deadline_score=1.0 if days>=0 else 0.0
            if days<0: reasons.append("listed deadline appears to have passed; verify the page")
            else: reasons.append("listing provides a future deadline")
        else: deadline_score=.5; missing.append("deadline")
        try: source_score=max(0.0,min(1.0,float(item.get("source_reliability",.5))))
        except (TypeError,ValueError): source_score=.5
        fit_score=0.0 if eligible=="ineligible" else .5 if eligible=="unknown" else 1.0
        # Funding preference only changes weight distribution, never eligibility.
        weights={"interest":.35,"eligibility":.25,"funding":.15 if funding_priority else .08,"deadline":.12,"source":.13 if funding_priority else .20}
        score=(weights["interest"]*interest_score+weights["eligibility"]*fit_score+weights["funding"]*funding_score+
               weights["deadline"]*deadline_score+weights["source"]*source_score)
        if eligible=="ineligible": score*=.15
        results.append({"id":str(item.get("id") or item.get("official_url")),"title":title,"official_url":url,
                        "score":round(score,5),"eligibility":"not_eligible_on_supplied_fields" if eligible=="ineligible" else ("likely_matches_known_fields" if eligible=="eligible" else "unknown_verify_before_applying"),
                        "interest_match":round(interest_score,4),"funding_match":round(funding_score,4),"deadline_score":round(deadline_score,4),
                        "source_reliability":source_score,"reasons":reasons,"missing_information":sorted(set(missing)),
                        "source_evidence":item.get("evidence",[]),"human_verification_required":True})
    results.sort(key=lambda x:(x["score"],x["eligibility"]=="likely_matches_known_fields"),reverse=True)
    return {"count":len(results),"items":results[:limit],"scoring":{"interest":.35,"eligibility":.25,"funding":.08 if not funding_priority else .15,
            "deadline":.12,"source":.20 if not funding_priority else .13},
            "warning":"Scores order supplied listings; they do not verify eligibility, deadlines, program quality, or selection probability."}


def research_dossier(topic: str, sources: Sequence[dict[str,Any]], *, max_sources:int=30) -> dict[str,Any]:
    """Make an evidence inventory without synthesizing unsupported claims."""
    if not topic.strip(): raise ValueError("topic required")
    chosen=[]; seen=set()
    topic_tokens=_tokens(topic)
    ranked=sorted(sources,key=lambda s:_overlap(topic_tokens,_tokens(str(s.get("title",""))+" "+str(s.get("summary","")))),reverse=True)
    for s in ranked:
        url=str(s.get("link",s.get("official_url",s.get("source_url",""))))
        title=str(s.get("title","")).strip()
        if not title or not url.startswith("https://") or url in seen: continue
        seen.add(url)
        chosen.append({"title":title,"url":url,"source_domain":s.get("source_domain","unknown"),
                       "summary_excerpt":str(s.get("summary",s.get("excerpt","")))[:1000],
                       "content_hash":s.get("content_hash"),"published_at":s.get("published_at"),
                       "relevance_overlap":round(_overlap(topic_tokens,_tokens(title+" "+str(s.get("summary","")))),4),
                       "claim_status":"source_excerpt_only_not_independently_verified"})
        if len(chosen)>=max(1,min(max_sources,100)): break
    return {"topic":topic,"source_count":len(chosen),"sources":chosen,
            "research_gaps":["Compare primary sources rather than relying only on summaries.",
                              "Check publication dates, methods, conflicts and independent replications.",
                              "Separate source claims from your own hypotheses and testable predictions."],
            "statement":"This dossier indexes sourced material; it does not independently establish the truth of the sources' claims."}


def draft_evidence_post(*, topic: str, audience: str, evidence: Sequence[dict[str,Any]],
                        voice: str="clear, curious, evidence-led", call_to_action: str="What evidence would change your mind?", max_sources:int=5) -> dict[str,Any]:
    """Create a source-linked draft scaffold; never auto-publish or invent findings."""
    if not topic.strip() or not audience.strip(): raise ValueError("topic and audience are required")
    dossier=research_dossier(topic,evidence,max_sources=max_sources)
    bullets=[]
    for s in dossier["sources"]:
        snippet=s["summary_excerpt"]
        bullets.append(f"- **{s['title']}** — {snippet if snippet else 'Read the linked source before stating a result.'} ([source]({s['url']}))")
    text=(f"# {topic}\n\nAudience: {audience}\nVoice: {voice}\n\n"
          "## Evidence to verify before publication\n"+("\n".join(bullets) if bullets else "- No qualifying HTTPS sources supplied. Do not make factual claims yet.")+
          f"\n\n## Draft framing\nA useful question about {topic.lower()} is what the available evidence establishes—and what remains uncertain. "
          "The sources above are starting points, not proof; I would compare their methods and look for independent replication before drawing a strong conclusion.\n\n"
          f"## Conversation prompt\n{call_to_action}")
    return {"draft":text,"status":"draft_requires_human_fact_check","publish_action":"not_performed",
            "source_count":dossier["source_count"],"unsupported_claim_policy":"No result, credential, achievement, or numerical claim is invented."}
