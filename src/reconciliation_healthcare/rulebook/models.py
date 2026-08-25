"""Controlled vocabularies and result models for payment-rule execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any


class RuleType(StrEnum):
    CLASSIFICATION = "classification"
    BASE_RATE = "base_rate"
    LOOKUP = "lookup"
    MULTIPLIER = "multiplier"
    ADD_ON = "add_on"
    REDUCTION = "reduction"
    GEOGRAPHIC_ADJUSTMENT = "geographic_adjustment"
    SETTING_ADJUSTMENT = "setting_adjustment"
    PACKAGING = "packaging"
    ELIGIBILITY = "eligibility"
    EXCLUSION = "exclusion"
    COST_SHARING = "cost_sharing"
    BUDGET_NEUTRALITY = "budget_neutrality"
    QUALITY_ADJUSTMENT = "quality_adjustment"
    OUTLIER = "outlier"


class PolicyFunction(StrEnum):
    RESOURCE_PRICING = "resource_pricing"
    GEOGRAPHIC_ADJUSTMENT = "geographic_adjustment"
    RISK_ADJUSTMENT = "risk_adjustment"
    SITE_OF_SERVICE = "site_of_service"
    SAFETY_NET = "safety_net"
    TEACHING_SUBSIDY = "teaching_subsidy"
    UNCOMPENSATED_CARE = "uncompensated_care"
    INNOVATION_SUBSIDY = "innovation_subsidy"
    QUALITY_INCENTIVE = "quality_incentive"
    UTILIZATION_CONTROL = "utilization_control"
    BENEFICIARY_PROTECTION = "beneficiary_protection"
    BUDGET_NEUTRALITY = "budget_neutrality"
    ADMINISTRATIVE = "administrative"
    OTHER = "other"
    UNKNOWN = "unknown"


class ExecutionStatus(StrEnum):
    EXECUTABLE = "executable"
    LOOKUP_ONLY = "lookup_only"
    DOCUMENTED_ONLY = "documented_only"
    DEFERRED = "deferred"


class CalculationStatus(StrEnum):
    CALCULATED = "calculated"
    LOOKUP_ONLY = "lookup_only"
    UNSUPPORTED = "unsupported"


class EntityType(StrEnum):
    RULE = "rule"
    PARAMETER = "parameter"
    ASSIGNMENT = "assignment"


class SourceRole(StrEnum):
    PRIMARY_NUMERIC_AUTHORITY = "primary_numeric_authority"
    LEGAL_AUTHORITY = "legal_authority"
    REGULATORY_AUTHORITY = "regulatory_authority"
    IMPLEMENTATION_GUIDANCE = "implementation_guidance"
    CORRECTION = "correction"
    RETROACTIVE_CORRECTION = "retroactive_correction"
    SUPERSEDING_RELEASE = "superseding_release"
    VALIDATION_REFERENCE = "validation_reference"
    SUPPORTING_DOCUMENTATION = "supporting_documentation"


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, StrEnum)):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class PaymentTrace:
    """Auditable result of a calculation or deterministic payment lookup."""

    payment_system: str
    service_date: date
    calculation_status: CalculationStatus
    input_context: dict[str, Any]
    selected_rule_versions: list[dict[str, Any]] = field(default_factory=list)
    selected_parameters: list[dict[str, Any]] = field(default_factory=list)
    components: dict[str, Any] = field(default_factory=dict)
    calculated_amount: Decimal | None = None
    amount_label: str | None = None
    unsupported_adjustments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_artifact_ids: list[str] = field(default_factory=list)
    source_links: list[dict[str, Any]] = field(default_factory=list)
    missing_rule: str | None = None
    missing_parameters: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation without losing decimal precision."""
        return _json_value(asdict(self))
