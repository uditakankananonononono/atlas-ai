"""Bounded caller-declared blockers/UNVERIFIED register. No detection or effects."""

def _text(value, name, limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError(f'{name}: expected nonblank string of length 1..{limit}')
    return value


def register_blockers(items):
    """Return canonical register of supplied declarations, not real-world truth."""
    if type(items) is not list or len(items)>256:
        raise ValueError('items: expected list of at most 256 records')
    rows=[];seen=set();counts={'BLOCKED':0,'UNVERIFIED':0,'RESOLVED':0}
    for item in items:
        if type(item) is not dict or set(item)!={'id','owner','status','reason','source_refs'}:
            raise ValueError('item: exactly id,owner,status,reason,source_refs required')
        ident=_text(item['id'],'id',128)
        if ident in seen:raise ValueError(f'duplicate item id: {ident}')
        seen.add(ident)
        owner=_text(item['owner'],'owner',128);reason=_text(item['reason'],'reason',2000)
        status=item['status']
        if not isinstance(status,str) or status not in counts:
            raise ValueError('status: expected BLOCKED, UNVERIFIED or RESOLVED')
        refs=item['source_refs']
        if type(refs) is not list or len(refs)>16:
            raise ValueError('source_refs: expected list of at most 16 references')
        checked=[]
        for ref in refs:
            ref=_text(ref,'source_ref',256)
            if ref in checked:raise ValueError(f'duplicate source_ref: {ref}')
            checked.append(ref)
        rows.append(dict(id=ident,owner=owner,status=status,reason=reason,source_refs=sorted(checked),
                         owner_is_caller_declared=True,status_is_caller_declared=True))
        counts[status]+=1
    rows.sort(key=lambda x:x['id'])
    return dict(items=rows,counts=counts,open_item_ids=[x['id'] for x in rows if x['status']!='RESOLVED'],
                missing_source_item_ids=[x['id'] for x in rows if not x['source_refs']],
                status='declared_input_register_only',evidence_verified=False,actual_blockers_exhaustively_checked=False,
                completion_verified=False,
                boundary='Only supplied records checked. Empty register does not prove absence of actual blockers; RESOLVED and owner are caller declarations, not verified completion or assignment.')
