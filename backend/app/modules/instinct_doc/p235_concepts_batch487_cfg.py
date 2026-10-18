"""P235 b487-cfg rev1: bounded exact parse-forest extensions over caller-supplied
CNF grammars. Recognition and raw parse counting are claimed by landed b598
(cfg_cyk_recognize, cfg_cyk_parse_count on CNF); this unit deliberately does
not duplicate them and only claims parse-forest structure: inside/outside
charts, root splits, per-rule and per-symbol usage, and active spans.
Each public function takes n (1..6 nonterminals), start (0..n-1), terminals
(list of <=24 unique [A,token] rules), binaries (list of <=64 unique [A,B,C]
rules), and word (list of <=10 tokens). IDs and tokens are exact ints; tokens
are 0..7. Epsilon and unit productions are excluded. Empty words have zero
parses. Validation order: n type/lower/upper; start type/range; terminal
container/cap, each row type/size then entries type/range, duplicate rules;
binary rules likewise; word container/cap then entries type/range. Bool is
rejected explicitly before integer checks. Rule-list order has no semantics.
Counts distinguish parse trees by rule and split. Table cell [A,i,j] counts
parses of word[i:j]; inside chart rows are [A,i,j,count] for positive counts,
sorted by A,i,j. Outside counts count contexts from the chosen start over the
whole word; usage counts count occurrences across all full parse trees, not
just trees containing a rule. Forest APIs do not enumerate trees. Outputs are
fresh int lists, exact ints, or bools. No grammar inference, arbitrary CFG
normalization, epsilon productions, language equivalence, or infinite-word
claims. All data is supplied by the caller; no retrieval or network.
"""
from importlib.util import find_spec
try:
 from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
 if exc.name!='app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:raise
 def make_fail(name):
  def fail(code):raise ValueError('P235:%s:%s'%(name,code))
  return fail
SCOPE='PARTIAL: bounded exact CNF parse-forest counts from supplied grammars'
NOT_CLAIMED=('CNF recognition and raw parse counting (landed b598: cfg_cyk_recognize, cfg_cyk_parse_count)','arbitrary CFG normalization','epsilon or unit productions','grammar inference','language equivalence','global novelty','production readiness')


def _integer(f,x,label,limit):
 if type(x) is bool:f('bad_type:'+label)
 if type(x) is not int:f('bad_type:'+label)
 if not 0<=x<limit:f('bad_value:'+label)

def _rules(f,rows,label,size,cap,n):
 if type(rows) is not list:f('bad_type:'+label)
 if len(rows)>cap:f('too_many:'+label)
 seen=set()
 for row in rows:
  if type(row) is not list:f('bad_type:rule')
  if len(row)!=size:f('bad_value:rule_size')
  for i,x in enumerate(row):_integer(f,x,'symbol',8 if label=='terminals' and i==1 else n)
  if tuple(row)in seen:f('bad_value:duplicate_rule')
  seen.add(tuple(row))

def _check(name,n,start,terminals,binaries,word):
 f=make_fail(name)
 if type(n) is bool:f('bad_type:n')
 if type(n) is not int:f('bad_type:n')
 if n<1:f('bad_value:n')
 if n>6:f('too_many:n')
 _integer(f,start,'start',n)
 _rules(f,terminals,'terminals',2,24,n)
 _rules(f,binaries,'binaries',3,64,n)
 if type(word) is not list:f('bad_type:word')
 if len(word)>10:f('too_many:word')
 for x in word:_integer(f,x,'token',8)

def _inside(n,terminals,binaries,word):
 L=len(word);d={}
 for i,tok in enumerate(word):
  for a,t in terminals:
   if t==tok:d[a,i,i+1]=1
 for length in range(2,L+1):
  for i in range(L-length+1):
   j=i+length
   for a,b,c in binaries:
    for k in range(i+1,j):d[a,i,j]=d.get((a,i,j),0)+d.get((b,i,k),0)*d.get((c,k,j),0)
 return d

def _outside(start,binaries,word,d):
 L=len(word);o={(start,0,L):1}if L else {}
 for length in range(L,1,-1):
  for i in range(L-length+1):
   j=i+length
   for a,b,c in binaries:
    v=o.get((a,i,j),0)
    for k in range(i+1,j):
     o[b,i,k]=o.get((b,i,k),0)+v*d.get((c,k,j),0)
     o[c,k,j]=o.get((c,k,j),0)+v*d.get((b,i,k),0)
 return o

def _data(name,n,start,terminals,binaries,word):
 _check(name,n,start,terminals,binaries,word)
 return _inside(n,terminals,binaries,word)

def _chart(d):return [[a,i,j,v]for (a,i,j),v in sorted(d.items())if v]





def cfg_inside_chart(n,start,terminals,binaries,word):
 """Positive inside cells as [A,i,j,count], sorted lexicographically."""
 return _chart(_data('cfg_inside_chart',n,start,terminals,binaries,word))


def cfg_outside_chart(n,start,terminals,binaries,word):
 """Positive context counts [A,i,j,count]; a root context exists even if
 no full parse does, provided word is nonempty."""
 d=_data('cfg_outside_chart',n,start,terminals,binaries,word)
 return _chart(_outside(start,binaries,word,d))


def cfg_root_splits(n,start,terminals,binaries,word):
 """Counts by root split k=1..len(word)-1, summed across start rules."""
 d=_data('cfg_root_splits',n,start,terminals,binaries,word)
 return [sum(d.get((b,0,k),0)*d.get((c,k,len(word)),0)for a,b,c in binaries if a==start)for k in range(1,len(word))]


def cfg_terminal_usage(n,start,terminals,binaries,word):
 """Total occurrences of each terminal rule across all full parse trees,
 in input rule order."""
 d=_data('cfg_terminal_usage',n,start,terminals,binaries,word)
 o=_outside(start,binaries,word,d)
 return [sum(o.get((a,i,i+1),0)for i,t in enumerate(word)if t==tok)for a,tok in terminals]


def cfg_binary_usage(n,start,terminals,binaries,word):
 """Total occurrences of each binary rule across all full parse trees,
 in input rule order."""
 d=_data('cfg_binary_usage',n,start,terminals,binaries,word)
 o=_outside(start,binaries,word,d);L=len(word)
 return [sum(o.get((a,i,j),0)*d.get((b,i,k),0)*d.get((c,k,j),0)for i in range(L)for j in range(i+2,L+1)for k in range(i+1,j))for a,b,c in binaries]


def cfg_symbol_usage(n,start,terminals,binaries,word):
 """Total occurrences of each nonterminal ID across all full parse trees."""
 d=_data('cfg_symbol_usage',n,start,terminals,binaries,word)
 o=_outside(start,binaries,word,d);L=len(word)
 return [sum(d.get((a,i,j),0)*o.get((a,i,j),0)for i in range(L)for j in range(i+1,L+1))for a in range(n)]


def cfg_active_spans(n,start,terminals,binaries,word):
 """Sorted [A,i,j] cells appearing in at least one full parse tree."""
 d=_data('cfg_active_spans',n,start,terminals,binaries,word)
 o=_outside(start,binaries,word,d)
 return [[a,i,j]for a,i,j in sorted(d)if d[a,i,j]>0 and o.get((a,i,j),0)>0]
