"""Row87 supplied deal-control declaration inventory, no prevention claim."""
import copy

CLASSES=('monitoring','bonding','deductible')
LIMITS=[
    'Caller declarations only; no verification of actual monitoring, incentive alignment, enforceability or control effectiveness.',
    'Missing classes are schema inventory gaps, not a recommendation every deal must use every class.',
    'No causal moral-hazard prevention, risk prediction, deal decision, outreach or external action is performed.',
]

def _fail(message):raise ValueError('MORAL87: '+message)
def _text(value,label):
    if not isinstance(value,str) or not value.strip() or len(value)>200 or any(ord(c)<32 for c in value):
        _fail(label+' must be nonblank control-free text up to 200 characters')
    return value.strip()
def _keys(value,expected,label):
    if not isinstance(value,dict) or set(value)!=set(expected):_fail(label+' must have exactly '+','.join(expected))

def inventory(data):
    """Return exact declared class presence per action and named input gaps."""
    _keys(data,('source_ref','actions','controls'),'request')
    source=_text(data['source_ref'],'source_ref')
    if not isinstance(data['actions'],list) or not 1<=len(data['actions'])<=100:_fail('actions must be a list of 1-100 records')
    if not isinstance(data['controls'],list) or len(data['controls'])>300:_fail('controls must be a list of at most 300 records')
    actions={}
    for item in data['actions']:
        _keys(item,('id','observable','incentive'),'action')
        identifier=_text(item['id'],'action id')
        if identifier in actions:_fail('duplicate action id')
        if type(item['observable']) is not bool:_fail('observable must be boolean')
        if item['incentive'] not in ('aligned','misaligned','unknown'):_fail('incentive must be aligned, misaligned or unknown')
        actions[identifier]={'id':identifier,'observable':item['observable'],'incentive':item['incentive']}
    controls=[];seen=set();presence={i:set() for i in actions}
    for item in data['controls']:
        _keys(item,('action_id','class','source_ref'),'control')
        identifier=_text(item['action_id'],'control action_id')
        if identifier not in actions:_fail('control references unknown action')
        kind=item['class']
        if kind not in CLASSES:_fail('control class must be monitoring, bonding or deductible')
        ref=_text(item['source_ref'],'control source_ref')
        key=(identifier,kind)
        if key in seen:_fail('duplicate action/class declaration')
        seen.add(key);presence[identifier].add(kind)
        controls.append({'action_id':identifier,'class':kind,'source_ref':ref})
    rows=[actions[i] for i in sorted(actions)]
    gaps=[{'action_id':i,'missing_classes':[c for c in CLASSES if c not in presence[i]]} for i in sorted(actions)]
    return {'source_ref':source,'actions':copy.deepcopy(rows),'controls':sorted(controls,key=lambda x:(x['action_id'],x['class'])),
            'action_gaps':gaps,'declared_class_counts':{c:sum(c in p for p in presence.values()) for c in CLASSES},
            'unobservable_action_ids':[x['id'] for x in rows if not x['observable']],
            'misaligned_action_ids':[x['id'] for x in rows if x['incentive']=='misaligned'],
            'unknown_incentive_action_ids':[x['id'] for x in rows if x['incentive']=='unknown'],
            'all_declared_classes_present':all(not x['missing_classes'] for x in gaps),
            'controls_effective_verified':False,'limits':list(LIMITS)}
