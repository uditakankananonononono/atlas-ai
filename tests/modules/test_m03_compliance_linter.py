from app.modules.m03_grant_writer.compliance import lint_proposal
def test_science_grant_linter_catches_cap_attachment_criteria_and_inputs():
 guidelines='''Maximum 100 words. Maximum USD $5,000. Required attachments: biosketch and data management plan. Evaluation criteria: Scientific merit; Reproducibility; Broader impacts'''
 proposal=('Scientific merit and reproducibility are addressed. [NEEDS INPUT: broader impacts] ')*20
 out=lint_proposal(proposal=proposal,guidelines=guidelines,budget_total=6000,attachments=['biosketch.pdf'])
 assert not out['ready']
 evidence=' '.join(out['issues'])
 assert 'limit' in evidence and 'cap' in evidence and 'data management plan' in evidence and out['unresolved_placeholders']
def test_linter_passes_explicit_rules_without_inventing_requirements():
 out=lint_proposal(proposal='Scientific merit reproducibility broader impacts with a careful computational plan.',guidelines='Maximum 200 words. Maximum $10,000. Evaluation criteria: Scientific merit; Reproducibility; Broader impacts',budget_total=5000)
 assert out['ready']
