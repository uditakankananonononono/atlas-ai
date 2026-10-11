import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[2]/'backend/app/modules/m02_competition_manager/site_application_planner.py'
s=importlib.util.spec_from_file_location('planner',PATH);p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
HTML='<form><input id="name" required><textarea id="essay" required></textarea><input type="submit"></form>'
FACTS={'name':{'value':'Supplied Name','source_ids':['bio']},'essay':{'value':'Supplied answer','source_ids':['bio']}}
SOURCES=[{'id':'bio','url':'https://example.invalid/bio','excerpt':'Supplied biography'}]
def plan(html=HTML, facts=FACTS, bindings=None, **kw):
 return p.plan_application(site_url='https://example.invalid/apply',html=html,facts=facts,
                           bindings={'name':'name','essay':'essay'} if bindings is None else bindings,
                           sources=SOURCES,**kw)
class PlannerTests(unittest.TestCase):
 def test_draft_exact_and_disabled_submission(self):
  o=plan();self.assertEqual(o['draft_values'],{'name':'Supplied Name','essay':'Supplied answer'})
  self.assertEqual(o['status'],'draft_ready_for_review');self.assertFalse(o['submission_enabled'])
  self.assertEqual(o['handoff']['approval_module'],'m00');self.assertEqual(o['handoff']['mode'],'proposal_only')
  self.assertEqual(len(o['snapshot_sha256']),64);self.assertEqual(o,plan())
 def test_missing_required_not_invented(self):
  o=plan(bindings={'name':'name'});self.assertEqual(o['missing_required'],['essay']);self.assertEqual(o['status'],'needs_input')
 def test_unknown_field_or_fact_rejected(self):
  for b in [{'missing':'name'},{'name':'missing'}]:
   with self.assertRaises(ValueError):plan(bindings=b)
 def test_blockers_empty_draft(self):
  for html,block in [('<input id="phone" type="tel">','phone'),('<input id="passport">','id'),
                     ('<div>Payment required</div>','payment'),('<div class="g-recaptcha"></div>','captcha')]:
   o=plan(html);self.assertIn(block,o['blockers']);self.assertEqual(o['draft_values'],{});self.assertEqual(o['status'],'blocked')
 def test_login_secret_fields_blocked(self):
  o=plan('<input id="secret" type="password">');self.assertIn('credentials',o['blockers']);self.assertEqual(o['draft_values'],{})
 def test_credential_fact_refused(self):
  with self.assertRaisesRegex(ValueError,'^APPPLAN: credential facts forbidden$'):plan(facts={'password':{'value':'not-a-secret','source_ids':['bio']}},bindings={})
 def test_source_reference_required(self):
  for f in [{'name':{'value':'x','source_ids':[]}}, {'name':{'value':'x','source_ids':['missing']}}]:
   with self.assertRaises(ValueError):plan(facts=f,bindings={'name':'name'})
 def test_duplicate_id_and_unmapped_control_refused(self):
  with self.assertRaisesRegex(ValueError,'^APPPLAN: duplicate field identifier$'):plan('<input id="x"><input id="x">',bindings={})
  with self.assertRaisesRegex(ValueError,'^APPPLAN: fillable control has no id or name$'):plan('<input required>',bindings={})
 def test_choice_value_checked(self):
  html='<select id="name"><option value="other">Other</option></select>'
  with self.assertRaises(ValueError):plan(html,bindings={'name':'name'})
 def test_html_source_and_url_types(self):
  for html in [None,1,'x'*1000001]:
   with self.assertRaises(ValueError):plan(html)
  with self.assertRaises(ValueError):p.plan_application(site_url='https://exa mple.invalid',html=HTML,facts=FACTS,bindings={},sources=SOURCES)
 def test_explicit_challenges_fail_closed(self):
  for block in ['captcha','phone','id','payment']:
   self.assertEqual(plan(challenges=[block])['status'],'blocked')
  with self.assertRaises(ValueError):plan(challenges=['unknown'])
 def test_sources_and_values_not_mutated(self):
  result=plan();result['sources'][0]['excerpt']='changed';self.assertEqual(SOURCES[0]['excerpt'],'Supplied biography')
