"""Row105 bounded bookkeeping endpoint. No deployment or persuasion effect."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth.context import require_tenant
from . import pre_suasion105

router = APIRouter(prefix='/m20/pre-suasion105', tags=['row105'],
                   dependencies=[Depends(require_tenant)])
MAX_BODY_BYTES = 8192


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _reject_constant(_):
    raise ValueError('non-finite number')


@router.post('/review')
async def review(request: Request):
    media_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
    if media_type != 'application/json':
        raise HTTPException(415, 'PRESUA105: application/json required')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(413, 'PRESUA105: body exceeds byte limit')
        body.extend(chunk)
    try:
        data = json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise HTTPException(422, 'PRESUA105: invalid JSON') from None
    try:
        return pre_suasion105.review(data)
    except pre_suasion105.PreSuasionError as exc:
        raise HTTPException(422, str(exc)) from None
