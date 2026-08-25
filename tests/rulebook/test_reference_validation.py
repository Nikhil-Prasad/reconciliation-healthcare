from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

import pytest

from reconciliation_healthcare.rulebook.graph import build_rule_graph
from reconciliation_healthcare.rulebook.normalize import normalize_sources
from reconciliation_healthcare.rulebook.reference_validation import (
    IPPSReferenceCase,
    PFSCarrierReferenceCase,
    build_ipps_reference_cases,
    build_pfs_carrier_reference_cases,
    validate_ipps_references,
    validate_pfs_carrier_references,
)
from reconciliation_healthcare.rulebook.store import RulebookStore


@pytest.fixture(scope="module")
def pfs_reference_cases() -> tuple[PFSCarrierReferenceCase, ...]:
    return build_pfs_carrier_reference_cases()


@pytest.fixture(scope="module")
def ipps_reference_cases() -> tuple[IPPSReferenceCase, ...]:
    return build_ipps_reference_cases()


@pytest.fixture(scope="module")
def reference_store() -> RulebookStore:
    """Build the in-memory canonical inputs without writing generated artifacts."""
    rules, _ = build_rule_graph()
    parameters, assignments, source_artifacts = normalize_sources()
    return RulebookStore(
        payment_rules=rules,
        rule_parameters=parameters,
        code_assignments=assignments,
        source_artifacts=source_artifacts,
    )


def test_pfs_carrier_matrix_is_balanced_and_source_derived(
    pfs_reference_cases: tuple[PFSCarrierReferenceCase, ...],
) -> None:
    cases = pfs_reference_cases

    assert len(cases) == 40
    assert len({case.case_id for case in cases}) == 40
    assert Counter(case.rule_version for case in cases) == {
        "rvu24a": 8,
        "rvu24ar": 8,
        "rvu24b": 8,
        "rvu24c": 8,
        "rvu24d": 8,
    }
    assert Counter(case.code for case in cases) == {
        "80503": 10,
        "86077": 10,
        "90961": 10,
        "99305": 10,
    }
    assert Counter(case.locality for case in cases) == {
        "AK:01": 8,
        "AL:00": 8,
        "CA:05": 8,
        "NY:01": 8,
        "TX:09": 8,
    }
    assert Counter(case.setting for case in cases) == {
        "facility": 20,
        "nonfacility": 20,
    }
    assert Counter(case.reference_artifact_id for case in cases) == {
        "cms_pfs_carrier_2024_jan_mar8": 8,
        "cms_pfs_carrier_2024_mar9_dec31": 32,
    }
    assert all(case.expected_amount > 0 for case in cases)
    assert all("blank modifier" in case.source_locator for case in cases)


def test_pfs_selected_codes_remain_uncomplicated_in_every_snapshot(
    reference_store: RulebookStore,
    pfs_reference_cases: tuple[PFSCarrierReferenceCase, ...],
) -> None:
    selected_codes = sorted({case.code for case in pfs_reference_cases})
    assert selected_codes == ["80503", "86077", "90961", "99305"]
    assert [
        sum(lower <= int(code) <= upper for code in selected_codes)
        for lower, upper in (
            (80000, 84999),
            (85000, 89999),
            (90000, 94999),
            (95000, 99999),
        )
    ] == [1, 1, 1, 1]

    assignments = reference_store.code_assignments
    selected = assignments[
        assignments["payment_system"].eq("PFS")
        & assignments["code"].isin(selected_codes)
        & assignments["modifier"].fillna("").astype("string").str.strip().eq("")
    ]
    assert len(selected) == 20
    assert Counter(selected["code"]) == {code: 5 for code in selected_codes}
    assert set(selected["status_code"]) == {"A"}
    assert set(selected["value_status"]) == {"published"}

    for column in (
        "work_rvu",
        "nonfacility_pe_rvu",
        "facility_pe_rvu",
        "malpractice_rvu",
    ):
        assert all(Decimal(str(value)) > 0 for value in selected[column])
    for column in ("nonfacility_na_indicator", "facility_na_indicator"):
        assert selected[column].fillna("").astype("string").str.strip().eq("").all()
    for column in (
        "multiple_procedure_indicator",
        "bilateral_surgery_indicator",
        "assistant_surgery_indicator",
        "co_surgery_indicator",
        "team_surgery_indicator",
    ):
        assert set(selected[column].fillna("").astype("string")) <= {"0", "9"}


