from datetime import datetime, timedelta, timezone
import pytest
from app.modules.m25_knowledge_copilot.schemas import *
from app.modules.m25_knowledge_copilot.service import Repository,Service

def setup(redactions=None):
 s=Service(Repository());v=s.start_capture('tenant-a','actor-a',CaptureStart(device_id='pc-pair-1',selected_screen_ids=['screen-2'],redactions=redactions or []));return s,v.id

def ingest(s,sid,source=SourceKind.SCREEN_OCR,content='fact',ref='doc:1',**kw):return s.ingest('tenant-a','actor-a',sid,IngestEvent(source=source,content=content,source_ref=ref,screen_id='screen-2' if source==SourceKind.SCREEN_OCR else None,**kw))

def test_m25_17_selected_screen_redaction_and_tenant_actor_isolation():
 s,sid=setup([Redaction(pattern=r'secret-\d+')]); item=ingest(s,sid,content='visible secret-123')
 assert item.content=='visible [REDACTED]' and s.view('tenant-a','actor-a',sid).indicator_visible
 with pytest.raises(KeyError):s.view('tenant-a','actor-b',sid)
 with pytest.raises(PermissionError):s.ingest('tenant-a','actor-a',sid,IngestEvent(source='screen_ocr',content='x',source_ref='r',screen_id='screen-1'))

def test_m25_18_pause_stop_consent_indicator_and_bounded_audio_retention():
 s,sid=setup();s.start_audio('tenant-a','actor-a',sid,AudioStart(sources={'mic','system_audio'},consent=True,max_buffer_seconds=10))
 t=datetime.now(timezone.utc); old=ingest(s,sid,SourceKind.MIC,'old','mic:1',observed_at=t-timedelta(seconds=11));ingest(s,sid,SourceKind.MIC,'new','mic:2',observed_at=t)
 v=s.view('tenant-a','actor-a',sid);assert v.audio_consent_indicator and old.id not in {x.id for x in v.timeline}
 s.recording_state('tenant-a','actor-a',sid,CaptureState.PAUSED)
 with pytest.raises(RuntimeError):ingest(s,sid)
 v=s.recording_state('tenant-a','actor-a',sid,CaptureState.STOPPED);assert not v.indicator_visible and not v.audio_consent_indicator

def test_m25_19_timeline_fuses_ocr_audio_and_knowledge_with_source_refs():
 s,sid=setup();s.start_audio('tenant-a','actor-a',sid,AudioStart(sources={'mic'},consent=True,max_buffer_seconds=60))
 for kind,ref in [(SourceKind.SCREEN_OCR,'screen:slide-3'),(SourceKind.MIC,'mic:00:12'),(SourceKind.KNOWLEDGE,'kb:policy')]:ingest(s,sid,kind,kind.value,ref)
 assert [(x.source,x.source_ref) for x in s.view('tenant-a','actor-a',sid).timeline]==[(SourceKind.SCREEN_OCR,'screen:slide-3'),(SourceKind.MIC,'mic:00:12'),(SourceKind.KNOWLEDGE,'kb:policy')]

def test_m25_20_meeting_copilot_is_source_cited_draft_only():
 s,sid=setup();item=ingest(s,sid,content='deadline is Friday',ref='meeting:12:03')
 out=s.copilot('tenant-a','actor-a',sid,CopilotRequest(mode='meeting',prompt='suggest follow-up',citation_item_ids=[item.id]));assert out.status=='draft' and out.citations[0].source_ref=='meeting:12:03'

def test_m25_21_study_hints_preserve_learner_work_and_refuse_live_exam():
 s,sid=setup();item=ingest(s,sid,content='Pythagorean theorem',ref='book:p44')
 hint=s.copilot('tenant-a','actor-a',sid,CopilotRequest(mode='study',prompt='help me reason',citation_item_ids=[item.id]));assert hint.learner_work_preserved and hint.content.startswith('Hint:')
 refused=s.copilot('tenant-a','actor-a',sid,CopilotRequest(mode='study',prompt='answer this proctored exam question',citation_item_ids=[item.id]));assert refused.refused and refused.reason=='live_assessment_context' and not refused.citations

def test_m25_22_research_claim_evidence_has_complete_citation_trace():
 s,sid=setup();item=ingest(s,sid,content='Revenue was 10',ref='report:p7')
 row=s.claim_table('tenant-a','actor-a',sid,[ClaimInput(claim='Revenue was 10',evidence_item_ids=[item.id])])[0];assert row.trace_complete and row.evidence[0].quote=='Revenue was 10'

def test_m25_23_all_external_effects_require_exact_preview_approval():
 s,_=setup();calls=[];r=s.propose('tenant-a','actor-a',ApprovalRequest(action='purchase',destination='merchant',exact_preview='$10 for item'))
 with pytest.raises(PermissionError):s.execute('tenant-a','actor-a',r.id,lambda *x:calls.append(x))
 s.decide('tenant-a','actor-a',r.id,ApprovalDecision(approved=True));done=s.execute('tenant-a','actor-a',r.id,lambda *x:calls.append(x));assert done.executed and calls==[(ActionKind.PURCHASE,'merchant','$10 for item')]

def test_m25_24_visible_indicator_and_hash_chained_immutable_local_audit():
 s,sid=setup();ingest(s,sid);log=s.audit_log('tenant-a','actor-a');assert log[0]['prior_hash']=='GENESIS' and log[1]['prior_hash']==log[0]['hash']
 with pytest.raises(TypeError):log[0]['event']='tamper'

def test_m25_24_honest_site_or_device_failure_is_blocked_not_simulated():
 s,sid=setup();v=s.failure('tenant-a','actor-a',sid,FailureReport(component='device',reason='capture permission revoked',blocked=True));assert v.state==CaptureState.BLOCKED
 assert s.audit_log('tenant-a','actor-a')[-1]['detail']['reason']=='capture permission revoked'

def test_m25_20_cluely_parakeet_safe_feature_parity_speaker_split_languages_followups_and_actions():
 s,sid=setup();s.start_audio('tenant-a','actor-a',sid,AudioStart(sources={'mic'},consent=True,max_buffer_seconds=60))
 first=ingest(s,sid,SourceKind.MIC,'Bonjour','mic:00:01',speaker='Speaker 1',speaker_confidence=.91,language='fr')
 second=ingest(s,sid,SourceKind.MIC,'Next step is review','mic:00:04',speaker='Speaker 2',speaker_confidence=.88,language='en')
 out=s.copilot('tenant-a','actor-a',sid,CopilotRequest(mode='meeting',prompt='Suggest my response',citation_item_ids=[first.id,second.id],output_language='fr'))
 assert [x.speaker for x in s.view('tenant-a','actor-a',sid).timeline]==['Speaker 1','Speaker 2']
 assert out.status=='draft' and out.output_language=='fr' and out.follow_up_questions and out.summary and out.action_items

def test_m25_25_live_exam_context_refuses_real_time_answer_assistance():
 s,sid=setup();item=ingest(s,sid,content='Question 4',ref='screen:q4')
 for request in [
  CopilotRequest(mode='study',prompt='give the answer',citation_item_ids=[item.id],assessment_declared=True),
  CopilotRequest(mode='meeting',prompt='what should I say',citation_item_ids=[item.id],observed_context=['Lockdown Browser exam in progress']),
 ]:
  out=s.copilot('tenant-a','actor-a',sid,request);assert out.refused and out.reason=='live_assessment_context' and out.citations==[]
