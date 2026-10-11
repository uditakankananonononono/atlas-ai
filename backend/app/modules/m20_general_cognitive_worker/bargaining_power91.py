"""BARGAIN91: exact caller-declared factor arithmetic, not empirical power."""
from fractions import Fraction
import copy
import re

LIMITS={'parties':64,'text':2000,'id':100,'scale':1000000,'rational_component':1000000}
FACTORS=('alternatives','resources','time_pressure','dependency')

class Bargain91Error(ValueError):
    pass

def _refuse(text):raise Bargain91Error('BARGAIN91: '+text)
def _shape(value,keys,label):
    if type(value)is not dict or set(value)!=set(keys):_refuse(label+' must contain exactly '+', '.join(keys))
def _text(value,label,limit):
    if type(value)is not str or not value.strip() or len(value)>limit or any(ord(c)<32 or ord(c)==127 for c in value):_refuse(label+' must be nonempty bounded text without controls')
def _weight(value):
    if type(value)is not str or not re.fullmatch(r'\d+(?:/[1-9]\d*)?',value):_refuse('weight must be a nonnegative rational string')
    parts=value.split('/')
    if any(len(x)>7 or int(x)>LIMITS['rational_component'] for x in parts):_refuse('weight numerator and denominator exceed limit')
    return Fraction(value)

def evaluate_bargaining_power(packet):
    """Score supplied factors only. Alternatives are caller ratings, not BATNA utility."""
    _shape(packet,('model','parties'),'packet')
    model=packet['model'];_shape(model,FACTORS,'model');weights={}
    for factor in FACTORS:
        row=model[factor];_shape(row,('weight','scale','direction'),'model factor')
        weights[factor]=_weight(row['weight'])
        if type(row['scale'])is not int or not 1<=row['scale']<=LIMITS['scale']:_refuse('scale must be integer within 1..1000000')
        direction='benefit' if factor in ('alternatives','resources') else 'penalty'
        if row['direction']!=direction:_refuse(factor+' direction must be '+direction)
        if factor in ('time_pressure','dependency') and row['scale']!=1:_refuse(factor+' flag scale must be 1')
    if not any(weights.values()):_refuse('at least one weight must be positive')
    parties=packet['parties']
    if type(parties)is not list or not 1<=len(parties)<=LIMITS['parties']:_refuse('parties must be a list with 1..64 entries')
    seen=set();rows=[]
    for party in parties:
        if type(party)is not dict or set(party) not in ({'id','position','factors'},{'id','position','factors','batna_record'}):_refuse('party schema invalid')
        batna=validate_batna_record(party['batna_record']) if 'batna_record' in party else None
        _text(party['id'],'party id',LIMITS['id']);_text(party['position'],'position',LIMITS['text'])
        if party['id'] in seen:_refuse('duplicate party id')
        seen.add(party['id']);_shape(party['factors'],FACTORS,'factors');components={};score=Fraction(0)
        for factor in FACTORS:
            value=party['factors'][factor]
            if factor in ('time_pressure','dependency'):
                if type(value)is not bool:_refuse(factor+' must be bool')
                value=int(value)
            elif type(value)is not int or not 0<=value<=model[factor]['scale']:_refuse(factor+' must be integer within declared scale')
            contribution=weights[factor]*Fraction(value,model[factor]['scale'])
            if model[factor]['direction']=='penalty':contribution=-contribution
            score+=contribution;components[factor]=str(contribution)
        rows.append({'id':party['id'],'position':party['position'],'components':components,'score':str(score),'batna_record':batna,'_score':score})
    rows.sort(key=lambda row:(-row['_score'],row['id']));last=None;rank=0;ties={}
    for index,row in enumerate(rows,1):
        if row['_score']!=last:rank=index;last=row['_score']
        row['rank']=rank;ties.setdefault(row['score'],[]).append(row['id']);del row['_score']
    return {'model':copy.deepcopy(model),'ranking':rows,'tie_groups':[ids for ids in ties.values() if len(ids)>1],
            'scope':'caller_declared_factor_model_only','real_world_power_verified':False,
            'limits':dict(LIMITS),'boundary':'Heuristic declared factor arithmetic only. Caller weights and ratings, not actual negotiating power, evidence verification, outcome prediction or permission to act.'}

def _utility(value):
    if type(value)is not str or len(value)>128 or not re.fullmatch(r'-?\d+(?:/[1-9]\d*)?',value):_refuse('BATNA utility must be bounded rational string')
    return Fraction(value)

def validate_batna_record(record):
    """Validate supplied BATNA92 to_dict shape, no import or utility-to-power mapping."""
    _shape(record,('version','options_count','best_names','best_utility','is_tie','ranking','margin_to_next','limits'),'BATNA record')
    if record['version']!='1':_refuse('BATNA version must be 1')
    if type(record['options_count'])is not int or not 1<=record['options_count']<=1000:_refuse('BATNA options_count must be integer within 1..1000')
    ranking=record['ranking']
    if type(ranking)is not list or len(ranking)!=record['options_count']:_refuse('BATNA ranking count mismatch')
    seen=set();values=[];expected_rank=0;last=None
    for index,row in enumerate(ranking,1):
        _shape(row,('name','utility','rank'),'BATNA rank entry');_text(row['name'],'BATNA name',2000)
        if row['name'] in seen:_refuse('BATNA duplicate name')
        seen.add(row['name']);value=_utility(row['utility'])
        if last is not None and value>last:_refuse('BATNA ranking must descend')
        if value!=last:expected_rank=index
        if type(row['rank'])is not int or row['rank']!=expected_rank:_refuse('BATNA competition rank mismatch')
        values.append(value);last=value
    best=values[0];names=[row['name'] for row,v in zip(ranking,values) if v==best]
    if type(record['best_names'])is not list or record['best_names']!=names:_refuse('BATNA best_names mismatch')
    if _utility(record['best_utility'])!=best:_refuse('BATNA best_utility mismatch')
    if type(record['is_tie'])is not bool or record['is_tie']!=(len(names)>1):_refuse('BATNA tie flag mismatch')
    lower=next((v for v in values if v<best),None)
    margin=None if lower is None else best-lower
    supplied=record['margin_to_next']
    if (None if supplied is None else _utility(supplied))!=margin:_refuse('BATNA margin mismatch')
    if type(record['limits'])is not list or len(record['limits'])!=5:_refuse('BATNA limits must contain five declarations')
    for text in record['limits']:_text(text,'BATNA limit',2000)
    return copy.deepcopy(record)
