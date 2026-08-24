from __future__ import annotations

from datetime import date

import pytest

from reconciliation_healthcare.rulebook.temporal import (
    TemporalResolutionError,
    select_effective,
    validate_contiguous_intervals,
)


def test_controlled_release_intervals_cover_cy2024_without_gaps() -> None:
    validate_contiguous_intervals(
        [
            ("2024-01-01", "2024-03-08"),
            ("2024-03-09", "2024-03-31"),
            ("2024-04-01", "2024-06-30"),
            ("2024-07-01", "2024-09-30"),
            ("2024-10-01", "2024-12-31"),
        ],
        expected_start="2024-01-01",
        expected_end="2024-12-31",
        label="PFS releases",
    )
    validate_contiguous_intervals(
        [
            ("2024-01-01", "2024-03-31"),
            ("2024-04-01", "2024-06-30"),
            ("2024-07-01", "2024-09-30"),
            ("2024-10-01", "2024-12-31"),
        ],
        expected_start="2024-01-01",
        expected_end="2024-12-31",
        label="OPPS snapshots",
    )


def test_ipps_resolver_switches_on_october_first() -> None:
    records = [
        {
            "rule_version": "FY2024",
            "effective_start": date(2023, 10, 1),
            "effective_end": date(2024, 9, 30),
        },
        {
            "rule_version": "FY2025",
            "effective_start": date(2024, 10, 1),
            "effective_end": date(2025, 9, 30),
        },
    ]
    assert select_effective(records, "2024-09-30", label="IPPS")["rule_version"] == "FY2024"
    assert select_effective(records, "2024-10-01", label="IPPS")["rule_version"] == "FY2025"


def test_temporal_resolution_fails_on_gaps_and_overlaps() -> None:
    with pytest.raises(TemporalResolutionError, match="found 0"):
        select_effective(
            [{"effective_start": "2024-01-01", "effective_end": "2024-01-10"}],
            "2024-01-11",
            label="fixture",
        )
    with pytest.raises(TemporalResolutionError, match="found 2"):
        select_effective(
            [
                {"effective_start": "2024-01-01", "effective_end": "2024-01-10"},
                {"effective_start": "2024-01-10", "effective_end": "2024-01-20"},
            ],
            "2024-01-10",
            label="fixture",
        )
