"""Auditable software-development practice engines for ledger rows 685-709."""
from __future__ import annotations
import re
from collections import Counter
from typing import Any
METHODS=['example_mapping','behavior_driven_development','test_driven_development','acceptance_test_driven_development','refactoring','code_review','pair_programming','mob_programming','technical_debt_management','legacy_code_modernization','strangler_fig_pattern','branch_by_abstraction','feature_toggle','trunk_based_development','git_flow','semantic_versioning','changelog_generation','release_notes','documentation_generation','api_documentation','architecture_decision_records','code_comments','naming_conventions','code_formatting','linting']
NAMES={x:x.replace('_',' ').title() for x in METHODS}
REQUIRED={
'example_mapping':['story','rules','examples','questions'],'behavior_driven_development':['feature','scenarios'],'test_driven_development':['behavior','failing_test','minimal_change','refactor_checks'],'acceptance_test_driven_development':['acceptance_criteria','examples','stakeholders'],'refactoring':['changes','characterization_tests'],'code_review':['diff','review_checklist'],'pair_programming':['driver','navigator','task','rotation_minutes'],'mob_programming':['participants','driver','navigator','task','rotation_minutes'],'technical_debt_management':['items','scoring_model'],'legacy_code_modernization':['system','capability_slices','constraints'],'strangler_fig_pattern':['legacy_routes','replacement_routes','routing_plan'],'branch_by_abstraction':['abstraction','old_implementation','new_implementation','migration_steps'],'feature_toggle':['flags','evaluation_context'],'trunk_based_development':['branches','max_branch_age_hours','required_checks'],'git_flow':['branches','release_branch','hotfix_policy'],'semantic_versioning':['current_version','changes'],'changelog_generation':['changes','version'],'release_notes':['version','changes','audience'],'documentation_generation':['symbols','source_revision'],'api_documentation':['operations','servers'],'architecture_decision_records':['title','context','decision','consequences'],'code_comments':['code_units'],'naming_conventions':['identifiers','rules'],'code_formatting':['files','style'],'linting':['findings','ruleset']}

def _need(m,d):
 miss=[x for x in REQUIRED[m] if x not in d or d[x] is None or d[x]==''];
 if miss:raise ValueError('missing required fields: '+', '.join(miss))
def _example(d):
 linked={str(x.get('rule_id')) for x in d['examples']}; ruleids={str(x.get('id')) for x in d['rules']};return {'story':d['story'],'rules':d['rules'],'examples':d['examples'],'questions':d['questions'],'uncovered_rule_ids':sorted(ruleids-linked),'ready_for_delivery':not d['questions'] and ruleids<=linked}
def _bdd(d):
 rows=[]
 for s in d['scenarios']:
  missing=[x for x in ('given','when','then') if not s.get(x)];rows.append({**s,'missing_steps':missing,'executable':not missing})
 return {'feature':d['feature'],'scenarios':rows,'executable_count':sum(x['executable'] for x in rows),'language':'Given/When/Then'}
def _tdd(d):return {'behavior':d['behavior'],'cycle':['red','green','refactor'],'red_evidence':d['failing_test'],'green_change':d['minimal_change'],'refactor_checks':d['refactor_checks'],'red_confirmed':bool(d.get('red_confirmed')),'green_confirmed':bool(d.get('green_confirmed')),'cycle_complete':bool(d.get('red_confirmed') and d.get('green_confirmed') and d['refactor_checks'])}
def _atdd(d):
 return {'criteria':d['acceptance_criteria'],'examples':d['examples'],'stakeholders':d['stakeholders'],'agreed_by':d.get('agreed_by',[]),'executable_before_implementation':True,'agreement_complete':set(d['stakeholders'])<=set(d.get('agreed_by',[]))}
def _refactor(d):return {'changes':d['changes'],'behavior_preservation_tests':d['characterization_tests'],'tests_pass_before':bool(d.get('tests_pass_before')),'tests_pass_after':bool(d.get('tests_pass_after')),'behavior_preserved':bool(d.get('tests_pass_before') and d.get('tests_pass_after')),'new_behavior_allowed':False}
def _review(d):
 checklist=d['review_checklist'];findings=d.get('findings',[]);return {'diff':d['diff'],'checklist':checklist,'findings':findings,'unresolved_blockers':[x for x in findings if x.get('severity')=='blocking' and x.get('status')!='resolved'],'approval':d.get('approval'),'self_approval_forbidden':True}
