# Direct approval proposal TTL validation

Direct submit now permits None or a positive actual integer TTL. Zero previously
silently removed expiry; negative values created already-overdue proposals, while
boolean/fractional values were accepted. Tests use real SQLite proposal storage. HTTP schema already required positive values; no HTTP change here.
No upper bound or clock-overflow handling added. Policy review TTL validation,
approved-permit deadline semantics and external effects unchanged. No M00 closure.
