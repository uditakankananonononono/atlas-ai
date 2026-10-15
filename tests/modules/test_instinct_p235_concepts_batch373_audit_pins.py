import builtins,runpy,sys,types,unittest
from unittest.mock import patch
from app.modules.instinct_doc import p235_concepts_batch373 as m
class GuardPins(unittest.TestCase):
 def test_guard_matrix(self):
  name='app.modules.instinct_doc.p235_concepts_registry';orig=builtins.__import__
  for claimed,present in ((name,False),(name,True),('other_dependency',False)):
   def bad(n,*args,**kw):
    if n==name:raise ModuleNotFoundError('synthetic',name=claimed)
    return orig(n,*args,**kw)
   with patch('builtins.__import__',bad),patch('importlib.util.find_spec',lambda _:object()if present else None):
    if present or claimed!=name:
     with self.assertRaises(ModuleNotFoundError):runpy.run_path(m.__file__)
    else:
     ns=runpy.run_path(m.__file__)
     with self.assertRaisesRegex(ValueError,'^P235:semigroup_power_orbits:bad_type:table$'):ns['semigroup_power_orbits'](None)
  fake=types.ModuleType(name);sentinel=object();fake.make_fail=lambda _:sentinel
  with patch.dict(sys.modules,{name:fake}):self.assertIs(runpy.run_path(m.__file__)['make_fail']('x'),sentinel)