def _pair(d,mob=False):return {'mode':'mob' if mob else 'pair','driver':d['driver'],'navigator':d['navigator'],'participants':d.get('participants',[d['driver'],d['navigator']]),'task':d['task'],'rotation_minutes':int(d['rotation_minutes']),'next_driver':d.get('participants',[d['navigator']])[0],'shared_understanding_check':d.get('shared_understanding_check',[])}
def _debt(d):
 rows=[]
 for x in d['items']:
  impact=float(x.get('impact',0));frequency=float(x.get('frequency',0));cost=float(x.get('remediation_cost',1));score=impact*frequency/cost if cost>0 else None;rows.append({**x,'priority_score':score,'decision':x.get('decision','untriaged')})
 return {'scoring_model':d['scoring_model'],'items':sorted(rows,key=lambda x:x['priority_score'] if x['priority_score'] is not None else -1,reverse=True),'total_unowned':sum(not x.get('owner') for x in rows)}
def _legacy(d):return {'system':d['system'],'slices':[{'capability':x.get('capability'),'seam':x.get('seam'),'characterization_tests':x.get('characterization_tests',[]),'rollback':x.get('rollback'),'ready':all(x.get(k) for k in ('capability','seam','characterization_tests','rollback'))} for x in d['capability_slices']],'constraints':d['constraints'],'big_bang_forbidden':True}
def _strangler(d):
 legacy=set(d['legacy_routes']);new=set(d['replacement_routes']);plan=d['routing_plan'];migrated={x['route'] for x in plan if x.get('target')=='replacement'};return {'legacy_routes':sorted(legacy),'replacement_routes':sorted(new),'routing_plan':plan,'migrated_routes':sorted(migrated),'unmapped_replacements':sorted(new-{x['route'] for x in plan}),'rollback_per_route_required':True}
def _branch_abs(d):return {'abstraction':d['abstraction'],'implementations':{'old':d['old_implementation'],'new':d['new_implementation']},'migration_steps':d['migration_steps'],'callers_use_abstraction':bool(d.get('callers_use_abstraction')),'old_removal_allowed':bool(d.get('callers_use_abstraction') and d.get('new_verified'))}
def _flags(d):
 rows=[]
 for f in d['flags']:rows.append({**f,'safe':all(k in f for k in ('owner','default','expires_at','kill_switch')),'evaluation_context_fields':sorted(d['evaluation_context'].keys())})
 return {'flags':rows,'unsafe_flag_names':[x.get('name') for x in rows if not x['safe']],'server_authoritative':True}
def _trunk(d):
 maxage=float(d['max_branch_age_hours']);branches=[{**x,'too_old':float(x.get('age_hours',0))>maxage} for x in d['branches']];return {'branches':branches,'too_old_names':[x.get('name') for x in branches if x['too_old']],'required_checks':d['required_checks'],'direct_push_protected':True}
def _gitflow(d):return {'branches':d['branches'],'release_branch':d['release_branch'],'hotfix_policy':d['hotfix_policy'],'required_long_lived':sorted({'main','develop'}-set(d['branches'])),'release_merges_back_to_develop_required':True}
def _semver(d):
 cur=d['current_version'];m=re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?',cur)
 if not m:raise ValueError('invalid semantic version')
 level='patch'
 if any(x.get('breaking') for x in d['changes']):level='major'
 elif any(x.get('type')=='feature' for x in d['changes']):level='minor'
 a,b,c=map(int,m.groups());nxt=f'{a+1}.0.0' if level=='major' else f'{a}.{b+1}.0' if level=='minor' else f'{a}.{b}.{c+1}'
 return {'current_version':cur,'bump':level,'next_version':nxt,'changes':d['changes']}
def _changelog(d):
 groups={k:[] for k in ('added','changed','deprecated','removed','fixed','security')}
 for x in d['changes']:groups.setdefault(x.get('category','changed').lower(),[]).append(x.get('description'))
 return {'version':d['version'],'sections':groups,'unreleased':bool(d.get('unreleased')),'source_change_ids':[x.get('id') for x in d['changes']]}
