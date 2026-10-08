# M11 calendar occupancy candidate

## Executable feature

`calendar_occupancy.py` calculates occupied time from actual timestamp intervals.
It clips to each civil day, unions overlapping meetings, records elapsed time
with two or more simultaneous meetings and peak concurrency, and counts free
seconds. It preserves fractional seconds. It excludes cancelled and transparent
(non-busy) records. All endpoints must be aware, and event IDs must be unique.
Duplicate records, nonexistent local endpoint times and reversed or zero-length
intervals are rejected, not silently guessed or dropped.

Civil-day boundaries use IANA ZoneInfo. The tested boundaries include 23-hour
and 25-hour days, an ambiguous midnight, a missing midnight, and Apia's skipped
civil date. Seconds are elapsed UTC seconds, not wall-clock subtraction. A
skipped date has zero seconds. Intervals are half-open: an event ending at the
horizon start or starting at its end is excluded.

`occupied_seconds` is union length. `event_seconds` is the sum of individual
clipped event durations. `overlapping_seconds` is union length of regions with
at least two events, not `event_seconds - occupied_seconds`. No metric is
rounded to minutes, and no score or prediction is generated.

## Run

From the repository root:

```sh
python3 tests/modules/test_m11_calendar_occupancy_lane.py
printf '%s\n' '[{"event_id":"a","start":"2026-10-08T09:00:00+00:00","end":"2026-10-08T10:00:00+00:00"}]' |
  python3 backend/app/modules/m11_calendar_intelligence/calendar_occupancy.py \
    --start-date 2026-10-08 --timezone Asia/Kolkata --days 1
```

The second command emits an occupancy report with 3600 occupied seconds, 3600
event seconds, no overlap, peak concurrency 1 and 82800 free seconds.
The CLI consumes a JSON array. Allowed fields are `event_id`, `start`, `end`,
`busy` and `cancelled`. Unknown fields and invalid shapes produce a generic JSON
error on stderr with exit code 2, without echoing input data.

The implementation uses only the Python standard library. A system IANA tzdb
(or installed tzdata provider) is required. The standalone executable tests
load the module by file path to avoid importing the repository's eager module
registration and its unrelated backend dependencies.

## Verification scope

The retained receipts name exact commands and counts. Tests run the real
calculation and CLI process. A seeded 200-case discrete oracle independently
checks union seconds, summed event seconds, overlap seconds, peak concurrency
and input-order invariance. A 10000-event case runs the same implementation.
These are generated input fixtures, not claims of connected-calendar execution.

## Not integrated or verified

No service, routes, schema, solver, OAuth or provider files are changed. In this
public base, `Service.meeting_load` still uses UTC boundaries and sums full
unclipped event durations. This additive module does NOT fix that deployed API.
An integrator must decide how to expose occupied time versus meeting-duration
sum without silently changing the legacy field's meaning, pass tenant-scoped
repository events, preserve event transparency and cancellation metadata, and
run route/repository compatibility tests on the authoritative branch.

Token refresh is outside this change. Existing unpublished refresh wiring is
not in this public clone and is not independently accepted by these receipts.
No live OAuth, connected calendar, calendar sync, auth, database, production
rollout, full M11 closure or end-product acceptance is claimed. Civil-date
boundary tests cover the named zones and dates, not every historical IANA
transition or leap seconds (Python datetime does not represent leap seconds).

All work is on a private branch. No main edits, pushes or live external effects.

## Follow-up: integrated service and refresh repair

The follow-up commit integrates the calculator into `Service.meeting_load` and
adds the `timezone` query parameter to the mounted analytics route. Invalid
IANA timezone names return 422 before service execution. `meeting_minutes`
retains its individual-event sum meaning, but is now clipped to each local day
and rounded once per day. Union seconds are separate additive fields, including
weekly totals. Short gaps are measured between merged occupied regions so a
nested event does not hide a gap after a longer enclosing event. Repository
queries are tenant-scoped and explicitly unbounded for this seven-day report;
ordinary event-list callers retain the 500-row default. Memory use scales with
the number of retrieved events and report execution is not quota-limited here.

SQLite stores UTC instants without tzinfo. The existing `_aware` convention
reattaches UTC before occupancy computation. Null endpoint records cannot be
included in duration accounting. Cancelled records are excluded by the query.
Event transparency is not stored by the current repository, so integrated
service accounting treats all remaining events as busy; standalone callers can
still specify transparency. No schema migration or transparency-sync repair is
claimed.

Watch and sync now await the configured refresh provider rather than using the
stored refresh token as Bearer. The route constructs `GoogleRefreshExchange`
using its actual HTTP client. It reads `ATLAS_GOOGLE_CLIENT_ID` and
`ATLAS_GOOGLE_CLIENT_SECRET` and POSTs the refresh grant to Google's token
endpoint. Non-2xx (including valid-looking-token bodies), missing configuration,
missing/invalid access tokens, a token equal to the refresh token and non-Bearer
token type stop provider use. Errors do not echo token response bodies. Tokens
are not cached or persisted; each required watch/sync operation exchanges again.
No live OAuth was attempted, since owner client configuration and a connected
calendar were not available in this isolated test environment.

Verification: same 15 regression pins fail on the earlier standalone commit and
pass after integration on Python 3.12.14. New regression file has 26 test cases
including HTTP mock transport response tests. Full `test_m11*` selection has 112
passes after integration and after restoring five integration mutants; the
receipts distinguish these from the earlier standalone 17-case selection.
Existing watch/sync tests have one fixture adaptation: an explicit offline
refresh callback returns a test access token. No production fallback sends
refresh credentials as Bearer. Full main-app route imports run under Python
3.12, not a compatibility shim. Earlier failed setup attempts are retained.

This supersedes the earlier 'Not integrated' paragraph only for the service,
route and local repository paths named above. It does not establish deployment,
connected-calendar behavior, live OAuth, all solver/plan paths, tenant auth
review, or whole M11/constitution acceptance. Integration into authoritative
main remains the owner's next step, not performed by this branch.
