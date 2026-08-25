"""Inclusive effective-date selection and interval validation."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence


class TemporalResolutionError(ValueError):
    """Raised when an effective-dated lookup is missing or ambiguous."""


def as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Expected an ISO service date, received {value!r}") from error


def select_effective(
    records: Iterable[Mapping[str, Any]],
    service_date: date | str,
    *,
    label: str,
) -> Mapping[str, Any]:
    """Select exactly one record whose inclusive interval contains the date."""
    target = as_date(service_date)
    matches = []
    for record in records:
        start = as_date(record["effective_start"])
        end = as_date(record["effective_end"])
        if start <= target <= end:
            matches.append(record)
    if len(matches) != 1:
        raise TemporalResolutionError(
            f"Expected exactly one effective {label} on {target}; found {len(matches)}"
        )
    return matches[0]


def validate_contiguous_intervals(
    intervals: Sequence[tuple[date | str, date | str]],
    *,
    expected_start: date | str,
    expected_end: date | str,
    label: str,
) -> None:
    """Require sorted inclusive intervals to cover a range without gaps/overlaps."""
    normalized = sorted((as_date(start), as_date(end)) for start, end in intervals)
    if not normalized:
        raise TemporalResolutionError(f"No intervals supplied for {label}")
    if normalized[0][0] != as_date(expected_start):
        raise TemporalResolutionError(
            f"{label} starts {normalized[0][0]}, expected {as_date(expected_start)}"
        )
    cursor = as_date(expected_start)
    for start, end in normalized:
        if end < start:
            raise TemporalResolutionError(f"Invalid {label} interval {start}..{end}")
        if start != cursor:
            kind = "overlap" if start < cursor else "gap"
            raise TemporalResolutionError(
                f"{label} has a {kind} before {start}; expected next date {cursor}"
            )
        cursor = end + timedelta(days=1)
    if normalized[-1][1] != as_date(expected_end):
        raise TemporalResolutionError(
            f"{label} ends {normalized[-1][1]}, expected {as_date(expected_end)}"
        )
