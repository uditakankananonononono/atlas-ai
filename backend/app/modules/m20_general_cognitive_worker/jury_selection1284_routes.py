"""Row1284 jury selection: supplied-reference bookkeeping only. No legal advice, juror profiling or effects."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth.context import require_tenant
from . import jury_selection1284
from .legal_a3_engine import LegalA3Refusal

router = APIRouter(prefix='/m20/legal/1284', tags=['row1284'],
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
        raise HTTPException(415, 'JURYSE1284: application/json required')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(413, 'JURYSE1284: body exceeds byte limit')
        body.extend(chunk)
    try:
        data = json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise HTTPException(422, 'JURYSE1284: invalid JSON') from None
    try:
        return jury_selection1284.run(data)
    except LegalA3Refusal as exc:
        raise HTTPException(422, str(exc)) from None
