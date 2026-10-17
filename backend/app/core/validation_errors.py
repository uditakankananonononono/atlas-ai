"""422 rendering boundary: request-validation errors can carry non-finite float inputs
(NaN/inf) in their payload; the default JSONResponse (allow_nan=False) then fails with a 500
instead of delivering the 422. Sanitize non-finite floats to their string form, then apply the default jsonable_encoder so Decimal/date/bytes/Enum error values render exactly as the baseline handler rendered them."""
import math
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

def _finite_safe(value):
    if isinstance(value,float) and not math.isfinite(value):return str(value)
    if isinstance(value,dict):return {k:_finite_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_finite_safe(v) for v in value]
    return value

async def request_validation_error_handler(request:Request,exc:RequestValidationError)->JSONResponse:
    return JSONResponse(status_code=422,content={"detail":jsonable_encoder(_finite_safe(exc.errors()))})
