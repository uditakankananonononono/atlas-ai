from dataclasses import asdict
from app.modules.m18_side_hustle_scraper.lane_models import CollectionError
from app.modules.m18_side_hustle_scraper.lane_http import HttpError

def test_every_http_boundary_and_adjacent_integer():
 for x in range(-10,611):
  expected=x if 100<=x<=599 else None
  assert CollectionError('audit','https://example.org/','blocked',x).status==expected
  assert HttpError('https://example.org/',x,'blocked').status==expected

def test_object_hooks_never_touched_and_pickle_free_record():
 class Hostile:
  def __str__(self):raise AssertionError('str')
  def __repr__(self):raise AssertionError('repr')
  def __eq__(self,other):raise AssertionError('eq')
  def __int__(self):raise AssertionError('int')
 x=Hostile();r=CollectionError('audit','https://user:sentinel@example.org/private?q=sentinel','sentinel',x);e=HttpError('https://user:sentinel@example.org/private?q=sentinel',x,'sentinel')
 assert r.status is None and e.status is None
 assert 'sentinel' not in repr(asdict(r)) and 'sentinel' not in str(e)
