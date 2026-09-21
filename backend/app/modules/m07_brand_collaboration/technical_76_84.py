from typing import Any
ROWS={76:'legal_platform_discovery',77:'competitor_partnership_monitoring',78:'alignment_assessment',79:'official_contact_enrichment',80:'pdf_media_kit',81:'sponsorship_packages',82:'invoice_generation',83:'partnership_crm',84:'approval_gated_performance_reports'}
def need(d,*ks):
 m=[k for k in ks if k not in d or d[k] in ('',None)];
 if m:raise ValueError('missing required fields: '+', '.join(m))
def run(row:int,d:dict[str,Any]):
 if row not in ROWS:raise ValueError('unsupported row')
 if row==76:need(d,'platforms');r={'platforms':[dict(x,allowed=bool(x.get('public') and x.get('terms_permit_research') and x.get('source_url'))) for x in d['platforms']]}
 elif row==77:need(d,'announcements');r={'events':[dict(x,verified=bool(x.get('source_url') and x.get('announced_at'))) for x in d['announcements']],'private_scraping':False}
 elif row==78:need(d,'brand','mission','evidence');r={'brand':d['brand'],'mission':d['mission'],'evidence':d['evidence'],'alignment_dimensions':d.get('alignment_dimensions',{}),'score':sum(float(x) for x in d.get('alignment_dimensions',{}).values()),'evidence_required':True}
 elif row==79:need(d,'contacts');r={'contacts':[dict(x,allowed_source=bool(x.get('official_source_url') or x.get('public_business_directory'))) for x in d['contacts']],'guessed_emails_forbidden':True}
 elif row==80:need(d,'creator','metrics','portfolio');r={'document':{'format':'pdf','creator':d['creator'],'metrics':d['metrics'],'portfolio':d['portfolio'],'brand_style':d.get('brand_style',{})},'rendered':False}
 elif row==81:need(d,'tiers');r={'tiers':[dict(x,complete=all(x.get(k) is not None for k in ('name','deliverables','price','usage_rights'))) for x in d['tiers']],'draft_only':True}
 elif row==82:need(d,'seller','buyer','line_items','currency');total=sum(float(x['quantity'])*float(x['unit_price']) for x in d['line_items']);r={'invoice':{'seller':d['seller'],'buyer':d['buyer'],'line_items':d['line_items'],'currency':d['currency'],'total':total},'issued':False,'payment_committed':False}
 elif row==83:need(d,'partnership_id','events','deliverables');r={'partnership_id':d['partnership_id'],'events':d['events'],'deliverables':d['deliverables'],'overdue_ids':[x.get('id') for x in d['deliverables'] if x.get('status')!='done' and x.get('overdue')]}
 else:need(d,'report','approval');r={'report':d['report'],'approval_id':d['approval'].get('id'),'share_allowed':d['approval'].get('status')=='approved','shared':False}
 return {'row':row,'requirement':ROWS[row],'result':r,'external_effect_performed':False}
