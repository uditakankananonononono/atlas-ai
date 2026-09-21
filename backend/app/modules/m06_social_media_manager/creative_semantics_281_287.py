"""Deterministic semantic checks for creative rows 281-287.

These checks turn LLM-authored draft sections into inspectable discipline-specific
invariants. They do not render assets and they fail closed on malformed domain data.
"""
from __future__ import annotations
import re
from typing import Any
class CreativeSemanticError(ValueError):pass
def _hex(v):
 if not isinstance(v,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',v):raise CreativeSemanticError('color must be #RRGGBB')
 return tuple(int(v[i:i+2],16)/255 for i in (1,3,5))
def _lum(v):
 def f(x):return x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4
 r,g,b=_hex(v);return .2126*f(r)+.7152*f(g)+.0722*f(b)
def _contrast(a,b):
 x,y=sorted((_lum(a),_lum(b)),reverse=True);return round((x+.05)/(y+.05),3)
def validate(slug:str,sections:dict[str,Any])->dict[str,Any]:
 if slug=='color-theory':
  palette=sections.get('palette');pairs=sections.get('accessibility_pairs')
  if not isinstance(palette,list) or len(palette)<2 or not isinstance(pairs,list) or not pairs:raise CreativeSemanticError('palette and accessibility_pairs required')
  roles={x.get('role'):x.get('hex') for x in palette};results=[]
  for p in pairs:
   if p.get('foreground') not in roles or p.get('background') not in roles:raise CreativeSemanticError('contrast pair uses unknown role')
   ratio=_contrast(roles[p['foreground']],roles[p['background']]);results.append({**p,'ratio':ratio,'wcag_aa_normal':ratio>=4.5})
  return {'palette_roles':sorted(roles),'contrast_results':results}
 if slug=='composition':
  grid=sections.get('grid');hier=sections.get('visual_hierarchy')
  if not isinstance(grid,dict) or int(grid.get('columns',0))<1 or not isinstance(hier,list) or len(set(hier))!=len(hier):raise CreativeSemanticError('valid grid and unique hierarchy required')
  return {'grid_columns':int(grid['columns']),'hierarchy_count':len(hier),'white_space_token':grid.get('gutter')}
 if slug=='typography':
  scale=sections.get('scale');faces=sections.get('typefaces')
  if not isinstance(scale,list) or len(scale)<2 or any(float(b)<=float(a) for a,b in zip(scale,scale[1:])) or not isinstance(faces,dict):raise CreativeSemanticError('ascending numeric scale and typeface roles required')
  return {'scale_ratio':round(float(scale[1])/float(scale[0]),3),'roles':sorted(faces),'has_fallbacks':bool(sections.get('fallbacks'))}
 if slug=='logo-design':
  concepts=sections.get('concepts')
  if not isinstance(concepts,list) or len(concepts)<2 or any(not x.get('symbolism') or not x.get('construction') for x in concepts):raise CreativeSemanticError('at least two constructed concepts required')
  return {'concept_count':len(concepts),'all_originality_attested':all(bool(x.get('originality_attested')) for x in concepts),'clear_space_defined':bool(sections.get('clear_space'))}
 if slug=='brand-identity':
  elements=sections.get('elements');rules=sections.get('application_rules')
  if not isinstance(elements,list) or not isinstance(rules,dict) or not {'social','print','product'}<=set(rules):raise CreativeSemanticError('elements and social/print/product rules required')
  return {'element_ids':sorted(x.get('id') for x in elements),'surface_coverage':sorted(rules),'governance_defined':bool(sections.get('governance'))}
 if slug=='packaging-design':
  panels=sections.get('panel_layout');materials=sections.get('materials')
  if not isinstance(panels,list) or not {'front','back'}<={x.get('panel') for x in panels} or not isinstance(materials,list):raise CreativeSemanticError('front/back panels and materials required')
  return {'panels':sorted(x['panel'] for x in panels),'materials_count':len(materials),'dieline_status':'described_not_drawn'}
 if slug=='ui-ux-design':
  screens=sections.get('screens');components=sections.get('components');states=sections.get('states')
  required={'default','hover','disabled','loading','error','empty'}
  if not isinstance(screens,list) or not screens or not isinstance(components,list) or not required<=set(states or []):raise CreativeSemanticError('screens, components and all interaction states required')
  return {'screen_ids':sorted(x.get('id') for x in screens),'component_count':len(components),'state_coverage':sorted(required),'usability_notes_present':bool(sections.get('usability_notes'))}
 raise CreativeSemanticError('semantic validation only supports rows 281-287')
