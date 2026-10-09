# Approval list row limit

Service.list now requires an actual integer from 1 to 1000; HTTP query validation
uses the same bounds. The explicit ceiling of 1000 is NEW policy introduced
by this change, not a pre-existing limit; default 100 is unchanged. SQLite negative LIMIT previously meant no limit, and zero,
booleans and oversized requests were accepted. Tests verify domain refusals and
HTTP 422 for negative input, with actual SQLite/test-client execution. This is a
row cap, not payload-byte/metadata bounding, pagination or full M00 closure.
