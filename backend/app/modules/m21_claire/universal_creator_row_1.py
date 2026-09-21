"""Row 1: safe planning for cross-domain creations, applications, and tool discovery."""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse
ALLOWED_KINDS={"research_project","bioinformatics_project","computer_science_project","summer_program_application","competition_application","essay","debate","mun","olympiad","hackathon","tool_discovery"}
@dataclass(frozen=True)
class Candidate:
 name:str;url:str;requirements:tuple[str,...];preferences:tuple[str,...]=();source:str="official"
def _official_url(url):return urlparse(url).scheme=="https" and bool(urlparse(url).netloc)
def plan(goal:str,kind:str,candidates:list[dict],owner_facts:dict,requested_actions:list[str]|None=None)->dict:
 if kind not in ALLOWED_KINDS:raise ValueError("unsupported creation/application kind")
 if not goal.strip():raise ValueError("goal is required")
 if not isinstance(owner_facts,dict):raise ValueError("owner_facts must be a mapping")
 checked=[]
 for raw in candidates:
  c=Candidate(str(raw.get("name","")).strip(),str(raw.get("url","")).strip(),tuple(raw.get("requirements",[])),tuple(raw.get("preferences",[])),str(raw.get("source","official")))
  if not c.name or not _official_url(c.url):raise ValueError("each candidate needs a name and HTTPS source URL")
  missing=[x for x in c.requirements if x not in owner_facts or owner_facts[x] in (None,"")]
  fit=sum(1 for x in c.preferences if owner_facts.get(x) not in (None,""))/len(c.preferences) if c.preferences else 1
  evidence_known=sum(1 for x in c.requirements if x in owner_facts and owner_facts[x] not in (None,""))+sum(1 for x in c.preferences if owner_facts.get(x) not in (None,""))
  evidence_total=len(c.requirements)+len(c.preferences)
  fit_confidence=round(evidence_known/evidence_total,4) if evidence_total else .5
  checked.append({"name":c.name,"official_url":c.url,"source":c.source,"requirements":list(c.requirements),"missing_requirements":missing,"fit_score":fit,"fit_confidence":fit_confidence,"fit_uncertainty":"fit reflects only owner facts supplied; unreported facts can change eligibility and fit" if fit_confidence<1 else "all declared requirements and preferences matched against supplied owner facts","eligible_from_known_facts":not missing})
 checked.sort(key=lambda x:(x["eligible_from_known_facts"],x["fit_score"]),reverse=True)
 actions=requested_actions or []
 external=any(a in {"submit","sign_up","send","publish","pay"} for a in actions)
 artifact={"title":goal.strip(),"kind":kind,"sections":["objective","evidence_and_sources","requirements","work_plan","verification"]}
 if "application" in kind:artifact["sections"]=["program_fit","eligibility","authentic_activity_evidence","responses","review_checklist"]
 return {"feature_row":1,"artifact_blueprint":artifact,"ranked_candidates":checked,"tool_discovery":{"query":goal.strip(),"official_sources_only":True,"install_or_account_action_requires_approval":True},"result_seeking":{"fallbacks":["try another verified official source","prepare an offline draft","surface the blocker without fabricating completion"],"never_claim_success_without_receipt":True},"humanization":{"allowed":"improve factual clarity and natural owner voice","forbidden":["evade detection","conceal authorship","fabricate activities or credentials"]},"requested_actions":actions,"status":"exact_preview_required" if external else "draft_ready","requires_exact_preview_review":external,"execution_performed":False,"owner_facts_used":sorted(owner_facts)}
