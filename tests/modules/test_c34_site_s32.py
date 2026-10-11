"""S3.2 static source checks only, never visual-quality verification."""
import copy
import importlib.util
import json
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
spec=importlib.util.spec_from_file_location('s32_target',ROOT/'backend/app/modules/c34/site.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def req():
    return {'brand':{'name':'Studio','palette':{'bg':'#FFFFFF','fg':'#000000','accent':'#111111'},'font_stack':'Georgia, serif','scale':1.25,'base_px':16},
        'pages':[{'slug':'index','title':'Welcome','sections':[{'kind':'hero','heading':'Start','body':'Body','images':[{'src':'img/a.png','alt':'Portrait'}]},
            {'kind':'grid','heading':'Work','cards':[{'heading':'One','body':'Card'}]}]}]}

def check(out,name):
    return next(r for r in out['checks'] if r['check']==name)

class Site(unittest.TestCase):
    def refused(self,d,code):
        with self.assertRaises(ValueError) as cm:m.run(d)
        self.assertEqual(str(cm.exception),'PROTO_REFUSED_'+code)
    def test_three_brand_fixture(self):
        for fg,expected in [('#000000',True),('#111111',True),('#EEEEEE',False)]:
            d=req();d['brand']['palette']['fg']=fg;o=m.run(d)
            self.assertEqual(check(o,'contrast_fg_bg')['pass'],expected)
            self.assertEqual(o['visual_quality'],'unverified');self.assertTrue(o['assets_unverified'])
            self.assertEqual(set(o['files']),{'index.html','style.css'})
        self.assertEqual(check(m.run(req()),'contrast_fg_bg')['value'],21.0)
        self.assertTrue(check(m.run(req()),'contrast_accent_bg')['pass'])
    def test_color_oracle_gamma_weights_and_rounding(self):
        # Independent numeric oracle: RGB red has linear channels 1,0,0.
        self.assertAlmostEqual(m._contrast('#FF0000','#000000'),5.252,places=6)
        self.assertAlmostEqual(m._contrast('#FF0000','#FFFFFF'),3.9984767707539985,places=6)
        self.assertAlmostEqual(m._contrast('#777777','#FFFFFF'),4.478089453577214,places=6)
        self.assertAlmostEqual(m._contrast('#767676','#FFFFFF'),4.542224959605253,places=6)
        for color,expected in [('#777777',False),('#767676',True)]:
            d=req();d['brand']['palette']['fg']=color
            self.assertEqual(check(m.run(d),'contrast_fg_bg')['pass'],expected)
        d=req();d['brand']['palette']['accent']='#EEEEEE'
        self.assertFalse(check(m.run(d),'contrast_accent_bg')['pass'])

    def test_css_scale_spacing(self):
        css=m.run(req())['files']['style.css']
        for text in ('--bg:#FFFFFF','--fg:#000000','--accent:#111111','--body:16.0px','--h3:20.0px','--h2:25.0px','--h1:31.25px','--space-0:8.0px','--space-3:64.0px'):
            self.assertIn(text,css)
        d=req();d['brand']['scale']=1.333333333
        self.assertIn('--h1:37.925926px',m.run(d)['files']['style.css'])
    def test_structure_checks_parse_html(self):
        o=m.run(req());h=o['files']['index.html']
        self.assertEqual(h.count('<h1>'),1);self.assertEqual(h.count('<h2>'),2);self.assertEqual(h.count('<h3>'),1)
        self.assertTrue(check(o,'one_h1')['pass']);self.assertTrue(check(o,'heading_order')['pass'])
        bad=m._inspect('<h1>x</h1><h3>skip</h3><img src="x.png"><script>x</script>', '')
        self.assertFalse(bad['heading_order'][0]);self.assertFalse(bad['image_alt'][0]);self.assertFalse(bad['no_scripts'][0])
        self.assertFalse(m._inspect('<h1>a</h1><h1>b</h1>','')['one_h1'][0])
        self.assertFalse(m._inspect('<img src="https://bad.invalid/a.png" alt="a">','')['no_external_resources'][0])
    def test_escaping_all_contexts(self):
        d=req();x='<script>alert("x")</script>&'
        d['brand']['name']=x;d['pages'][0]['title']=x
        s=d['pages'][0]['sections'][0];s['heading']=x;s['body']=x;s['images'][0]['alt']=x
        d['pages'][0]['sections'][1]['cards'][0]={'heading':x,'body':x}
        o=m.run(d);h=o['files']['index.html']
        self.assertNotIn('<script>',h);self.assertIn('&lt;script&gt;',h);self.assertIn('&quot;x&quot;',h)
        self.assertTrue(check(o,'no_scripts')['pass'])
    def test_alt_missing_blank_and_type(self):
        for alt in (None,'','  '):
            d=req();im=d['pages'][0]['sections'][0]['images'][0]
            if alt is None:del im['alt']
            else:im['alt']=alt
            self.assertFalse(check(m.run(d),'image_alt')['pass'])
        d=req();d['pages'][0]['sections'][0]['images'][0]['alt']=1;self.refused(d,'BAD_TYPE:alt')
    def test_image_paths_unsafe(self):
        for src in ('http://a/a.png','https://a/a.png','//a/a.png','/a.png','../a.png','a\\b.png','a.svg?x=1','data:x','a\x00.png','a.PNG','a b.png'):
            d=req();d['pages'][0]['sections'][0]['images'][0]['src']=src;self.refused(d,'UNSAFE:image_src')
        for src in ('a.png','a-b/a_2.svg','img/a.jpeg'):
            d=req();d['pages'][0]['sections'][0]['images'][0]['src']=src;m.run(d)
    def test_css_unsafe(self):
        for value in ('serif; color:red','url','import','Georgia\\x','A"B','a/b','<style>','a(b)','@font','a*b','a{b}'):
            d=req();d['brand']['font_stack']=value;self.refused(d,'UNSAFE:css')
        for color in ('red','#123','#GGGGGG','#000000;'):
            d=req();d['brand']['palette']['bg']=color;self.refused(d,'UNSAFE:css')
        d=req();d['brand']['font_stack']="'Times New Roman', serif";m.run(d)
    def test_numeric_bounds_types(self):
        for value in (True,0.9,2.1,float('nan'),float('inf'),10**400,'1.2'):
            d=req();d['brand']['scale']=value;self.refused(d,'BAD_TYPE:scale')
        for value in (True,12.0,11,25,'16'):
            d=req();d['brand']['base_px']=value;self.refused(d,'BAD_TYPE:base_px')
        for value in (1,2):d=req();d['brand']['scale']=value;m.run(d)
        for value in (12,24):d=req();d['brand']['base_px']=value;m.run(d)
    def test_recursive_spend_precedence(self):
        for key in ('deploy','HOST','hosting','domain','Publish','upload','cdn'):
            for value in (False,None,{},''):
                d=req();d['pages'][0]['sections'][0]['extra']={key:value};self.refused(d,'SPEND')
    def test_fields_missing_unknown_kind(self):
        for key in ('brand','pages'):
            d=req();del d[key];self.refused(d,'NOSPEC:'+key)
        self.refused(None,'BAD_TYPE:request')
        d=req();d['extra']=1;self.refused(d,'NOSPEC:extra')
        d=req();d['brand']['extra']=1;self.refused(d,'NOSPEC:brand.extra')
        d=req();d['pages'][0]['sections'][0]['cards']=[];self.refused(d,'NOSPEC:pages[0].sections[0].cards')
        d=req();d['pages'][0]['sections'][1]['body']='x';self.refused(d,'NOSPEC:pages[0].sections[1].body')
        d=req();d['pages'][0]['sections'][0]['kind']='bad';self.refused(d,'NOSPEC:pages[0].sections[0].kind')
        d=req();d['pages'][0]['sections'][0]['heading']=' ';self.refused(d,'BAD_TYPE:heading')
        d=req();d['pages'][0]['title']=' ';self.refused(d,'BAD_TYPE:title')
    def test_empty_and_duplicate_slug(self):
        d=req();d['pages']=[];self.refused(d,'NOSPEC:pages')
        for value in (None,{},True):
            d=req();d['pages']=value;self.refused(d,'NOSPEC:pages')
        d=req();d['pages'][0]['sections']=[];h=m.run(d)['files']['index.html'];self.assertNotIn('<h2>',h)
        d=req();d['pages'][0]['sections'][1]['cards']=[];self.assertNotIn('<h3>',m.run(d)['files']['index.html'])
        for slug in ('../x','X','x.html','-x','x_1'):
            d=req();d['pages'][0]['slug']=slug;self.refused(d,'BAD_TYPE:slug')
        d=req();d['pages']*=2;self.refused(d,'BAD_TYPE:slug')
    def test_caps(self):
        for field,cap in [('pages',20)]:
            d=req();d[field]=[{}]*(cap+1);self.refused(d,'OVERSIZE:'+field)
        d=req();d['pages'][0]['sections']=[{}]*31;self.refused(d,'OVERSIZE:pages[0].sections')
        d=req();d['pages'][0]['sections'][1]['cards']=[{}]*13;self.refused(d,'OVERSIZE:pages[0].sections[1].cards')
        d=req();d['pages'][0]['sections'][0]['images']=[{}]*31;self.refused(d,'OVERSIZE:pages[0].sections[0].images')
        for field,limit in [('heading',120),('body',5000)]:
            d=req();d['pages'][0]['sections'][0][field]='x'*(limit+1);self.refused(d,'OVERSIZE:'+field)
        d=req();d['pages'][0]['slug']='x'*41;self.refused(d,'OVERSIZE:slug')
    def test_budget_inclusive_utf8_shared_css(self):
        self.assertTrue(m._inspect('a'*102399,'x')['size_bytes'][0])
        self.assertFalse(m._inspect('a'*102400,'x')['size_bytes'][0])
        self.assertEqual(m._inspect('é','x')['size_bytes'][1],3)
        d=req();d['pages'][0]['sections']=[{'kind':'text','heading':'H','body':'é'*5000} for _ in range(30)]
        o=m.run(d);self.assertFalse(check(o,'size_bytes')['pass']);self.assertGreater(check(o,'size_bytes')['value'],102400)
    def test_scope_determinism_no_mutation_effects(self):
        d=req();before=copy.deepcopy(d);o=m.run(d);self.assertEqual(d,before);self.assertEqual(o,m.run(d))
        self.assertEqual(list(o),sorted(o));json.dumps(o,allow_nan=False)
        self.assertEqual(o['scope']['as_of'],'supplied-input')
        d['as_of']='2026-10-11';self.assertEqual(m.run(d)['scope']['as_of'],'2026-10-11')
        self.assertEqual([k for k,v in vars(m).items() if callable(v) and not k.startswith('_')],['run'])
        self.assertIs(m.policy,sys.modules['app.modules.c30.policy'])
        self.assertIn('visual quality or WCAG conformance',o['scope']['not_implemented'])

if __name__=='__main__':unittest.main(verbosity=2)

# Independent-gate boundary and source-check pins; no rendered-quality claim.
import pytest

@pytest.mark.parametrize('field,cap',[('name',120),('font_stack',200),('slug',40),('title',120),('heading',120),('card_heading',120),('card_body',5000),('body',5000),('alt',200),('as_of',128)])
def test_raw_cap_n_and_n_plus_one(field,cap):
    def fill(d,value):
        if field in ('name','font_stack'):d['brand'][field]=value
        elif field=='as_of':d[field]=value
        elif field in ('slug','title'):d['pages'][0][field]=value
        elif field in ('card_heading','card_body'):d['pages'][0]['sections'][1]['cards'][0][field[5:]]=value
        elif field=='alt':d['pages'][0]['sections'][0]['images'][0]['alt']=value
        else:d['pages'][0]['sections'][0][field]=value
    d=req();fill(d,'x'*cap);assert m.run(d)['files']
    fill(d,'x'*(cap+1))
    with pytest.raises(ValueError)as e:m.run(d)
    assert str(e.value)=='PROTO_REFUSED_OVERSIZE:'+('heading' if field=='card_heading' else 'body' if field=='card_body' else field)

@pytest.mark.parametrize('field,cap',[('pages',20),('cards',12),('images',30)])
def test_list_cap_n_and_n_plus_one(field,cap):
    d=req()
    if field=='pages':
        d['pages']=[dict(copy.deepcopy(d['pages'][0]),slug='p'+str(i))for i in range(cap)]
        add=copy.deepcopy(d['pages'][0]);add['slug']='extra';target=d['pages'];path='pages'
    elif field=='cards':
        target=d['pages'][0]['sections'][1]['cards'];target[:]=[copy.deepcopy(target[0])for _ in range(cap)];add=copy.deepcopy(target[0]);path='pages[0].sections[1].cards'
    else:
        target=d['pages'][0]['sections'][0]['images'];target[:]=[copy.deepcopy(target[0])for _ in range(cap)];add=copy.deepcopy(target[0]);path='pages[0].sections[0].images'
    assert m.run(d)['files'];target.append(add)
    with pytest.raises(ValueError)as e:m.run(d)
    assert str(e.value)=='PROTO_REFUSED_OVERSIZE:'+path

@pytest.mark.parametrize('source,count,passed',[('',0,False),('<h1>A</h1>',1,True),('<h1>A</h1><h1>B</h1>',2,False)])
def test_one_h1_exact_value(source,count,passed):assert m._inspect(source,'')['one_h1']==(passed,count)

def test_inspection_counts_and_order():
    assert m._inspect('<h2>x</h2>','')['heading_order']==(False,[2])
    assert m._inspect('<h1>x</h1><h2>y</h2>','')['heading_order']==(True,[1,2])
    assert m._inspect('<script>x</script><script>y</script>','')['no_scripts']==(False,2)
    assert m._inspect('','')['no_scripts']==(True,0)
    assert m._inspect('<img alt="a"><img alt=" "><img>','')['image_alt']==(False,{'images':3,'missing':2})
    assert m._inspect('<img alt="a">','')['image_alt']==(True,{'images':1,'missing':0})

@pytest.mark.parametrize('ratio,passed',[(4.5,True),(4.49999999,False),(4.56789123,True)])
def test_raw_contrast_threshold_and_six_rounding(monkeypatch,ratio,passed):
    monkeypatch.setattr(m,'_contrast',lambda a,b:ratio)
    row=check(m.run(req()),'contrast_fg_bg')
    assert row['pass'] is passed and row['value']==round(ratio,6)

def test_gamma_seam_branch_exact(monkeypatch):
    # Fault injection: no byte/255 equals .04045. Pins helper branch, not caller reachability.
    monkeypatch.setattr(m,'int',lambda value,base:.04045*255,raising=False)
    assert m._luminance('#000000')==sum((.04045/12.92)*w for w in (.2126,.7152,.0722))

def test_spacing_exact_values():
    css=m.run(req())['files']['style.css']
    for value in ('--space-0:8.0px;','--space-1:16.0px;','--space-2:32.0px;','--space-3:64.0px;'):assert value in css


def test_empty_body_card_body_and_prose_whitespace():
    d=req();d['pages'][0]['sections'][0]['body']='';d['pages'][0]['sections'][1]['cards'][0]['body']=''
    assert '<p></p>' in m.run(d)['files']['index.html']
    d['pages'][0]['sections'][0]['body']='Line one\n\tLine two'
    assert 'Line one\n\tLine two' in m.run(d)['files']['index.html']


def test_exact_refusal_messages_paths():
    for d,reason in [(dict(req(),brand={}), 'NOSPEC:brand.base_px')]:
        with pytest.raises(ValueError)as e:m.run(d)
        assert str(e.value)=='PROTO_REFUSED_'+reason
    d=req();d['pages'][0]['sections']=5
    with pytest.raises(ValueError)as e:m.run(d)
    assert str(e.value)=='PROTO_REFUSED_BAD_TYPE:pages[0].sections'
    d=req();d['pages'][0]['sections']=[5]
    with pytest.raises(ValueError)as e:m.run(d)
    assert str(e.value)=='PROTO_REFUSED_BAD_TYPE:pages[0].sections[0]'


def test_entity_encoded_resources_and_alt():
    values=m._inspect('<img src="https&#58;//bad.invalid/x.png" alt="&#32;"><img alt="&#65;">','')
    assert values['no_external_resources']==(False,['https://bad.invalid/x.png'])
    assert values['image_alt']==(False,{'images':2,'missing':1})


def test_nan_serialization_refused(monkeypatch):
    # Fault injection into policy output; accepted request numbers remain finite.
    real=m.policy.scope
    monkeypatch.setattr(m.policy,'scope',lambda *args,**kw:dict(real(*args,**kw),injected=float('nan')))
    with pytest.raises(ValueError,match='Out of range float'):m.run(req())


def test_whitespace_and_entity_checks_together():
    d=req();d['pages'][0]['sections'][0]['body']='One\n\tTwo'
    assert 'One\n\tTwo' in m.run(d)['files']['index.html']
    result=m._inspect('<img src="http&#58;//bad.invalid/a.png" alt="&#32;">','')
    assert result['image_alt']==(False,{'images':1,'missing':1})
    assert result['no_external_resources']==(False,['http://bad.invalid/a.png'])
