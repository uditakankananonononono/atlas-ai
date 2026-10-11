"""S3.2 static HTML/CSS drafts and local source checks, never rendered quality."""
from __future__ import annotations
import html
import json
import math
import re
from html import parser as _parser
from app.modules.c30 import policy

PREFIX='PROTO'
_SPEND=frozenset(('deploy','host','hosting','domain','publish','upload','cdn'))
_IMAGE=re.compile(r'[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*\.(png|jpg|jpeg|webp|svg|gif)')
_SLUG=re.compile(r'[a-z0-9]+(-[a-z0-9]+)*')
_HEX=re.compile(r'#[0-9a-fA-F]{6}')
_FONT=re.compile(r"[A-Za-z0-9 ,'-]+")

def _refuse(reason):
    raise ValueError('PROTO_REFUSED_'+reason)

def _spend_scan(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if isinstance(key,str) and key.casefold() in _SPEND:
                policy.check('spend',PREFIX)
            _spend_scan(item)
    elif isinstance(value,list):
        for item in value:_spend_scan(item)

def _fields(value,required,optional,path):
    if not isinstance(value,dict):_refuse('BAD_TYPE:'+path)
    for key in value:
        if key not in required|optional:_refuse('NOSPEC:'+ (path+'.' if path!='request' else '')+str(key))
    for key in sorted(required-set(value)):
        _refuse('NOSPEC:'+ (path+'.' if path!='request' else '')+key)

def _text(value,name,cap,blank=False):
    if not isinstance(value,str):_refuse('BAD_TYPE:'+name)
    if len(value)>cap:_refuse('OVERSIZE:'+name)
    if not blank and not value.strip():_refuse('BAD_TYPE:'+name)
    return policy.clean_text(value,PREFIX,name,cap,allow_blank=blank,allow_ws=True)

def _rows(value,path,cap):
    if not isinstance(value,list):_refuse('BAD_TYPE:'+path)
    if len(value)>cap:_refuse('OVERSIZE:'+path)
    return value

def _luminance(color):
    rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))

def _contrast(a,b):
    hi,lo=sorted((_luminance(a),_luminance(b)),reverse=True)
    return (hi+.05)/(lo+.05)

class _Page(_parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings=[];self.alts=[];self.external=[];self.scripts=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if re.fullmatch(r'h[1-6]',tag):self.headings.append(int(tag[1]))
        if tag=='img':self.alts.append(bool((attrs.get('alt') or '').strip()))
        if tag=='script':self.scripts+=1
        for key in ('src','href'):
            src=(attrs.get(key) or '').strip().lower()
            if src.startswith(('http:','https:','//')):self.external.append(src)
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)

def _inspect(page,css):
    p=_Page();p.feed(page);p.close()
    order=all(b<=a+1 for a,b in zip([0]+p.headings,p.headings))
    size=len(page.encode('utf-8'))+len(css.encode('utf-8'))
    external=p.external+re.findall(r'https?://[^\s\)]+',css,flags=re.I)
    return {'one_h1':(p.headings.count(1)==1,p.headings.count(1)),
        'heading_order':(order,p.headings),'image_alt':(all(p.alts),{'images':len(p.alts),'missing':p.alts.count(False)}),
        'size_bytes':(size<=102400,size),'no_external_resources':(not external,external),
        'no_scripts':(p.scripts==0,p.scripts)}

def _escape(value):return html.escape(value,quote=True)

