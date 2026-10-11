"""S7.2 deterministic supplied-OHLC simulation, trusted callbacks only.

No broker, network, order routing, code eval, leverage or shorting. The prefix
view catches ordinary peeking but is not a hostile Python code sandbox.
"""
from datetime import date
from collections.abc import Sequence
import math
import statistics
from types import MappingProxyType
from app.modules.c30 import policy

MAX_BARS=10000
DISCLAIMER='not financial advice, simulated, past results'
FIELDS={'bars','initial_cash','fee_bps','slippage_bps','periods_per_year','as_of','action','guarantee_profit',
        'forecast_predictions','forecast_resolutions','forecast_bins','forecast_calibrated'}

class PaperRefusal(ValueError):
    def __init__(self,code,detail=''):
        self.code=code;super().__init__(code+(': '+detail if detail else ''))

def refuse(reason,detail):raise PaperRefusal('MONEY_REFUSED_'+reason,detail)

class PrefixHistory(Sequence):
    """Only available bars stored; records immutable. Mark invalid future access."""
    def __init__(self,bars):self._bars=tuple(MappingProxyType(dict(b)) for b in bars);self.peeked=False
    def __len__(self):return len(self._bars)
    def __iter__(self):return iter(self._bars)
    def __getitem__(self,key):
        if isinstance(key,slice):
            if (key.stop is not None and key.stop>len(self)) or (key.start is not None and key.start>=len(self)):
                self.peeked=True;raise IndexError('future slice')
            return tuple(self._bars[key])
        if type(key) is not int:raise TypeError('integer history index required')
        if key>=len(self) or key< -len(self):self.peeked=True;raise IndexError('future bar')
        return self._bars[key]

def number(value,name,minimum,maximum):
    if type(value) not in (int,float) or not minimum<=value<=maximum or not math.isfinite(value):
        refuse('SCHEMA',name+' must be finite numeric in bounds')
    return float(value)

def _load_j1():
    from .j1_forecast import score_predictions
    return score_predictions

def cash_strategy(history):return 0.0

def _signal(strategy,bars):
    outputs=[]
    for _ in range(2):
        history=PrefixHistory(bars)
        try:result=strategy(history)
        except Exception as exc:
            if history.peeked:refuse('LOOKAHEAD','future history access attempted')
            refuse('STRATEGY','trusted callback failed: '+type(exc).__name__)
        if history.peeked:refuse('LOOKAHEAD','future history access attempted')
        if type(result) not in (int,float) or not 0<=result<=1 or not math.isfinite(result):
            refuse('STRATEGY','long-only target must be finite numeric [0,1], not bool')
        outputs.append(float(result))
    if outputs[0]!=outputs[1]:refuse('STRATEGY','callback is not deterministic on identical prefix')
    return outputs[0]