import hashlib
import json
URLMSG='^APPPLAN: URL must be credential-free HTTPS$'
class SafetyFlagPins(unittest.TestCase):
 def check(self,o):
  self.assertIs(o['submission_enabled'],False);self.assertIs(o['browser_action_performed'],False)
  self.assertIs(o['source_facts_verified'],False);self.assertIs(o['handoff']['requires_exact_review'],True)
  self.assertEqual(o['handoff'],{'approval_module':'m00','mode':'proposal_only','requires_exact_review':True,
   'site_url':o['site_url'],'snapshot_sha256':o['snapshot_sha256'],'draft_sha256':o['draft_sha256']})
 def test_flags_on_ready_needs_input_and_blocked(self):
  self.check(plan());self.check(plan(bindings={'name':'name'}));self.check(plan('<input id="phone" type="tel">'))
  self.check(plan(challenges=['captcha']))
 def test_status_values_exact(self):
  self.assertEqual(plan()['status'],'draft_ready_for_review');self.assertEqual(plan(bindings={})['status'],'needs_input')
  self.assertEqual(plan(challenges=['id'])['status'],'blocked')
class DigestPins(unittest.TestCase):
 def test_draft_digest_is_sorted_key_json_literal(self):
  o=plan();exact='{"essay": "Supplied answer", "name": "Supplied Name"}'
  self.assertEqual(o['draft_sha256'],hashlib.sha256(exact.encode()).hexdigest())
  self.assertEqual(o['handoff']['draft_sha256'],o['draft_sha256'])
 def test_draft_digest_independent_of_binding_order(self):
  a=plan(bindings={'name':'name','essay':'essay'});b=plan(bindings={'essay':'essay','name':'name'})
  self.assertEqual(a['draft_sha256'],b['draft_sha256'])
  self.assertEqual(list(a['draft_values']),['name','essay']);self.assertEqual(list(b['draft_values']),['essay','name'])
 def test_snapshot_digest_is_sha256_of_html(self):
  self.assertEqual(plan()['snapshot_sha256'],hashlib.sha256(HTML.encode()).hexdigest())
class HtmlCapPins(unittest.TestCase):
 def test_cap_1000000_accepted_1000001_refused(self):
  base='<form></form>';ok=base+' '*(1000000-len(base));self.assertEqual(len(ok),1000000)
  self.assertEqual(plan(ok,bindings={})['status'],'draft_ready_for_review')
  with self.assertRaisesRegex(ValueError,'^APPPLAN: HTML must be text at most 1000000 characters$'):plan(ok+' ',bindings={})
  for bad in [None,1,b'x',['x']]:
   with self.assertRaisesRegex(ValueError,'^APPPLAN: HTML must be text at most 1000000 characters$'):plan(bad,bindings={})
class UrlGatePins(unittest.TestCase):
 def go(self,url):
  return p.plan_application(site_url=url,html=HTML,facts=FACTS,bindings={},sources=SOURCES)
 def test_each_gate_part_refused_with_exact_message(self):
  for url in ['http://example.invalid/a','ftp://example.invalid/a','HTTP://example.invalid/','https:///path','https://user@example.invalid/',
              'https://user:pw@example.invalid/','https://:pw@example.invalid/','//example.invalid/a','example.invalid']:
   with self.subTest(url=url),self.assertRaisesRegex(ValueError,URLMSG):self.go(url)
 def test_control_and_space_boundary(self):
  for code in [1,8,31,32]:
   with self.subTest(code=code),self.assertRaisesRegex(ValueError,URLMSG):self.go('https://example.invalid/a'+chr(code)+'b')
  for code in [33,126]:
   self.assertEqual(self.go('https://example.invalid/a'+chr(code)+'b')['status'],'needs_input')
 def test_url_type_and_malformed(self):
  for bad in [None,5,'',' ']:
   with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'^APPPLAN: URL must be nonempty text$'):self.go(bad)
  with self.assertRaisesRegex(ValueError,'^APPPLAN: malformed URL$'):self.go('https://example.invalid:99999/')
 def test_source_url_gate_applies(self):
  for url in ['http://example.invalid/bio','https://u:p@example.invalid/bio','https:///bio']:
   with self.subTest(url=url),self.assertRaisesRegex(ValueError,URLMSG):
    p.plan_application(site_url='https://example.invalid/apply',html=HTML,facts=FACTS,bindings={},sources=[{'id':'bio','url':url,'excerpt':'x'}])
