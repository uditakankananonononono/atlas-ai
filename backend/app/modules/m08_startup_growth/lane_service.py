"""Growth workflows: experiments, funnels, customer evidence, and measurement."""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import NormalDist
from uuid import uuid4

from .lane_models import (
    CustomerEvidence, EvidenceKind, Experiment, ExperimentStatus, Funnel, FunnelEvent,
    FunnelStep, MeasurementDefinition, MetricObservation, Variant,
)
from .lane_repository import InMemoryGrowthRepository

_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{2,}", re.I)
_STOPWORDS = {"the", "and", "that", "this", "with", "from", "have", "was", "were", "for", "but", "not", "you", "our", "are"}


class ValidationError(ValueError):
    pass


class InvalidTransitionError(ValueError):
    pass


class StartupGrowthService:
    def __init__(self, repository: InMemoryGrowthRepository | None = None) -> None:
        self.repo = repository or InMemoryGrowthRepository()
        self.measurements: dict[str, MeasurementDefinition] = {}

    def create_experiment(self, *, name: str, hypothesis: str, primary_metric: str,
                          variants: list[dict], minimum_sample_size: int = 100,
                          guardrail_metrics: list[str] | None = None,
                          experiment_id: str | None = None) -> Experiment:
        if not name.strip() or not hypothesis.strip() or not primary_metric.strip():
            raise ValidationError("name, hypothesis, and primary_metric are required")
        if minimum_sample_size < 2:
            raise ValidationError("minimum_sample_size must be at least 2")
        parsed = tuple(Variant(key=str(v["key"]).strip(), weight=float(v["weight"]),
                               description=str(v.get("description", ""))) for v in variants)
        if len(parsed) < 2 or len({v.key for v in parsed}) != len(parsed):
            raise ValidationError("at least two uniquely keyed variants are required")
        if any(not v.key or v.weight <= 0 for v in parsed) or not math.isclose(sum(v.weight for v in parsed), 1.0, abs_tol=1e-9):
            raise ValidationError("variant weights must be positive and sum to 1")
        experiment = Experiment(
            id=experiment_id or str(uuid4()), name=name.strip(), hypothesis=hypothesis.strip(),
            primary_metric=primary_metric.strip(), variants=parsed,
            minimum_sample_size=minimum_sample_size,
            guardrail_metrics=tuple(dict.fromkeys(guardrail_metrics or [])),
        )
        return self.repo.add_experiment(experiment)

    def transition_experiment(self, experiment_id: str, status: ExperimentStatus,
                              *, at: datetime | None = None) -> Experiment:
        experiment = self.repo.get_experiment(experiment_id)
        target = ExperimentStatus(status)
        allowed = {
            ExperimentStatus.DRAFT: {ExperimentStatus.RUNNING, ExperimentStatus.CANCELLED},
            ExperimentStatus.RUNNING: {ExperimentStatus.PAUSED, ExperimentStatus.COMPLETED, ExperimentStatus.CANCELLED},
            ExperimentStatus.PAUSED: {ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED, ExperimentStatus.CANCELLED},
            ExperimentStatus.COMPLETED: set(), ExperimentStatus.CANCELLED: set(),
        }
        if target not in allowed[experiment.status]:
            raise InvalidTransitionError(f"cannot move experiment from {experiment.status} to {target}")
        now = at or datetime.now(timezone.utc)
        if target == ExperimentStatus.RUNNING and experiment.started_at is None:
            experiment.started_at = now
        if target in {ExperimentStatus.COMPLETED, ExperimentStatus.CANCELLED}:
            experiment.ended_at = now
        experiment.status = target
        return experiment

    def assign_variant(self, experiment_id: str, subject_id: str) -> str:
        experiment = self.repo.get_experiment(experiment_id)
        if experiment.status != ExperimentStatus.RUNNING:
            raise InvalidTransitionError("variant assignment requires a running experiment")
        if not subject_id:
            raise ValidationError("subject_id is required")
        digest = hashlib.sha256(f"{experiment_id}\0{subject_id}".encode()).digest()
        point = int.from_bytes(digest[:8], "big") / 2**64
        cumulative = 0.0
        for variant in experiment.variants:
            cumulative += variant.weight
            if point < cumulative:
                return variant.key
        return experiment.variants[-1].key

    def record_metric(self, *, event_id: str, experiment_id: str, subject_id: str,
                      variant_key: str, metric: str, value: float,
                      occurred_at: datetime | None = None, properties: dict | None = None) -> bool:
        experiment = self.repo.get_experiment(experiment_id)
        if variant_key not in {v.key for v in experiment.variants}:
            raise ValidationError("variant_key does not belong to experiment")
        if not event_id or not subject_id or not metric or not math.isfinite(float(value)):
            raise ValidationError("valid event_id, subject_id, metric, and finite value are required")
        return self.repo.add_observation(MetricObservation(
            event_id=event_id, experiment_id=experiment_id, subject_id=subject_id,
            variant_key=variant_key, metric=metric, value=float(value),
            occurred_at=occurred_at or datetime.now(timezone.utc), properties=properties or {},
        ))

    @staticmethod
    def _wilson(successes: int, total: int, confidence: float) -> tuple[float, float]:
        if total == 0:
            return (0.0, 0.0)
        z = NormalDist().inv_cdf(0.5 + confidence / 2)
        p = successes / total
        d = 1 + z * z / total
        center = (p + z * z / (2 * total)) / d
        margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / d
        return (max(0.0, center - margin), min(1.0, center + margin))

    def analyze_experiment(self, experiment_id: str, *, confidence: float = 0.95) -> dict:
        if not 0.5 < confidence < 1:
            raise ValidationError("confidence must be between .5 and 1")
        experiment = self.repo.get_experiment(experiment_id)
        events = [e for e in self.repo.list_observations(experiment_id) if e.metric == experiment.primary_metric]
        by_variant: dict[str, dict[str, float | int | tuple]] = {}
        assigned_subjects = defaultdict(set)
        for e in events:
            assigned_subjects[e.variant_key].add(e.subject_id)
        for variant in experiment.variants:
            rows = [e for e in events if e.variant_key == variant.key]
            # One latest observation per subject prevents event-heavy users dominating.
            latest = {}
            for row in sorted(rows, key=lambda x: x.occurred_at):
                latest[row.subject_id] = row
            values = [row.value for row in latest.values()]
            n = len(values); successes = sum(v > 0 for v in values)
            by_variant[variant.key] = {
                "subjects": n, "mean": sum(values) / n if n else 0.0,
                "conversion_rate": successes / n if n else 0.0,
                "conversion_interval": self._wilson(successes, n, confidence),
            }
        total = sum(len(v) for v in assigned_subjects.values())
        expected = {v.key: total * v.weight for v in experiment.variants}
        chi_square = sum((len(assigned_subjects[v.key]) - expected[v.key]) ** 2 / expected[v.key]
                         for v in experiment.variants if expected[v.key] > 0) if total else 0.0
        enough = all(int(by_variant[v.key]["subjects"]) >= experiment.minimum_sample_size for v in experiment.variants)
        winner = max(experiment.variants, key=lambda v: float(by_variant[v.key]["mean"])).key if enough else None
        return {"experiment_id": experiment.id, "metric": experiment.primary_metric,
                "variants": by_variant, "sample_ratio_chi_square": chi_square,
                "sample_ratio_mismatch": chi_square > 6.635, "ready": enough, "winner": winner}

    def create_funnel(self, *, name: str, steps: list[dict], funnel_id: str | None = None) -> Funnel:
        parsed = tuple(FunnelStep(key=str(s["key"]).strip(), name=str(s.get("name", s["key"])).strip()) for s in steps)
        if not name.strip() or len(parsed) < 2 or len({s.key for s in parsed}) != len(parsed) or any(not s.key for s in parsed):
            raise ValidationError("funnel requires a name and at least two unique steps")
        return self.repo.add_funnel(Funnel(id=funnel_id or str(uuid4()), name=name.strip(), steps=parsed))

    def record_funnel_event(self, *, event_id: str, funnel_id: str, subject_id: str,
                            step_key: str, occurred_at: datetime | None = None,
                            segment: dict[str, str] | None = None) -> bool:
        funnel = self.repo.get_funnel(funnel_id)
        if step_key not in {s.key for s in funnel.steps}:
            raise ValidationError("unknown funnel step")
        if not event_id or not subject_id:
            raise ValidationError("event_id and subject_id are required")
        return self.repo.add_funnel_event(FunnelEvent(
            event_id=event_id, funnel_id=funnel_id, subject_id=subject_id, step_key=step_key,
            occurred_at=occurred_at or datetime.now(timezone.utc), segment=segment or {},
        ))

    def analyze_funnel(self, funnel_id: str, *, segment: dict[str, str] | None = None) -> dict:
        funnel = self.repo.get_funnel(funnel_id)
        events = self.repo.list_funnel_events(funnel_id)
        if segment:
            events = [e for e in events if all(e.segment.get(k) == v for k, v in segment.items())]
        by_subject = defaultdict(list)
        for event in events:
            by_subject[event.subject_id].append(event)
        reached: dict[str, set[str]] = {s.key: set() for s in funnel.steps}
        for subject, rows in by_subject.items():
            rows.sort(key=lambda e: e.occurred_at)
            cursor = 0
            for row in rows:
                if cursor < len(funnel.steps) and row.step_key == funnel.steps[cursor].key:
                    reached[row.step_key].add(subject); cursor += 1
        result = []
        for i, step in enumerate(funnel.steps):
            count = len(reached[step.key])
            previous = len(reached[funnel.steps[i - 1].key]) if i else count
            first = len(reached[funnel.steps[0].key])
            result.append({"key": step.key, "name": step.name, "subjects": count,
                           "from_previous": count / previous if previous else 0.0,
                           "from_start": count / first if first else 0.0,
                           "dropoff": previous - count if i else 0})
        return {"funnel_id": funnel.id, "segment": segment or {}, "steps": result}

    def add_customer_evidence(self, *, kind: EvidenceKind, text: str, source: str,
                              customer_id: str | None = None, tags: list[str] | None = None,
                              sentiment: float | None = None, evidence_id: str | None = None,
                              occurred_at: datetime | None = None) -> CustomerEvidence:
        if not text.strip() or not source.strip():
            raise ValidationError("text and source are required")
        if sentiment is not None and not -1 <= sentiment <= 1:
            raise ValidationError("sentiment must be between -1 and 1")
        normalized_tags = tuple(dict.fromkeys(t.strip().lower() for t in tags or [] if t.strip()))
        item = CustomerEvidence(id=evidence_id or str(uuid4()), kind=EvidenceKind(kind), text=text.strip(),
                                source=source.strip(), customer_id=customer_id, tags=normalized_tags,
                                sentiment=sentiment, occurred_at=occurred_at or datetime.now(timezone.utc))
        return self.repo.add_evidence(item)

    def synthesize_evidence(self, *, tags: set[str] | None = None, limit: int = 10) -> dict:
        rows = self.repo.list_evidence()
        if tags:
            wanted = {t.lower() for t in tags}
            rows = [r for r in rows if wanted.intersection(r.tags)]
        tag_counts = Counter(tag for r in rows for tag in r.tags)
        terms = Counter(token.lower() for r in rows for token in _TOKEN.findall(r.text)
                        if token.lower() not in _STOPWORDS)
        sentiments = [r.sentiment for r in rows if r.sentiment is not None]
        return {"evidence_count": len(rows), "distinct_customers": len({r.customer_id for r in rows if r.customer_id}),
                "kind_counts": dict(Counter(r.kind.value for r in rows)), "tag_counts": dict(tag_counts.most_common(limit)),
                "top_terms": dict(terms.most_common(limit)),
                "average_sentiment": sum(sentiments) / len(sentiments) if sentiments else None,
                "source_ids": [r.id for r in sorted(rows, key=lambda r: r.occurred_at, reverse=True)]}

    def define_measurement(self, definition: MeasurementDefinition) -> MeasurementDefinition:
        if definition.key in self.measurements:
            raise ValidationError(f"measurement {definition.key!r} already exists")
        if definition.direction not in {"increase", "decrease", "maintain"}:
            raise ValidationError("direction must be increase, decrease, or maintain")
        self.measurements[definition.key] = definition
        return definition

    def measurement_scorecard(self, actuals: dict[str, float]) -> dict:
        unknown = set(actuals) - set(self.measurements)
        if unknown:
            raise ValidationError(f"unknown measurements: {sorted(unknown)}")
        rows = []
        for key, definition in self.measurements.items():
            actual = actuals.get(key)
            if actual is None or definition.target is None:
                state = "unmeasured"
            elif definition.direction == "increase": state = "on_track" if actual >= definition.target else "off_track"
            elif definition.direction == "decrease": state = "on_track" if actual <= definition.target else "off_track"
            else: state = "on_track" if math.isclose(actual, definition.target) else "off_track"
            rows.append({"key": key, "actual": actual, "target": definition.target,
                         "direction": definition.direction, "state": state, "owner": definition.owner})
        return {"measurements": rows, "on_track": sum(r["state"] == "on_track" for r in rows),
                "off_track": sum(r["state"] == "off_track" for r in rows),
                "unmeasured": sum(r["state"] == "unmeasured" for r in rows)}
