"""Source-grounded program base rates for advisory opportunity context.

A program prior is an aggregate historical award rate, never a prediction that
an individual applicant will win. Records retain their source and as-of date so
callers can judge freshness and comparability.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date
from io import StringIO
from typing import Iterable
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ProgramPriorKey:
    sponsor: str
    mechanism: str
    cycle: str
    geography: str

    def __post_init__(self) -> None:
        if not all((self.sponsor.strip(), self.mechanism.strip(), self.cycle.strip(), self.geography.strip())):
            raise ValueError("sponsor, mechanism, cycle and geography are required")

    def normalized(self) -> tuple[str, str, str, str]:
        return tuple(value.strip().casefold() for value in (self.sponsor, self.mechanism, self.cycle, self.geography))


@dataclass(frozen=True, slots=True)
class ProgramPrior:
    key: ProgramPriorKey
    numerator: int
    denominator: int
    source_url: str
    as_of: date
    confidence_low: float
    confidence_high: float
    score_kind: str = "aggregate_program_prior"
    advisory_only: bool = True

    @property
    def rate(self) -> float:
        return self.numerator / self.denominator

    @property
    def awards(self) -> int:
        return self.numerator

    @property
    def applications(self) -> int:
        return self.denominator


def wilson_interval(awards: int, applications: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Return a 95% Wilson score interval for a binomial aggregate."""
    if applications <= 0:
        raise ValueError("applications must be positive")
    if awards < 0 or awards > applications:
        raise ValueError("awards must be between zero and applications")
    p = awards / applications
    z2 = z * z
    denominator = 1 + z2 / applications
    center = (p + z2 / (2 * applications)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * applications)) / applications) / denominator
    return round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)


def build_prior(*, sponsor: str, mechanism: str, cycle: str, geography: str, awards: int,
                applications: int, source_url: str, as_of: date) -> ProgramPrior:
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("source_url must be an absolute HTTPS URL")
    low, high = wilson_interval(awards, applications)
    return ProgramPrior(
        key=ProgramPriorKey(sponsor, mechanism, cycle, geography),
        numerator=awards,
        denominator=applications,
        source_url=source_url,
        as_of=as_of,
        confidence_low=low,
        confidence_high=high,
    )


class ProgramPriorRegistry:
    """Deterministic exact-key registry; it never fabricates a fallback prior."""
    def __init__(self, priors: Iterable[ProgramPrior] = ()) -> None:
        self._items: dict[tuple[str, str, str, str], ProgramPrior] = {}
        for prior in priors:
            self.add(prior)

    def add(self, prior: ProgramPrior) -> None:
        key = prior.key.normalized()
        if key in self._items:
            raise ValueError(f"duplicate program prior key: {key}")
        self._items[key] = prior

    def get(self, *, sponsor: str, mechanism: str, cycle: str, geography: str) -> ProgramPrior | None:
        return self._items.get(ProgramPriorKey(sponsor, mechanism, cycle, geography).normalized())


class ProgramPriorCsvAdapter:
    """Parse a versioned official aggregate export supplied by an integration.

    Fetching remains outside this adapter so the caller controls authentication,
    caching and provenance. Every row must carry its own official HTTPS source.
    """
    REQUIRED = {"sponsor", "mechanism", "cycle", "geography", "awards", "applications", "source_url", "as_of"}

    def parse(self, content: str) -> tuple[ProgramPrior, ...]:
        reader = csv.DictReader(StringIO(content))
        if reader.fieldnames is None or not self.REQUIRED.issubset(reader.fieldnames):
            missing = sorted(self.REQUIRED.difference(reader.fieldnames or ()))
            raise ValueError(f"program prior CSV missing columns: {', '.join(missing)}")
        priors = []
        for line, row in enumerate(reader, start=2):
            try:
                priors.append(build_prior(
                    sponsor=row["sponsor"], mechanism=row["mechanism"], cycle=row["cycle"],
                    geography=row["geography"], awards=int(row["awards"]),
                    applications=int(row["applications"]), source_url=row["source_url"],
                    as_of=date.fromisoformat(row["as_of"]),
                ))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid program prior CSV row {line}: {exc}") from exc
        return tuple(priors)
