from app.reports import claim_status as m

def test_mismatched_fence_not_closing():
 text='````python\n~~~\nCLAIM: hidden [VERIFIED]\n````\nCLAIM: outside [UNVERIFIED]'
 assert [c.text for c in m.extract_claims(text)]==['outside [UNVERIFIED]']
def test_shorter_fence_not_closing():
 text='````\n```\nCLAIM: hidden [VERIFIED]\n````\nCLAIM: outside [UNVERIFIED]'
 assert [c.text for c in m.extract_claims(text)]==['outside [UNVERIFIED]']
def test_two_label_columns_conflict():
 r=m.check_text('| Claim | Label | Status |\n|---|---|---|\n| x | VERIFIED | UNVERIFIED |')
 assert not r['ok']
def test_marker_unknown_plus_known():
 r=m.check_text('CLAIM: x [UNKNOWN] [VERIFIED]')
 assert not r['ok']
