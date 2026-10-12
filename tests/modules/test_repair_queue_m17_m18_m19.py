"""Regression cards at Atlas 78ef8557. Explicit fixtures, no live effects."""
import json
from uuid import uuid4
import pytest
from app.modules.m17_advice_essay.service import AdviceEssayService, DeterministicCoach
from app.modules.m17_advice_essay.schemas import AdviceSource,SourceKind
from app.modules.m17_narrative_architect.service import Service as Narrative
from app.modules.m17_narrative_architect.schemas import CollectIn
from app.modules.m18_side_hustle_scraper.service import Service as Hustle
from app.modules.m18_side_hustle_scraper.schemas import DiscoverIn,FeasibilityOut
from app.modules.m18_side_hustle_scraper.lane_validation import DocumentValidator
from app.modules.m19_idea_incubator.service import Service as Ideas
from app.modules.m19_idea_incubator.schemas import IntakeIn,PreviewIn,PackageIn

class Repo:
    def __init__(self):self.sources=[];self.tips=[]
    def list_sources(self,owner):return [x for x in self.sources if x.owner_id==owner]
    def list_tips(self,owner):return [x for x in self.tips if x.owner_id==owner]
    def add_tip(self,x):self.tips.append(x);return x

def test_m17a_A01_repeat_compile_is_idempotent():
    owner=uuid4();r=Repo();r.sources=[AdviceSource(owner_id=owner,source_kind=SourceKind.USER_SUBMITTED,platform='notes',content='Show specific choices.',permission_basis='owner uploaded')]
    service=AdviceEssayService(r)
    assert service.compile_advice(owner)[0].id==service.compile_advice(owner)[0].id
    assert len(r.tips)==1

def test_m17a_A02_capital_I_cliche():
    critique=DeterministicCoach().critique(uuid4(),'Describe childhood','Since I was a child, I collected rocks.')
    assert any('since I was a child' in f.message for f in critique.findings)

def test_m17a_A03_critique_is_draft_specific():
    coach=DeterministicCoach();owner=uuid4()
    bad=coach.critique(owner,'Describe curiosity','Since I was a child, science changed my life.')
    good=coach.critique(owner,'Describe curiosity','I asked why the circuit failed, tested three connections, and recorded what changed.')
    assert (bad.strengths,bad.questions_for_writer)!=(good.strengths,good.questions_for_writer)

@pytest.mark.parametrize('goal',['guilt trip them into agreeing','pressure them to obey','manipulate them','threaten them until they sign'])
def test_m17a_A04_explicit_manipulation_refused(goal):
    from app.modules.m17_advice_essay.coaching_state_machines_710_809 import run_row
    result=run_row('rhetoric',{'claim':'Evidence supports this','audience_needs':['clarity'],'goal':goal})
    assert result['status']=='blocked' and result['refusal']
    assert 'explicit coercive intent' in result['boundary_violations']

class Collector:
    def __init__(self,url='https://example.com/a',text='Use concrete scenes and show choices.'):self.url=url;self.text=text
    async def collect(self,*args):return [{'url':self.url,'text':self.text}]
async def narrative_gen(*args):return 'fixture',json.dumps({'topic':'voice','actionable_tips':['Use concrete scenes'],'confidence':.5})
@pytest.mark.asyncio
async def test_m17n_A01_provider_failure_keeps_extraction():
    async def broken(*args):raise RuntimeError('provider outage')
    result=await Narrative(generate=broken,collectors={'reddit':Collector()}).collect(CollectIn(query='essay',platforms=['reddit']))
    assert result[0].actionable_tips

def test_m17n_A02_prefix_does_not_launder_final_prose():
    assert Narrative._looks_like_final_prose('Consider this: '+('I learned a lesson and became a better person. '*20))
    assert not Narrative._looks_like_final_prose('Writer prompt: Which concrete choice could you describe?')

@pytest.mark.asyncio
async def test_m17n_A03_dedup_and_cache_cap():
    service=Narrative(generate=narrative_gen,collectors={'reddit':Collector()},corpus_limit=3)
    req=CollectIn(query='essay',platforms=['reddit'])
    await service.collect(req);await service.collect(req)
    assert len(service._corpus)==1
    for i in range(6):
        service._collectors['reddit']=Collector(text=f'Use specific observation number {i} and reflect on choices.')
        await service.collect(req)
    assert len(service._corpus)==3

