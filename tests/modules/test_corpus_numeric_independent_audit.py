from itertools import permutations
from app.modules.m20_general_cognitive_worker.corpus_semantics import SemanticHit,_rank_hits

def test_anchored_band_reference_all_input_orders():
 values=[('a',.8-1.5e-12),('z',.8),('b',.8-.75e-12),('c',.4)]
 for order in permutations(values):
  remaining={k:v for k,v in order};expected=[]
  while remaining:
   highest=max(remaining.values());band=sorted(k for k,v in remaining.items() if highest-v<=1e-12)
   expected.extend(band)
   for k in band:del remaining[k]
  hits=[SemanticHit(k,'text',v) for k,v in order]
  ranked=_rank_hits(hits)
  assert [h.id for h in ranked]==expected
  assert dict((h.id,h.score) for h in ranked)==dict(values)

def test_tolerance_inclusive_exact_binary_boundary():
 # Near zero absolute1e-12 difference is exactly represented by the same float.
 hits=[SemanticHit('z','',1e-12),SemanticHit('a','',0.),SemanticHit('b','',-1e-12)]
 assert [h.id for h in _rank_hits(hits)]==['a','z','b']
