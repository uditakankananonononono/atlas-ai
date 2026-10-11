"""Rendered supplied-only creative artifacts, RED before runtime file."""
import importlib.util
from pathlib import Path
import sys
import pytest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/c36/creative.py'
spec=importlib.util.spec_from_file_location('s55',P);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

def req(mode='game',**changes):
 concept={'title':'Garden','premise':'Collect seeds','mechanics':['jump','collect'],'characters':[{'name':'A','trait':'curious'}],'episodes':2,**changes}
 return {'as_of':'2026-10-11','mode':mode,'concept':concept}
def refuse(code,r):
 with pytest.raises(ValueError)as e:m.run(r)
 assert str(e.value)==code


@pytest.mark.parametrize('title',['Garden','Cloud Runner'])
def test_game_rendered_doc_and_lua(title):
 out=m.run(req(title=title));assert set(out)=={'documents','scope'}
 docs=out['documents'];assert set(docs)=={'game_design.md','mechanics.lua'}
 assert title in docs['game_design.md'] and 'Collect seeds' in docs['game_design.md']
 for section in ('Premise','Core loop','Mechanics','Win/Lose','UI list'):assert '## '+section in docs['game_design.md']
 assert 'TO_WRITE' in docs['game_design.md']
 assert 'local function jump() end' in docs['mechanics.lua']
 assert 'local function collect() end' in docs['mechanics.lua']
 for word in ('HttpService','require','loadstring','socket','http'):assert word not in docs['mechanics.lua']


@pytest.mark.parametrize('title',['Garden','Sky'])
def test_anime_bible_and_acts_only(title):
 docs=m.run(req('anime',title=title))['documents']
 assert set(docs)=={'series_bible.md','episode_beats.md'}
 assert 'A: curious' in docs['series_bible.md']
 assert docs['episode_beats.md'].count('Act 1: TO_WRITE')==2
 assert docs['episode_beats.md'].count('Act 2: TO_WRITE')==2
 assert docs['episode_beats.md'].count('Act 3: TO_WRITE')==2
 for word in ('shot_lists','storyboards','panel_plan','scenes','scripts'):assert word not in str(docs)


@pytest.mark.parametrize('mechanic',['x-y','1x','x()','x\nend','require','loadstring','HttpService'])
def test_mechanic_invalid_or_dangerous_names(mechanic):
 # Reserved network identifiers are refused even when Lua-identifier shaped.
 refuse('VENT_REFUSED_CONTROL_CHARS:mechanics' if '\n' in mechanic else 'VENT_REFUSED_BAD_TYPE:mechanics',req(mechanics=[mechanic]))


def test_duplicate_mechanics():refuse('VENT_REFUSED_BAD_TYPE:mechanics',req(mechanics=['jump','jump']))


@pytest.mark.parametrize('episodes',[0,25,True,1.5])
def test_episode_bounds(episodes):refuse('VENT_REFUSED_BAD_TYPE:episodes',req('anime',episodes=episodes))


def test_modes_and_required_lists():
 r=req();r['mode']='unknown';refuse('VENT_REFUSED_UNKNOWN:mode',r)
 r=req();r['mode']=None;refuse('VENT_REFUSED_BAD_TYPE:mode',r)
 refuse('VENT_REFUSED_EMPTY:mechanics',req(mechanics=[]))
 refuse('VENT_REFUSED_EMPTY:characters',req('anime',characters=[]))


@pytest.mark.parametrize('key,reason',[('publish','PUBLISH'),('token','SEND'),('buy','SPEND'),('login','NOCREDS')])
def test_effects(key,reason):
 r=req();r[key]=True;refuse('VENT_REFUSED_'+reason+':'+key,r)


def test_count_first():
 r=req(mechanics=[{'token':1}]*31);r['x'*201]=1
 refuse('VENT_REFUSED_OVERSIZE:mechanics',r)


@pytest.mark.parametrize('field,cap',[('title',200),('premise',2000)])
def test_raw_text_boundaries(field,cap):
 assert m.run(req(**{field:'x'*cap}))['documents']
 refuse('VENT_REFUSED_OVERSIZE:'+field,req(**{field:'x'*(cap+1)+'\x00'}))


@pytest.mark.parametrize('char',['\x00','\x81','\u200b','\u2028','\u2029'])
def test_unicode_full_controls(char):refuse('VENT_REFUSED_CONTROL_CHARS:premise',req(premise='x'+char))


def test_zs_and_ignored_fields_still_validated():
 assert '\u00a0' in m.run(req(title='\u00a0Garden\u00a0'))['documents']['game_design.md']
 refuse('VENT_REFUSED_CONTROL_CHARS:trait',req(characters=[{'name':'A','trait':'x\u200b'}]))


