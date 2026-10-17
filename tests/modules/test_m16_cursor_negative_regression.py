"""Desired safety pin: out-of-range negative cursor must fail before stream."""
import unittest
from fastapi import HTTPException
from app.modules.m16_executive_dashboard import routes
class Request:
 headers={}
 async def is_disconnected(self):return False
class NegativeCursor(unittest.IsolatedAsyncioTestCase):
 async def test_cursor_below_int64_refused_before_stream(self):
  with self.assertRaises(HTTPException) as caught:await routes.live(Request(),-(2**63)-1,object())
  self.assertEqual(caught.exception.status_code,422)
