"""Deterministic funder-rule compliance checks for scientific proposals."""
from __future__ import annotations
import re
from typing import Any

def lint_proposal(*,proposal:str,guidelines:str,budget_total:float|None=None,attachments:list[str]|None=None)->dict[str,Any]:
 if not proposal.strip() or not guidelines.strip():raise ValueError('proposal and guidelines are required')
 attachments=attachments or [];issues=[];warnings=[];checks=[]
 def add(name,passed,evidence,severity='error'):
  checks.append({'check':name,'passed':passed,'evidence':evidence})
  if not passed:(issues if severity=='error' else warnings).append(evidence)
 # Explicit, machine-readable funder conventions, never guessed from vague prose.
 word_limits=[int(x) for x in re.findall(r'(?i)(?:maximum|max(?:imum)?|limit(?:ed)? to|no more than)\s+(\d{2,6})\s+words?',guidelines)]
 if word_limits:
  limit=min(word_limits);count=len(re.findall(r"\b[\w'-]+\b",proposal));add('word_limit',count<=limit,f'proposal has {count} words; limit is {limit}')
 else:add('word_limit',True,'no explicit word limit parsed from guidelines','warning')
 money=[float(x.replace(',','')) for x in re.findall(r'(?i)(?:maximum|max(?:imum)?|up to|not exceed)\s*(?:(?:USD|US)\s*)?\$\s*([\d,]+(?:\.\d+)?)',guidelines)]
 if money and budget_total is not None:add('budget_cap',budget_total<=min(money),f'budget {budget_total:.2f}; cap {min(money):.2f}')
 elif money:add('budget_cap',False,'guidelines state a budget cap but no budget_total was supplied')
 else:add('budget_cap',True,'no explicit monetary cap parsed','warning')
 required=[]
 for pattern in (r'(?i)required attachments?\s*[:\-]\s*([^\n.]+)',r'(?i)must include\s*[:\-]\s*([^\n.]+)'):
  for group in re.findall(pattern,guidelines):required += [x.strip().lower() for x in re.split(r',|;|\band\b',group) if x.strip()]
 missing=[x for x in required if not any(x in a.lower() or a.lower() in x for a in attachments)]
 add('required_attachments',not missing,'missing attachments: '+', '.join(missing) if missing else f'{len(required)} parsed attachment requirements satisfied')
 criteria=[]
 m=re.search(r'(?is)(?:evaluation|review|selection|scoring) criteria\s*[:\-]\s*(.+?)(?:\n\n|\Z)',guidelines)
 if m:criteria=[x.strip(' \t-*0123456789.') for x in re.split(r'\n|;',m.group(1)) if len(x.strip())>2]
 uncovered=[c for c in criteria if not any(w in proposal.lower() for w in re.findall(r'[a-z]{5,}',c.lower())[:3])]
 add('evaluation_criteria_coverage',not uncovered,'uncovered criteria: '+', '.join(uncovered) if uncovered else f'{len(criteria)} parsed criteria covered')
 needs=sorted(set(re.findall(r'\[NEEDS INPUT(?::[^\]]+)?\]',proposal,re.I)))
 add('unresolved_inputs',not needs,f'unresolved placeholders: {len(needs)}')
 return {'ready':not issues,'issues':issues,'warnings':warnings,'checks':checks,'unresolved_placeholders':needs,'boundary':'Deterministic preflight only; the applicant must verify the authoritative funder instructions.'}