def test_date_and_unknown_allowlists():
 r=req();r['as_of']='2026-10-11x';refuse('VENT_REFUSED_OVERSIZE:as_of',r)
 r=req();r['as_of']='2026-02-30';refuse('VENT_REFUSED_BAD_TYPE:as_of',r)
 r=req();r['concept']['extra']=1;refuse('VENT_REFUSED_UNKNOWN:concept',r)
 r=req();r['concept']['characters'][0]['extra']=1;refuse('VENT_REFUSED_UNKNOWN:characters',r)


class DS(dict):pass
class LS(list):pass
class SS(str):pass
class IS(int):pass

def test_exact_types():
 refuse('VENT_REFUSED_BAD_TYPE:request',DS(req()))
 refuse('VENT_REFUSED_BAD_TYPE:mechanics',req(mechanics=LS(['jump'])))
 refuse('VENT_REFUSED_BAD_TYPE:title',req(title=SS('Garden')))
 refuse('VENT_REFUSED_BAD_TYPE:episodes',req('anime',episodes=IS(2)))


def test_real_floor_and_no_wrapper():
 from app.core import providers
 assert '/backend/app/' in providers.__file__
 from app.modules.c30 import policy
 assert m.policy is policy
 source=P.read_text()
 assert 'x10_preproduction' not in source
 assert not any(hasattr(m,x)for x in ('send','publish','spend','create_account'))
 assert m.run(req())==m.run(req())


@pytest.mark.parametrize('field,limit',[('characters',30),('mechanics',30)])
def test_list_count_precedence(field,limit):
 r=req(**{field:[{'token':1}]*(limit+1)});r['bad\u200b']=1
 refuse('VENT_REFUSED_OVERSIZE:'+field,r)


def test_exact_max_lists_and_leaves():
 assert m.run(req(mechanics=['m'+str(i)for i in range(30)]))['documents']
 assert m.run(req('anime',characters=[{'name':'N','trait':'T'}]*30,episodes=24))['documents']['episode_beats.md'].count('Act 3: TO_WRITE')==24
 assert m.run(req(mechanics=['x'*64]))['documents']
 refuse('VENT_REFUSED_OVERSIZE:mechanics',req(mechanics=['x'*65]))
 for field in ('name','trait'):
  assert m.run(req('anime',characters=[{'name':'N','trait':'T',field:'x'*200}]))['documents']
  refuse('VENT_REFUSED_OVERSIZE:'+field,req(characters=[{'name':'N','trait':'T',field:'x'*201}]))


def test_resource_cycle_depth_and_count():
 r={};r['loop']=r;refuse('VENT_REFUSED_BAD_TYPE:request',r)
 def tree(nodes):
  if nodes==1:return []
  children=min(64,nodes-1);q,rem=divmod(nodes-1,children)
  return [tree(q+(i<rem))for i in range(children)]
 r={'extra':tree(9999)};refuse('VENT_REFUSED_UNKNOWN:request',r)
 r={'extra':tree(10000)};refuse('VENT_REFUSED_OVERSIZE:request',r)
 def nested(edges):
  node='leaf'
  for _ in range(edges):node=[node]
  return {'extra':node}
 refuse('VENT_REFUSED_UNKNOWN:request',nested(31))
 refuse('VENT_REFUSED_OVERSIZE:request',nested(32))


def test_key_cap_exact_and_asof_10_boundary():
 r=req();r['x'*200]=1;refuse('VENT_REFUSED_UNKNOWN:request',r)
 r=req();r['x'*201]=1;refuse('VENT_REFUSED_OVERSIZE:key',r)
 r=req();r['as_of']='2026-1-11';refuse('VENT_REFUSED_BAD_TYPE:as_of',r)


def test_mode_specific_fields_validated_even_if_ignored():
 refuse('VENT_REFUSED_BAD_TYPE:episodes',req(episodes=True))
 refuse('VENT_REFUSED_BAD_TYPE:mechanics',req('anime',mechanics=['1invalid']))
 refuse('VENT_REFUSED_BAD_TYPE:characters',req(characters=[None]))


def test_mode_key_controls_and_raw_caps_before_scan():
 r=req(title='x'*201);r['token']=1;refuse('VENT_REFUSED_OVERSIZE:title',r)
 r=req();r['mode']='x\u200b';refuse('VENT_REFUSED_CONTROL_CHARS:mode',r)
 r=req();r['mode']='x'*201;refuse('VENT_REFUSED_OVERSIZE:mode',r)


def test_forbidden_global_precedence_sorted_and_no_unknown_echo():
 r=req();r['login']=1;r['buy']=1;r['publish']=1;r['token']=1;r['approve']=1
 refuse('VENT_REFUSED_SEND:approve',r)
 r=req();r['concept']['extra']='private';refuse('VENT_REFUSED_UNKNOWN:concept',r)


@pytest.mark.parametrize('word',['end','local','function','true'])
def test_lua_reserved_words(word):refuse('VENT_REFUSED_BAD_TYPE:mechanics',req(mechanics=[word]))


def test_episode1_minimum():
 assert m.run(req('anime',episodes=1))['documents']['episode_beats.md'].count('Act 1: TO_WRITE')==1


