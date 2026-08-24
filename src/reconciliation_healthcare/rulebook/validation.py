"""Validate Stage 2A sources, temporal coverage, parameters, formulas, and traces."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable

import duckdb
import pandas as pd

from reconciliation_healthcare.paths import (
    DUCKDB_PATH,
    RULEBOOK_EXAMPLE_TRACES_DIR,
    RULEBOOK_MANIFEST_PATH,
    RULEBOOK_RAW_DIR,
    RULEBOOK_VALIDATION_REPORT_PATH,
)
from reconciliation_healthcare.rulebook.ipps import calculate_ipps_base_payment
from reconciliation_healthcare.rulebook.models import (
    CalculationStatus,
    ExecutionStatus,
    PolicyFunction,
    RuleType,
)
from reconciliation_healthcare.rulebook.opps import lookup_opps
from reconciliation_healthcare.rulebook.pfs import calculate_pfs
from reconciliation_healthcare.rulebook.sources import SOURCES, sha256_file
from reconciliation_healthcare.rulebook.store import RulebookStore
from reconciliation_healthcare.rulebook.temporal import validate_contiguous_intervals
from reconciliation_healthcare.rulebook.trace import validate_trace, write_trace


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    passed: bool
    detail: str


def _run_check(name: str, check: Callable[[], str]) -> ValidationCheck:
    try:
        return ValidationCheck(name=name, passed=True, detail=check())
    except Exception as error:  # report every validation failure in one pass
        return ValidationCheck(name=name, passed=False, detail=f"{type(error).__name__}: {error}")


def _manifest() -> dict[str, object]:
    return json.loads(RULEBOOK_MANIFEST_PATH.read_text(encoding="utf-8"))


def _source_integrity() -> str:
    manifest = _manifest()
    records = manifest["records"]
    assert len(records) == len(SOURCES)
    for record in records:
        path = RULEBOOK_RAW_DIR / record["relative_path"]
        assert path.is_file(), path
        assert path.stat().st_size == record["bytes"], path
        assert sha256_file(path) == record["sha256"], path
    return f"{len(records)} CMS artifacts exist and match pinned byte counts/SHA-256 values."


def _source_families() -> str:
    systems = {record["payment_system"] for record in _manifest()["records"]}
    assert systems == {"PFS", "OPPS", "IPPS"}
    ids = {record["source_artifact_id"] for record in _manifest()["records"]}
    required = {
        "cms_pfs_rvu24a",
        "cms_pfs_rvu24ar",
        "cms_pfs_rvu24b",
        "cms_pfs_rvu24c",
        "cms_pfs_rvu24d",
        "cms_opps_2024_q1_addendum_b",
        "cms_opps_2024_q2_addendum_b",
        "cms_opps_2024_q3_addendum_b",
        "cms_opps_2024_q4_addendum_b",
        "cms_opps_2024_final_addenda",
        "cms_ipps_fy2024_table1",
        "cms_ipps_fy2024_wage_tables",
        "cms_ipps_fy2024_table5",
        "cms_ipps_fy2025_table1",
        "cms_ipps_fy2025_wage_tables",
        "cms_ipps_fy2025_table5",
    }
    assert required <= ids
    return "PFS, quarterly OPPS, FY2024 IPPS, and FY2025 IPPS core families are pinned."


def _keys_and_foreign_keys(store: RulebookStore) -> str:
    rules = store.payment_rules
    params = store.rule_parameters
    assignments = store.code_assignments
    artifacts = store.source_artifacts
    assert rules["rule_id"].is_unique
    assert params["parameter_id"].is_unique
    assert assignments["assignment_id"].is_unique
    assert artifacts["source_artifact_id"].is_unique
    rule_ids = set(rules["rule_id"])
    artifact_ids = set(artifacts["source_artifact_id"])
    assert set(params["rule_id"]) <= rule_ids
    assert set(assignments["rule_id"]) <= rule_ids
    assert set(rules["source_artifact_id"]) <= artifact_ids
    assert set(params["source_artifact_id"]) <= artifact_ids
    assert set(assignments["source_artifact_id"]) <= artifact_ids
    return (
        f"Unique keys and rule/source foreign keys pass across {len(rules):,} rules, "
        f"{len(params):,} parameters, and {len(assignments):,} assignments."
    )


def _controlled_vocabularies(store: RulebookStore) -> str:
    rules = store.payment_rules
    assert set(rules["rule_type"]) <= {item.value for item in RuleType}
    assert set(rules["policy_function"]) <= {item.value for item in PolicyFunction}
    assert set(rules["execution_status"]) <= {item.value for item in ExecutionStatus}
    forbidden = {"waste", "rent", "inefficient", "overpayment"}
    assert not forbidden.intersection(set(rules["policy_function"]))
    counts = rules["execution_status"].value_counts().to_dict()
    return "Controlled taxonomies pass; rule status counts are " + ", ".join(
        f"{key}={value}" for key, value in sorted(counts.items())
    ) + "."


def _temporal_coverage() -> str:
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
        label="PFS",
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
        label="OPPS",
    )
    validate_contiguous_intervals(
        [("2024-01-01", "2024-09-30"), ("2024-10-01", "2024-12-31")],
        expected_start="2024-01-01",
        expected_end="2024-12-31",
        label="CY2024 IPPS",
    )
    return "PFS/OPPS calendar boundaries and the September 30/October 1 IPPS switch are contiguous."


def _parameter_values(store: RulebookStore) -> str:
    params = store.rule_parameters.set_index("parameter_id")
    assignments = store.code_assignments.set_index("assignment_id")
    expected_parameters = {
        "pfs.rvu24a.conversion_factor": Decimal("32.7442"),
        "pfs.rvu24ar.conversion_factor": Decimal("33.2875"),
        "pfs.rvu24a.AL:00.work_gpci": Decimal("1.000"),
        "pfs.rvu24a.AL:00.pe_gpci": Decimal("0.869"),
        "ipps.fy2024.050008.wage_index": Decimal("1.8744"),
        "ipps.fy2025.050008.wage_index": Decimal("1.7807"),
        "ipps.fy2025.quality_submitted_ehr_user.labor_share_67.6.labor": Decimal(
            "4478.09"
        ),
    }
    for parameter_id, expected in expected_parameters.items():
        assert Decimal(params.loc[parameter_id, "numeric_value"]) == expected
    expected_assignments = {
        "pfs.rvu24a.99213.blank": ("work_rvu", Decimal("1.30")),
        "opps.2024_q1.G0402": ("payment_rate", Decimal("125.950")),
        "opps.2024_q1.C9790": ("payment_rate", Decimal("17500.500")),
        "ipps.fy2024.ms_drg.039": ("relative_weight", Decimal("1.1410")),
        "ipps.fy2025.ms_drg.039": ("relative_weight", Decimal("1.1382")),
    }
    for assignment_id, (column, expected) in expected_assignments.items():
        assert Decimal(assignments.loc[assignment_id, column]) == expected
    return f"{len(expected_parameters) + len(expected_assignments)} direct CMS parameter cells/rows match."


def _carrier_amount(
    artifact_id: str,
    *,
    member: str,
    carrier: str,
    locality: str,
    code: str,
) -> tuple[Decimal, Decimal]:
    by_id = {record["source_artifact_id"]: record for record in _manifest()["records"]}
    path = RULEBOOK_RAW_DIR / by_id[artifact_id]["relative_path"]
    with zipfile.ZipFile(path) as archive:
        rows = csv.reader(io.TextIOWrapper(archive.open(member), encoding="ascii"))
        matches = [
            row
            for row in rows
            if len(row) >= 7
            and row[1].strip() == carrier
            and row[2].strip() == locality
            and row[3].strip() == code
            and not row[4].strip()
        ]
    assert len(matches) == 1
    return Decimal(matches[0][5]), Decimal(matches[0][6])


def _pfs_formula_and_independent_reference(store: RulebookStore) -> str:
    fixtures = (
        (
            "cms_pfs_carrier_2024_jan_mar8",
            "2024-01-15",
            Decimal("82.30"),
            Decimal("60.38"),
        ),
        (
            "cms_pfs_carrier_2024_mar9_dec31",
            "2024-03-09",
            Decimal("83.66"),
            Decimal("61.39"),
        ),
    )
    for artifact_id, service_date, expected_nf, expected_f in fixtures:
        carrier_nf, carrier_f = _carrier_amount(
            artifact_id,
            member="PFAL24A.TXT",
            carrier="10112",
            locality="00",
            code="99213",
        )
        assert (carrier_nf, carrier_f) == (expected_nf, expected_f)
        nonfacility = calculate_pfs(
            "99213", service_date, "AL:00", "nonfacility", store
        )
        facility = calculate_pfs("99213", service_date, "AL:00", "facility", store)
        assert nonfacility.calculated_amount == carrier_nf
        assert facility.calculated_amount == carrier_f
        validate_trace(nonfacility)
        validate_trace(facility)
    return "Four PFS amounts reproduce independent CMS Alabama carrier-file values exactly to cents."


def _opps_lookups(store: RulebookStore) -> str:
    separate = lookup_opps("G0402", "2024-01-01", store)
    packaged = lookup_opps("C1734", "2024-03-31", store)
    capc = lookup_opps("C9600", "2024-01-01", store)
    assert separate.calculation_status is CalculationStatus.LOOKUP_ONLY
    assert separate.calculated_amount == Decimal("125.950")
    assert packaged.components["status_indicator"] == "N"
    assert packaged.calculated_amount is None
    assert capc.components["status_indicator"] == "J1"
    assert capc.components["claim_context_required"] is True
    for trace in (separate, packaged, capc):
        validate_trace(trace)
    return "Separate, packaged, and comprehensive-APC Addendum B paths resolve with non-final labels."


def _ipps_formula(store: RulebookStore) -> str:
    inputs = dict(
        store=store,
        ms_drg="039",
        provider_ccn="050008",
        quality_submitted=True,
        meaningful_ehr_user=True,
    )
    september = calculate_ipps_base_payment(discharge_date="2024-09-30", **inputs)
    october = calculate_ipps_base_payment(discharge_date="2024-10-01", **inputs)
    assert september.calculated_amount == Decimal("11796.30")
    assert october.calculated_amount == Decimal("11519.08")
    assert september.components["fiscal_year"] == "FY2024"
    assert october.components["fiscal_year"] == "FY2025"
    validate_trace(september)
    validate_trace(october)
    return "MS-DRG 039/CCN 050008 reproduces $11,796.30 (FY2024) and $11,519.08 (FY2025 IFC)."


def _fail_closed(store: RulebookStore) -> str:
    pfs = calculate_pfs("01951", "2024-01-15", "AL:00", "nonfacility", store)
    unresolved_row = store.code_assignments[
        (store.code_assignments["payment_system"] == "OPPS")
        & (store.code_assignments["value_status"] == "unresolved_effective_date")
    ].iloc[0]
    opps = lookup_opps(
        str(unresolved_row["code"]),
        str(unresolved_row["effective_start"]),
        store,
    )
    ipps = calculate_ipps_base_payment(
        store,
        ms_drg="039",
        discharge_date="2024-10-01",
        provider_ccn="010006",
        quality_submitted=True,
        meaningful_ehr_user=True,
    )
    for trace in (pfs, opps, ipps):
        assert trace.calculation_status is CalculationStatus.UNSUPPORTED
        assert trace.calculated_amount is None
        validate_trace(trace)
    return "Anesthesia, unresolved OPPS dates, and IPPS out-migration all return UNSUPPORTED without amounts."


def _trace_foreign_keys(store: RulebookStore) -> str:
    trace = calculate_pfs("99213", "2024-03-09", "NY:01", "facility", store)
    validate_trace(trace)
    rule_ids = set(store.payment_rules["rule_id"])
    parameter_ids = set(store.rule_parameters["parameter_id"])
    assignment_ids = set(store.code_assignments["assignment_id"])
    artifact_ids = set(store.source_artifacts["source_artifact_id"])
    assert {rule["rule_id"] for rule in trace.selected_rule_versions} <= rule_ids
    selected_ids = {
        parameter.get("parameter_id") for parameter in trace.selected_parameters
    }
    assert selected_ids <= parameter_ids | assignment_ids
    assert set(trace.source_artifact_ids) <= artifact_ids
    return "Executed trace rule, parameter/assignment, and artifact identifiers resolve to canonical tables."


def _duckdb_integration(store: RulebookStore) -> str:
    expected = {
        "payment_rules": len(store.payment_rules),
        "rule_parameters": len(store.rule_parameters),
        "code_assignments": len(store.code_assignments),
        "source_artifacts": len(store.source_artifacts),
    }
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as connection:
        observed_tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        assert {"nhea_source_service", "nhea_sponsor", *expected} <= observed_tables
        for table, expected_count in expected.items():
            observed_count = connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            assert observed_count == expected_count
    return "Stage 1 and Stage 2 logical tables coexist in healthcare.duckdb with matching row counts."


def _copyright_boundary(store: RulebookStore) -> str:
    forbidden = {"description", "short_descriptor", "long_descriptor", "cpt_description"}
    assert not forbidden.intersection({column.lower() for column in store.code_assignments})
    assert not forbidden.intersection({column.lower() for column in store.rule_parameters})
    return "Normalized code/parameter schemas contain no CPT/HCPCS description fields."


def validation_checks(store: RulebookStore) -> list[ValidationCheck]:
    specifications: tuple[tuple[str, Callable[[], str]], ...] = (
        ("Source integrity", _source_integrity),
        ("Source family coverage", _source_families),
        ("Primary/foreign keys", lambda: _keys_and_foreign_keys(store)),
        ("Controlled vocabularies", lambda: _controlled_vocabularies(store)),
        ("Temporal coverage", _temporal_coverage),
        ("Direct parameter checks", lambda: _parameter_values(store)),
        ("PFS independent formula validation", lambda: _pfs_formula_and_independent_reference(store)),
        ("OPPS lookup validation", lambda: _opps_lookups(store)),
        ("IPPS formula/boundary validation", lambda: _ipps_formula(store)),
        ("Fail-closed behavior", lambda: _fail_closed(store)),
        ("Trace foreign keys", lambda: _trace_foreign_keys(store)),
        ("Integrated DuckDB", lambda: _duckdb_integration(store)),
        ("Copyright boundary", lambda: _copyright_boundary(store)),
    )
    return [_run_check(name, check) for name, check in specifications]


def _write_example_traces(store: RulebookStore) -> None:
    traces = {
        "pfs_99213_alabama_nonfacility_2024-03-09.json": calculate_pfs(
            "99213", "2024-03-09", "AL:00", "nonfacility", store
        ),
        "pfs_99213_alabama_facility_2024-03-09.json": calculate_pfs(
            "99213", "2024-03-09", "AL:00", "facility", store
        ),
        "pfs_01951_anesthesia_unsupported.json": calculate_pfs(
            "01951", "2024-01-15", "AL:00", "facility", store
        ),
        "opps_g0402_published_rate_2024-01-01.json": lookup_opps(
            "G0402", "2024-01-01", store
        ),
        "opps_c1734_packaged_2024-03-31.json": lookup_opps(
            "C1734", "2024-03-31", store
        ),
        "ipps_drg039_ccn050008_2024-09-30.json": calculate_ipps_base_payment(
            store,
            ms_drg="039",
            discharge_date="2024-09-30",
            provider_ccn="050008",
            quality_submitted=True,
            meaningful_ehr_user=True,
        ),
        "ipps_drg039_ccn050008_2024-10-01.json": calculate_ipps_base_payment(
            store,
            ms_drg="039",
            discharge_date="2024-10-01",
            provider_ccn="050008",
            quality_submitted=True,
            meaningful_ehr_user=True,
        ),
    }
    for filename, trace in traces.items():
        write_trace(trace, RULEBOOK_EXAMPLE_TRACES_DIR / filename)


def _write_report(checks: list[ValidationCheck], store: RulebookStore) -> None:
    passed = sum(check.passed for check in checks)
    status_counts = store.payment_rules["execution_status"].value_counts().to_dict()
    assignment_status = (
        store.code_assignments.groupby(["payment_system", "value_status"])
        .size()
        .to_dict()
    )
    lines = [
        "# Stage 2A validation report",
        "",
        f"**Result: {passed}/{len(checks)} checks passed.**",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        lines.append(f"- **{marker} — {check.name}:** {check.detail}")
    lines.extend(
        [
            "",
            "## Artifact coverage",
            "",
            f"- Payment rules: {len(store.payment_rules):,}",
            f"- Rule parameters: {len(store.rule_parameters):,}",
            f"- Code assignments: {len(store.code_assignments):,}",
            f"- Source artifacts: {len(store.source_artifacts):,}",
            "- Rule execution statuses: "
            + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items())),
            "",
            "Changed quarterly rows without normalized row-specific dates are deliberately "
            "not counted as executable coverage. Assignment statuses:",
            "",
        ]
    )
    for (system, value_status), count in sorted(assignment_status.items()):
        lines.append(f"- {system} / `{value_status}`: {count:,}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The PFS and IPPS checks validate labeled base amounts, not final claims. The OPPS "
            "checks validate published national unadjusted lookup values and packaging context. "
            "Provider/claim adjustments listed in each trace remain outside Stage 2A.",
            "",
        ]
    )
    RULEBOOK_VALIDATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULEBOOK_VALIDATION_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def validate_rulebook() -> list[ValidationCheck]:
    store = RulebookStore.load()
    checks = validation_checks(store)
    _write_example_traces(store)
    _write_report(checks, store)
    failed = [check for check in checks if not check.passed]
    if failed:
        raise RuntimeError(
            "Rulebook validation failed: "
            + "; ".join(f"{check.name}: {check.detail}" for check in failed)
        )
    return checks


def main() -> None:
    checks = validate_rulebook()
    for check in checks:
        print(f"PASS  {check.name}: {check.detail}")


if __name__ == "__main__":
    main()
