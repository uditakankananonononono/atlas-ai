import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.modules.m20_general_cognitive_worker.software_practice_685_709 import METHODS,REQUIRED,software_practice_685_709
from app.modules.m20_general_cognitive_worker.routes import router
S=software_practice_685_709

def data(m):
 d={k:k for k in REQUIRED[m]}
 vals={'rules':[{'id':'r'}],'examples':[{'rule_id':'r','given':'g','when':'w','then':'t'}],'questions':['q'],'scenarios':[{'given':'g','when':'w','then':'t'}],'refactor_checks':['tests'],'acceptance_criteria':['c'],'stakeholders':['po'],'changes':[{'id':'1','category':'Added','description':'x','type':'feature','user_visible':True}],'characterization_tests':['t'],'review_checklist':['correctness'],'participants':['a','b'],'items':[{'impact':4,'frequency':2,'remediation_cost':2,'owner':'o'}],'capability_slices':[{'capability':'x','seam':'api','characterization_tests':['t'],'rollback':'old'}],'constraints':['uptime'],'legacy_routes':['/a'],'replacement_routes':['/a'],'routing_plan':[{'route':'/a','target':'replacement'}],'migration_steps':['introduce'],'flags':[{'name':'x','owner':'o','default':False,'expires_at':'2027','kill_switch':True}],'evaluation_context':{'tenant':'t'},'branches':[{'name':'x','age_hours':2}],'required_checks':['test'],'operations':[{'method':'GET','path':'/x','summary':'x','responses':{'200':'ok'}}],'servers':['https://x'],'consequences':['c'],'code_units':[{'name':'x','comment':'Because protocol requires ordering','explains_why':True}],'identifiers':[{'name':'good_name','kind':'variable'}],'files':[{'path':'a.py','before':'x','after':'x'}],'findings':[{'severity':'warning'}]}
 for k,v in vals.items():
  if k in d:d[k]=v
 nums={'rotation_minutes':15,'max_branch_age_hours':24};
 for k,v in nums.items():
  if k in d:d[k]=v
 if m=='example_mapping':d.update(story='As user',questions=[])
 if m=='behavior_driven_development':d['feature']='login'
 if m=='test_driven_development':d.update(behavior='x',failing_test='fails',minimal_change='return x')
 if m=='acceptance_test_driven_development':d['agreed_by']=['po']
 if m=='code_review':d['diff']='+x'
 if m in {'pair_programming','mob_programming'}:d.update(driver='a',navigator='b',task='x')
 if m=='technical_debt_management':d['scoring_model']='impact*frequency/cost'
 if m=='legacy_code_modernization':d['system']='legacy'
 if m=='branch_by_abstraction':d.update(abstraction='I',old_implementation='old',new_implementation='new')
 if m=='git_flow':d.update(branches=['main','develop'],release_branch='release/1',hotfix_policy='from main')
 if m=='semantic_versioning':d.update(current_version='1.2.3')
 if m=='changelog_generation':d['version']='1.3.0'
 if m=='release_notes':d.update(version='1.3.0',audience='users')
 if m=='documentation_generation':d.update(symbols=[{'name':'f','signature':'f()','doc':'does f'}],source_revision='abc')
 if m=='architecture_decision_records':d.update(title='Use DB',context='need storage',decision='Postgres')
 if m=='naming_conventions':d['rules']={'variable':r'[a-z_][a-z0-9_]*'}
 if m=='code_formatting':d['style']='black'
 if m=='linting':d['ruleset']='ruff'
 return d

def test_exact_rows():assert len(METHODS)==25 and len(set(METHODS))==25
@pytest.mark.parametrize('m',METHODS)
def test_each_row_substantive_output(m):
 o=S(m,data(m));assert o['method']==m and o['result'] and o['human_review_required']
@pytest.mark.parametrize('m',METHODS)
def test_each_row_rejects_missing_required_field(m):
 d=data(m);d.pop(REQUIRED[m][0]);
 with pytest.raises(ValueError,match='missing required'):S(m,d)
def test_685_example_mapping_coverage():assert S('example_mapping',data('example_mapping'))['result']['ready_for_delivery']
def test_686_bdd_missing_given_not_executable():
 d=data('behavior_driven_development');d['scenarios']=[{'when':'w','then':'t'}];assert not S('behavior_driven_development',d)['result']['scenarios'][0]['executable']
