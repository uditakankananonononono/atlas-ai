import importlib.util,pathlib,pytest
# import test factory without invoking mounted test; use true package source.
from app.modules.m20_general_cognitive_worker import scientific_protocol as m
p=pathlib.Path(__file__).parent/'test_m20_learn_science859.py';s=importlib.util.spec_from_file_location('factory',p);factory=importlib.util.module_from_spec(s);s.loader.exec_module(factory)
def test_bad_prediction():
 p=factory.packet();p['scientific_protocol']['prediction']=1
 with pytest.raises(ValueError):m.check(p)
def test_bad_variable():
 p=factory.packet();p['scientific_protocol']['independent_variable']=1
 with pytest.raises(ValueError):m.check(p)
def test_false_truth_boundary():
 r=m.check(factory.packet());assert r['replication_performed'] is False and r['hypothesis_truth_verified'] is False and r['predeclaration_verified'] is False and r['source_truth_verified'] is False
