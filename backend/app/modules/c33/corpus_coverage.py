"""Inventory supplied category records with missing coverage and source hashes.

A supplied URL is provenance asserted by the caller, not a fetched or verified
post. No scraping, account operations, publishing or category completeness.
"""
import hashlib
from urllib.parse import urlsplit
from app.modules.c30 import policy
from app.modules.c33 import corpus

def coverage(posts:list, categories:list)->dict:
    if type(categories) is not list or not 1<=len(categories)<=100:
        raise ValueError('bounded categories required')
    clean=[policy.clean_text(c,'SOCIAL','category',128) for c in categories]
    if len(set(clean))!=len(clean):raise ValueError('duplicate category')
    if type(posts) is not list or not 1<=len(posts)<=corpus.MAX_POSTS:
        raise ValueError('bounded supplied posts required')
    groups={c:[] for c in clean};seen=set();receipts=[]
    for p in posts:
        if type(p) is not dict or set(p)!={'id','category','source_url','text','likes','shares'}:
            raise ValueError('explicit supplied record fields required')
        rid=policy.clean_text(p['id'],'SOCIAL','id',128)
        if rid in seen:raise ValueError('duplicate post id')
        seen.add(rid)
        category=policy.clean_text(p['category'],'SOCIAL','category',128)
        if category not in groups:raise ValueError('unlisted category')
        url=policy.clean_text(p['source_url'],'SOCIAL','source_url',2048)
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('public source URL required')
        text=policy.clean_text(p['text'],'SOCIAL','text',20000,allow_ws=True)
        # Existing corpus owns engagement validation and explicit cue-only scope.
        item={'id':rid,'text':text,'likes':p['likes'],'shares':p['shares']}
        corpus.analyze([item]);groups[category].append((item,url))
        receipts.append({'id':rid,'category':category,'source_url':url,
                         'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
                         'source_status':'caller-supplied, not fetched or verified'})
    result={}
    for c,items in groups.items():
        result[c]={'count':len(items),'source_count':len({u for _,u in items}),
                   'status':'supplied_records_only' if items else 'no_supplied_posts',
                   'analysis':corpus.analyze([p for p,_ in items]) if items else None}
    return {'categories':result,'posts':receipts,'represented_supplied_categories':sum(bool(v) for v in groups.values()),
            'complete_category_coverage':False,
            'scope':'Supplied records only; no platform collection, accounts or publishing.'}
