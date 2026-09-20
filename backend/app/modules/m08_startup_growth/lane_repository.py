"""Repository boundary and deterministic in-memory implementation.

The in-memory repository is useful for tests and single-process deployments.  Its API is
small enough for a durable adapter to implement without changing the domain service.
"""
from __future__ import annotations

from collections import defaultdict
from threading import RLock

from .lane_models import CustomerEvidence, Experiment, Funnel, FunnelEvent, MetricObservation


class ConflictError(ValueError):
    pass


class NotFoundError(LookupError):
    pass


class InMemoryGrowthRepository:
    def __init__(self) -> None:
        self.experiments: dict[str, Experiment] = {}
        self.observations: dict[str, MetricObservation] = {}
        self.funnels: dict[str, Funnel] = {}
        self.funnel_events: dict[str, FunnelEvent] = {}
        self.evidence: dict[str, CustomerEvidence] = {}
        self._experiment_events: dict[str, list[str]] = defaultdict(list)
        self._funnel_events: dict[str, list[str]] = defaultdict(list)
        self._lock = RLock()

    def add_experiment(self, experiment: Experiment) -> Experiment:
        with self._lock:
            if experiment.id in self.experiments:
                raise ConflictError(f"experiment {experiment.id!r} already exists")
            self.experiments[experiment.id] = experiment
            return experiment

    def get_experiment(self, experiment_id: str) -> Experiment:
        try:
            return self.experiments[experiment_id]
        except KeyError as exc:
            raise NotFoundError(f"experiment {experiment_id!r} not found") from exc

    def add_observation(self, observation: MetricObservation) -> bool:
        """Store once. Returns False for an exact retry and rejects ID collisions."""
        with self._lock:
            old = self.observations.get(observation.event_id)
            if old is not None:
                same_payload = (old.event_id, old.experiment_id, old.subject_id, old.variant_key, old.metric, old.value, old.properties) == (observation.event_id, observation.experiment_id, observation.subject_id, observation.variant_key, observation.metric, observation.value, observation.properties)
                if same_payload:
                    return False
                raise ConflictError(f"event id {observation.event_id!r} has different payload")
            self.observations[observation.event_id] = observation
            self._experiment_events[observation.experiment_id].append(observation.event_id)
            return True

    def list_observations(self, experiment_id: str) -> list[MetricObservation]:
        return [self.observations[k] for k in self._experiment_events[experiment_id]]

    def add_funnel(self, funnel: Funnel) -> Funnel:
        with self._lock:
            if funnel.id in self.funnels:
                raise ConflictError(f"funnel {funnel.id!r} already exists")
            self.funnels[funnel.id] = funnel
            return funnel

    def get_funnel(self, funnel_id: str) -> Funnel:
        try:
            return self.funnels[funnel_id]
        except KeyError as exc:
            raise NotFoundError(f"funnel {funnel_id!r} not found") from exc

    def add_funnel_event(self, event: FunnelEvent) -> bool:
        with self._lock:
            old = self.funnel_events.get(event.event_id)
            if old is not None:
                if old == event:
                    return False
                raise ConflictError(f"event id {event.event_id!r} has different payload")
            self.funnel_events[event.event_id] = event
            self._funnel_events[event.funnel_id].append(event.event_id)
            return True

    def list_funnel_events(self, funnel_id: str) -> list[FunnelEvent]:
        return [self.funnel_events[k] for k in self._funnel_events[funnel_id]]

    def add_evidence(self, item: CustomerEvidence) -> CustomerEvidence:
        with self._lock:
            if item.id in self.evidence:
                raise ConflictError(f"evidence {item.id!r} already exists")
            self.evidence[item.id] = item
            return item

    def list_evidence(self) -> list[CustomerEvidence]:
        return list(self.evidence.values())