def run(request,*,strategy=None):
    if not isinstance(request,dict):refuse('SCHEMA','request must be dict')
    action=request.get('action','simulate')
    if action in ('trade','order_route','broker'):refuse('TRADE','no order-routing exists')
    if action=='spend':refuse('SPEND','paper unit cannot spend real money')
    if request.get('guarantee_profit') is True:refuse('GUARANTEE','no profit guarantees')
    if action!='simulate':
        try:policy.check(str(action),'MONEY')
        except ValueError as exc:raise PaperRefusal(str(exc).split(':')[0],str(exc)) from exc
    if not set(request)<=FIELDS:refuse('SCHEMA','unknown request fields')
    decision=policy.classify({'class':'offline','module_id':20,'tenant_id':'s72-supplied-fixture','action_type':'analyze','payload':{}})
    if decision.get('decision')!='allow':raise PaperRefusal(decision.get('code') or 'POLICY_REFUSED_UNKNOWN','offline simulation not allowed')
    raw=request.get('bars')
    if raw is None or raw==[]:refuse('NODATA','supplied OHLC bars required')
    if not isinstance(raw,list) or not 2<=len(raw)<=MAX_BARS:refuse('SCHEMA','bars must be list of2..10000')
    bars=[];previous=None
    for row in raw:
        if not isinstance(row,dict) or set(row)!={'date','open','high','low','close'}:refuse('SCHEMA','exact OHLC fields required')
        try:
            if not isinstance(row['date'],str) or len(row['date'])!=10:raise ValueError()
            day=date.fromisoformat(row['date'])
        except ValueError:refuse('SCHEMA','bar date must be YYYY-MM-DD')
        if previous is not None and day<=previous:refuse('SCHEMA','dates must strictly increase')
        previous=day
        bar={'date':day.isoformat()}
        for key in ('open','high','low','close'):bar[key]=number(row[key],key,1e-9,1e12)
        if not bar['low']<=min(bar['open'],bar['close'])<=max(bar['open'],bar['close'])<=bar['high']:
            refuse('SCHEMA','OHLC envelope violated')
        bars.append(bar)
    initial=number(request.get('initial_cash',1000),'initial_cash',1e-9,1e12)
    fee=number(request.get('fee_bps',0),'fee_bps',0,9999)/10000
    slip=number(request.get('slippage_bps',0),'slippage_bps',0,9999)/10000
    annual=request.get('periods_per_year',252)
    if type(annual) is not int or not 1<=annual<=10000:refuse('SCHEMA','periods_per_year int1..10000 required')
    as_of=request.get('as_of')
    try:policy.clean_text(as_of,'MONEY','as_of',64)
    except ValueError as exc:refuse('SCHEMA',str(exc))
    if request.get('guarantee_profit',False) is not False:refuse('SCHEMA','guarantee_profit must be exactly false')
    strategy=cash_strategy if strategy is None else strategy
    if not callable(strategy):refuse('STRATEGY','trusted callable required')
    cash=initial;shares=0.0;curve=[{'date':bars[0]['date'],'equity':initial,'cash':cash,'shares':shares}]
    trades=[];notional=0.0;fees=0.0
    for index in range(1,len(bars)):
        weight=_signal(strategy,bars[:index]);bar=bars[index];open_price=bar['open']
        delta_value=weight*(cash+shares*open_price)-shares*open_price
        side='buy' if delta_value>1e-9 else 'sell' if delta_value< -1e-9 else None
        if side:
            fill=open_price*(1+slip if side=='buy' else 1-slip)
            eq=cash+shares*fill
            if side=='buy':
                quantity=max(0,(weight*eq-shares*fill)/(fill*(1+weight*fee)))
                quantity=min(quantity,cash/(fill*(1+fee)))
                charge=quantity*fill*fee;cash-=quantity*fill+charge;shares+=quantity
            else:
                denominator=1-weight*fee
                if denominator<=0:refuse('SCHEMA','fee/weight liquidation denominator invalid')
                quantity=max(0,(shares*fill-weight*eq)/(fill*denominator));quantity=min(quantity,shares)
                charge=quantity*fill*fee;cash+=quantity*fill-charge;shares-=quantity
            if quantity>0:
                notional+=quantity*open_price;fees+=charge
                trades.append({'date':bar['date'],'signal_date':bars[index-1]['date'],'side':side,'shares':quantity,'fill_price':fill,'fee':charge,'target_weight':weight})
        equity=cash+shares*bar['close']
        if not math.isfinite(equity) or cash< -1e-6 or shares< -1e-9:refuse('NUMERIC','invalid simulation state')
        curve.append({'date':bar['date'],'equity':equity,'cash':cash,'shares':shares})
    if any(p['equity']<=0 for p in curve):refuse('NUMERIC','equity must remain positive for returns')
    returns=[curve[i]['equity']/curve[i-1]['equity']-1 for i in range(1,len(curve))]
    deviation=statistics.stdev(returns) if len(returns)>=2 else 0
    sharpe=statistics.mean(returns)/deviation*math.sqrt(annual) if deviation>1e-12 else None
    peak=initial;drawdown=0
    for point in curve:
        peak=max(peak,point['equity']);drawdown=max(drawdown,(peak-point['equity'])/peak)
    forecasts=None
    if 'forecast_predictions' in request or 'forecast_resolutions' in request:
        if not {'forecast_predictions','forecast_resolutions'}<=set(request):refuse('SCHEMA','both forecast collections required')
        try:scorer=_load_j1()
        except ImportError:refuse('DEPENDENCY','J1 single scorer unavailable; no fallback')
        forecasts=scorer(request['forecast_predictions'],request['forecast_resolutions'],bins=request.get('forecast_bins',10),calibrated=request.get('forecast_calibrated',True))
    return {'unit':'S7.2','disclaimer':DISCLAIMER,'equity_curve':curve,'trades':trades,'total_return':curve[-1]['equity']/initial-1,
            'max_drawdown':drawdown,'sharpe':sharpe,'turnover':notional/initial,'fees_paid':fees,'returns':returns,
            'forecast_scoring':forecasts,'scope':policy.scope(['prefix-only walk-forward long-only simulation','fees and adverse slippage','drawdown','sample-Sharpe','turnover'],
            ['hostile-code sandbox','external closure leak detection','live feeds','broker routing','real money','profit guarantees','independent source verification'],
            'supplied OHLC fixture and trusted deterministic strategy callable',as_of),
            'strategy_limit':'Ordinary history peeking detected; trusted code can access external globals, inspect Python objects or perform side effects. Not a security sandbox.'}
