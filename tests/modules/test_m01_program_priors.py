from datetime import date

import pytest

from app.modules.m01_opportunity_discovery.program_priors import (
    ProgramPriorCsvAdapter,
    ProgramPriorRegistry,
    build_prior,
    wilson_interval,
)


def test_wilson_interval_and_advisory_prior():
    prior = build_prior(
        sponsor="NIH", mechanism="R01", cycle="2025", geography="US",
        awards=200, applications=1000,
        source_url="https://report.nih.gov/example.csv", as_of=date(2026, 3, 1),
    )
    assert prior.rate == pytest.approx(0.2)
    assert prior.confidence_low < prior.rate < prior.confidence_high
    assert prior.score_kind == "aggregate_program_prior"
    assert prior.advisory_only is True


def test_invalid_counts_and_source_are_rejected():
    with pytest.raises(ValueError):
        wilson_interval(2, 1)
    with pytest.raises(ValueError, match="HTTPS"):
        build_prior(sponsor="x", mechanism="y", cycle="z", geography="g", awards=1,
                    applications=2, source_url="http://example.org", as_of=date.today())


def test_exact_key_registry_does_not_invent_fallbacks():
    prior = build_prior(sponsor="NIH", mechanism="R01", cycle="2025", geography="US", awards=1,
                        applications=4, source_url="https://report.nih.gov/x", as_of=date(2026, 1, 1))
    registry = ProgramPriorRegistry([prior])
    assert registry.get(sponsor=" nih ", mechanism="r01", cycle="2025", geography="us") is prior
    assert registry.get(sponsor="NIH", mechanism="R21", cycle="2025", geography="US") is None
    with pytest.raises(ValueError, match="duplicate"):
        registry.add(prior)


def test_csv_adapter_preserves_provenance_and_reports_bad_rows():
    header = "sponsor,mechanism,cycle,geography,awards,applications,source_url,as_of\n"
    body = "UKRI,Fellowship,2024,UK,30,200,https://www.ukri.org/data.csv,2025-07-01\n"
    prior = ProgramPriorCsvAdapter().parse(header + body)[0]
    assert prior.key.sponsor == "UKRI" and prior.applications == 200
    assert prior.source_url == "https://www.ukri.org/data.csv"
    with pytest.raises(ValueError, match="row 2"):
        ProgramPriorCsvAdapter().parse(header + body.replace(",200,", ",0,"))