def run(request):
    """Return static source strings, computed checks and explicit unverified status."""
    _spend_scan(request)
    _fields(request,{'brand','pages'},{'as_of'},'request')
    brand=request['brand'];_fields(brand,{'name','palette','font_stack','scale','base_px'},set(),'brand')
    name=_text(brand['name'],'name',120)
    palette=brand['palette'];_fields(palette,{'bg','fg','accent'},set(),'brand.palette')
    for color in palette.values():
        if not isinstance(color,str):_refuse('BAD_TYPE:palette')
        if not _HEX.fullmatch(color):_refuse('UNSAFE:css')
    font=_text(brand['font_stack'],'font_stack',200)
    if not _FONT.fullmatch(font) or re.search(r'\b(url|import)\b',font,re.I):_refuse('UNSAFE:css')
    scale=brand['scale'];base=brand['base_px']
    if isinstance(scale,bool) or not isinstance(scale,(int,float)) or not 1<=scale<=2 or not math.isfinite(scale):_refuse('BAD_TYPE:scale')
    if isinstance(base,bool) or not isinstance(base,int) or not 12<=base<=24:_refuse('BAD_TYPE:base_px')
    if not isinstance(request['pages'],list) or not request['pages']:_refuse('NOSPEC:pages')
    pages=_rows(request['pages'],'pages',20)
    css=':root{'+''.join('--'+k+':'+palette[k]+';' for k in ('bg','fg','accent'))
    css+=''.join('--'+key+':'+str(round(float(base*scale**power),6))+'px;' for key,power in (('body',0),('h3',1),('h2',2),('h1',3)))
    css+=''.join('--space-'+str(i)+':'+str(round(float(base*v),6))+'px;' for i,v in enumerate((.5,1,2,4)))+'}\n'
    css+='body{margin:0;background:var(--bg);color:var(--fg);font-family:'+font+';font-size:var(--body);line-height:1.5;}\n'
    css+='main{max-width:72rem;margin:auto;padding:var(--space-2);}h1{font-size:var(--h1);}h2{font-size:var(--h2);}h3{font-size:var(--h3);}\n'
    css+='section{margin-block:var(--space-3);} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:var(--space-1);}img{max-width:100%;height:auto;} .brand{color:var(--accent);}\n'
    files={'style.css':css};checks=[];slugs=set()
    for i,page in enumerate(pages):
        path='pages['+str(i)+']';_fields(page,{'slug','title','sections'},set(),path)
        slug=_text(page['slug'],'slug',40)
        if not _SLUG.fullmatch(slug) or slug in slugs:_refuse('BAD_TYPE:slug')
        slugs.add(slug);title=_text(page['title'],'title',120)
        sections=_rows(page['sections'],path+'.sections',30)
        content=['<!doctype html>','<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
            '<title>'+_escape(title)+'</title><link rel="stylesheet" href="style.css"></head><body><main>',
            '<p class="brand">'+_escape(name)+'</p>','<h1>'+_escape(title)+'</h1>']
        for j,section in enumerate(sections):
            sp=path+'.sections['+str(j)+']'
            if not isinstance(section,dict):_refuse('BAD_TYPE:'+sp)
            kind=section.get('kind')
            if kind not in ('hero','text','grid'):_refuse('NOSPEC:'+sp+'.kind')
            required={'kind','heading','cards' if kind=='grid' else 'body'}
            _fields(section,required,{'images'},sp)
            heading=_text(section['heading'],'heading',120)
            content.extend(('<section>','<h2>'+_escape(heading)+'</h2>'))
            if kind=='grid':
                content.append('<div class="grid">')
                for k,card in enumerate(_rows(section['cards'],sp+'.cards',12)):
                    cp=sp+'.cards['+str(k)+']';_fields(card,{'heading','body'},set(),cp)
                    ch=_text(card['heading'],'heading',120);cb=_text(card['body'],'body',5000,blank=True)
                    content.append('<article><h3>'+_escape(ch)+'</h3><p>'+_escape(cb)+'</p></article>')
                content.append('</div>')
            else:
                content.append('<p>'+_escape(_text(section['body'],'body',5000,blank=True))+'</p>')
            for k,image in enumerate(_rows(section.get('images',[]),sp+'.images',30)):
                ip=sp+'.images['+str(k)+']';_fields(image,{'src'},{'alt'},ip)
                src=image['src']
                if not isinstance(src,str):_refuse('BAD_TYPE:image_src')
                if not _IMAGE.fullmatch(src):_refuse('UNSAFE:image_src')
                alt=_text(image.get('alt',''),'alt',200,blank=True)
                content.append('<img src="'+_escape(src)+'" alt="'+_escape(alt)+'">')
            content.append('</section>')
        content.append('</main></body></html>');text='\n'.join(content)+'\n';files[slug+'.html']=text
        values=_inspect(text,css)
        for pair in ('fg','accent'):
            ratio=_contrast(palette[pair],palette['bg'])
            values['contrast_'+pair+'_bg']=(ratio>=4.5,round(ratio,6))
        checks.extend({'page':slug+'.html','check':key,'pass':passed,'value':value} for key,(passed,value) in sorted(values.items()))
    as_of=_text(request['as_of'],'as_of',128) if 'as_of' in request else 'supplied-input'
    result={'files':files,'checks':sorted(checks,key=lambda c:(c['page'],c['check'])),
        'visual_quality':'unverified','assets_unverified':True,
        'scope':policy.scope(['static HTML/CSS strings','local source contrast, structure, alt, bytes, resource and script checks'],
            ['visual quality or WCAG conformance','browser rendering or Lighthouse','image asset contents or existence','deploy, hosting, domains or effects'],
            'supplied brand and page content',as_of)}
    return json.loads(json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False))
