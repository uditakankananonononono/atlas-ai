"""Domain logic for Calendar Intelligence (module 11).

Spec reference: user directive, Module 11.
- Sync: Google Calendar watch channels + incremental syncToken; external
  calendars (Outlook, Apple) via CalDAV.
- Smart scheduling: constraint solver (Solver protocol; OptaPy can plug in)
  over deadlines, user-configured energy levels, travel time, prep blocks.
- Conflict resolution: new deadline conflicts produce alternatives; applying
  any reschedule or weekly plan requires Approval Center approval first.

Advancement pass beyond spec: focus-block protection, splittable tasks,
sync-token expiry recovery, cancelled-event handling, channel-token
verification on webhooks, meeting-load analytics, append-only audit.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.core.models import ApprovalRequest
from app.core.token_crypto import TokenCipher

from .caldav import CalDAVClient
from .google_calendar import GoogleCalendarClient, SyncTokenExpiredError
from .conflicts import Availability, CalendarInterval, detect_conflicts
from .schemas import (
    CalDAVSourceCreate,
    CalendarEventView,
    CalendarSourceView,
    ConflictAlternative,
    ConflictReport,
    DayLoad,
    EventConflictView,
    GoogleSourceCreate,
    MeetingLoadReport,
    PlannedBlock,
    ProposedAction,
    SchedulingCandidateView,
    SchedulingPrefsSchema,
    SchedulingProposalRequest,
    SchedulingProposalView,
    SchedulingTaskCreate,
    SchedulingTaskView,
    SyncResult,
    WeeklyPlanView,
    WindowSchema,
)
from .proposals import ProposalRequest, propose_slots
from .sync_validation import validate_sync_batch
from .solver import (
    BuiltInSolver,
    FixedEvent,
    InfeasibleScheduleError,
    Placement,
    SchedulingPrefs,
    Solver,
    TaskSpec,
    Window,
)
from .sql_repository import SqlCalendarRepository


class SourceNotFoundError(LookupError):
    pass


class ChannelVerificationError(PermissionError):
    """A watch-channel notification carried the wrong token."""


class ApprovalNotGrantedError(PermissionError):
    """The referenced approval is missing, pending, or denied."""


class ApprovalGate(Protocol):
    """Module 0 boundary: propose actions and read their decisions."""

    def put(self, item: ApprovalRequest) -> ApprovalRequest: ...
    def status(self, approval_id: str) -> str: ...


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _prefs_from_schema(schema: SchedulingPrefsSchema | None) -> SchedulingPrefs:
    if schema is None:
        return SchedulingPrefs.default()
    prefs = SchedulingPrefs.default()
    if schema.working_hours:
        prefs.working_hours = {
            int(day): [Window(_to_min(w.start), _to_min(w.end)) for w in windows]
            for day, windows in schema.working_hours.items()
        }
    if schema.energy_curve:
        prefs.energy_curve = {int(h): int(v) for h, v in schema.energy_curve.items()}
    if schema.focus_blocks:
        prefs.focus_blocks = {
            int(day): [Window(_to_min(w.start), _to_min(w.end)) for w in windows]
            for day, windows in schema.focus_blocks.items()
        }
    prefs.travel_minutes_default = schema.travel_minutes_default
    prefs.travel_overrides = {
        tuple(sorted(k.split("|", 1))): int(v) for k, v in schema.travel_overrides.items()
    }
    return prefs


def _prefs_to_schema(prefs: SchedulingPrefs) -> SchedulingPrefsSchema:
    def win(w: Window) -> WindowSchema:
        return WindowSchema(start=f"{w.start_minute // 60:02d}:{w.start_minute % 60:02d}",
                            end=f"{w.end_minute // 60:02d}:{w.end_minute % 60:02d}")

    return SchedulingPrefsSchema(
        working_hours={d: [win(w) for w in ws] for d, ws in prefs.working_hours.items()},
        energy_curve=prefs.energy_curve,
        focus_blocks={d: [win(w) for w in ws] for d, ws in prefs.focus_blocks.items()},
        travel_minutes_default=prefs.travel_minutes_default,
        travel_overrides={"|".join(sorted(k)): v for k, v in prefs.travel_overrides.items()},
    )


def _to_min(hhmm: str) -> int:
    hours, _, minutes = hhmm.partition(":")
    return int(hours) * 60 + int(minutes)


def _block_view(placement: Placement) -> PlannedBlock:
    return PlannedBlock(
        task_id=placement.task_id, kind=placement.kind,  # type: ignore[arg-type]
        start=placement.start, end=placement.end, location=placement.location,
    )


class Service:
    def __init__(
        self,
        repository: SqlCalendarRepository,
        approval_gate: ApprovalGate,
        *,
        cipher: TokenCipher,
        google: GoogleCalendarClient | None = None,
        caldav: CalDAVClient | None = None,
        solver: Solver | None = None,
        webhook_base_url: str = "https://atlas.example.com/api/v1/calendar-intelligence/webhooks/google",
        google_access_token_provider=None,
    ) -> None:
        self.repository = repository
        self.approval_gate = approval_gate
        self.cipher = cipher
        self.google = google
        self.caldav = caldav
        self.solver = solver or BuiltInSolver()
        self.webhook_base_url = webhook_base_url
        self._google_access_token_provider = google_access_token_provider

    # -- sources --------------------------------------------------------------
    def register_google_source(self, data: GoogleSourceCreate) -> CalendarSourceView:
        source_id = str(uuid4())
        self.repository.save_source(
            source_id=source_id, provider="google", account_email=data.account_email,
            calendar_ref=data.calendar_id,
            encrypted_credentials=self.cipher.encrypt(data.refresh_token),
        )
        return self._source_view(self.repository.get_source(source_id))

    def register_caldav_source(self, data: CalDAVSourceCreate) -> CalendarSourceView:
        source_id = str(uuid4())
        self.repository.save_source(
            source_id=source_id, provider="caldav", account_email=data.account_email,
            calendar_ref=data.calendar_url,
            encrypted_credentials=self.cipher.encrypt(f"{data.username}:{data.password}"),
        )
        return self._source_view(self.repository.get_source(source_id))

    def list_sources(self) -> list[CalendarSourceView]:
        return [self._source_view(row) for row in self.repository.list_sources()]

    @staticmethod
    def _source_view(row) -> CalendarSourceView:
        return CalendarSourceView(
            id=row.id, provider=row.provider, account_email=row.account_email,
            calendar_ref=row.calendar_ref, watch_expiration=row.watch_expiration,
            has_sync_token=bool(row.sync_token), created_at=row.created_at,
        )

    # -- watch channels ----------------------------------------------------------
    async def ensure_watch(self, source_id: str) -> CalendarSourceView:
        if self.google is None:
            raise RuntimeError("google calendar client not configured")
        row = self._source(source_id)
        if row.provider != "google":
            raise ValueError("only google sources support watch channels")
        expiration = row.watch_expiration
        if expiration is not None and expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        if expiration and expiration > datetime.now(timezone.utc) + timedelta(hours=24):
            return self._source_view(row)  # still healthy
        access_token = self.cipher.decrypt(row.encrypted_credentials)
        channel_id = str(uuid4())
        channel_token = str(uuid4())
        info = await self.google.watch(
            access_token, row.calendar_ref, channel_id=channel_id,
            address=self.webhook_base_url, token=channel_token,
        )
        self.repository.update_watch(
            source_id,
            channel_id=info.channel_id, channel_token=channel_token,
            resource_id=info.resource_id,
            expiration=(
                datetime.fromtimestamp(info.expiration_ms / 1000.0, tz=timezone.utc)
                if info.expiration_ms else None
            ),
        )
        return self._source_view(self.repository.get_source(source_id))

    async def handle_google_notification(self, *, channel_id: str, channel_token: str,
                                         resource_state: str) -> SyncResult | None:
        row = self.repository.get_source_by_channel(channel_id)
        if row is None:
            raise SourceNotFoundError(channel_id)
        if channel_token != row.watch_channel_token:
            raise ChannelVerificationError("watch channel token mismatch")
        if resource_state == "sync":
            return None  # initial handshake; nothing to pull yet
        return await self.sync_source(row.id)

    # -- sync ------------------------------------------------------------------------
    async def sync_source(self, source_id: str) -> SyncResult:
        row = self._source(source_id)
        if row.provider == "google":
            return await self._sync_google(row)
        return await self._sync_caldav(row)

    async def _sync_google(self, row) -> SyncResult:
        if self.google is None:
            raise RuntimeError("google calendar client not configured")
        access_token = self.cipher.decrypt(row.encrypted_credentials)
        full_resync = False
        try:
            page = await self.google.list_events(
                access_token, row.calendar_ref, sync_token=row.sync_token, time_min=None)
        except SyncTokenExpiredError:
            full_resync = True
            page = await self.google.list_events(
                access_token, row.calendar_ref, sync_token=None,
                time_min=datetime.now(timezone.utc) - timedelta(days=30))
        result = self._upsert_events(row.id, page.events)
        result.full_resync = full_resync
        if page.next_sync_token:
            self.repository.update_sync_token(row.id, page.next_sync_token)
        return result

    async def _sync_caldav(self, row) -> SyncResult:
        if self.caldav is None:
            raise RuntimeError("caldav client not configured")
        username, _, password = self.cipher.decrypt(row.encrypted_credentials).partition(":")
        client = self.caldav
        if hasattr(client, "with_credentials"):
            client = client.with_credentials(username, password)  # type: ignore[union-attr]
        now = datetime.now(timezone.utc)
        events = await client.fetch_events(
            row.calendar_ref, now - timedelta(days=30), now + timedelta(days=180))
        return self._upsert_events(row.id, events)

    def _upsert_events(self, source_id: str, events) -> SyncResult:
        # Materialize and validate the whole provider response before the first
        # write, preventing malformed late entries from causing partial syncs.
        incoming = list(events)
        validated = validate_sync_batch(incoming)
        upserted = cancelled = 0
        for event in validated:
            self.repository.upsert_event(
                event_id=str(uuid4()), source_id=source_id, uid=event.uid,
                summary=event.summary, start=event.start, end=event.end,
                location=event.location, status=event.status,
            )
            if event.status == "cancelled":
                cancelled += 1
            else:
                upserted += 1
        return SyncResult(source_id=source_id, fetched=len(incoming),
                          upserted=upserted, cancelled=cancelled)

    def list_events(self, start: datetime | None = None, end: datetime | None = None) -> list[CalendarEventView]:
        return [
            CalendarEventView(
                id=row.id, uid=row.uid, source_id=row.source_id, summary=row.summary,
                start=row.start, end=row.end, location=row.location, status=row.status,
            )
            for row in self.repository.list_events(start=start, end=end)
        ]

    # -- prefs + tasks ------------------------------------------------------------------
    def propose_scheduling_slots(
        self, data: SchedulingProposalRequest
    ) -> SchedulingProposalView:
        if data.earliest.tzinfo is None or data.earliest.utcoffset() is None:
            raise ValueError("earliest must be timezone-aware")
        if data.latest.tzinfo is None or data.latest.utcoffset() is None:
            raise ValueError("latest must be timezone-aware")
        rows = self.repository.list_events(start=data.earliest, end=data.latest)
        if data.source_ids:
            allowed = set(data.source_ids)
            rows = [row for row in rows if row.source_id in allowed]
        fixed = [
            FixedEvent(
                id=row.id, summary=row.summary, start=_aware(row.start),
                end=_aware(row.end), location=row.location,
            )
            for row in rows
            if row.start is not None and row.end is not None
        ]
        saved = self.repository.get_prefs()
        prefs = _prefs_from_schema(
            SchedulingPrefsSchema.model_validate(saved) if saved else None
        )
        candidates = propose_slots(
            ProposalRequest(
                earliest=data.earliest, latest=data.latest,
                duration_minutes=data.duration_minutes, limit=data.limit,
                buffer_before_minutes=data.buffer_before_minutes,
                buffer_after_minutes=data.buffer_after_minutes,
                granularity_minutes=data.granularity_minutes,
            ),
            fixed,
            prefs,
        )
        return SchedulingProposalView(
            candidates=[
                SchedulingCandidateView(
                    start=item.start, end=item.end, score=item.score,
                    reasons=list(item.reasons),
                )
                for item in candidates
            ],
            considered_event_count=len(fixed),
        )

    def detect_event_conflicts(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        minimum_overlap_minutes: int = 1,
        across_sources_only: bool = False,
    ) -> list[EventConflictView]:
        """Find overlaps in the current synced event snapshot.

        Provider rows do not currently expose transparency/tentative metadata,
        so non-cancelled synced rows are conservatively treated as busy.
        """
        if minimum_overlap_minutes < 1:
            raise ValueError("minimum_overlap_minutes must be at least 1")
        intervals = [
            CalendarInterval(
                event_id=row.id,
                source_id=row.source_id,
                summary=row.summary,
                start=_aware(row.start),
                end=_aware(row.end),
                availability=Availability.BUSY,
                status=row.status,
            )
            for row in self.repository.list_events(
                start=start, end=end, include_cancelled=True
            )
            if row.start is not None and row.end is not None
        ]
        return [
            EventConflictView(
                id=conflict.id,
                left_event_id=conflict.left.event_id,
                right_event_id=conflict.right.event_id,
                left_source_id=conflict.left.source_id,
                right_source_id=conflict.right.source_id,
                overlap_start=conflict.overlap_start,
                overlap_end=conflict.overlap_end,
                overlap_minutes=conflict.overlap_minutes,
                severity=conflict.severity.value,
            )
            for conflict in detect_conflicts(
                intervals,
                minimum_overlap=timedelta(minutes=minimum_overlap_minutes),
                across_sources_only=across_sources_only,
            )
        ]

    def get_prefs(self) -> SchedulingPrefsSchema:
        stored = self.repository.get_prefs()
        return SchedulingPrefsSchema.model_validate(stored) if stored else _prefs_to_schema(SchedulingPrefs.default())

    def save_prefs(self, prefs: SchedulingPrefsSchema) -> SchedulingPrefsSchema:
        self.repository.save_prefs(prefs.model_dump(mode="json"))
        return prefs

    def create_task(self, data: SchedulingTaskCreate) -> SchedulingTaskView:
        task_id = str(uuid4())
        self.repository.save_task(
            task_id=task_id, title=data.title, duration_minutes=data.duration_minutes,
            deadline=data.deadline, priority=data.priority, location=data.location,
            prep_minutes=data.prep_minutes, splittable=data.splittable,
            min_block_minutes=data.min_block_minutes,
        )
        return SchedulingTaskView(id=task_id, created_at=datetime.now(timezone.utc), **data.model_dump())

    def list_tasks(self) -> list[SchedulingTaskView]:
        return [
            SchedulingTaskView(
                id=row.id, title=row.title, duration_minutes=row.duration_minutes,
                deadline=row.deadline, priority=row.priority, location=row.location,
                prep_minutes=row.prep_minutes, splittable=row.splittable,
                min_block_minutes=row.min_block_minutes, status=row.status,
                created_at=row.created_at,
            )
            for row in self.repository.list_tasks()
        ]

    # -- planning -------------------------------------------------------------------------
    def _solver_inputs(self, week_start: date, extra_tasks: list[TaskSpec] | None = None):
        horizon_start = datetime.combine(week_start, time(0, 0), tzinfo=timezone.utc)
        horizon_end = horizon_start + timedelta(days=7)
        fixed = [
            FixedEvent(id=row.uid, summary=row.summary, start=_aware(row.start),
                       end=_aware(row.end), location=row.location)
            for row in self.repository.list_events(start=horizon_start, end=horizon_end)
            if row.start is not None and row.end is not None
        ]
        tasks = [
            TaskSpec(
                id=row.id, title=row.title, duration_minutes=row.duration_minutes,
                deadline=_aware(row.deadline), priority=row.priority, location=row.location,
                prep_minutes=row.prep_minutes, splittable=row.splittable,
                min_block_minutes=row.min_block_minutes,
            )
            for row in self.repository.list_tasks(status="pending")
        ]
        if extra_tasks:
            tasks.extend(extra_tasks)
        prefs = _prefs_from_schema(SchedulingPrefsSchema.model_validate(self.repository.get_prefs()) if self.repository.get_prefs() else None)
        return tasks, fixed, prefs

    def plan_week(self, week_start: date) -> WeeklyPlanView:
        tasks, fixed, prefs = self._solver_inputs(week_start)
        placements = self.solver.solve(tasks, fixed, prefs, week_start)
        plan_id = str(uuid4())
        self.repository.save_plan(plan_id=plan_id, week_start=week_start.isoformat(),
                                  status="draft", approval_id=None)
        self.repository.replace_plan_blocks(
            plan_id, [self._placement_payload(p) for p in placements])
        return WeeklyPlanView(
            id=plan_id, week_start=week_start.isoformat(), status="draft",
            blocks=[_block_view(p) for p in placements],
        )

    def propose_plan(self, plan_id: str) -> ProposedAction:
        plan = self._plan(plan_id)
        blocks = self.repository.plan_blocks(plan_id)
        payload = {
            "plan_id": plan_id,
            "week_start": plan.week_start,
            "blocks": [
                {"task_id": b.task_id, "kind": b.kind, "start": _aware(b.start).isoformat(),
                 "end": _aware(b.end).isoformat(), "location": b.location}
                for b in blocks
            ],
        }
        approval = ApprovalRequest(
            id=str(uuid4()), module_id=11, action_type="apply_calendar_plan", payload=payload)
        self.approval_gate.put(approval)
        self.repository.set_plan_status(plan_id, "proposed", approval_id=approval.id)
        return ProposedAction(approval_id=approval.id,
                              action_type="apply_calendar_plan", payload=payload)

    def apply_plan(self, approval_id: str) -> WeeklyPlanView:
        """Apply only after the Approval Center approved. Calendar writes are a
        separate gated dispatcher; this marks the plan and tasks applied."""
        self._require_approved(approval_id)
        payload = self.approval_gate_payload(approval_id)
        plan_id = payload["plan_id"]
        plan = self._plan(plan_id)
        self.repository.set_plan_status(plan_id, "applied")
        for block in payload["blocks"]:
            self.repository.set_task_status(block["task_id"], "scheduled")
        blocks = self.repository.plan_blocks(plan_id)
        return WeeklyPlanView(
            id=plan_id, week_start=plan.week_start, status="applied",
            approval_id=approval_id,
            blocks=[PlannedBlock(task_id=b.task_id, kind=b.kind, start=b.start,  # type: ignore[arg-type]
                                 end=b.end, location=b.location) for b in blocks],
        )

    # -- conflict resolution ---------------------------------------------------------------
    def request_reschedule(self, data: SchedulingTaskCreate) -> tuple[ConflictReport | None, ProposedAction | None]:
        """Try to fit a new task. On conflict, build alternatives and propose
        the first viable one through the Approval Center."""
        new_task = TaskSpec(
            id=str(uuid4()), title=data.title, duration_minutes=data.duration_minutes,
            deadline=_aware(data.deadline), priority=data.priority, location=data.location,
            prep_minutes=data.prep_minutes, splittable=data.splittable,
            min_block_minutes=data.min_block_minutes,
        )
        week_start = min(datetime.now(timezone.utc).date(), _aware(data.deadline).date())
        tasks, fixed, prefs = self._solver_inputs(week_start)
        try:
            self.solver.solve(tasks + [new_task], fixed, prefs, week_start)
            return None, None  # fits without conflict
        except InfeasibleScheduleError as exc:
            reason = exc.reason

        alternatives: list[ConflictAlternative] = []

        if not new_task.splittable:
            split = replace(new_task, splittable=True)
            try:
                placements = self.solver.solve(tasks + [split], fixed, prefs, week_start)
                alternatives.append(ConflictAlternative(
                    kind="split_task",
                    summary=f"Split '{new_task.title}' into smaller blocks",
                    blocks=[_block_view(p) for p in placements if p.task_id == new_task.id],
                ))
            except InfeasibleScheduleError:
                pass

        deadline_weekday = min(_aware(data.deadline).weekday(), 6)
        extended = SchedulingPrefs(
            working_hours={d: list(ws) for d, ws in prefs.working_hours.items()},
            energy_curve=prefs.energy_curve, focus_blocks=prefs.focus_blocks,
            travel_minutes_default=prefs.travel_minutes_default,
            travel_overrides=prefs.travel_overrides,
        )
        base_windows = extended.working_hours.get(deadline_weekday, [])
        if base_windows:
            extended.working_hours[deadline_weekday] = [
                Window(w.start_minute, min(w.end_minute + 120, 23 * 60 + 45)) for w in base_windows
            ]
            try:
                placements = self.solver.solve(tasks + [new_task], fixed, extended, week_start)
                alternatives.append(ConflictAlternative(
                    kind="extend_hours",
                    summary=f"Extend working hours by 2h on the deadline day",
                    blocks=[_block_view(p) for p in placements if p.task_id == new_task.id],
                ))
            except InfeasibleScheduleError:
                pass

        if tasks:
            lowest = min(tasks, key=lambda t: (t.priority, -_aware(t.deadline).timestamp()))
            if lowest.priority < new_task.priority or len(tasks) > 1:
                remaining = [t for t in tasks if t.id != lowest.id]
                try:
                    placements = self.solver.solve(remaining + [new_task], fixed, prefs, week_start)
                    alternatives.append(ConflictAlternative(
                        kind="reschedule_lowest_priority",
                        summary=f"Push lower-priority task '{lowest.title}' out of this week",
                        blocks=[_block_view(p) for p in placements if p.task_id == new_task.id],
                        displaced_task_ids=[lowest.id],
                    ))
                except InfeasibleScheduleError:
                    pass

        report = ConflictReport(task_id=new_task.id, reason=reason, alternatives=alternatives)
        if not alternatives:
            return report, None

        chosen = alternatives[0]
        payload = {
            "task": {"id": new_task.id, **data.model_dump(mode="json")},
            "alternative": chosen.kind,
            "blocks": [b.model_dump(mode="json") for b in chosen.blocks],
            "displaced_task_ids": chosen.displaced_task_ids,
            "week_start": week_start.isoformat(),
        }
        approval = ApprovalRequest(
            id=str(uuid4()), module_id=11, action_type="apply_reschedule", payload=payload)
        self.approval_gate.put(approval)
        proposal = ProposedAction(approval_id=approval.id,
                                  action_type="apply_reschedule", payload=payload)
        return report, proposal

    def apply_reschedule(self, approval_id: str) -> SchedulingTaskView:
        """Apply an approved reschedule: persist the task and its new blocks."""
        self._require_approved(approval_id)
        payload = self.approval_gate_payload(approval_id)
        task_data = payload["task"]
        view = self.create_task(SchedulingTaskCreate(**{
            k: v for k, v in task_data.items() if k != "id"}))
        plan_id = str(uuid4())
        self.repository.save_plan(plan_id=plan_id, week_start=payload["week_start"],
                                  status="applied", approval_id=approval_id)
        self.repository.replace_plan_blocks(plan_id, [
            {"task_id": view.id, "kind": b["kind"],
             "start": _parse_iso(b["start"]), "end": _parse_iso(b["end"]),
             "location": b.get("location")}
            for b in payload["blocks"]
        ])
        for displaced in payload.get("displaced_task_ids", []):
            self.repository.set_task_status(displaced, "deferred")
        self.repository.set_task_status(view.id, "scheduled")
        return view.model_copy(update={"status": "scheduled"})

    # -- analytics (advancement pass) -------------------------------------------------------
    def meeting_load(self, week_start: date) -> MeetingLoadReport:
        horizon_start = datetime.combine(week_start, time(0, 0), tzinfo=timezone.utc)
        horizon_end = horizon_start + timedelta(days=7)
        events = self.repository.list_events(start=horizon_start, end=horizon_end)
        days: list[DayLoad] = []
        total = 0
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            day_start = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)
            todays = [
                e for e in events
                if e.start is not None and e.end is not None
                and _aware(e.start) < day_end and _aware(e.end) > day_start
            ]
            todays.sort(key=lambda e: _aware(e.start))
            minutes = sum(int((_aware(e.end) - _aware(e.start)).total_seconds() // 60) for e in todays)
            longest = max((int((_aware(e.end) - _aware(e.start)).total_seconds() // 60) for e in todays), default=0)
            short_gaps = 0
            for first, second in zip(todays, todays[1:]):
                gap = (_aware(second.start) - _aware(first.end)).total_seconds() / 60.0
                if 0 < gap < 30:
                    short_gaps += 1
            total += minutes
            days.append(DayLoad(
                date=day.isoformat(), meeting_minutes=minutes, meeting_count=len(todays),
                longest_meeting_minutes=longest, short_gaps=short_gaps,
            ))
        return MeetingLoadReport(week_start=week_start.isoformat(), days=days,
                                 total_meeting_minutes=total)

    # -- helpers --------------------------------------------------------------------------
    def _require_approved(self, approval_id: str) -> None:
        try:
            status = self.approval_gate.status(approval_id)
        except Exception as exc:
            raise ApprovalNotGrantedError(f"approval {approval_id} not found") from exc
        if status != "approved":
            raise ApprovalNotGrantedError(f"approval {approval_id} is {status}, not approved")

    def approval_gate_payload(self, approval_id: str) -> dict[str, Any]:
        getter = getattr(self.approval_gate, "payload", None)
        if getter is None:
            raise ApprovalNotGrantedError("approval gate cannot return payloads")
        return getter(approval_id)

    def _source(self, source_id: str):
        row = self.repository.get_source(source_id)
        if row is None:
            raise SourceNotFoundError(source_id)
        return row

    def _plan(self, plan_id: str):
        plan = self.repository.get_plan(plan_id)
        if plan is None:
            raise SourceNotFoundError(f"plan {plan_id}")
        return plan

    @staticmethod
    def _placement_payload(placement: Placement) -> dict[str, Any]:
        return {"task_id": placement.task_id, "kind": placement.kind,
                "start": placement.start, "end": placement.end,
                "location": placement.location}
