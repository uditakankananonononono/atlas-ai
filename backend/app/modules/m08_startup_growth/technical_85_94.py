from typing import Any
ROWS={85:'nextjs_tailwind_landing',86:'hero_feature_waitlist',87:'supabase_waitlist',88:'workspace_review_vercel_approval',89:'template_pptx_pitch_deck',90:'pitch_slide_structure',91:'matplotlib_chart_embedding',92:'code_grounded_redoc',93:'code_grounded_manual',94:'code_grounded_technical_blog'}
def need(d,*ks):
 m=[k for k in ks if k not in d or d[k] in ('',None)];
 if m:raise ValueError('missing required fields: '+', '.join(m))
def run(row:int,d:dict[str,Any]):
 if row not in ROWS:raise ValueError('unsupported row')
 if row==85:need(d,'brief');r={'files':{'app/page.tsx':'generated static component','app/globals.css':'tailwind styles'},'brief':d['brief'],'framework':'Next.js','styling':'Tailwind','static_export':True,'built':False}
 elif row==86:need(d,'hero','features','waitlist');r={'sections':[{'type':'hero','content':d['hero']},{'type':'features','content':d['features']},{'type':'waitlist','content':d['waitlist']}],'required_sections_present':True}
 elif row==87:need(d,'table','email_field','consent_field');r={'provider':'Supabase','table':d['table'],'email_field':d['email_field'],'consent_field':d['consent_field'],'rls_required':True,'service_role_exposed_to_browser':False,'collection_performed':False}
 elif row==88:need(d,'workspace_files','approval');r={'workspace_files':d['workspace_files'],'reviewable':bool(d['workspace_files']),'approval':d['approval'],'vercel_push_allowed':d['approval'].get('status')=='approved','pushed':False}
 elif row==89:need(d,'template','slides');r={'format':'pptx','template':d['template'],'slides':d['slides'],'editable':True,'rendered':False}
 elif row==90:need(d,'slides');required=['problem','solution','market','traction','ask'];types=[x.get('type') for x in d['slides']];r={'slides':d['slides'],'missing_required': [x for x in required if x not in types],'correct_order':all(types.index(a)<types.index(b) for a,b in zip(required,required[1:])) if all(x in types for x in required) else False}
 elif row==91:need(d,'chart_spec','data','slide_id');r={'engine':'matplotlib','chart_spec':d['chart_spec'],'data':d['data'],'slide_id':d['slide_id'],'alt_text':d.get('alt_text'),'rendered':False,'embedded':False}
 elif row in {92,93,94}:need(d,'source_revision','code_symbols');kind={92:'ReDoc API documentation',93:'user manual',94:'technical blog'}[row];r={'kind':kind,'source_revision':d['source_revision'],'code_symbols':d['code_symbols'],'claims':[dict(x,grounded=bool(x.get('symbol_ref'))) for x in d.get('claims',[])],'ungrounded_claims':[x for x in d.get('claims',[]) if not x.get('symbol_ref')],'published':False}
 return {'row':row,'requirement':ROWS[row],'result':r,'external_effect_performed':False}
