import itertools
import pytest
from app.modules.m20_general_cognitive_worker.interleaved_practice import interleave

def run(skills):return interleave({'practice_items':[{'id':str(i),'skill':s,'task':'real '+s} for i,s in enumerate(skills)]})


def test_balanced_catalog_uses_all_exercises_without_repeating_skill():
 r=run(['a','a','a','b','b','c']);assert r['avoids_same_skill_runs']
 assert len(r['exercises'])==6 and set(e['id'] for e in r['exercises'])==set(map(str,range(6)))
 assert all(a!=b for a,b in zip(r['sequence'],r['sequence'][1:]))


def test_imbalance_report_does_not_assert_false_variety_or_drop_items():
 r=run(['a','a','a','a','b'])
 assert not r['avoids_same_skill_runs'] and r['status']=='catalog_imbalance_requires_repeats'
 assert len(r['exercises'])==5 and r['adjacent_repeat_positions']


def test_small_multisets_match_exact_no_repeat_feasibility():
 for counts in itertools.product(range(1,5),repeat=3):
  skills=sum(([s]*n for s,n in zip('abc',counts)),[]);r=run(skills)
  assert r['avoids_same_skill_runs']==(max(counts)<=sum(counts)-max(counts)+1)
  assert len(r['exercises'])==sum(counts)


def test_duplicate_exercises_and_missing_catalog_rejected():
 with pytest.raises(ValueError):interleave({'practice_items':[{'id':'a','skill':'x','task':'one'},{'id':'a','skill':'y','task':'two'}]})
 with pytest.raises(ValueError):interleave({'skills':['a','b']})
