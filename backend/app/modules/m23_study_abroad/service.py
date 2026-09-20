"""Study Abroad core: identity, coaching-only narrative, contextual fit."""
from collections import Counter
from .schemas import *
class Service:
 def identity_vector(self,p:StudentProfileIn):
  terms=[]
  for x in [*p.values,*p.turning_points,*p.strengths,*p.goals]:terms.extend(w.lower() for w in x.split() if len(w)>3)
  patterns=[x for x,n in Counter(terms).most_common(12)]
  return {'values':p.values,'strengths':p.strengths,'patterns':patterns,'academics':p.academics,'finances':p.finances,'goals':p.goals,'source':'student_supplied'}
 def coach_essay(self,x:EssayCoachingIn):
  draft=x.student_draft
  clichés=[c for c in ('since i was young','dream come true','passion for helping people','changed my life') if c in draft.lower()]
  return EssayCoachingOut(questions=['Which concrete moment best demonstrates this claim?','What changed in your thinking or behavior?','What detail could only come from your experience?'],outline_feedback=['Name the central value in one sentence.','Anchor each paragraph in a student-supplied scene.','Connect reflection to the application prompt.'],critique={'structure':'Check that each paragraph advances one idea.','admissions_view':'Make contribution and fit specific without guessing selection logic.','authenticity':'Keep only claims supported by student evidence.','cliches':', '.join(clichés) if clichés else 'No common cliché phrase detected.'},final_prose=None)
 def fit(self,profile,universities):
  goal=' '.join(profile.goals).lower();out=[]
  for u in universities:
   program_match=max([1 if p.lower() in goal or any(w in p.lower() for w in goal.split()) else 0 for p in u.programs] or [0]);afford=1 if u.annual_tuition_usd is not None and profile.finances.get('annual_budget_usd',0)>=u.annual_tuition_usd else 0
   score=round(.65*program_match+.35*afford,3);band='target' if score>=.65 else 'reach'
   out.append({'university_id':u.id,'name':u.name,'country':u.country,'score':score,'band':band,'official_url':u.official_url,'evidence':{'program_match':program_match,'budget_fit':afford}})
  return sorted(out,key=lambda x:x['score'],reverse=True)
