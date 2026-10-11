"""Human-readable focused hand battery, synthetic fixture inputs only."""
import importlib.util,sys,json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'backend/app/modules/m20_general_cognitive_worker/training_data_units.py'
s=importlib.util.spec_from_file_location('hand_units',p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
permit=m.SourcePermit('demo','https://example.org','CC0','https://example.org/terms','2026-10-11',True)
e=m.TrainingUnits({'demo':permit},policy=lambda _:None)
r={'source_id':'demo','url':'https://example.org/case','as_of':'2026-10-11','text':'SAT: 1480\nOutcome: admitted (source claim)\nAlways test claims before adopting them.'}
print(json.dumps({'registry':m.registry_report(),'T1':e.run('T1',{'records':[r,r]}),'T2':e.run('T2',{'kind':'git','source_id':'demo','url':'https://example.org/api','as_of':'2026-10-11','content':'{"items":[{"name":"Corpus tools","html_url":"https://github.com/demo/corpus","description":"public metadata"}]}','query':'corpus'}),'T3':e.run('T3',{'records':[r]}),'T4':e.run('T4',{'records':[r],'task':'prepare research plan','action':{'type':'research'}})},indent=2))
