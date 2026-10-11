"""CRIMIN1261: caller-declared criminal-appeal preservation bookkeeping, no merit view."""
import copy
import re
import unicodedata
from datetime import date

BOUNDARY=("Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, "
          "currency, citations, facts, duties, deadlines and strategy before use.")
LIMITS={'orders':50,'record_cites':500,'issues':100,'cite_ids':50,'text':2000,'enum':32,'id':100,'page':100000}
ORDER_KINDS=('judgment','sentence','post_trial_order','suppression_ruling','other_declared')
STATUSES=('preserved','not_preserved','unknown')
# Cc, Cf (full category, including U+00AD and U+2060), Zl, Zp refused; Zs accepted.
# Cs surrogates get no refusal here (disclosed residual). Co and Cn stay refused.
_BAD_CATEGORIES={'Cc','Cf','Zl','Zp','Co','Cn'}
_PINNED_BAD=('\u00ad','\u2060')


class Crimin1261Error(ValueError):
    pass


def _refuse(field,reason):
    # Field names and fixed reasons only; request text never enters a refusal.
    raise Crimin1261Error('CRIMIN1261:'+field+':'+reason)


def _keys(value,keys,field):
    if type(value) is not dict or len(value)!=len(keys) or any(type(k) is not str for k in value) or set(value)!=set(keys):
        _refuse(field,'unexpected or missing keys')


def _list(value,field,low,high):
    if type(value) is not list:
        _refuse(field,'must be a list')
    if not low<=len(value)<=high:
        _refuse(field,'must have %d..%d entries'%(low,high))
    return value


def _text(value,field):
    if type(value) is not str or len(value)>LIMITS['text']:
        _refuse(field,'must be bounded nonblank text')
    if not value.strip() or any(c in _PINNED_BAD or unicodedata.category(c) in _BAD_CATEGORIES for c in value):
        _refuse(field,'must be bounded nonblank text')
    return value


def _enum(value,allowed,field):
    # Strict type, then raw length cap, only then membership.
    if type(value) is not str or len(value)>LIMITS['enum']:
        _refuse(field,'must be bounded enum text')
    if value not in allowed:
        _refuse(field,'not an allowed value')
    return value


def _opt_text(value,field):
    return None if value is None else _text(value,field)


def _id(value,field):
    if type(value) is not str or len(value)>LIMITS['id'] or not re.fullmatch(r'[A-Za-z0-9_.:-]+',value):
        _refuse(field,'must be a bounded ascii id')
    return value


def _date(value,field):
    if type(value) is not str or len(value)!=10 or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):
        _refuse(field,'must be an ISO date')
    try:
        return date.fromisoformat(value)
    except ValueError:
        _refuse(field,'must be an ISO date')


def map_appeal_preservation(packet):
    """Organize supplied orders, record cites and issues; never assess merit or verify anything."""
    _keys(packet,('jurisdiction','as_of','orders','record_cites','issues'),'packet')
    orders=_list(packet['orders'],'orders',1,LIMITS['orders'])
    cites=_list(packet['record_cites'],'record_cites',1,LIMITS['record_cites'])
    issues=_list(packet['issues'],'issues',1,LIMITS['issues'])
    jurisdiction=_text(packet['jurisdiction'],'jurisdiction')
    as_of_text=packet['as_of'];as_of=_date(as_of_text,'as_of')
    order_by_id={}
    for o in orders:
        _keys(o,('id','kind','entered_on','court'),'orders')
        oid=_id(o['id'],'orders.id')
        if oid in order_by_id:_refuse('orders.id','duplicate id')
        _enum(o['kind'],ORDER_KINDS,'orders.kind')
        if _date(o['entered_on'],'orders.entered_on')>as_of:_refuse('orders.entered_on','after as_of')
        order_by_id[oid]={'id':oid,'kind':o['kind'],'entered_on':o['entered_on'],'court':_text(o['court'],'orders.court')}
    cite_by_id={}
    for c in cites:
        _keys(c,('id','document','page'),'record_cites')
        cid=_id(c['id'],'record_cites.id')
        if cid in cite_by_id:_refuse('record_cites.id','duplicate id')
        page=c['page']
        if type(page) is not int or not 1<=page<=LIMITS['page']:_refuse('record_cites.page','must be an integer within 1..100000')
        cite_by_id[cid]={'id':cid,'document':_text(c['document'],'record_cites.document'),'page':page}
    seen=set();rows=[]
    for i in issues:
        _keys(i,('id','order_id','label','preservation','review_standard','remedy'),'issues')
        iid=_id(i['id'],'issues.id')
        if iid in seen:_refuse('issues.id','duplicate id')
        seen.add(iid)
        oid=_id(i['order_id'],'issues.order_id')
        if oid not in order_by_id:_refuse('issues.order_id','unknown order id')
        label=_text(i['label'],'issues.label')
        pres=i['preservation'];_keys(pres,('status','cite_ids'),'issues.preservation')
        _enum(pres['status'],STATUSES,'issues.preservation.status')
        ids=_list(pres['cite_ids'],'issues.preservation.cite_ids',0,LIMITS['cite_ids'])
        used=set()
        for x in ids:
            _id(x,'issues.preservation.cite_ids')
            if x in used:_refuse('issues.preservation.cite_ids','duplicate cite id')
            if x not in cite_by_id:_refuse('issues.preservation.cite_ids','unknown record cite id')
            used.add(x)
        std=i['review_standard'];_keys(std,('label','authority_ref'),'issues.review_standard')
        std_label=_text(std['label'],'issues.review_standard.label')
        ref=_opt_text(std['authority_ref'],'issues.review_standard.authority_ref')
        rem=i['remedy'];_keys(rem,('sought','limit_note'),'issues.remedy')
        sought=_opt_text(rem['sought'],'issues.remedy.sought');note=_opt_text(rem['limit_note'],'issues.remedy.limit_note')
        gaps=[]
        if pres['status']=='preserved' and not ids:gaps.append('preserved_declared_without_record_cite')
        if pres['status']=='unknown':gaps.append('preservation_status_unknown')
        if pres['status']=='not_preserved':gaps.append('declared_not_preserved')
        if ref is None:gaps.append('review_standard_authority_ref_missing')
        if sought is None:gaps.append('remedy_sought_missing')
        if note is None:gaps.append('remedy_limit_note_missing')
        rows.append({'id':iid,'label':label,'order':copy.deepcopy(order_by_id[oid]),
            'preservation_status':pres['status'],'record_cites':[copy.deepcopy(cite_by_id[x]) for x in ids],
            'review_standard':{'label':std_label,'authority_ref':ref,'declared_by_caller':True,'verified':False},
            'remedy':{'sought':sought,'limit_note':note},'gaps':gaps})
    rows.sort(key=lambda r:r['id'])
    return {'scope':'caller_declared_appeal_bookkeeping_only','jurisdiction':jurisdiction,'as_of':as_of_text,
        'orders':[order_by_id[k] for k in sorted(order_by_id)],'issues':rows,
        'summary':{'order_count':len(order_by_id),'issue_count':len(rows),'issues_with_gaps':sum(1 for r in rows if r['gaps'])},
        'merit_assessed':False,'outcome_predicted':False,'deadlines_computed':False,'authority_verified':False,
        'record_verified':False,'filing_or_external_effect':False,'legal_conclusion':None,
        'review_state':'counsel_review_required','boundary':BOUNDARY}