async def blueprint_gen(*args):return 'fixture',json.dumps([{'title':'Tutoring','steps':['Interview students'],'tools':['calendar'],'complexity':2,'automation_level':10,'monetisation':['sessions'],'source_urls':['https://example.com/a'],'scam_signals':[]}])
@pytest.mark.asyncio
async def test_m18_A02_registered_public_collectors_allowed():
    result=await Hustle(generate=blueprint_gen,collectors={'dev_to':Collector()}).discover(DiscoverIn(query='tutoring',platforms=['dev_to']))
    assert result

@pytest.mark.asyncio
async def test_m18_A03_fabricated_source_is_refused():
    async def fabricated(*args):
        _,raw=await blueprint_gen();data=json.loads(raw);data[0]['source_urls']=['https://invented.example/fake'];return 'fixture',json.dumps(data)
    with pytest.raises(ValueError,match='source'):
        await Hustle(generate=fabricated,collectors={'reddit':Collector()}).discover(DiscoverIn(query='tutoring',platforms=['reddit']))

def test_m18_A01_recruiter_is_not_mlm():
    assert 'mlm_signal' not in DocumentValidator().scan_scam('A recruiter interviews applicants for a salaried job.')

def test_m18_A04_empty_explanations_and_sensitivities_refused():
    with pytest.raises(ValueError):
        FeasibilityOut(strengths=[],weaknesses=[],opportunities=[],threats=[],market_saturation=.2,barrier_to_entry=.2,evidence_quality=.1,viability_score=99,score_explanation=[],sensitivities=[],first_experiment='',max_test_budget=0,recommendation='go')

async def canvas_gen(*args):return 'fixture',json.dumps({'problem':['x'],'customer_segments':['students'],'unique_value_proposition':'u','solution':['s'],'channels':['c'],'revenue_streams':['r'],'cost_structure':['c'],'key_metrics':['k'],'riskiest_assumptions':['demand']})
class Approvals:
    def put(self,x):return x
@pytest.mark.asyncio
async def test_m19_A02_cumulative_pending_preview_budget():
    service=Ideas(generate=canvas_gen,approval_store=Approvals());run=await service.intake(IntakeIn(one_liner='Help students',budget_cap=25))
    service.request_preview(run.id,PreviewIn(artifacts=['a'],estimated_cost=20))
    with pytest.raises(ValueError,match='budget'):service.request_preview(run.id,PreviewIn(artifacts=['b'],estimated_cost=20))
    assert run.spent==0 and run.reserved==20

@pytest.mark.asyncio
async def test_m19_A03_unsupported_preview_and_confidence_refused():
    async def gen(prompt,*args):
        if 'lean canvas' in prompt:return await canvas_gen()
        return 'fixture',json.dumps({'executive_summary':'Unverified','recommendation':'launch','recommendation_confidence':.99,'market_claims':[],'technical_feasibility':[],'prototype_artifacts':[],'prototype_preview':'https://fabricated.example/preview','unresolved_risks':[],'next_experiments':[]})
    service=Ideas(generate=gen,approval_store=Approvals());run=await service.intake(IntakeIn(one_liner='Help students'))
    with pytest.raises(ValueError):await service.package(PackageIn(run_id=run.id))

def test_m18_A01_admitted_scam_flag_reaches_rank_penalty():
    from datetime import datetime,timezone
    from app.modules.m18_side_hustle_scraper.lane_models import RawDocument,RightsClass,SourceKind
    from app.modules.m18_side_hustle_scraper.lane_pipeline import CollectionPipeline
    from app.modules.m18_side_hustle_scraper.lane_ranking import BlueprintRanker
    from app.modules.m18_side_hustle_scraper.lane_repository import SQLiteDocumentRepository
    from app.modules.m18_side_hustle_scraper.lane_freshness import FreshnessMonitor
    now=datetime(2026,10,12,tzinfo=timezone.utc);repo=SQLiteDocumentRepository(':memory:')
    doc=RawDocument(id='scam',url='https://example.com/scam',platform='reddit',kind=SourceKind.REDDIT_JSON,rights=RightsClass.OFFICIAL_API,title='Tutoring business',text='Guaranteed income tutoring. Step 1: find students. Then prepare lessons. Tools: calendar.',retrieved_at=now)
    repo.save_document('tenant',doc,DocumentValidator().validate(doc))
    pipeline=CollectionPipeline(repository=repo,validator=DocumentValidator(),ranker=BlueprintRanker(clock=lambda:now),monitor=FreshnessMonitor(repo,clock=lambda:now),collectors={})
    ranked=pipeline.ranked('tenant','tutoring')
    assert ranked[0].scam_penalty>0