class ShapePins(unittest.TestCase):
 def test_facts_and_bindings_must_be_objects(self):
  for bad in [None,[],'x',5,()]:
   with self.subTest(facts=bad),self.assertRaisesRegex(ValueError,'^APPPLAN: facts and bindings must be objects$'):plan(facts=bad,bindings={})
   if bad is None:continue  # the plan() helper substitutes default bindings for None
   with self.subTest(bindings=bad),self.assertRaisesRegex(ValueError,'^APPPLAN: facts and bindings must be objects$'):plan(bindings=bad)
 def test_text_helper_types_and_empty_with_exact_messages(self):
  for bad in [None,5,[],'', '   ']:
   with self.subTest(source_id=bad),self.assertRaisesRegex(ValueError,'^APPPLAN: source id must be nonempty text$'):
    p.plan_application(site_url='https://example.invalid/a',html=HTML,facts={},bindings={},sources=[{'id':bad,'url':'https://example.invalid/b','excerpt':'x'}])
   with self.subTest(excerpt=bad),self.assertRaisesRegex(ValueError,'^APPPLAN: source excerpt must be nonempty text$'):
    p.plan_application(site_url='https://example.invalid/a',html=HTML,facts={},bindings={},sources=[{'id':'s','url':'https://example.invalid/b','excerpt':bad}])
   with self.subTest(value=bad),self.assertRaisesRegex(ValueError,'^APPPLAN: fact value must be nonempty text$'):
    plan(facts={'name':{'value':bad,'source_ids':['bio']}},bindings={'name':'name'})
 def test_misc_shape_refusals(self):
  with self.assertRaisesRegex(ValueError,'^APPPLAN: fact keys must be strings$'):plan(facts={1:{'value':'x','source_ids':['bio']}},bindings={})
  with self.assertRaisesRegex(ValueError,'^APPPLAN: sources must be a list$'):p.plan_application(site_url='https://example.invalid/a',html=HTML,facts={},bindings={},sources=None)
  with self.assertRaisesRegex(ValueError,'^APPPLAN: source must be an object$'):p.plan_application(site_url='https://example.invalid/a',html=HTML,facts={},bindings={},sources=['x'])
  with self.assertRaisesRegex(ValueError,'^APPPLAN: duplicate source id$'):p.plan_application(site_url='https://example.invalid/a',html=HTML,facts={},bindings={},sources=SOURCES*2)
  with self.assertRaisesRegex(ValueError,'^APPPLAN: fact must be an object$'):plan(facts={'name':'x'},bindings={'name':'name'})
  with self.assertRaisesRegex(ValueError,'^APPPLAN: fact requires known source ids$'):plan(facts={'name':{'value':'x','source_ids':'bio'}},bindings={'name':'name'})
class NoneBindingPin(unittest.TestCase):
 def test_none_bindings_refused_directly(self):
  with self.assertRaisesRegex(ValueError,'^APPPLAN: facts and bindings must be objects$'):
   p.plan_application(site_url='https://example.invalid/a',html=HTML,facts=FACTS,bindings=None,sources=SOURCES)