def _release(d):return {'version':d['version'],'audience':d['audience'],'highlights':[x for x in d['changes'] if x.get('user_visible')],'breaking_changes':[x for x in d['changes'] if x.get('breaking')],'upgrade_steps':d.get('upgrade_steps',[]),'known_issues':d.get('known_issues',[]),'generated_from_change_ids':[x.get('id') for x in d['changes']]}
def _docs(d):
 rows=[]
 for x in d['symbols']:rows.append({'symbol':x.get('name'),'signature':x.get('signature'),'summary':x.get('doc'),'examples':x.get('examples',[]),'undocumented':not bool(x.get('doc'))})
 return {'source_revision':d['source_revision'],'symbols':rows,'undocumented_symbols':[x['symbol'] for x in rows if x['undocumented']],'generated_claims_limited_to_source':True}
def _api(d):
 rows=[]
 for x in d['operations']:
  miss=[k for k in ('method','path','summary','responses') if not x.get(k)];rows.append({**x,'missing_fields':miss,'documented':not miss})
 return {'servers':d['servers'],'operations':rows,'undocumented_operations':[f"{x.get('method')} {x.get('path')}" for x in rows if not x['documented']],'auth_schemes':d.get('auth_schemes',[])}
def _adr(d):return {'title':d['title'],'status':d.get('status','proposed'),'context':d['context'],'decision':d['decision'],'alternatives':d.get('alternatives',[]),'consequences':d['consequences'],'supersedes':d.get('supersedes'),'immutable_history_required':True}
def _comments(d):
 rows=[]
 for x in d['code_units']:
  txt=str(x.get('comment',''));rows.append({**x,'useful':bool(txt and not re.search(r'^(increment|set|get|loop)\b',txt.lower())),'why_not_what':bool(x.get('explains_why'))})
 return {'code_units':rows,'weak_unit_names':[x.get('name') for x in rows if not x['useful'] or not x['why_not_what']]}
def _names(d):
 bad=[]
 for x in d['identifiers']:
  rule=d['rules'].get(x.get('kind'));name=x.get('name','');ok=bool(re.fullmatch(rule,name)) if rule else False
  if not ok:bad.append(name)
 return {'identifiers':d['identifiers'],'rules':d['rules'],'violations':bad}
def _format(d):
 changed=[x.get('path') for x in d['files'] if x.get('before')!=x.get('after')];return {'style':d['style'],'changed_files':changed,'idempotence_required':True,'semantics_must_not_change':True}
def _lint(d):
 bysev=Counter(x.get('severity','unknown') for x in d['findings']);blocking=[x for x in d['findings'] if x.get('severity') in {'error','critical'} and not x.get('suppressed')];return {'ruleset':d['ruleset'],'counts_by_severity':dict(bysev),'blocking':blocking,'suppression_requires_reason':True,'clean':not blocking}
DISPATCH={'example_mapping':_example,'behavior_driven_development':_bdd,'test_driven_development':_tdd,'acceptance_test_driven_development':_atdd,'refactoring':_refactor,'code_review':_review,'pair_programming':lambda d:_pair(d),'mob_programming':lambda d:_pair(d,True),'technical_debt_management':_debt,'legacy_code_modernization':_legacy,'strangler_fig_pattern':_strangler,'branch_by_abstraction':_branch_abs,'feature_toggle':_flags,'trunk_based_development':_trunk,'git_flow':_gitflow,'semantic_versioning':_semver,'changelog_generation':_changelog,'release_notes':_release,'documentation_generation':_docs,'api_documentation':_api,'architecture_decision_records':_adr,'code_comments':_comments,'naming_conventions':_names,'code_formatting':_format,'linting':_lint}
def software_practice_685_709(method:str,data:dict[str,Any])->dict[str,Any]:
 if method not in METHODS:raise ValueError(f'unsupported method: {method}')
 _need(method,data);return {'method':method,'capability':NAMES[method],'result':DISPATCH[method](data),'boundary':'Prepared engineering evidence only. No merge, release, deployment, approval, or repository mutation is performed.','human_review_required':True}
