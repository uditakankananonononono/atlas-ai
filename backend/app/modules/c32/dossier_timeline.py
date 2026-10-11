"""S2.7 additive supplied-source lexical dossier, no effects or retrieval."""
from __future__ import annotations
import calendar
import hashlib
import re
from datetime import date
from app.modules.c30 import policy
from .dossier import DIMENSIONS, MAX_SOURCES, MAX_FACTS_PER_DIM

PREFIX='TREND'
TRIGGERS=('founded','born','joined','launched')
MONTHS={name.casefold():i for i,name in enumerate(calendar.month_name) if name}
MONTHS.update({name.casefold():i for i,name in enumerate(calendar.month_abbr) if name})
MONTH_PATTERN='|'.join(sorted(MONTHS,key=lambda x:-len(x)))
DATE_RE=re.compile(r'(?<!\w)(\d{4}-\d{2}-\d{2}|(?:'+MONTH_PATTERN+r')\s+\d{4}|\d{4})(?!\w)',re.I)


def _refuse(reason):raise ValueError('TREND_REFUSED_'+reason)
def _norm(text):
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in text.casefold()).split())
def _mention(text,name):
    return (' '+_norm(name)+' ') in (' '+_norm(text)+' ')
def _sentences(text):
    # Preserve single-letter initials in aliases, but split other sentence stops.
    out=[];start=0
    for match in re.finditer(r'[.!?](?=\s|$)',text):
        if match.group()=='.' and re.search(r'(?:^|\s)[A-Za-z]$',text[start:match.start()]):continue
        value=text[start:match.end()].strip()
        if value:out.append(value)
        start=match.end()
    if text[start:].strip():out.append(text[start:].strip())
    return out

def _dates(text):
    result=[]
    for match in DATE_RE.finditer(text):
        token=match.group().casefold()
        try:
            if '-' in token:
                dt=date.fromisoformat(token);value=dt.isoformat();precision='day'
            elif ' ' in token:
                month,year=token.split();dt=date(int(year),MONTHS[month],1)
                value=f'{dt.year:04d}-{dt.month:02d}';precision='month'
            else:
                dt=date(int(token),1,1);value=f'{dt.year:04d}';precision='year'
        except ValueError:continue
        if (value,precision) not in [(x['date'],x['precision']) for x in result]:
            result.append({'date':value,'precision':precision,'year':dt.year})
    return result