class ParserPins(unittest.TestCase):
 def choices(self,html,field='a'):return plan(html,bindings={})['form_map'][field]['choices']
 def test_options_collected_across_end_tags_and_values(self):
  self.assertEqual(self.choices('<select id="a"><option value="1">x</option><option value="2">y</option><option>z</option></select>'),['1','2',''])
 def test_option_after_select_closes_or_outside_is_ignored(self):
  html='<select id="a"><option value="1">x</option></select><option value="stray">s</option>'
  self.assertEqual(self.choices(html),['1'])
  self.assertEqual(plan('<option value="stray">s</option><input id="n">',bindings={})['form_map'].keys(),{'n':0}.keys())
 def test_second_select_gets_only_its_own_options(self):
  fm=plan('<select id="a"><option value="1">x</option></select><select id="b"><option value="2">y</option></select>',bindings={})['form_map']
  self.assertEqual((fm['a']['choices'],fm['b']['choices']),(['1'],['2']))
 def test_charref_in_option_value_decoded(self):
  self.assertEqual(self.choices('<select id="a"><option value="a&amp;b">x</option></select>'),['a&b'])
 def test_control_kinds_and_flags(self):
  fm=plan('<input id="h" type="hidden"><input id="b" type="button"><input name="n" required disabled><textarea id="t"></textarea>',bindings={})['form_map']
  self.assertEqual(sorted(fm),['n','t']);self.assertTrue(fm['n']['required'] and fm['n']['disabled']);self.assertFalse(fm['t']['required'])
class CredentialFactPins(unittest.TestCase):
 KEYS=['password','passcode','otp','mfa','cookie','token','apikey','secret','privatekey',
       'cardnumber','cvv','ssn','creditcard','card_number','security_code','routing','account_number',
       'Card_Number','CVV','SSN','Credit-Card','Security Code','ROUTING','Account Number','api_key','Private-Key']
 def test_every_credential_key_refused_at_binding(self):
  for key in self.KEYS:
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'^APPPLAN: credential facts forbidden$'):
    plan(facts={key:{'value':'not-a-secret','source_ids':['bio']}},bindings={})
 LONG=['credit_card_number','social_security_number','user_password','password_hint','my passcode 2','access_token','auth-token','client_secret','secret_answer','stripe_api_key','private_key_pem','routing_number','bank_routing','bank_account_number','session_cookie','card_number_last','ssn_last4']
 SHORT=['cvv','cvv2','CVV2','cvc','CVC','pin','PIN','otp','OTP','mfa','MFA','iban','IBAN','c-v-v-2','P.I.N.']
 def test_long_token_variants_refused_by_substring(self):
  for key in self.LONG:
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'^APPPLAN: credential facts forbidden$'):
    plan(facts={key:{'value':'not-a-secret','source_ids':['bio']}},bindings={})
 def test_short_tokens_refused_exact_only(self):
  for key in self.SHORT:
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'^APPPLAN: credential facts forbidden$'):
    plan(facts={key:{'value':'not-a-secret','source_ids':['bio']}},bindings={})
  for key in ['pinecone','opinion','spinal','motivation','cvvs','ibanez','hotpot']:
   with self.subTest(key=key):plan(facts={key:{'value':'v','source_ids':['bio']}},bindings={})
 def test_ordinary_keys_still_accepted(self):
  for key in ['name','card_holder','account_name','essay','bio_text']:
   plan(facts={key:{'value':'v','source_ids':['bio']}},bindings={})
class FactValueCharPins(unittest.TestCase):
 def bad(self,value):
  with self.assertRaisesRegex(ValueError,'^APPPLAN: fact value contains control characters$'):
   plan(facts={'name':{'value':value,'source_ids':['bio']}},bindings={'name':'name'})
 def test_cc_cf_zl_zp_refused(self):
  for ch in ['\x00','\n','\r','\t','\x1f','\x7f','\u00ad','\u2060','\u200b','\u202e','\u2028','\u2029']:
   with self.subTest(ch=repr(ch)):self.bad('a'+ch+'b')
 def test_secret_text_not_echoed(self):
  with self.assertRaises(ValueError) as cm:plan(facts={'name':{'value':'SECRET-9917\x00','source_ids':['bio']}},bindings={'name':'name'})
  self.assertNotIn('SECRET',str(cm.exception))
 def test_space_separator_and_unicode_accepted(self):
  self.assertEqual(plan(facts={'name':{'value':'a\u00a0b caf\u00e9','source_ids':['bio']},'essay':FACTS['essay']})['draft_values']['name'],'a\u00a0b caf\u00e9')
 def test_control_in_unbound_fact_not_inspected_unbound_values_only_checked_when_bound(self):
  o=plan(facts={'name':FACTS['name'],'essay':FACTS['essay'],'x':{'value':'a\x00','source_ids':['bio']}})
  self.assertEqual(o['status'],'draft_ready_for_review')
