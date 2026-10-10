"""Actual synchronous Life cellular automaton, independent local-rule oracle."""
import pytest
from app.modules.m20_general_cognitive_worker.artificial_life import simulate

def request(**kw):return {'width':6,'height':6,'live_cells':[[2,1],[2,2],[2,3]],'steps':4,**kw}

def nextcells(live,w,h,boundary):
 result=set()
 for y in range(h):
  for x in range(w):
   count=0
   for dy in (-1,0,1):
    for dx in (-1,0,1):
     if dx==dy==0:continue
     a,b=x+dx,y+dy
     if boundary=='toroidal':a%=w;b%=h
     if (a,b)in live:count+=1
   if count==3 or ((x,y)in live and count==2):result.add((x,y))
 return result

def test_blinker_oscillator_exact_history_births_deaths_and_period():
 r=simulate(request())
 assert r['history'][0]['live_cells']==[[2,1],[2,2],[2,3]]
 assert r['history'][1]['live_cells']==[[1,2],[2,2],[3,2]]
 assert r['history'][2]['live_cells']==r['history'][0]['live_cells']
 assert r['history'][1]['births']==[[1,2],[3,2]] and r['history'][1]['deaths']==[[2,1],[2,3]]
 assert len(r['history'])==5 and r['history'][-1]['step']==4
 assert r['first_repeat']=={'first_seen_step':0,'repeated_at_step':2,'period':2}
 assert r['cell_evaluations']==6*6*4
 assert r['life_scope']=='Conway B3/S23 finite cellular automaton, not biological life or open-ended adaptive agents.'

def test_stilllife_extinction_and_glider_motion():
 block=[[1,1],[1,2],[2,1],[2,2]];r=simulate(request(live_cells=block))
 assert all(h['live_cells']==block for h in r['history']) and r['first_repeat']['period']==1
 dead=simulate(request(live_cells=[[1,1]],steps=2))
 assert dead['history'][1]['live_cells']==[] and dead['history'][1]['deaths']==[[1,1]]
 glider=[[1,0],[2,1],[0,2],[1,2],[2,2]]
 r=simulate(request(width=8,height=8,live_cells=glider))
 assert set(map(tuple,r['history'][4]['live_cells']))=={(x+1,y+1)for x,y in glider}

@pytest.mark.parametrize('boundary',['fixed','toroidal'])
def test_all_history_rules_independent_grid_oracle(boundary):
 d=request(width=5,height=4,live_cells=[[0,0],[4,0],[0,3],[2,1],[2,2]],steps=7,boundary=boundary)
 r=simulate(d);live=set(map(tuple,d['live_cells']))
 for h in r['history'][1:]:
  future=nextcells(live,5,4,boundary)
  assert set(map(tuple,h['live_cells']))==future
  assert set(map(tuple,h['births']))==future-live and set(map(tuple,h['deaths']))==live-future
  assert h['population']==len(future) and h['density']==len(future)/20
  live=future
 assert simulate({**d,'boundary':'fixed'})['history']!=simulate({**d,'boundary':'toroidal'})['history']

@pytest.mark.parametrize('bad',[{'width':2},{'height':129},{'width':True},{'steps':0},{'steps':1001},{'steps':True},{'boundary':'other'},{'live_cells':[[0,0],[0,0]]},{'live_cells':[[6,0]]},{'live_cells':[[True,0]]},{'live_cells':[[0]]},{'live_cells':'bad'}])
def test_invalid_input_refused(bad):
 with pytest.raises(ValueError):simulate(request(**bad))

def test_work_bound_and_empty_universe():
 with pytest.raises(ValueError,match='product'):simulate(request(width=128,height=128,steps=1000))
 r=simulate(request(live_cells=[],steps=1));assert r['history'][-1]['population']==0

def test_production_mounted_route(monkeypatch,oidc_auth_headers):
 from app.main import app
 from fastapi.testclient import TestClient
 monkeypatch.setenv('ATLAS_ENV','production');c=TestClient(app);path='/api/v1/api/modules/20/artificial-life/simulate'
 assert c.post(path,json=request()).status_code==401
 r=c.post(path,headers=oidc_auth_headers('life','owner'),json=request())
 assert r.status_code==200 and r.json()==simulate(request())
 assert c.post(path,headers=oidc_auth_headers('life','owner'),json=request(steps=0)).status_code==422

def test_size_step_upper_boundaries_and_independent_work_guard():
 with pytest.raises(ValueError,match='steps'):simulate(request(width=3,height=3,steps=1001))
 assert len(simulate(request(width=3,height=3,live_cells=[],steps=1000))['history'])==1001
 with pytest.raises(ValueError,match='width'):simulate(request(width=129,steps=1))
 assert simulate(request(width=128,steps=1))['width']==128
 with pytest.raises(ValueError,match='product'):simulate(request(width=128,height=128,steps=12))
 assert simulate(request(width=128,height=128,steps=11))['cell_evaluations']==128*128*11

def test_independent_minimum_dimensions_and_all_axis_coordinate_bounds():
 with pytest.raises(ValueError,match='width'):simulate(request(width=2,live_cells=[]))
 with pytest.raises(ValueError,match='height'):simulate(request(height=2,live_cells=[]))
 assert simulate(request(width=3,height=3,live_cells=[]))['width']==3
 for cell in ([0,6],[0,-1],[-1,0]):
  with pytest.raises(ValueError,match='outside grid'):simulate(request(live_cells=[cell]))

def test_omitted_steps_default_exact_history_and_work():
 d=request();del d['steps'];r=simulate(d)
 assert len(r['history'])==5 and r['history'][-1]['step']==4
 assert r['cell_evaluations']==6*6*4

def test_omitted_boundary_is_fixed_on_edge_touching_pattern():
 d=request(width=5,height=4,live_cells=[[0,0],[4,0],[0,3],[2,1],[2,2]],steps=3)
 r=simulate(d)
 assert r['boundary']=='fixed'and r==simulate({**d,'boundary':'fixed'})
 assert r['history']!=simulate({**d,'boundary':'toroidal'})['history']

def test_transient_period_uses_first_seen_not_absolute_step():
 d=request(live_cells=[[1,1]],steps=4);r=simulate(d)
 live=set(map(tuple,d['live_cells']));seen={frozenset(live):0};expected=None
 for step in range(1,5):
  live=nextcells(live,6,6,'fixed');state=frozenset(live)
  if state in seen and expected is None:expected={'first_seen_step':seen[state],'repeated_at_step':step,'period':step-seen[state]}
  seen.setdefault(state,step)
 assert r['first_repeat']==expected
 assert expected['first_seen_step']>0
 assert expected['period']==expected['repeated_at_step']-expected['first_seen_step']==1