def dossier_v2(request):
    if type(request) is not dict or set(request)-{'subject','aliases','known_entities','sources','include_private','as_of'}:
        _refuse('BAD_TYPE:request')
    private=request.get('include_private',False)
    if type(private) is not bool:_refuse('BAD_TYPE:include_private')
    if private:_refuse('PRIVATE')
    subject=policy.clean_text(request.get('subject'),PREFIX,'subject',128)
    aliases=request.get('aliases',[])
    if type(aliases) is not list or len(aliases)>16:_refuse('ALIAS')
    names=[subject]
    for alias in aliases:
        try:alias=policy.clean_text(alias,PREFIX,'alias',128)
        except ValueError:_refuse('ALIAS')
        if not _norm(alias):_refuse('ALIAS')
        if alias not in names:names.append(alias)
    if not _norm(subject):_refuse('EMPTY:subject')
    entities=request.get('known_entities',[])
    if type(entities) is not list or len(entities)>128:_refuse('BAD_TYPE:known_entities')
    checked=[]
    for entity in entities:
        if type(entity) is not dict or set(entity)!={'name','kind'} or entity['kind'] not in ('venture','person','event'):
            _refuse('BAD_TYPE:known_entity')
        name=policy.clean_text(entity['name'],PREFIX,'entity',128)
        if not _norm(name):_refuse('EMPTY:entity')
        if {'name':name,'kind':entity['kind']} not in checked:checked.append({'name':name,'kind':entity['kind']})
    sources=request.get('sources')
    if type(sources) not in (list,tuple):_refuse('BAD_TYPE:sources')
    if not sources:_refuse('EMPTY:sources')
    if len(sources)>MAX_SOURCES:_refuse('OVERSIZE')
    as_of=policy.clean_text(request.get('as_of','supplied-input'),PREFIX,'as_of',128)
    facts={};ambiguous=[];undated=[]
    tokens=_norm(subject).split()
    for source_index,source in enumerate(sources):
        if type(source) is not dict or set(source)-{'url','text','published'}:_refuse('BAD_TYPE:source')
        url=policy.clean_text(source.get('url'),PREFIX,'url',512)
        text=policy.clean_text(source.get('text'),PREFIX,'text',200000)
        published=source.get('published')
        if published is not None:policy.clean_text(published,PREFIX,'published',64)
        for sentence_index,sentence in enumerate(_sentences(text)):
            if not any(_mention(sentence,name) for name in names):
                if any(_mention(sentence,t) for t in tokens):
                    ambiguous.append({'sentence':sentence,'source':url,'reason':'partial-subject-token'})
                continue
            key=_norm(sentence)
            if key not in facts:
                facts[key]={'fact_id':hashlib.sha256(key.encode()).hexdigest(),'fact':sentence,'source':url,
                            'corroborating_sources':{'count':0,'urls':[]},'_order':(source_index,sentence_index),
                            '_dates':_dates(sentence)}
            fact=facts[key]
            if url not in fact['corroborating_sources']['urls']:
                fact['corroborating_sources']['urls'].append(url)
                fact['corroborating_sources']['count']+=1
    ranked=sorted(facts.values(),key=lambda f:(-f['corroborating_sources']['count'],f['_order']))
    def public(f):return {k:v for k,v in f.items() if not k.startswith('_')}
    dimensions={};depth={};truncated=0
    for dimension,keywords in DIMENSIONS.items():
        matched=[f for f in ranked if any(k in f['fact'].casefold() for k in keywords)]
        retained=matched[:MAX_FACTS_PER_DIM]
        truncated+=len(matched)-len(retained)
        if retained:dimensions[dimension]=[public(f) for f in retained]
        depth[dimension]={'fact_count':len(retained),
                          'corroborating_source_counts':[f['corroborating_sources']['count'] for f in retained],
                          'distinct_source_count':len({url for f in retained for url in f['corroborating_sources']['urls']})}
    timeline=[]
    ordered=sorted(facts.values(),key=lambda f:f['_order'])
    for f in ordered:
        if not f['_dates']:
            undated.append({'sentence':f['fact'],'source':f['source'],'fact_id':f['fact_id'],
                            'corroborating_sources':f['corroborating_sources']})
        for stamp in f['_dates']:
            timeline.append({'date':stamp['date'],'precision':stamp['precision'],'sentence':f['fact'],
                             'source':f['source'],'fact_id':f['fact_id'],'corroborating_sources':f['corroborating_sources']})
    timeline.sort(key=lambda e:(e['date'],e['fact_id']))
    conflicts=[]
    for trigger in TRIGGERS:
        candidates=[f for f in ordered if re.search(r'\b'+trigger+r'\b',f['fact'],re.I) and f['_dates']]
        years=sorted({stamp['year'] for f in candidates for stamp in f['_dates']})
        if len(years)>1 and len(candidates)>1:
            conflicts.append({'trigger':trigger,'years':years,'status':'unresolved',
                              'facts':[public(f) for f in candidates],
                              'basis':'Potential lexical year conflict; dates may describe separate events.'})
    entity_links=[]
    for entity in checked:
        matches=[f for f in ordered if _mention(f['fact'],entity['name'])]
        if matches:entity_links.append({**entity,'fact_ids':[f['fact_id'] for f in matches],
                                       'source_urls':list(dict.fromkeys(url for f in matches for url in f['corroborating_sources']['urls']))})
    covered=len(dimensions)
    return {'subject':subject,'dimensions':dimensions,'completeness':round(covered/len(DIMENSIONS),6),
            'dimensions_covered':covered,'dimension_count':len(DIMENSIONS),
            'citation_count':sum(len(v) for v in dimensions.values()),'source_count':len(sources),
            'timeline':timeline,'undated_sentences':undated,'ambiguous_mentions':ambiguous,
            'ambiguous_mention_count':len(ambiguous),'conflicts':conflicts,'entity_links':entity_links,
            'evidence_depth':depth,'unique_matched_sentence_count':len(facts),'truncated_fact_count':truncated,
            'scope':policy.scope(['supplied cited facts with strict names and aliases','lexical timeline',
                                  'normalized dedupe and distinct supplied URL corroboration','unresolved year conflicts',
                                  'supplied entity links','dimension coverage and evidence depth'],
                                 ['fetching','private facts','verified public status','verified source truth',
                                  'every-single-thing coverage','semantic contradiction resolution','source independence verification'],
                                 'supplied public-source declarations',as_of)}


def run(request:dict)->dict:return dossier_v2(request)