def test_all_pfs_carrier_references_match_engine(
    reference_store: RulebookStore,
    pfs_reference_cases: tuple[PFSCarrierReferenceCase, ...],
) -> None:
    summary = validate_pfs_carrier_references(
        reference_store,
        cases=pfs_reference_cases,
    )

    assert summary.payment_system == "PFS"
    assert summary.matched_cases == 40
    assert summary.codes == ("80503", "86077", "90961", "99305")
    assert summary.geographies == ("AK:01", "AL:00", "CA:05", "NY:01", "TX:09")
    assert summary.periods == ("rvu24a", "rvu24ar", "rvu24b", "rvu24c", "rvu24d")
    assert summary.settings == ("facility", "nonfacility")
    assert summary.source_artifact_ids == (
        "cms_pfs_carrier_2024_jan_mar8",
        "cms_pfs_carrier_2024_mar9_dec31",
    )


def test_pfs_validation_rejects_carrier_artifact_as_calculation_input(
    reference_store: RulebookStore,
    pfs_reference_cases: tuple[PFSCarrierReferenceCase, ...],
) -> None:
    case = pfs_reference_cases[0]
    assignments = reference_store.code_assignments.copy()
    target = assignments["assignment_id"].eq(
        f"pfs.{case.rule_version}.{case.code}.blank"
    )
    assert target.sum() == 1
    assignments.loc[target, "source_artifact_id"] = case.reference_artifact_id
    poisoned_store = RulebookStore(
        payment_rules=reference_store.payment_rules,
        rule_parameters=reference_store.rule_parameters,
        code_assignments=assignments,
        source_artifacts=reference_store.source_artifacts,
        entity_source_links=reference_store.entity_source_links,
    )

    with pytest.raises(
        AssertionError,
        match="carrier artifact used as a calculation input",
    ):
        validate_pfs_carrier_references(poisoned_store, cases=(case,))


def test_ipps_matrix_covers_fiscal_year_drg_wage_and_labor_branches(
    ipps_reference_cases: tuple[IPPSReferenceCase, ...],
) -> None:
    cases = ipps_reference_cases

    assert len(cases) == 8
    assert len({case.case_id for case in cases}) == 8
    assert Counter(case.fiscal_year for case in cases) == {"FY2024": 4, "FY2025": 4}
    assert Counter(case.ms_drg for case in cases) == {"039": 4, "470": 4}
    assert Counter(case.provider_ccn for case in cases) == {"010001": 4, "050008": 4}
    assert Counter(case.geography for case in cases) == {"20020": 4, "41884": 4}
    assert Counter(case.labor_share for case in cases) == {
        Decimal("62"): 4,
        Decimal("67.6"): 4,
    }
    assert all(case.wage_index <= 1 for case in cases if case.labor_share == 62)
    assert all(case.wage_index > 1 for case in cases if case.labor_share == Decimal("67.6"))
    assert all(
        case.amount_nine_places
        == case.unrounded_amount.quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP)
        for case in cases
    )
    assert all(
        case.expected_amount
        == case.amount_nine_places.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for case in cases
    )
    assert all(len(case.source_artifact_ids) == 3 for case in cases)
    assert all(len(case.source_locators) == 4 for case in cases)


def test_all_ipps_raw_table_references_match_engine(
    reference_store: RulebookStore,
    ipps_reference_cases: tuple[IPPSReferenceCase, ...],
) -> None:
    summary = validate_ipps_references(
        reference_store,
        cases=ipps_reference_cases,
    )

    assert summary.payment_system == "IPPS"
    assert summary.matched_cases == 8
    assert summary.codes == ("039", "470")
    assert summary.geographies == ("20020", "41884")
    assert summary.periods == ("FY2024", "FY2025")
    assert summary.labor_share_branches == ("62", "67.6")
    assert summary.source_artifact_ids == (
        "cms_ipps_fy2024_table1",
        "cms_ipps_fy2024_table5",
        "cms_ipps_fy2024_wage_tables",
        "cms_ipps_fy2025_table1",
        "cms_ipps_fy2025_table5",
        "cms_ipps_fy2025_wage_tables",
    )
