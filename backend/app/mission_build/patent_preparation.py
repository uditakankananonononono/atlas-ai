"""Source-linked patent drafting packet, not filing clearance or legal novelty."""
import re
from urllib.parse import urlsplit


def _text(value, cap=50000):
    if type(value) is not str or not value.strip() or len(value)>cap:
        raise ValueError('bounded nonempty text required')
    return value.strip()


def prepare(payload):
    title = _text(payload.get('title'), 500)
    features = payload.get('features')
    arts = payload.get('prior_art')
    if type(features) is not list or not 1 <= len(features) <= 100 or type(arts) is not list or len(arts)>200:
        raise ValueError('1..100 features and <=200 prior art records')
    features = [_text(x,2000) for x in features]
    if len(set(features)) != len(features):raise ValueError('distinct features required')
    corpus = []
    ids = set()
    for art in arts:
        ident = _text(art.get('id'),120)
        if ident in ids:raise ValueError('duplicate prior-art id')
        ids.add(ident)
        url = urlsplit(_text(art.get('url'),2000))
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('HTTPS source required')
        content = _text(art.get('text'))
        normalized = ' '.join(re.findall(r'\w+', content.casefold()))
        matched = [f for f in features if ' '.join(re.findall(r'\w+',f.casefold())) in normalized]
        corpus.append({'id':ident,'url':art['url'],'matched_features':matched,
                       'coverage':len(matched)/len(features),'verified_retrieval':False})
    corpus.sort(key=lambda a:(-a['coverage'],a['id']))
    sections = payload.get('sections',{})
    if type(sections) is not dict:raise ValueError('sections object required')
    required = ('field','background','summary','drawing_descriptions','detailed_description','embodiments','industrial_applicability')
    unknown = set(sections)-set(required)
    if unknown:raise ValueError('unknown section')
    missing = [s for s in required if s not in sections or not sections[s]]
    accepted = {s:_text(v) for s,v in sections.items() if v}
    claim_basis = payload.get('claim_basis',{})
    if type(claim_basis) is not dict or set(claim_basis)-set(features):raise ValueError('claim_basis must map supplied features')
    basis = []
    for feature in features:
        quote = claim_basis.get(feature)
        verified = type(quote) is str and bool(quote.strip()) and quote in accepted.get('detailed_description','')
        basis.append({'feature':feature,'description_quote':quote,'quote_found_in_supplied_description':verified})
    abstract = payload.get('abstract')
    if abstract is not None:_text(abstract,10000)
    if not abstract:missing.append('abstract')
    elif len(abstract.split())>150:missing.append('abstract_over_150_words_review')
    if not arts:missing.append('prior_art_corpus')
    if any(not r['quote_found_in_supplied_description'] for r in basis):missing.append('unsupported_claim_features')
    packet = '# Patent drafting packet: '+title+'\n\nDRAFT NOT FOR FILING\n\n'
    if abstract:packet += '## Abstract\n'+abstract+'\n\n'
    for section,value in accepted.items():packet += '## '+section.replace('_',' ').title()+'\n'+value+'\n\n'
    claims = ['1. A '+title+' comprising '+ '; '.join(features)+'.']
    packet += '## Claims for review\n'+'\n'.join(claims)+'\n'
    return {'packet_markdown':packet,'claims':claims,'prior_art_comparison':corpus,'claim_basis':basis,
            'missing_or_review':missing,'sections_present':list(accepted),'filing_ready':False,
            'novelty_determined':False,'filing_performed':False,
            'mandatory_review':['inventorship and ownership','jurisdiction formalities','prior-art search completeness',
                                'enablement and claim scope','legal novelty and inventive step'],
            'scope':'Text packet and literal supplied-corpus comparison only; no live search, legal opinion, or filing.'}