def test_mechanic_raw_cap_beats_forbidden_key():
 r=req(mechanics=['x'*65]);r['token']=1
 refuse('VENT_REFUSED_OVERSIZE:mechanics',r)


@pytest.mark.parametrize('mode,omitted',[('game','characters'),('anime','mechanics')])
def test_optional_field_omission(mode,omitted):
 r=req(mode);del r['concept'][omitted]
 assert m.run(r)['documents']


@pytest.mark.parametrize('value',[5,None,[],{},b'2026-10-11',True,SS('2026-10-11')])
def test_asof_exact_bad_type(value):
 r=req();r['as_of']=value
 refuse('VENT_REFUSED_BAD_TYPE:as_of',r)


@pytest.mark.parametrize('value',[None,5,[],'x',True])
def test_concept_exact_bad_type(value):
 r=req();r['concept']=value
 refuse('VENT_REFUSED_BAD_TYPE:concept',r)


def test_concept_missing_bad_type():
 r=req();del r['concept']
 refuse('VENT_REFUSED_BAD_TYPE:concept',r)


@pytest.mark.parametrize('value',[None,5,{},'x',True,LS([])])
def test_characters_nonlist_reason(value):
 refuse('VENT_REFUSED_BAD_TYPE:characters',req(characters=value))


@pytest.mark.parametrize('value',['2',[],{},b'2'])
def test_episode_bad_type_reason(value):
 refuse('VENT_REFUSED_BAD_TYPE:episodes',req('anime',episodes=value))


def test_nonstring_and_control_key_reasons():
 r=req();r[5]=1
 refuse('VENT_REFUSED_BAD_TYPE:key',r)
 r=req();r['extra\u200b']=1
 refuse('VENT_REFUSED_CONTROL_CHARS:key',r)


def test_mode_boundary_and_bad_date_precedence():
 r=req();r['mode']='x'*200
 refuse('VENT_REFUSED_UNKNOWN:mode',r)
 r=req();r['mode']='x'*201;r['as_of']=5
 refuse('VENT_REFUSED_OVERSIZE:mode',r)


def test_premise_preflight_beats_title_controls():
 refuse('VENT_REFUSED_OVERSIZE:premise',req(title='x\u200b',premise='x'*2001))


@pytest.mark.parametrize('field',['name','trait'])
def test_nested_character_raw_caps_before_scan(field):
 r=req(characters=[{'name':'N','trait':'T',field:'x'*201}]);r['token']=1
 refuse('VENT_REFUSED_OVERSIZE:'+field,r)


@pytest.mark.parametrize('missing',[True,False])
def test_game_missing_or_none_episodes_accepted(missing):
 r=req(episodes=None)
 if missing:del r['concept']['episodes']
 assert set(m.run(r)['documents'])=={'game_design.md','mechanics.lua'}


@pytest.mark.parametrize('missing',[True,False])
def test_anime_missing_or_none_episodes_exact_reason(missing):
 r=req('anime',episodes=None)
 if missing:del r['concept']['episodes']
 refuse('VENT_REFUSED_BAD_TYPE:episodes',r)


@pytest.mark.parametrize('kind,limit',[(dict,32),(list,64),(tuple,64)])
def test_container_cardinality_exact_boundaries(kind,limit):
 def node(n):return {str(i):0 for i in range(n)} if kind is dict else kind(range(n))
 refuse('VENT_REFUSED_UNKNOWN:request',{'extra':node(limit)})
 refuse('VENT_REFUSED_OVERSIZE:request',{'extra':node(limit+1)})


def test_root_dictionary_cardinality_boundary():
 refuse('VENT_REFUSED_UNKNOWN:request',{str(i):0 for i in range(32)})
 refuse('VENT_REFUSED_OVERSIZE:request',{str(i):0 for i in range(33)})


@pytest.mark.parametrize('kind',[dict,list,tuple])
def test_hostile_cardinality_refuses_before_materialization(monkeypatch,kind):
 import builtins
 hostile={str(i):0 for i in range(100000)} if kind is dict else kind(range(100000))
 request=hostile if kind is dict else {'extra':hostile}
 visited=[]
 def spy(value):
  assert len(value)<=64,'oversized node reached materialization/traversal'
  visited.append(len(value))
  return builtins.reversed(value)
 monkeypatch.setattr(m,'reversed',spy,raising=False)
 refuse('VENT_REFUSED_OVERSIZE:request',request)
 assert visited==([] if kind is dict else [1])
import tracemalloc
@pytest.mark.parametrize('kind',[dict,list,tuple])
def test_hostile_cardinality_peak_allocation_bounded(kind):
 hostile={str(i):0 for i in range(200000)} if kind is dict else kind(range(200000))
 request=hostile if kind is dict else {'extra':hostile}
 tracemalloc.start()
 try:refuse('VENT_REFUSED_OVERSIZE:request',request);peak=tracemalloc.get_traced_memory()[1]
 finally:tracemalloc.stop()
 assert peak<100_000,peak
