"""Payment-trace serialization and structural checks."""

from __future__ import annotations

import json
from pathlib import Path

from reconciliation_healthcare.rulebook.models import CalculationStatus, PaymentTrace


def validate_trace(trace: PaymentTrace) -> None:
    """Fail if a successful trace cannot be followed back to rules and sources."""
    if trace.calculation_status is not CalculationStatus.UNSUPPORTED:
        if not trace.selected_rule_versions:
            raise ValueError("Supported trace has no selected rule version")
        if not trace.source_artifact_ids:
            raise ValueError("Supported trace has no source artifact")
    if trace.calculation_status is CalculationStatus.CALCULATED:
        if trace.calculated_amount is None or not trace.amount_label:
            raise ValueError("Calculated trace lacks a labeled amount")
        if not trace.selected_parameters:
            raise ValueError("Calculated trace has no selected parameters")
    if trace.calculation_status is CalculationStatus.UNSUPPORTED:
        if trace.calculated_amount is not None:
            raise ValueError("Unsupported trace must not expose a calculated amount")
        if not (trace.missing_rule or trace.missing_parameters or trace.unsupported_adjustments):
            raise ValueError("Unsupported trace does not explain why it failed closed")


def write_trace(trace: PaymentTrace, path: Path) -> None:
    validate_trace(trace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace.to_dict(), indent=2) + "\n", encoding="utf-8")
