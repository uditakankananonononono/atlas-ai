import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/knowledge_trace1458.py'
s=importlib.util.spec_from_file_location('unicode1458',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class UnicodePins(unittest.TestCase):
 def test_seven_named_unicode_refusals(self):
  for code in [0x85,0x2028,0x2029,0x202E,0x200B,0xFEFF,0x7F]:
   with self.subTest(code=hex(code)):
    value='a'+chr(code)+'b'
    with self.assertRaises(m.KnowledgeTraceError) as cm:m._text(value,'source_field')
    self.assertIn('source_field',str(cm.exception));self.assertNotIn(value,str(cm.exception))
 def test_all_named_ranges_refuse(self):
  for code in list(range(0x200B,0x2010))+list(range(0x202A,0x202F))+list(range(0x2066,0x206A))+[0,31,0x9F]:
   with self.subTest(code=hex(code)),self.assertRaises(m.KnowledgeTraceError):m._text('a'+chr(code)+'b','source_field')
 def test_spaces_printable_nonascii_and_length_edges(self):
  for value in ['a b','café','日本語','தமிழ்','a'+chr(0xA0)+'b']:
   self.assertEqual(m._text(value,'source_field'),value)
  self.assertEqual(m._text('x'*10,'source_field',10),'x'*10)
  with self.assertRaises(m.KnowledgeTraceError):m._text('x'*11,'source_field',10)
 def test_raw_oversize_does_not_strip(self):
  class NoStrip(str):
   def strip(self,*args,**kwargs):raise AssertionError('strip allocation before cap')
  for value in [NoStrip('x'*11),NoStrip('x'*(10*1024*1024))]:
   with self.assertRaises(m.KnowledgeTraceError):m._text(value,'source_field',10)
 def test_length_cap_precedes_unicode_scan(self):
  with patch.object(m.unicodedata,'category',side_effect=AssertionError('scan ran before length refusal')):
   with self.assertRaises(m.KnowledgeTraceError):m._text('x'*11,'source_field',10)
if __name__=='__main__':unittest.main()
