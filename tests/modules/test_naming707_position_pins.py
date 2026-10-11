"""Replacement-owner position pins; synthetic AST cases labeled explicitly."""
import ast
import importlib.util
from pathlib import Path
import re
import unittest
from unittest import mock

CORE=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/naming_checker707.py'
s=importlib.util.spec_from_file_location('position_pins',CORE);n=importlib.util.module_from_spec(s);s.loader.exec_module(n)

class PositionPins(unittest.TestCase):
 def test_initial_and_exact_fallback_count_spans(self):
  src=n._Source('abc\nxyz')
  self.assertEqual(src.unverified,0)
  self.assertEqual(src.locate(re.compile(r'(nope)'),1,0,'abc'),('abc',1,1,1,4))
  self.assertEqual(src.unverified,1)
  self.assertEqual(src.locate(re.compile(r'(xyz)'),2,0,'different'),('different',2,1,2,10))
  self.assertEqual(src.unverified,2)
  self.assertEqual(src.locate(re.compile(r'(xyz)'),2,0,'xyz'),('xyz',2,1,2,4))
  self.assertEqual(src.unverified,2)
 def test_public_exact_position_count_and_nfkc(self):
  rules={'rules':[{'id':'r','kinds':['function','local','module_variable'],'style':'snake_case','scope':'function'}]}
  r=n.check_naming('def good():\n    Bad = [BadItem for BadItem in [1]]\n',rules)
  self.assertEqual(r['position_unverified_count'],0)
  self.assertEqual({x['name'] for x in r['checked']},{'Bad','BadItem'})
  src=n._Source('Kname')
  self.assertEqual(src.locate(re.compile(r'(\w+)'),1,0,'Kname'),('Kname',1,1,1,6))
  self.assertEqual(src.unverified,0)
 def test_comprehension_category_not_module_or_class(self):
  self.assertEqual(n._Scope('comprehension',None).category,'function')
  for kind in ['function','module','class']:self.assertEqual(n._Scope(kind,None).category,kind)
 def test_unrenamed_import_span_internal_not_public_check(self):
  src=n._Source('import package.submodule\n');c=n._Collector(src);scope=c.new_scope('module',None)
  c.visit(ast.parse(src.text).body[0],scope)
  row=scope.cands['package'][0]
  self.assertEqual((row['line'],row['col'],row['end_line'],row['end_col']),(1,8,1,15))
  self.assertIsNone(row['kind']);self.assertEqual(src.unverified,0)
 def test_bare_except_actual_parse_never_visits_none(self):
  src=n._Source('try:\n    pass\nexcept:\n    pass\n');c=n._Collector(src);scope=c.new_scope('module',None)
  node=ast.parse(src.text).body[0].handlers[0]
  with mock.patch.object(c,'visit',wraps=c.visit) as visit:c.v_ExceptHandler(node,scope)
  self.assertEqual(visit.call_count,1)
  self.assertIsInstance(visit.call_args.args[0],ast.Pass)
  self.assertEqual(src.unverified,0)
 def test_synthetic_except_name_without_type_fallback_exact(self):
  # Cannot arise from valid Python syntax; branch mechanism, not public feature proof.
  src=n._Source('except:\n pass\n');c=n._Collector(src);scope=c.new_scope('function',None)
  node=ast.ExceptHandler(type=None,name='BadName',body=[]);node.lineno=1;node.col_offset=0
  c.v_ExceptHandler(node,scope)
  row=scope.cands['BadName'][0]
  self.assertEqual((row['line'],row['col'],row['end_line'],row['end_col']),(1,1,1,8))
  self.assertEqual(src.unverified,1)
 def test_syntax_error_exact_real_positions_and_missing_attributes(self):
  for text in ['x =\n','def f(:\n pass\n']:
   try:ast.parse(text)
   except SyntaxError as original:
    with self.assertRaises(n.NamingRefusal) as cm:n._parse(text)
    self.assertEqual(cm.exception.code,'syntax_error')
    self.assertEqual(cm.exception.detail,{'line':original.lineno,'col':original.offset})
    self.assertEqual(str(cm.exception),'source is not valid Python syntax at line %d'%original.lineno)
  for line,offset in [(None,None),(7,None),(None,9),(7,9),(0,0)]:
   exc=SyntaxError('synthetic');exc.lineno=line;exc.offset=offset
   with mock.patch.object(n.ast,'parse',side_effect=exc),self.assertRaises(n.NamingRefusal) as cm:n._parse('x')
   self.assertEqual(cm.exception.detail,{'line':line or 0,'col':offset or 0})
   self.assertEqual(str(cm.exception),'source is not valid Python syntax at line %d'%(line or 0))

if __name__=='__main__':unittest.main()
