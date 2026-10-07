from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)

def test_topic_and_outline_use_only_student_evidence_and_return_no_prose():
 evidence=[{"label":"Science club","description":"I restarted our community science club after the school lab closed.","values":["community","curiosity"]}]
 topic=client.post('/api/v1/study-abroad/essay-tools/topics',json={"prompt":"Describe your community contribution","evidence":evidence}).json()
 assert topic['candidates'][0]['label']=='Science club';assert topic['student_selects_topic'] is True;assert topic['generated_essay_prose'] is None
 outline=client.post('/api/v1/study-abroad/essay-tools/outline',json={"prompt":"Describe your community contribution","student_thesis":"I learned that access can be rebuilt collectively.","evidence":evidence}).json()
 assert outline['sections'][0]['student_evidence_options']==['Science club'];assert outline['generated_essay_prose'] is None

def test_hook_conclusion_and_clarity_are_coaching_only():
 hook=client.post('/api/v1/study-abroad/essay-tools/hook',json={"student_hook":"The locked laboratory door changed our science club.","evidence":["Our school laboratory closed and I restarted the club."]}).json()
 assert hook['overlaps_student_evidence'] is True and hook['replacement_hook'] is None and 'support_note' in hook
 conclusion=client.post('/api/v1/study-abroad/essay-tools/conclusion',json={"student_conclusion":"I now build access with my community.","thesis":"Community action can rebuild access."}).json()
 assert conclusion['checks']['student_authored'] is True and conclusion['replacement_conclusion'] is None
 clarity=client.post('/api/v1/study-abroad/essay-tools/clarity',json={"draft":"I organized the science club after our laboratory closed. I asked students what experiments they wanted and found donated supplies."}).json()
 assert clarity['revised_draft'] is None and clarity['guardrail']=='student-authored-final'


def test_clarity_review_detects_actual_repeated_terms():
    # KILL: Counter over a set made repeated_terms permanently empty.
    from app.modules.m23_study_abroad.essay_tools import EssayToolService
    out = EssayToolService().clarity_review("leadership leadership leadership leadership and more words")
    assert out['repeated_terms'] == ['leadership']

def test_conclusion_coach_flags_wholly_new_claim_and_lists_terms():
    # KILL: introduces_new_claim was hardcoded False.
    from app.modules.m23_study_abroad.essay_tools import EssayToolService
    out = EssayToolService().conclusion_coach(
        "I founded a Nobel winning company last year",
        "My robotics club taught me persistence")
    assert out['checks']['introduces_new_vocabulary'] is True
    assert 'introduces_new_claim' not in out['checks']
    assert {'nobel', 'company', 'founded'} <= set(out['new_terms_beyond_thesis'])

def test_conclusion_coach_restated_conclusion_does_not_flag():
    # Characterization: thesis-restating conclusions report no new claim.
    from app.modules.m23_study_abroad.essay_tools import EssayToolService
    out = EssayToolService().conclusion_coach(
        "Community action rebuilds access", "Community action rebuilds access")
    assert out['checks']['introduces_new_vocabulary'] is False

def test_hook_overlap_is_not_labeled_factual_support():
    # KILL: the old key implied factual support from term overlap.
    from app.modules.m23_study_abroad.essay_tools import EssayToolService
    out = EssayToolService().hook_coach("The locked laboratory door changed our club",
                                        ["Our laboratory closed"])
    assert 'supported_by_evidence' not in out
    assert out['overlaps_student_evidence'] is True
    assert 'not factual verification' in out['support_note']


def test_conclusion_novelty_basis_is_caller_visible():
    # The novelty signal is a heuristic; the output must say so, not only
    # the code comment.
    from app.modules.m23_study_abroad.essay_tools import EssayToolService
    out = EssayToolService().conclusion_coach("I founded a company", "My club taught me persistence")
    assert "vocabulary_difference_note" in out
    assert "not factual new-claim detection" in out["vocabulary_difference_note"]


def test_conclusion_negation_keeps_vocabulary_characterization():
    # Characterization of the documented limit: negation/numeric changes share
    # vocabulary with the thesis, so they do NOT flag. This is why the output
    # describes vocabulary difference, not claim detection.
    from app.modules.m23_study_abroad.essay_tools import EssayToolService
    out = EssayToolService().conclusion_coach(
        "I did not win the Nobel prize", "I won the Nobel prize")
    assert out['checks']['introduces_new_vocabulary'] is False
