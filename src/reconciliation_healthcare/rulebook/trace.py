"""Payment-trace serialization and structural checks."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from reconciliation_healthcare.rulebook.models import (
    AmountKind,
    CalculationStatus,
    DateBasis,
    PaymentTrace,
    PaymentUnit,
)


_SEMANTICS = {
    "PFS": (
        CalculationStatus.CALCULATED,
        AmountKind.PFS_BASE_PAYMENT,
        PaymentUnit.PROFESSIONAL_SERVICE,
        DateBasis.SERVICE_DATE,
    ),
    "OPPS": (
        CalculationStatus.LOOKUP_ONLY,
        AmountKind.OPPS_PUBLISHED_RATE,
        PaymentUnit.OUTPATIENT_HCPCS_LOOKUP,
        DateBasis.SERVICE_DATE,
    ),
    "IPPS": (
        CalculationStatus.CALCULATED,
        AmountKind.IPPS_BASE_OPERATING_PAYMENT,
        PaymentUnit.INPATIENT_DISCHARGE,
        DateBasis.DISCHARGE_DATE,
    ),
}


def validate_trace(trace: PaymentTrace) -> None:
    """Require a truthful amount/date contract and traceable supported results."""
    if trace.payment_system not in _SEMANTICS:
        raise ValueError(f"Unknown trace payment system: {trace.payment_system!r}")
    status, amount_kind, payment_unit, date_basis = _SEMANTICS[trace.payment_system]
    if trace.payment_unit is not payment_unit:
        raise ValueError("Trace payment unit does not match its payment system")
    if trace.date_basis is not date_basis:
        raise ValueError("Trace date basis does not match its payment system")
    if trace.calculation_status is CalculationStatus.UNSUPPORTED:
        if trace.amount_kind is not None:
            raise ValueError("Unsupported trace must not expose an amount kind")
    else:
        if trace.calculation_status is not status:
            raise ValueError("Trace calculation status does not match its payment system")
        if trace.amount_kind is not amount_kind:
            raise ValueError("Trace amount kind does not match its payment system")
    if trace.calculated_amount is not None:
        if not isinstance(trace.calculated_amount, Decimal) or not trace.calculated_amount.is_finite():
            raise ValueError("Trace amount must be a finite Decimal in USD")
        if not trace.amount_label:
            raise ValueError("Trace numeric amount lacks a readable label")
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
