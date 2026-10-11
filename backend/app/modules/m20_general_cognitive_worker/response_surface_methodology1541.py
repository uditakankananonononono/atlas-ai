"""Bounded exact supplied-input bookkeeping, not physical engineering validation."""
PREFIX='RESPSU1541'
from fractions import Fraction
import re
class UnitError(ValueError):pass
def refuse(code):raise UnitError(PREFIX+': '+code)
def shape(d,keys,code):
 if type(d)is not dict or set(d)!=set(keys):refuse(code)
def text(v):
 if type(v)is not str or len(v)>100 or not v.strip() or any(ord(c)<32 or ord(c)==127 for c in v):refuse('text must be nonblank control-free1..100')
 return v
def names(v,label,cap):
 if type(v)is not list or not 1<=len(v)<=cap:refuse(label+' must have1..'+str(cap)+' entries')
 for x in v:text(x)
 if len(v)!=len(set(v)):refuse('duplicate '+label)
 return v
def rational(v):
 if type(v)is not str:refuse('rational string required')
 if len(v)>16:refuse('rational raw length exceeds16')
 if not re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?',v):refuse('rational string required')
 parts=v.lstrip('-').split('/')
 if any(len(p)>7 or int(p)>1000000 for p in parts):refuse('rational components exceed1000000')
 return Fraction(v)
def bounded_rows(v,label):
 if type(v)is not list or not 1<=len(v)<=100:refuse(label+' must have1..100 entries')
 return v
def boundary():return {'release_authorized':False,'physical_validity_verified':False,'scope':'caller_supplied_bookkeeping_only'}
def rank(matrix):
 a=[r[:] for r in matrix];pivot=0
 for col in range(len(a[0])):
  found=next((i for i in range(pivot,len(a)) if a[i][col]),None)
  if found is None:continue
  a[pivot],a[found]=a[found],a[pivot];scale=a[pivot][col];a[pivot]=[x/scale for x in a[pivot]]
  for i in range(len(a)):
   if i!=pivot:
    scale=a[i][col];a[i]=[x-scale*y for x,y in zip(a[i],a[pivot])]
  pivot+=1
  if pivot==len(a):break
 return pivot
def prepare(d):
 shape(d,('factors','points','responses'),'packet schema');f=names(d['factors'],'factors',8);points=bounded_rows(d['points'],'points')
 if type(d['responses'])is not list or len(d['responses'])!=len(points):refuse('response count mismatch')
 terms=['1']+list(f)+[x+'^2' for x in f]+[f[i]+'*'+f[j] for i in range(len(f)) for j in range(i+1,len(f))]
 matrix=[]
 for p in points:
  shape(p,f,'point schema');values=[rational(p[x]) for x in f]
  matrix.append([Fraction(1)]+values+[x*x for x in values]+[values[i]*values[j] for i in range(len(f)) for j in range(i+1,len(f))])
 responses=[rational(x) for x in d['responses']];r=rank(matrix)
 return {**boundary(),'factor_count':len(f),'point_count':len(points),'term_names':terms,'design_matrix':[[str(x) for x in row] for row in matrix],
  'design_rank':r,'residual_degrees_of_freedom':len(points)-r,'full_column_rank':r==len(terms),'response_sum':str(sum(responses,Fraction(0))),
  'response_mean':str(sum(responses,Fraction(0))/len(responses)),'fit_executed':False,'prediction_validated':False}
