"""Rendered supplied-concept templates only; no execution or release path."""
from __future__ import annotations
from datetime import date
import re
import unicodedata
from app.modules.c30 import policy

PREFIX='VENT'
TOP=frozenset({'as_of','mode','concept'})
CONCEPT=frozenset({'title','premise','characters','episodes','mechanics'})
CHARACTER=frozenset({'name','trait'})
CLASSES=(
 ('SEND',frozenset({'send','approve','approved','approval','approval_token','smtp','token','email_send','sender','smtp_host','smtp_port','smtp_user'})),
 ('SPEND',frozenset({'pay','purchase','spend','buy','checkout','card_number'})),
 ('PUBLISH',frozenset({'publish','upload','monetize','revenue','roblox_api','deploy'})),
 ('NOCREDS',frozenset({'login','password','username','credentials','otp','api_key','access_token','refresh_token','bearer','pass','passwd'})),
)
LUA_RESERVED=frozenset({'and','break','do','else','elseif','end','false','for','function','goto','if','in','local','nil','not','or','repeat','return','then','true','until','while'})


def _refuse(reason,field):raise ValueError('VENT_REFUSED_'+reason+':'+field)
def _cap(value,field,limit):
 if type(value) is str and len(value)>limit:_refuse('OVERSIZE',field)
def _text(value,field,limit):
 if type(value) is not str:_refuse('BAD_TYPE',field)
 _cap(value,field,limit)
 return policy.clean_text(value,PREFIX,field,limit)


def _preflight(request):
 concept=request.get('concept')
 if type(concept) is dict:
  for field in ('characters','mechanics'):
   v=concept.get(field)
   if type(v) is list and len(v)>30:_refuse('OVERSIZE',field)
  for field,limit in (('title',200),('premise',2000)):_cap(concept.get(field),field,limit)
  mechanics=concept.get('mechanics')
  if type(mechanics) is list:
   for value in mechanics:_cap(value,'mechanics',64)
  characters=concept.get('characters')
  if type(characters) is list:
   for character in characters:
    if type(character) is dict:
     for field in ('name','trait'):_cap(character.get(field),field,200)
 _cap(request.get('as_of'),'as_of',10)
 _cap(request.get('mode'),'mode',200)
 stack=[(request,0,False)];active=set();count=0;hits=[];bad_key=False
 while stack:
  node,depth,leaving=stack.pop()
  if leaving:active.remove(id(node));continue
  if type(node) in (dict,list,tuple):count+=1
  if count>10000 or depth>32:_refuse('OVERSIZE','request')
  if type(node) not in (dict,list,tuple):continue
  if len(node)>(32 if type(node) is dict else 64):_refuse('OVERSIZE','request')
  if id(node) in active:_refuse('BAD_TYPE','request')
  active.add(id(node));stack.append((node,depth,True))
  if type(node) is dict:
   for key,value in reversed(list(node.items())):
    if type(key) is not str:bad_key=True
    else:
     _cap(key,'key',200)
     if any(unicodedata.category(c) in {'Cc','Cf','Zl','Zp'}for c in key):_refuse('CONTROL_CHARS','key')
     norm=key.casefold().replace('-','_')
     for rank,(reason,table)in enumerate(CLASSES):
      if norm in table:hits.append((rank,norm,reason))
    stack.append((value,depth+1,False))
  else:stack.extend((v,depth+1,False)for v in reversed(node))
 if hits:
  _,key,reason=min(hits);_refuse(reason,key)
 if bad_key:_refuse('BAD_TYPE','key')


def run(request:dict)->dict:
 if type(request) is not dict:_refuse('BAD_TYPE','request')
 _preflight(request)
 if set(request)-TOP:_refuse('UNKNOWN','request')
 concept=request.get('concept')
 if type(concept) is dict:
  if set(concept)-CONCEPT:_refuse('UNKNOWN','concept')
  chars=concept.get('characters',[])
  if type(chars) is list:
   for char in chars:
    if type(char) is dict and set(char)-CHARACTER:_refuse('UNKNOWN','characters')
 as_of=request.get('as_of')
 if type(as_of) is not str or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',as_of):_refuse('BAD_TYPE','as_of')
 try:date.fromisoformat(as_of)
 except ValueError:_refuse('BAD_TYPE','as_of')
 mode=_text(request.get('mode'),'mode',200)
 if mode not in ('game','anime'):_refuse('UNKNOWN','mode')
 if type(concept) is not dict:_refuse('BAD_TYPE','concept')
 title=_text(concept.get('title'),'title',200)
 premise=_text(concept.get('premise'),'premise',2000)
 characters=concept.get('characters',[])
 if type(characters) is not list:_refuse('BAD_TYPE','characters')
 clean_chars=[]
 for char in characters:
  if type(char) is not dict:_refuse('BAD_TYPE','characters')
  clean_chars.append((_text(char.get('name'),'name',200),_text(char.get('trait'),'trait',200)))
 mechanics=concept.get('mechanics',[])
 if type(mechanics) is not list:_refuse('BAD_TYPE','mechanics')
 clean_mechanics=[]
 for value in mechanics:
  mechanic=_text(value,'mechanics',64)
  if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',mechanic) or mechanic in LUA_RESERVED or any(word in mechanic.casefold()for word in ('http','require','loadstring','socket')):
   _refuse('BAD_TYPE','mechanics')
  clean_mechanics.append(mechanic)
 if len(set(clean_mechanics))!=len(clean_mechanics):_refuse('BAD_TYPE','mechanics')
 episodes=concept.get('episodes')
 if episodes is not None and (type(episodes) is not int or not 1<=episodes<=24):_refuse('BAD_TYPE','episodes')
 if mode=='game':
  if not clean_mechanics:_refuse('EMPTY','mechanics')
  documents={
   'game_design.md':f'# {title}\n\n## Premise\n{premise}\n\n## Core loop\nTO_WRITE\n\n## Mechanics\n'+''.join('- '+x+'\n'for x in clean_mechanics)+'\n## Win/Lose\nTO_WRITE\n\n## UI list\nTO_WRITE\n',
   'mechanics.lua':''.join('-- Mechanic '+x+' (unimplemented)\nlocal function '+x+'() end\n'for x in clean_mechanics),
  }
 else:
  if not clean_chars:_refuse('EMPTY','characters')
  if episodes is None:_refuse('BAD_TYPE','episodes')
  documents={
   'series_bible.md':f'# {title}\n\n## Premise\n{premise}\n\n## Characters\n'+''.join('- '+name+': '+trait+'\n'for name,trait in clean_chars),
   'episode_beats.md':''.join(f'## Episode {i}\nAct 1: TO_WRITE\nAct 2: TO_WRITE\nAct 3: TO_WRITE\n\n'for i in range(1,episodes+1)),
  }
 return {'documents':documents,'scope':policy.scope(['rendered supplied game document and unimplemented Lua stubs','rendered supplied anime bible and fixed episode acts'],['publishing','monetization','execution','creative-quality claim','shot/panel/storyboard/scene formatting'],'supplied request only',as_of)}