def test_687_tdd_requires_observed_red_and_green():
 d=data('test_driven_development');assert not S('test_driven_development',d)['result']['cycle_complete'];d.update(red_confirmed=True,green_confirmed=True);assert S('test_driven_development',d)['result']['cycle_complete']
def test_688_atdd_stakeholder_agreement():assert S('acceptance_test_driven_development',data('acceptance_test_driven_development'))['result']['agreement_complete']
def test_689_refactoring_behavior_preservation():
 d=data('refactoring');d.update(tests_pass_before=True,tests_pass_after=True);assert S('refactoring',d)['result']['behavior_preserved']
def test_690_review_blocks_unresolved_finding():
 d=data('code_review');d['findings']=[{'severity':'blocking','status':'open'}];assert len(S('code_review',d)['result']['unresolved_blockers'])==1
@pytest.mark.parametrize('m,mode',[('pair_programming','pair'),('mob_programming','mob')])
def test_691_692_collaboration_modes(m,mode):assert S(m,data(m))['result']['mode']==mode
def test_693_debt_priority():assert S('technical_debt_management',data('technical_debt_management'))['result']['items'][0]['priority_score']==4
def test_694_legacy_slice_ready():assert S('legacy_code_modernization',data('legacy_code_modernization'))['result']['slices'][0]['ready']
def test_695_strangler_route_migration():assert S('strangler_fig_pattern',data('strangler_fig_pattern'))['result']['migrated_routes']==['/a']
def test_696_branch_abstraction_removal_gate():
 d=data('branch_by_abstraction');assert not S('branch_by_abstraction',d)['result']['old_removal_allowed']
def test_697_toggle_requires_owner_expiry_kill_switch():
 d=data('feature_toggle');d['flags']=[{'name':'bad','default':False}];assert S('feature_toggle',d)['result']['unsafe_flag_names']==['bad']
def test_698_trunk_branch_age():
 d=data('trunk_based_development');d['branches']=[{'name':'old','age_hours':30}];assert S('trunk_based_development',d)['result']['too_old_names']==['old']
def test_699_gitflow_requires_main_develop():
 d=data('git_flow');d['branches']=['main'];assert S('git_flow',d)['result']['required_long_lived']==['develop']
def test_700_semver_breaking_bumps_major():
 d=data('semantic_versioning');d['changes']=[{'breaking':True}];assert S('semantic_versioning',d)['result']['next_version']=='2.0.0'
def test_700_semver_rejects_invalid():
 d=data('semantic_versioning');d['current_version']='v1';
 with pytest.raises(ValueError):S('semantic_versioning',d)
def test_701_changelog_sections():assert S('changelog_generation',data('changelog_generation'))['result']['sections']['added']==['x']
def test_702_release_notes_user_visible():assert len(S('release_notes',data('release_notes'))['result']['highlights'])==1
def test_703_docs_reports_undocumented():
 d=data('documentation_generation');d['symbols']=[{'name':'x'}];assert S('documentation_generation',d)['result']['undocumented_symbols']==['x']
def test_704_api_docs_missing_responses():
 d=data('api_documentation');d['operations']=[{'method':'GET','path':'/x','summary':'x'}];assert S('api_documentation',d)['result']['undocumented_operations']==['GET /x']
def test_705_adr_immutable_history():assert S('architecture_decision_records',data('architecture_decision_records'))['result']['immutable_history_required']
def test_706_comments_explain_why():assert S('code_comments',data('code_comments'))['result']['weak_unit_names']==[]
def test_707_naming_regex_violation():
 d=data('naming_conventions');d['identifiers']=[{'name':'BadName','kind':'variable'}];assert S('naming_conventions',d)['result']['violations']==['BadName']
def test_708_formatting_semantics_guard():assert S('code_formatting',data('code_formatting'))['result']['semantics_must_not_change']
def test_709_lint_blocking_errors():
 d=data('linting');d['findings']=[{'severity':'error'}];assert not S('linting',d)['result']['clean']
def test_route_mounted_and_negative_path():
 app=FastAPI();app.include_router(router);c=TestClient(app)
 assert c.post('/api/modules/20/software-practice/685-709/analyze',json={'method':'semantic_versioning','data':data('semantic_versioning')}).status_code==200
 assert c.post('/api/modules/20/software-practice/685-709/analyze',json={'method':'semantic_versioning','data':{}}).status_code==422