class BindingValuePins(unittest.TestCase):
 def test_unhashable_and_nonstring_binding_values_refused(self):
  for bad in [['name'],{'a':1},{'name'},None,5,1.5,('name',),True]:
   with self.subTest(bad=repr(bad)),self.assertRaisesRegex(ValueError,'^APPPLAN: binding must name a fact key$'):plan(bindings={'name':bad})
 def test_str_subclass_binding_value_refused(self):
  class S(str):pass
  with self.assertRaisesRegex(ValueError,'^APPPLAN: binding must name a fact key$'):plan(bindings={'name':S('name')})
 def test_unknown_names_keep_existing_message(self):
  for b in [{'missing':'name'},{'name':'missing'}]:
   with self.assertRaisesRegex(ValueError,'^APPPLAN: binding references unknown field or fact$'):plan(bindings=b)
class ExactDictPins(unittest.TestCase):
 def spy(self):
  class Spy(dict):
   touched=0
   def __iter__(self):Spy.touched+=1;return iter(())
   def __len__(self):Spy.touched+=1;return 0
   def __contains__(self,k):Spy.touched+=1;return False
   def __getitem__(self,k):Spy.touched+=1;raise KeyError(k)
   def get(self,*a):Spy.touched+=1
   def items(self):Spy.touched+=1;return []
   def keys(self):Spy.touched+=1;return []
  return Spy
 def test_facts_subclass_refused_untouched(self):
  Spy=self.spy()
  with self.assertRaisesRegex(ValueError,'^APPPLAN: facts and bindings must be objects$'):plan(facts=Spy(FACTS),bindings={})
  self.assertEqual(Spy.touched,0)
 def test_bindings_subclass_refused_untouched(self):
  Spy=self.spy()
  with self.assertRaisesRegex(ValueError,'^APPPLAN: facts and bindings must be objects$'):plan(bindings=Spy({'name':'name'}))
  self.assertEqual(Spy.touched,0)
 def test_source_and_fact_subclass_refused_untouched(self):
  Spy=self.spy()
  with self.assertRaisesRegex(ValueError,'^APPPLAN: source must be an object$'):
   p.plan_application(site_url='https://example.invalid/a',html=HTML,facts={},bindings={},sources=[Spy(SOURCES[0])])
  with self.assertRaisesRegex(ValueError,'^APPPLAN: fact must be an object$'):plan(facts={'name':Spy(FACTS['name'])},bindings={'name':'name'})
  self.assertEqual(Spy.touched,0)
 def test_plain_dicts_still_accepted(self):
  self.assertEqual(plan()['status'],'draft_ready_for_review')
if __name__=='__main__':unittest.main(verbosity=2)
class OrderPins(unittest.TestCase):
 def test_missing_required_sorted(self):
  o=plan('<input id="zeta" required><input id="mid" required><input id="alpha" required>',bindings={})
  self.assertEqual(o['missing_required'],['alpha','mid','zeta'])
 def test_blockers_sorted(self):
  o=plan('<div>recaptcha payment</div><input id="x" type="tel">',bindings={})
  self.assertEqual(o['blockers'],['captcha','payment','phone'])
 def test_blockers_sorted_all_five(self):
  o=plan('<div>recaptcha payment passport</div><input id="x" type="tel"><input id="s" type="password">',bindings={})
  self.assertEqual(o['blockers'],['captcha','credentials','id','payment','phone'])
