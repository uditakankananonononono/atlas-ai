"""Structured source-stated product facts, exact spans and disagreement flags."""
import hashlib,re
from .teardown import teardown_sources

def analyze_product_evidence(brand,sources):
    # Reuse URL/text hygiene; no fetch, account creation or registration path.
    baseline=teardown_sources(brand,sources)
    ingredients=[];founders=[];affiliate=[]
    for page in sources:
        text=page['text'];url=page['url'];digest=hashlib.sha256(text.encode()).hexdigest()
        def provenance(match):return {'url':url,'start':match.start(),'end':match.end(),'quote':match.group(),'source_sha256':digest,'basis':'source-stated, not independently verified'}
        for match in re.finditer(r'\b(?:ingredients|composition|materials)\s*:\s*([^.!?\n]+)',text,re.I):
            parts=[p.strip() for p in re.split(r',|;',match[1]) if p.strip()]
            if len(parts)>200:raise ValueError('ingredient list exceeds 200 entries')
            if parts:ingredients.append({**provenance(match),'items':parts})
        for match in re.finditer(r'\bfounded\s+by\s+([A-Za-z][A-Za-z\s\-]{0,100}?)\s+in\s+(\d{4})\b',text,re.I):
            founders.append({**provenance(match),'name':match[1].strip(),'year':int(match[2])})
        for match in re.finditer(r'\b(?:affiliate\s+)?commission\s*:\s*(\d+(?:\.\d+)?)\s*%',text,re.I):
            value=float(match[1])
            if not 0<=value<=100:raise ValueError('commission percentage outside 0..100')
            affiliate.append({**provenance(match),'commission_percent':value,'currency':None,'payout_conditions_verified':False})
    conflicts=[]
    for field,records,key in [('founder',founders,lambda r:r['name'].casefold()),('founding_year',founders,lambda r:r['year']),('ingredient_list',ingredients,lambda r:tuple(v.casefold() for v in r['items']))]:
        variants={}
        for record in records:variants.setdefault(key(record),[]).append(record['url'])
        if len(variants)>1:conflicts.append({'field':field,'variants':[{'value':value,'source_urls':sorted(set(urls))} for value,urls in variants.items()],'resolution':'unresolved supplied-source disagreement'})
    return {**baseline,'ingredients':ingredients,'founders':founders,'affiliate_terms':affiliate,'conflicts':conflicts,'ingredient_safety_assessed':False,'external_actions':[],
            'limits':'Delimited ingredient labels, explicit founded-by-in-year phrasing and numeric commission text only. Regex extraction may miss or misread context. Disagreements may reflect different products or updated formulas, not factual errors. No chemical safety, legal affiliate eligibility, enrollment or business-success inference.'}
