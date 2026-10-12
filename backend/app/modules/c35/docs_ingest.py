"""S4.2 supplied bookmark/waiver Doc exports. No retrieval or dispatch."""
from __future__ import annotations
import json
import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from app.modules.c30 import policy

PREFIX='APPLY'
PINNED_DOC_URLS_ENV='ATLAS_C35_PINNED_DOC_URLS'


def _configured_doc_urls():
    """Read an exact allowlist from deployment configuration, never request data.

    JSON array of HTTPS Google Doc edit URLs. No owner-specific defaults.
    Reading per invocation permits config changes without module reload.
    """
    raw=os.environ.get(PINNED_DOC_URLS_ENV)
    if raw is None or not raw.strip():_refuse('DOC_CONFIG_MISSING')
    if len(raw)>4096:_refuse('DOC_CONFIG_INVALID')
    try:urls=json.loads(raw)
    except (ValueError,TypeError):_refuse('DOC_CONFIG_INVALID')
    if type(urls) is not list or not 1<=len(urls)<=16:_refuse('DOC_CONFIG_INVALID')
    checked=[]
    for url in urls:
        if type(url) is not str or len(url)>512 or any(ord(c)<33 or ord(c)==127 for c in url):_refuse('DOC_CONFIG_INVALID')
        try:parts=urlsplit(url)
        except ValueError:_refuse('DOC_CONFIG_INVALID')
        if (parts.scheme!='https' or parts.netloc!='docs.google.com' or parts.fragment or
            not re.fullmatch(r'/document/d/[A-Za-z0-9_-]+/edit',parts.path)):_refuse('DOC_CONFIG_INVALID')
        checked.append(url)
    if len(set(checked))!=len(checked):_refuse('DOC_CONFIG_INVALID')
    return frozenset(checked)

# First matching host keyword group wins. Labels do not affect classification.
HOST_KEYWORDS=(
 ('scholarship',('scholarship',)),
 ('competition',('competition','contest','olympiad','sciencefair')),
 ('grant',('grant',)),
 ('admissions',('admission','college','university')),
 ('job',('jobs','careers')),
)
LINK_RE=re.compile(r'https?://[^\s<>"\x27]+',re.I)
TEMPLATE_RE=re.compile(r'fee waiver|waiver request',re.I)
PLACEHOLDERS=frozenset({'name','school','opportunity'})


def _refuse(reason):raise ValueError('APPLY_REFUSED_'+reason)


def _normalize(url):
    # Common prose/Markdown delimiter trim, not a universal URL grammar parser.
    url=url.rstrip('.,;!?)]}')
    try:
        parts=urlsplit(url)
        host=parts.hostname
        if parts.scheme.lower() not in ('http','https') or not host or parts.username is not None or parts.password is not None:
            _refuse('BAD_TYPE:url')
        port=parts.port
        authority=host.lower()
        if ':' in authority:authority='['+authority+']'
        if port is not None:authority+=':'+str(port)
        query=urlencode([(key,value)for key,value in parse_qsl(parts.query,keep_blank_values=True)if not key.casefold().startswith('utm_')])
        return urlunsplit((parts.scheme.lower(),authority,parts.path.rstrip('/'),query,''))
    except ValueError:_refuse('BAD_TYPE:url')


def _kind(url):
    host=urlsplit(url).hostname
    for kind,keywords in HOST_KEYWORDS:
        if any(word in host for word in keywords):return kind
    return 'unknown'


def _templates(text,doc_url):
    # Keep the block's original internal whitespace/newlines; remove only the
    # final line separator before a blank delimiter, not indentation/content.
    lines=text.splitlines(keepends=True)
    out=[];i=0
    while i<len(lines):
        if not TEMPLATE_RE.search(lines[i]):i+=1;continue
        start=i;i+=1
        while i<len(lines) and lines[i].strip():i+=1
        block=''.join(lines[start:i]).removesuffix('\r\n')
        if block.endswith('\n') or block.endswith('\r'):block=block[:-1]
        out.append({'text':block,'placeholders':sorted(set(re.findall(r'\{(name|school|opportunity)\}',block))), 'doc_url':doc_url})
    return out


def run(request:dict)->dict:
    if type(request) is not dict or set(request)-{'as_of','docs'}:_refuse('BAD_TYPE:request')
    docs=request.get('docs')
    if docs is None or docs==[]:_refuse('NOSOURCE')
    if type(docs) is not list:_refuse('BAD_TYPE:docs')
    as_of=policy.clean_text(request.get('as_of'),PREFIX,'as_of',128)
    pinned_doc_urls=_configured_doc_urls()
    index=[];by_url={};templates=[];found=duplicates=0
    for doc in docs:
        if type(doc) is not dict or set(doc)!={'doc_url','text'}:_refuse('BAD_TYPE:doc')
        doc_url=policy.clean_text(doc['doc_url'],PREFIX,'doc_url',512)
        if doc_url not in pinned_doc_urls:_refuse('URL_NOT_PINNED')
        text=policy.clean_text(doc['text'],PREFIX,'text',2_000_000,allow_ws=True)
        for line in text.splitlines():
            for match in LINK_RE.finditer(line):
                found+=1
                url=_normalize(match.group())
                if url in by_url:
                    duplicates+=1
                    if doc_url not in by_url[url]['doc_urls']:by_url[url]['doc_urls'].append(doc_url)
                else:
                    entry={'url':url,'label':line,'kind':_kind(url),'doc_urls':[doc_url]}
                    index.append(entry);by_url[url]=entry
        templates.extend(_templates(text,doc_url))
    return {'index':index,'waiver_templates':templates,
            'coverage':{'links_found':found,'duplicates_dropped':duplicates,'unknown_kind':sum(row['kind']=='unknown'for row in index)},
            'scope':policy.scope(['supplied pinned-Doc link index','URL normalization and dedupe','host-keyword classification','verbatim waiver blocks and known placeholders'],
                                 ['fetching','live verification','dead-link detection','opportunity selection','submission or outreach'],
                                 'supplied exports of two owner-pinned Docs',as_of)}
