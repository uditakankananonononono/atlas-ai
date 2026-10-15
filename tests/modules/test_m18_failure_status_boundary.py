"""M18 bounded numeric status boundary. All diagnostics are synthetic."""
import unittest
from dataclasses import asdict
from unittest.mock import patch
from urllib.error import HTTPError
from app.modules.m18_side_hustle_scraper.lane_models import CollectionError, FetchPolicy
from app.modules.m18_side_hustle_scraper.lane_http import HttpError, UrllibHttpClient

class StatusBoundary(unittest.TestCase):
 def test_untrusted_status_does_not_bypass_record_redaction(self):
  marker='SYNTHETIC_DIAGNOSTIC_SENTINEL'
  e=CollectionError('audit','https://example.invalid/path','blocked',marker)
  self.assertIsNone(e.status)
  self.assertNotIn(marker,repr(e))
  self.assertNotIn(marker,repr(asdict(e)))
 def test_untrusted_status_does_not_bypass_exception_redaction(self):
  marker='SYNTHETIC_DIAGNOSTIC_SENTINEL'
  e=HttpError('https://example.invalid/',marker,'blocked')
  self.assertIsNone(e.status)
  self.assertNotIn(marker,str(e))
  self.assertNotIn(marker,repr(vars(e)))
 def test_invalid_status_types_and_bounds(self):
  class Number(int): pass
  for x in [True,False,200.0,Number(200),[],{},99,600,-1,10**10000]:
   with self.subTest(kind=type(x).__name__):
    self.assertIsNone(CollectionError('audit','https://example.invalid/','blocked',x).status)
    self.assertIsNone(HttpError('https://example.invalid/',x,'blocked').status)
 def test_hostile_status_is_never_formatted(self):
  class Diagnostic:
   def __str__(self):raise AssertionError('status must not be formatted')
   def __repr__(self):raise AssertionError('status must not be represented')
  x=Diagnostic()
  self.assertIsNone(CollectionError('audit','https://example.invalid/','blocked',x).status)
  self.assertIsNone(HttpError('https://example.invalid/',x,'blocked').status)
 def test_valid_http_statuses_and_none_preserved(self):
  for x in [None,100,200,304,400,429,500,508,599]:
   with self.subTest(status=x):
    self.assertEqual(CollectionError('audit','https://example.invalid/','blocked',x).status,x)
    self.assertEqual(HttpError('https://example.invalid/',x,'blocked').status,x)
 def test_actual_urllib_error_path_normalizes_before_raise(self):
  class Opener:
   def open(self,*args,**kwargs):
    raise HTTPError('https://example.invalid/private', 'SYNTHETIC_STATUS', 'SYNTHETIC_REASON', {},None)
  with patch('urllib.request.build_opener',return_value=Opener()):
   with self.assertRaises(HttpError) as caught:
    UrllibHttpClient().fetch('https://example.invalid/private',policy=FetchPolicy())
  e=caught.exception
  self.assertIsNone(e.status)
  self.assertNotIn('SYNTHETIC',str(e))
  self.assertIsNone(e.__context__)
  self.assertIsNone(e.__cause__)
if __name__=='__main__':unittest.main()
