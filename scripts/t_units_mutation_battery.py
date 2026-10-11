"""Run concrete guard-removal mutants against focused hermetic tests. Restores source."""
from pathlib import Path
import subprocess,sys,json
root=Path(__file__).resolve().parents[1]
p=root/'backend/app/modules/m20_general_cognitive_worker/training_data_units.py'
original=p.read_text()
mutations={
 'skip_policy':("self._policy(payload.get('action',{}),prefix)",'pass'),
 'skip_search_policy':("self._policy(p.get('action',{}),'TREND');rows=[]",'rows=[]'),
 'permit_missing':("if permit is None:raise Refusal(prefix+'_REFUSED_SCRAPE')",'if False:pass'),
 'ignore_paywall':("if r.get('paywalled'):",'if False:'),
 'ignore_piracy':("if r.get('piracy'):",'if False:'),
 'ignore_auth_wall':("if r.get('credentials') or r.get('logged_in'):",'if False:'),
 'disable_terms':('if self.terms_allowed is not True or not self.checked_at or self.license not in','if False and self.license not in'),
 'cross_origin':("if urlsplit(url).netloc.lower()!=urlsplit(self.origin).netloc.lower():",'if False:'),
 'remove_url_check':('public_url(url);public_url(self.origin);public_url(self.terms_url)','pass'),
 'remove_text_limit':('len(text.encode())>100000','len(text.encode())>1000000'),
 'remove_record_limit':('len(records)>500','len(records)>5000'),
 'remove_date':("if not isinstance(r.get('as_of'),str) or not re.fullmatch(r'\\d{4}-\\d{2}-\\d{2}',r['as_of']):",'if False:'),
 'no_advice':("if not records:raise Refusal('FLEET_REFUSED_NOADVICE')",'pass'),
 'fake_training':("result['model_trained']=False","result['model_trained']=True"),
 'dedupe':("if (r['source_id'],digest) in seen:continue",'if False:continue'),
 'robots':("if not rp.can_fetch('AtlasPublicCorpus',url):",'if False:'),
 'rate_limit':("if now-self.last.get(host,float('-inf'))<self.interval:",'if False:'),
 'crawl_delay':('if delay>self.interval:','if False:'),
 'robots_status':('if robots.status!=200 or len(robots.text.encode())>self.limit:','if False:'),
 'reply_size':('if len(reply.text.encode())>self.limit:','if False:'),
 'xml_dtd':("if '<!DOCTYPE' in content.upper() or '<!ENTITY' in content.upper():",'if False:'),
 'result_limit':("'results':accepted[:100]","'results':accepted"),
 'query_filter':("if all(term in (str(r['title'])+' '+str(r['summary'])).lower() for term in query.lower().split()):",'if True:'),
 'private_ip':('if not ip.is_global:','if False:'),
 'url_scheme':("p.scheme!='https'",'False'),
 'fetch_config_limit':('if interval<60 or not 1<=limit<=100000:','if False:'),
}
results=[]
try:
 for name,(old,new) in mutations.items():
  assert old in original,name
  p.write_text(original.replace(old,new,1))
  run=subprocess.run([sys.executable,'-B','-m','pytest','tests/t_units','-q'],cwd=root,env={**__import__('os').environ,'PYTHONPATH':'backend','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True)
  results.append({'mutant':name,'killed':run.returncode!=0,'exit':run.returncode})
finally:p.write_text(original)
print(json.dumps({'mutants':results,'killed':sum(r['killed'] for r in results),'total':len(results)},indent=2))
if any(not r['killed'] for r in results):sys.exit(1)
