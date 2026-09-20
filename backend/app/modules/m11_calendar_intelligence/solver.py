"""Constraint-satisfaction weekly scheduler.

Spec reference: "A constraint-satisfaction solver (optapy) considers task
deadlines, energy levels (user-configured), travel time, and preparatory work
blocks. It suggests an optimised weekly schedule."

The OptaPy/optaplanner seam is the Solver protocol: a JVM-backed
implementation can plug in later without touching the service. The built-in
solver is a real CSP: hard constraints (working hours, no overlap, deadline,
travel buffers, prep blocks, protected focus time) and a soft objective
(energy fit, then earliest placement). Tasks are placed highest-priority /
earliest-deadline first; failure raises InfeasibleScheduleError, which the
conflict-resolution layer turns into human-reviewable alternatives.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol

SLOT_MINUTES = 15


@dataclass(frozen=True)
class FixedEvent:
    id: str
    summary: str
    start: datetime
    end: datetime
    location: str | None = None


@dataclass(frozen=True)
class TaskSpec:
    id: str
    title: str
    duration_minutes: int
    deadline: datetime
    priority: int = 3
    location: str | None = None
    prep_minutes: int = 0
    splittable: bool = False
    min_block_minutes: int = 30


@dataclass(frozen=True)
class Window:
    start_minute: int  # minutes since midnight
    end_minute: int


@dataclass
class SchedulingPrefs:
    working_hours: dict[int, list[Window]] = field(default_factory=dict)
    energy_curve: dict[int, int] = field(default_factory=dict)  # hour -> 1..5
    focus_blocks: dict[int, list[Window]] = field(default_factory=dict)
    travel_minutes_default: int = 0
    travel_overrides: dict[tuple[str, str], int] = field(default_factory=dict)

    @staticmethod
    def default() -> "SchedulingPrefs":
        return SchedulingPrefs(
            working_hours={d: [Window(9 * 60, 17 * 60)] for d in range(7)},
            energy_curve={h: 3 for h in range(24)},
        )

    def energy_at(self, hour: int) -> int:
        return self.energy_curve.get(hour, 3)

    def travel_minutes(self, a: str | None, b: str | None) -> int:
        if not a or not b or a == b:
            return 0
        key = tuple(sorted([a, b]))
        return self.travel_overrides.get(key, self.travel_minutes_default)


@dataclass(frozen=True)
class Placement:
    task_id: str
    kind: str  # "task" | "prep"
    start: datetime
    end: datetime
    location: str | None = None


class InfeasibleScheduleError(RuntimeError):
    def __init__(self, task_id: str, reason: str) -> None:
        super().__init__(f"cannot schedule task {task_id}: {reason}")
        self.task_id = task_id
        self.reason = reason


class Solver(Protocol):
    def solve(self, tasks: list[TaskSpec], fixed_events: list[FixedEvent],
              prefs: SchedulingPrefs, week_start: date, days: int = 7) -> list[Placement]: ...


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _day_dt(day: date, minute: int) -> datetime:
    return datetime.combine(day, time(minute // 60, minute % 60), tzinfo=timezone.utc)


@dataclass
class _Busy:
    start: datetime
    end: datetime
    location: str | None


class BuiltInSolver:
    """Greedy best-slot CSP with 15-minute granularity."""

    def solve(self, tasks: list[TaskSpec], fixed_events: list[FixedEvent],
              prefs: SchedulingPrefs, week_start: date, days: int = 7) -> list[Placement]:
        busy: list[_Busy] = [
            _Busy(_aware(e.start), _aware(e.end), e.location) for e in fixed_events
        ]
        # Focus blocks are protected time: treated as busy.
        for offset in range(days):
            day = week_start + timedelta(days=offset)
            for window in prefs.focus_blocks.get(day.weekday(), []):
                busy.append(_Busy(_day_dt(day, window.start_minute), _day_dt(day, window.end_minute), None))

        placements: list[Placement] = []
        ordered = sorted(tasks, key=lambda t: (-t.priority, _aware(t.deadline), t.id))
        for task in ordered:
            placed = self._place_task(task, busy, prefs, week_start, days)
            placements.extend(placed)
        return placements

    # -- placement ---------------------------------------------------------
    def _place_task(self, task: TaskSpec, busy: list[_Busy],
                    prefs: SchedulingPrefs, week_start: date, days: int) -> list[Placement]:
        deadline = _aware(task.deadline)
        horizon_end = _day_dt(week_start + timedelta(days=days), 0)
        if deadline <= _day_dt(week_start, 0):
            raise InfeasibleScheduleError(task.id, "deadline is before the planning horizon")
        effective_end = min(deadline, horizon_end)

        if not task.splittable:
            block = self._best_slot(task, task.duration_minutes, task.prep_minutes,
                                    busy, prefs, week_start, effective_end)
            if block is None:
                raise InfeasibleScheduleError(
                    task.id, "no feasible slot before its deadline")
            return self._commit(task, block, task.prep_minutes, busy)

        remaining = task.duration_minutes
        placements: list[Placement] = []
        while remaining > 0:
            chunk = self._best_slot(task, remaining, 0, busy, prefs, week_start,
                                    effective_end, allow_partial=True,
                                    min_block=task.min_block_minutes)
            if chunk is None:
                raise InfeasibleScheduleError(
                    task.id, f"splittable task still short {remaining} minutes before deadline")
            length = int((chunk[1] - chunk[0]).total_seconds() // 60)
            placements.extend(self._commit(task, chunk, 0, busy))
            remaining -= length
        if task.prep_minutes:
            # Prep goes immediately before the first work block.
            first = min(placements, key=lambda p: p.start)
            prep_end = first.start
            prep_start = prep_end - timedelta(minutes=task.prep_minutes)
            if not self._fits(prep_start, prep_end, task.location, busy, prefs):
                raise InfeasibleScheduleError(task.id, "no room for the preparatory block")
            prep = Placement(task.id, "prep", prep_start, prep_end, task.location)
            busy.append(_Busy(prep_start, prep_end, task.location))
            placements.append(prep)
        return placements

    def _commit(self, task: TaskSpec, block: tuple[datetime, datetime],
                prep_minutes: int, busy: list[_Busy]) -> list[Placement]:
        start, end = block
        placements = [Placement(task.id, "task", start, end, task.location)]
        busy.append(_Busy(start, end, task.location))
        if prep_minutes:
            prep_start = start - timedelta(minutes=prep_minutes)
            placements.append(Placement(task.id, "prep", prep_start, start, task.location))
            busy.append(_Busy(prep_start, start, task.location))
        return placements

    def _best_slot(self, task: TaskSpec, minutes: int, prep_minutes: int,
                   busy: list[_Busy], prefs: SchedulingPrefs, week_start: date,
                   effective_end: datetime, allow_partial: bool = False,
                   min_block: int = 30) -> tuple[datetime, datetime] | None:
        best: tuple[float, datetime, datetime] | None = None  # (score, start, end) - max score, earliest
        deadline_day = effective_end.date()
        day = week_start
        while day <= deadline_day:
            for window in prefs.working_hours.get(day.weekday(), []):
                cursor = _day_dt(day, window.start_minute)
                window_end = min(_day_dt(day, window.end_minute), effective_end)
                while cursor < window_end:
                    need = minutes
                    if allow_partial:
                        need = max(min_block, 0)  # grow to whatever fits
                    total = need + prep_minutes
                    start = cursor + timedelta(minutes=prep_minutes)
                    if allow_partial:
                        end = self._grow(start, remaining=minutes, window_end=window_end,
                                         location=task.location, busy=busy, prefs=prefs,
                                         min_block=min_block)
                        if end is None:
                            cursor += timedelta(minutes=SLOT_MINUTES)
                            continue
                    else:
                        end = start + timedelta(minutes=minutes)
                        prep_start = cursor
                        if end > window_end or not self._fits(prep_start, end, task.location, busy, prefs):
                            cursor += timedelta(minutes=SLOT_MINUTES)
                            continue
                    block_end_ok = end <= effective_end
                    if block_end_ok and (allow_partial or self._fits(start, end, task.location, busy, prefs)):
                        score = self._energy_score(start, end, prefs) - start.timestamp() / 1e12
                        if best is None or score > best[0]:
                            best = (score, start, end)
                    cursor += timedelta(minutes=SLOT_MINUTES)
            day += timedelta(days=1)
        return (best[1], best[2]) if best else None

    def _grow(self, start: datetime, remaining: int, window_end: datetime,
              location: str | None, busy: list[_Busy], prefs: SchedulingPrefs,
              min_block: int) -> datetime | None:
        """Extend a split chunk from start until blocked; None if < min_block fits."""
        limit = min(start + timedelta(minutes=remaining), window_end)
        end = start
        step = timedelta(minutes=SLOT_MINUTES)
        while end + step <= limit and self._fits(end, end + step, location, busy, prefs):
            end += step
        if (end - start) < timedelta(minutes=min_block):
            return None
        return end

    def _fits(self, start: datetime, end: datetime, location: str | None,
              busy: list[_Busy], prefs: SchedulingPrefs) -> bool:
        """No overlap, and travel buffers when adjacent events are elsewhere."""
        for item in busy:
            if end <= item.start or start >= item.end:
                # Adjacent: apply travel time when locations differ.
                travel = prefs.travel_minutes(location, item.location)
                if travel:
                    if item.end <= start and start - item.end < timedelta(minutes=travel):
                        return False
                    if end <= item.start and item.start - end < timedelta(minutes=travel):
                        return False
                continue
            return False
        return True

    @staticmethod
    def _energy_score(start: datetime, end: datetime, prefs: SchedulingPrefs) -> float:
        hours: list[int] = []
        cursor = start
        while cursor < end:
            hours.append(cursor.hour)
            cursor += timedelta(minutes=SLOT_MINUTES)
        if not hours:
            return 0.0
        return sum(prefs.energy_at(h) for h in hours) / len(hours)
