"""Technical spec rows 67-75: asset adapters, publishing gates and analytics."""
from __future__ import annotations
from typing import Any
ROWS={67:'comfyui_sdxl',68:'bark_tortoise_tts',69:'meta_graph_publish',70:'x_api_v2_publish',71:'linkedin_publish',72:'publish_approval_queue',73:'daily_engagement_ingestion',74:'evidence_grounded_improvements',75:'caption_ab_test'}
def need(d,*ks):
 m=[k for k in ks if k not in d or d[k] in ('',None)];
 if m:raise ValueError('missing required fields: '+', '.join(m))
def run(row:int,d:dict[str,Any]):
 if row not in ROWS:raise ValueError('unsupported row')
 if row==67:need(d,'workflow','prompt','output_spec');r={'adapter':'ComfyUI/SDXL','workflow':d['workflow'],'prompt':d['prompt'],'negative_prompt':d.get('negative_prompt'),'seed':d.get('seed'),'output_spec':d['output_spec'],'asset_generated':False,'provenance_required':True}
 elif row==68:need(d,'engine','text','voice','output_spec');
 elif row in {69,70,71}:need(d,'content_id','account_id','approval');r={'platform':{69:'Meta Graph API',70:'X API v2',71:'LinkedIn API'}[row],'content_id':d['content_id'],'account_id':d['account_id'],'approval_id':d['approval'].get('id'),'approval_status':d['approval'].get('status'),'publish_allowed':d['approval'].get('status')=='approved','published':False,'idempotency_key':d.get('idempotency_key')}
 elif row==72:need(d,'effect','approval');r={'effect':d['effect'],'approval':d['approval'],'queued':d['approval'].get('status')!='approved','executable':d['approval'].get('status')=='approved','reverify_at_execution':True}
 elif row==73:need(d,'date','platform','metrics');r={'date':d['date'],'platform':d['platform'],'metrics':d['metrics'],'metric_keys':sorted(d['metrics']),'source_snapshot_id':d.get('source_snapshot_id'),'daily_granularity':True}
 elif row==74:need(d,'snapshots');valid=[x for x in d['snapshots'] if x.get('timestamp') and x.get('metrics')];r={'suggestions':[{'suggestion':x.get('suggestion'),'evidence_snapshot_ids':x.get('evidence_snapshot_ids',[]),'grounded':bool(x.get('evidence_snapshot_ids'))} for x in d.get('candidates',[])],'snapshot_count':len(valid),'causal_claim_forbidden':True}
 elif row==75:need(d,'variants','primary_metric','approval');r={'variants':d['variants'],'primary_metric':d['primary_metric'],'allocation':d.get('allocation',[1/len(d['variants'])]*len(d['variants'])),'proposal_only':True,'execution_allowed':d['approval'].get('status')=='approved','winner':None}
 if row==68:r={'adapter':d['engine'],'text':d['text'],'voice':d['voice'],'output_spec':d['output_spec'],'audio_generated':False,'voice_rights_confirmed':bool(d.get('voice_rights_confirmed'))}
 return {'row':row,'requirement':ROWS[row],'result':r,'external_effect_performed':False}
