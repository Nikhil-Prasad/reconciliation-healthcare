"""Many-to-many provenance links for Stage 2 rulebook entities."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping, TYPE_CHECKING

import pandas as pd

from reconciliation_healthcare.rulebook.models import (
    CalculationStatus,
    EntityType,
    ExecutionStatus,
    PaymentTrace,
    SourceRole,
)

if TYPE_CHECKING:
    from reconciliation_healthcare.rulebook.store import RulebookStore


ENTITY_SOURCE_LINK_COLUMNS = [
    "source_link_id",
    "entity_type",
    "entity_id",
    "source_artifact_id",
    "source_role",
    "source_locator",
    "effective_start",
    "effective_end",
    "notes",
]

_NATURAL_KEY = [
    "entity_type",
    "entity_id",
    "source_artifact_id",
    "source_role",
    "effective_start",
    "effective_end",
]


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _source_link(
    *,
    entity_type: EntityType | str,
    entity_id: str,
    source_artifact_id: str,
    source_role: SourceRole | str,
    source_locator: str,
    effective_start: Any,
    effective_end: Any,
    notes: str = "",
) -> dict[str, str]:
    entity_type_value = EntityType(entity_type).value
    source_role_value = SourceRole(source_role).value
    start = _text(effective_start)
    end = _text(effective_end)
    source_link_id = "|".join(
        (
            entity_type_value,
            entity_id,
            source_role_value,
            source_artifact_id,
            start,
            end,
        )
    )
    return {
        "source_link_id": source_link_id,
        "entity_type": entity_type_value,
        "entity_id": entity_id,
        "source_artifact_id": source_artifact_id,
        "source_role": source_role_value,
        "source_locator": source_locator,
        "effective_start": start,
        "effective_end": end,
        "notes": notes,
    }


def _entity_interval(record: Mapping[str, Any]) -> tuple[str, str]:
    return _text(record.get("effective_start")), _text(record.get("effective_end"))


def _append_link(
    links: list[dict[str, str]],
    record: Mapping[str, Any],
    *,
    entity_type: EntityType,
    entity_id_column: str,
    source_artifact_id: str,
    source_role: SourceRole,
    source_locator: str,
    notes: str = "",
) -> None:
    start, end = _entity_interval(record)
    links.append(
        _source_link(
            entity_type=entity_type,
            entity_id=_text(record.get(entity_id_column)),
            source_artifact_id=source_artifact_id,
            source_role=source_role,
            source_locator=source_locator,
            effective_start=start,
            effective_end=end,
            notes=notes,
        )
    )


def _primary_role(entity_type: EntityType, record: Mapping[str, Any]) -> SourceRole:
    if entity_type is EntityType.RULE and _text(record.get("execution_status")) in {
        ExecutionStatus.DEFERRED.value,
        ExecutionStatus.DOCUMENTED_ONLY.value,
    }:
        return SourceRole.SUPPORTING_DOCUMENTATION
    return SourceRole.PRIMARY_NUMERIC_AUTHORITY


def _add_primary_links(
    links: list[dict[str, str]],
    frame: pd.DataFrame,
    *,
    entity_type: EntityType,
    entity_id_column: str,
) -> None:
    for record in frame.to_dict(orient="records"):
        artifact_id = _text(record.get("source_artifact_id"))
        if not artifact_id:
            continue
        _append_link(
            links,
            record,
            entity_type=entity_type,
            entity_id_column=entity_id_column,
            source_artifact_id=artifact_id,
            source_role=_primary_role(entity_type, record),
            source_locator=_text(record.get("source_locator")),
            notes=(
                "Legacy source_artifact_id retained as a convenient direct pointer; "
                "entity_source_links is authoritative."
            ),
        )


def _add_rule_link(
    links: list[dict[str, str]],
    by_rule_id: dict[str, dict[str, Any]],
    rule_id: str,
    artifact_id: str,
    role: SourceRole,
    locator: str,
    notes: str = "",
) -> None:
    record = by_rule_id.get(rule_id)
    if record is None:
        return
    _append_link(
        links,
        record,
        entity_type=EntityType.RULE,
        entity_id_column="rule_id",
        source_artifact_id=artifact_id,
        source_role=role,
        source_locator=locator,
        notes=notes,
    )


def _add_rule_provenance(
    links: list[dict[str, str]], rules: pd.DataFrame
) -> None:
    by_rule_id = {
        _text(record.get("rule_id")): record for record in rules.to_dict(orient="records")
    }

    pfs_validation_artifacts = {
        "rvu24a": "cms_pfs_carrier_2024_jan_mar8",
        "rvu24ar": "cms_pfs_carrier_2024_mar9_dec31",
        "rvu24b": "cms_pfs_carrier_2024_mar9_dec31",
        "rvu24c": "cms_pfs_carrier_2024_mar9_dec31",
        "rvu24d": "cms_pfs_carrier_2024_mar9_dec31",
    }
    for version, artifact_id in pfs_validation_artifacts.items():
        _add_rule_link(
            links,
            by_rule_id,
            f"pfs.{version}.base_payment",
            artifact_id,
            SourceRole.VALIDATION_REFERENCE,
            "CMS all-states carrier payment file",
            "Independent published payment output; never used as a calculation input.",
        )

    opps_updates = {
        "2024_q1": "cms_opps_2024_january_update",
        "2024_q2": "cms_opps_2024_april_update",
        "2024_q3": "cms_opps_2024_july_update",
        "2024_q4": "cms_opps_2024_october_update",
    }
    for version, artifact_id in opps_updates.items():
        for suffix in ("hcpcs_status_apc", "published_rate"):
            _add_rule_link(
                links,
                by_rule_id,
                f"opps.{version}.{suffix}",
                artifact_id,
                SourceRole.IMPLEMENTATION_GUIDANCE,
                "Quarterly CMS OPPS update memorandum",
            )

    for rule_id in by_rule_id:
        if rule_id.startswith("ipps.fy2024."):
            _add_rule_link(
                links,
                by_rule_id,
                rule_id,
                "cms_ipps_fy2024_final_rule",
                SourceRole.REGULATORY_AUTHORITY,
                "CMS-1785-F; 88 FR 58640",
            )
            _add_rule_link(
                links,
                by_rule_id,
                rule_id,
                "cms_ipps_fy2024_correction_notice_2",
                SourceRole.SUPPORTING_DOCUMENTATION,
                "CMS-1785-CN2; 88 FR 77211",
                "Restores an omitted comment and response; no Stage 2A numeric input changed.",
            )
        elif rule_id.startswith("ipps.fy2025."):
            _add_rule_link(
                links,
                by_rule_id,
                rule_id,
                "cms_ipps_fy2025_final_rule",
                SourceRole.REGULATORY_AUTHORITY,
                "CMS-1808-F; 89 FR 68986",
            )

    for rule_id in (
        "ipps.fy2024.base_operating_payment",
        "ipps.fy2024.wage_index",
        "ipps.fy2024.uncompensated_care",
        "ipps.fy2024.final_payment",
    ):
        _add_rule_link(
            links,
            by_rule_id,
            rule_id,
            "cms_ipps_fy2024_correction_notice",
            SourceRole.CORRECTION,
            "CMS-1785-CN; 88 FR 68482",
        )
    for rule_id in (
        "ipps.fy2025.base_operating_payment",
        "ipps.fy2025.standardized_amount",
        "ipps.fy2025.wage_index",
        "ipps.fy2025.final_payment",
    ):
        _add_rule_link(
            links,
            by_rule_id,
            rule_id,
            "cms_ipps_fy2025_ifc",
            SourceRole.SUPERSEDING_RELEASE,
            "CMS-1808-IFC; 89 FR 80405",
            "FY2025 wage-index and conforming rate changes effective September 30, 2024.",
        )
    for rule_id in (
        "ipps.fy2025.base_operating_payment",
        "ipps.fy2025.ms_drg_weight",
        "ipps.fy2025.standardized_amount",
        "ipps.fy2025.wage_index",
        "ipps.fy2025.final_payment",
        "ipps.fy2025.ntap",
        "ipps.fy2025.hac",
    ):
        _add_rule_link(
            links,
            by_rule_id,
            rule_id,
            "cms_ipps_fy2025_correction_notice",
            SourceRole.CORRECTION,
            "CMS-1808-CN2; 89 FR 80098",
        )

    pfs_releases = (
        "cms_pfs_rvu24a",
        "cms_pfs_rvu24ar",
        "cms_pfs_rvu24b",
        "cms_pfs_rvu24c",
        "cms_pfs_rvu24d",
    )
    for rule_id in ("site.office_professional_path", "site.hospital_outpatient_path"):
        for artifact_id in pfs_releases:
            if rule_id == "site.office_professional_path" and artifact_id == "cms_pfs_rvu24a":
                continue
            _add_rule_link(
                links,
                by_rule_id,
                rule_id,
                artifact_id,
                SourceRole.SUPPORTING_DOCUMENTATION,
                "Effective PFS facility/nonfacility release",
            )


def _add_parameter_provenance(
    links: list[dict[str, str]], parameters: pd.DataFrame
) -> None:
    for record in parameters.to_dict(orient="records"):
        status = _text(record.get("value_status"))
        rule_id = _text(record.get("rule_id"))
        if status == "published_correction_notice":
            fiscal_year = "fy2025" if ".fy2025." in f".{rule_id}." else "fy2024"
            _append_link(
                links,
                record,
                entity_type=EntityType.PARAMETER,
                entity_id_column="parameter_id",
                source_artifact_id=f"cms_ipps_{fiscal_year}_correction_notice",
                source_role=SourceRole.CORRECTION,
                source_locator=f"{fiscal_year.upper()} IPPS correction notice",
            )
        if status == "published_ifc":
            _append_link(
                links,
                record,
                entity_type=EntityType.PARAMETER,
                entity_id_column="parameter_id",
                source_artifact_id="cms_ipps_fy2025_ifc",
                source_role=SourceRole.SUPERSEDING_RELEASE,
                source_locator="CMS-1808-IFC; 89 FR 80405",
            )


def _add_assignment_provenance(
    links: list[dict[str, str]], assignments: pd.DataFrame
) -> None:
    records = assignments.to_dict(orient="records")
    by_assignment_id = {
        _text(record.get("assignment_id")): record for record in records
    }
    q1_c9790 = by_assignment_id.get("opps.2024_q1.C9790")
    q2_c9790 = by_assignment_id.get("opps.2024_q2.C9790")
    if q1_c9790 is not None:
        _append_link(
            links,
            q1_c9790,
            entity_type=EntityType.ASSIGNMENT,
            entity_id_column="assignment_id",
            source_artifact_id="cms_opps_2024_q1_addendum_b",
            source_role=SourceRole.SUPPORTING_DOCUMENTATION,
            source_locator="January Addendum B original C9790 row",
            notes="Original Q1 snapshot retained after the retroactive correction.",
        )
        _append_link(
            links,
            q1_c9790,
            entity_type=EntityType.ASSIGNMENT,
            entity_id_column="assignment_id",
            source_artifact_id="cms_opps_2024_april_update",
            source_role=SourceRole.RETROACTIVE_CORRECTION,
            source_locator="MM13568 C9790 correction effective January 1, 2024",
        )
        if _text(q1_c9790.get("source_artifact_id")) != "cms_opps_2024_q2_addendum_b":
            _append_link(
                links,
                q1_c9790,
                entity_type=EntityType.ASSIGNMENT,
                entity_id_column="assignment_id",
                source_artifact_id="cms_opps_2024_q2_addendum_b",
                source_role=SourceRole.PRIMARY_NUMERIC_AUTHORITY,
                source_locator=(
                    _text(q2_c9790.get("source_locator"))
                    if q2_c9790 is not None
                    else "April Addendum B corrected C9790 numeric row"
                ),
                notes="Corrected APC and rate copied back to the Q1 effective interval.",
            )

    pfs_guidance = {
        "rvu24b": ("cms_pfs_cr13529",),
        "rvu24c": ("cms_pfs_cr13624",),
        "rvu24d": ("cms_pfs_cr13751", "cms_pfs_cr13751_attachment"),
    }
    opps_guidance = {
        "2024_q1": "cms_opps_2024_january_update",
        "2024_q2": "cms_opps_2024_april_update",
        "2024_q3": "cms_opps_2024_july_update",
        "2024_q4": "cms_opps_2024_october_update",
    }
    for record in records:
        assignment_id = _text(record.get("assignment_id"))
        status = _text(record.get("value_status"))
        if status == "published_cr_effective_date" and assignment_id.startswith("pfs."):
            version = assignment_id.split(".", maxsplit=2)[1]
            for artifact_id in pfs_guidance.get(version, ()):
                _append_link(
                    links,
                    record,
                    entity_type=EntityType.ASSIGNMENT,
                    entity_id_column="assignment_id",
                    source_artifact_id=artifact_id,
                    source_role=SourceRole.IMPLEMENTATION_GUIDANCE,
                    source_locator="CMS PFS change-request effective-date instruction",
                )
        if status == "published_cr_effective_date" and assignment_id.startswith("opps."):
            version = assignment_id.split(".")[1]
            artifact_id = opps_guidance.get(version)
            if artifact_id:
                _append_link(
                    links,
                    record,
                    entity_type=EntityType.ASSIGNMENT,
                    entity_id_column="assignment_id",
                    source_artifact_id=artifact_id,
                    source_role=SourceRole.IMPLEMENTATION_GUIDANCE,
                    source_locator="CMS OPPS update effective-date instruction",
                )
        if status == "published_correction_notice" and assignment_id.startswith("ipps."):
            fiscal_year = "fy2025" if ".fy2025." in f".{assignment_id}." else "fy2024"
            _append_link(
                links,
                record,
                entity_type=EntityType.ASSIGNMENT,
                entity_id_column="assignment_id",
                source_artifact_id=f"cms_ipps_{fiscal_year}_correction_notice",
                source_role=SourceRole.CORRECTION,
                source_locator=f"{fiscal_year.upper()} IPPS correction notice",
            )


def build_entity_source_links(
    payment_rules: pd.DataFrame,
    rule_parameters: pd.DataFrame,
    code_assignments: pd.DataFrame,
    source_artifacts: pd.DataFrame,
) -> pd.DataFrame:
    """Build and validate the authoritative entity-to-source relationship table."""

    links: list[dict[str, str]] = []
    _add_primary_links(
        links,
        payment_rules,
        entity_type=EntityType.RULE,
        entity_id_column="rule_id",
    )
    _add_primary_links(
        links,
        rule_parameters,
        entity_type=EntityType.PARAMETER,
        entity_id_column="parameter_id",
    )
    _add_primary_links(
        links,
        code_assignments,
        entity_type=EntityType.ASSIGNMENT,
        entity_id_column="assignment_id",
    )
    _add_rule_provenance(links, payment_rules)
    _add_parameter_provenance(links, rule_parameters)
    _add_assignment_provenance(links, code_assignments)

    frame = pd.DataFrame(links, columns=ENTITY_SOURCE_LINK_COLUMNS)
    frame = frame.sort_values(
        ["entity_type", "entity_id", "source_role", "source_artifact_id"],
        kind="stable",
    ).reset_index(drop=True)
    validate_entity_source_links(
        frame,
        payment_rules=payment_rules,
        rule_parameters=rule_parameters,
        code_assignments=code_assignments,
        source_artifacts=source_artifacts,
    )
    for column in ("effective_start", "effective_end"):
        frame[column] = pd.to_datetime(frame[column]).dt.date
    for column in frame.columns:
        if column not in {"effective_start", "effective_end"}:
            frame[column] = pd.array(frame[column], dtype="string")
    return frame


def validate_entity_source_links(
    links: pd.DataFrame,
    *,
    payment_rules: pd.DataFrame,
    rule_parameters: pd.DataFrame,
    code_assignments: pd.DataFrame,
    source_artifacts: pd.DataFrame,
) -> None:
    """Reject invalid, incomplete, or duplicate provenance relationships."""

    if list(links.columns) != ENTITY_SOURCE_LINK_COLUMNS:
        raise ValueError("entity_source_links has unexpected columns")
    if links["source_link_id"].duplicated().any() or links.duplicated(_NATURAL_KEY).any():
        raise ValueError("entity_source_links contains duplicate source links")
    if not set(links["entity_type"]) <= {value.value for value in EntityType}:
        raise ValueError("entity_source_links contains an unknown entity_type")
    if not set(links["source_role"]) <= {value.value for value in SourceRole}:
        raise ValueError("entity_source_links contains an unknown source_role")
    for column in ENTITY_SOURCE_LINK_COLUMNS:
        if links[column].isna().any() or links[column].astype("string").str.strip().eq("").any():
            if column != "notes":
                raise ValueError(f"entity_source_links contains a blank {column}")

    artifact_ids = set(source_artifacts["source_artifact_id"])
    if not set(links["source_artifact_id"]) <= artifact_ids:
        missing = sorted(set(links["source_artifact_id"]) - artifact_ids)
        raise ValueError(f"entity_source_links has missing source artifacts: {missing}")

    entity_ids = {
        EntityType.RULE.value: set(payment_rules["rule_id"]),
        EntityType.PARAMETER.value: set(rule_parameters["parameter_id"]),
        EntityType.ASSIGNMENT.value: set(code_assignments["assignment_id"]),
    }
    for entity_type, expected_ids in entity_ids.items():
        observed = set(links.loc[links["entity_type"] == entity_type, "entity_id"])
        unknown = observed - expected_ids
        missing = expected_ids - observed
        if unknown:
            raise ValueError(f"Unknown {entity_type} provenance entities: {sorted(unknown)[:5]}")
        if missing:
            raise ValueError(f"Missing {entity_type} source links: {sorted(missing)[:5]}")

    entity_intervals = {
        EntityType.RULE.value: {
            _text(record["rule_id"]): _entity_interval(record)
            for record in payment_rules.to_dict(orient="records")
        },
        EntityType.PARAMETER.value: {
            _text(record["parameter_id"]): _entity_interval(record)
            for record in rule_parameters.to_dict(orient="records")
        },
        EntityType.ASSIGNMENT.value: {
            _text(record["assignment_id"]): _entity_interval(record)
            for record in code_assignments.to_dict(orient="records")
        },
    }
    for link in links.to_dict(orient="records"):
        start, end = _entity_interval(link)
        entity_start, entity_end = entity_intervals[_text(link["entity_type"])][
            _text(link["entity_id"])
        ]
        if not entity_start <= start <= end <= entity_end:
            raise ValueError(
                "entity_source_links interval is outside its entity: "
                f"{link['source_link_id']}"
            )


def enrich_trace_sources(trace: PaymentTrace, store: "RulebookStore") -> PaymentTrace:
    """Attach complete linked source provenance for entities selected by a trace."""

    links = store.entity_source_links
    if links.empty:
        if (
            store.provenance_required
            and trace.calculation_status is not CalculationStatus.UNSUPPORTED
        ):
            raise ValueError(
                "Canonical RulebookStore has no entity_source_links for a supported trace"
            )
        return trace

    entity_refs: set[tuple[str, str]] = set()
    for rule in trace.selected_rule_versions:
        rule_id = _text(rule.get("rule_id"))
        if rule_id:
            entity_refs.add((EntityType.RULE.value, rule_id))

    parameter_ids = set(store.rule_parameters.get("parameter_id", pd.Series(dtype="string")))
    assignment_ids = set(store.code_assignments.get("assignment_id", pd.Series(dtype="string")))
    for parameter in trace.selected_parameters:
        assignment_id = _text(parameter.get("assignment_id"))
        if assignment_id:
            entity_refs.add((EntityType.ASSIGNMENT.value, assignment_id))
        parameter_id = _text(parameter.get("parameter_id"))
        if parameter_id in parameter_ids:
            entity_refs.add((EntityType.PARAMETER.value, parameter_id))
        elif parameter_id in assignment_ids:
            entity_refs.add((EntityType.ASSIGNMENT.value, parameter_id))

    if not entity_refs:
        if (
            store.provenance_required
            and trace.calculation_status is not CalculationStatus.UNSUPPORTED
        ):
            raise ValueError("Supported trace selects no provenance-bearing entity")
        return trace
    mask = pd.Series(False, index=links.index)
    for entity_type, entity_id in entity_refs:
        mask |= (links["entity_type"] == entity_type) & (links["entity_id"] == entity_id)
    service_date = trace.service_date.isoformat()
    active = (
        links["effective_start"].astype("string").le(service_date)
        & links["effective_end"].astype("string").ge(service_date)
    )
    selected = links.loc[mask & active].sort_values("source_link_id", kind="stable")
    linked_refs = set(zip(selected["entity_type"], selected["entity_id"], strict=True))
    missing_refs = sorted(entity_refs - linked_refs)
    if missing_refs:
        raise ValueError(
            "Selected trace entities lack an active entity_source_link: "
            + ", ".join(f"{kind}:{entity_id}" for kind, entity_id in missing_refs)
        )
    compact_columns = [
        "entity_type",
        "entity_id",
        "source_artifact_id",
        "source_role",
        "source_locator",
        "effective_start",
        "effective_end",
    ]
    source_links = selected[compact_columns].to_dict(orient="records")
    artifact_ids: list[str] = []
    for artifact_id in selected["source_artifact_id"]:
        value = _text(artifact_id)
        if value and value not in artifact_ids:
            artifact_ids.append(value)
    return replace(trace, source_artifact_ids=artifact_ids, source_links=source_links)


__all__ = [
    "ENTITY_SOURCE_LINK_COLUMNS",
    "build_entity_source_links",
    "enrich_trace_sources",
    "validate_entity_source_links",
]
