from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from reconciliation_healthcare.rulebook.models import CalculationStatus
from reconciliation_healthcare.rulebook.pfs import calculate_pfs
from reconciliation_healthcare.rulebook.store import RulebookStore
from reconciliation_healthcare.rulebook.trace import validate_trace


RELEASES = {
    "rvu24a": ("2024-01-01", "2024-03-08", "32.7442"),
    "rvu24ar": ("2024-03-09", "2024-03-31", "33.2875"),
    "rvu24b": ("2024-04-01", "2024-06-30", "33.2875"),
    "rvu24c": ("2024-07-01", "2024-09-30", "33.2875"),
    "rvu24d": ("2024-10-01", "2024-12-31", "33.2875"),
}

LOCALITIES = {
    "AL:00": ("1.000", "0.869", "0.575"),
    "NY:01": ("1.065", "1.166", "1.656"),
}


def _pfs_assignment(
    *,
    version: str,
    code: str,
    status: str,
    work_rvu: str,
    nonfacility_pe_rvu: str,
    facility_pe_rvu: str,
    malpractice_rvu: str,
) -> dict[str, object]:
    start, end, _ = RELEASES[version]
    artifact = f"cms_pfs_{version}"
    return {
        "assignment_id": f"pfs.{version}.{code}.blank",
        "rule_id": f"pfs.{version}.base_payment",
        "payment_system": "PFS",
        "assignment_type": "pfs_rvu",
        "code": code,
        "modifier": "",
        "effective_start": start,
        "effective_end": end,
        "status_code": status,
        "work_rvu": Decimal(work_rvu),
        "nonfacility_pe_rvu": Decimal(nonfacility_pe_rvu),
        "nonfacility_na_indicator": None,
        "facility_pe_rvu": Decimal(facility_pe_rvu),
        "facility_na_indicator": None,
        "malpractice_rvu": Decimal(malpractice_rvu),
        "multiple_procedure_indicator": "0",
        "bilateral_surgery_indicator": "0",
        "assistant_surgery_indicator": "0",
        "co_surgery_indicator": "0",
        "team_surgery_indicator": "0",
        "source_artifact_id": artifact,
        "source_locator": f"PPRRVU24::{code}",
        "value_status": "published",
    }


def _parameter(
    *,
    version: str,
    name: str,
    value: str,
    key_value: str,
) -> dict[str, object]:
    start, end, _ = RELEASES[version]
    artifact = f"cms_pfs_{version}"
    rule_suffix = "conversion_factor" if name == "conversion_factor" else "gpci"
    return {
        "parameter_id": f"pfs.{version}.{key_value}.{name}",
        "rule_id": f"pfs.{version}.{rule_suffix}",
        "parameter_name": name,
        "effective_start": start,
        "effective_end": end,
        "key_type": "national" if name == "conversion_factor" else "state_locality",
        "key_value": key_value,
        "numeric_value": Decimal(value),
        "unit": "USD per geographically adjusted RVU" if name == "conversion_factor" else "index",
        "source_artifact_id": artifact,
        "source_locator": f"fixture::{name}::{key_value}",
        "value_status": "published",
    }


@pytest.fixture
def pfs_store() -> RulebookStore:
    assignments: list[dict[str, object]] = []
    parameters: list[dict[str, object]] = []
    rules: list[dict[str, object]] = []
    artifacts: list[dict[str, str]] = []

    for version, (start, end, conversion_factor) in RELEASES.items():
        artifact = f"cms_pfs_{version}"
        artifacts.append({"source_artifact_id": artifact})
        assignments.append(
            _pfs_assignment(
                version=version,
                code="99213",
                status="A",
                work_rvu="1.30",
                nonfacility_pe_rvu="1.33",
                facility_pe_rvu="0.56",
                malpractice_rvu="0.10",
            )
        )
        parameters.append(
            _parameter(
                version=version,
                name="conversion_factor",
                value=conversion_factor,
                key_value="US",
            )
        )
        for locality, (work_gpci, pe_gpci, mp_gpci) in LOCALITIES.items():
            parameters.extend(
                [
                    _parameter(
                        version=version,
                        name="work_gpci",
                        value=work_gpci,
                        key_value=locality,
                    ),
                    _parameter(
                        version=version,
                        name="pe_gpci",
                        value=pe_gpci,
                        key_value=locality,
                    ),
                    _parameter(
                        version=version,
                        name="mp_gpci",
                        value=mp_gpci,
                        key_value=locality,
                    ),
                ]
            )
        for suffix, name in (
            ("base_payment", "Core geographically adjusted PFS base payment"),
            ("work_rvu", "Work RVU lookup"),
            ("practice_expense_rvu", "Facility/nonfacility PE RVU selection"),
            ("malpractice_rvu", "Malpractice RVU lookup"),
            ("gpci", "Locality GPCI lookup"),
            ("conversion_factor", "PFS conversion factor"),
        ):
            rules.append(
                {
                    "rule_id": f"pfs.{version}.{suffix}",
                    "rule_name": name,
                    "rule_version": version,
                    "effective_start": start,
                    "effective_end": end,
                    "execution_status": "executable",
                    "source_artifact_id": artifact,
                    "source_locator": "fixture",
                }
            )

    # G9037 is a defensible quarterly-boundary fixture: CMS made it active July 1.
    for version in ("rvu24c", "rvu24d"):
        assignments.append(
            _pfs_assignment(
                version=version,
                code="G9037",
                status="A",
                work_rvu="0.57",
                nonfacility_pe_rvu="0.59",
                facility_pe_rvu="0.59",
                malpractice_rvu="0.04",
            )
        )

    assignments.append(
        _pfs_assignment(
            version="rvu24a",
            code="01951",
            status="J",
            work_rvu="0",
            nonfacility_pe_rvu="0",
            facility_pe_rvu="0",
            malpractice_rvu="0",
        )
    )

    return RulebookStore(
        payment_rules=pd.DataFrame(rules),
        rule_parameters=pd.DataFrame(parameters),
        code_assignments=pd.DataFrame(assignments),
        source_artifacts=pd.DataFrame(artifacts),
    )


@pytest.mark.parametrize(
    ("date_of_service", "locality", "setting", "expected"),
    [
        ("2024-01-15", "AL:00", "nonfacility", "82.30"),
        ("2024-01-15", "AL:00", "facility", "60.38"),
        ("2024-01-15", "NY:01", "nonfacility", "101.54"),
        ("2024-01-15", "NY:01", "facility", "72.14"),
        ("2024-03-09", "AL:00", "nonfacility", "83.66"),
        ("2024-03-09", "AL:00", "facility", "61.39"),
        ("2024-03-09", "NY:01", "nonfacility", "103.22"),
        ("2024-03-09", "NY:01", "facility", "73.33"),
    ],
)
def test_99213_exact_published_locality_amounts(
    pfs_store: RulebookStore,
    date_of_service: str,
    locality: str,
    setting: str,
    expected: str,
) -> None:
    trace = calculate_pfs("99213", date_of_service, locality, setting, pfs_store)

    assert trace.calculation_status is CalculationStatus.CALCULATED
    assert trace.calculated_amount == Decimal(expected)
    assert trace.components["setting"] == setting
    assert trace.components["rounding"] == "nearest_cent_half_up"
    assert trace.selected_parameters[0]["parameter_id"].endswith("99213.blank")
    validate_trace(trace)


@pytest.mark.parametrize(
    ("date_of_service", "expected_version", "expected_cf"),
    [
        ("2024-01-01", "rvu24a", "32.7442"),
        ("2024-03-08", "rvu24a", "32.7442"),
        ("2024-03-09", "rvu24ar", "33.2875"),
        ("2024-03-31", "rvu24ar", "33.2875"),
        ("2024-04-01", "rvu24b", "33.2875"),
        ("2024-06-30", "rvu24b", "33.2875"),
        ("2024-07-01", "rvu24c", "33.2875"),
        ("2024-09-30", "rvu24c", "33.2875"),
        ("2024-10-01", "rvu24d", "33.2875"),
        ("2024-12-31", "rvu24d", "33.2875"),
    ],
)
def test_exact_march_and_quarterly_snapshot_selection(
    pfs_store: RulebookStore,
    date_of_service: str,
    expected_version: str,
    expected_cf: str,
) -> None:
    trace = calculate_pfs("99213", date_of_service, "AL:00", "nonfacility", pfs_store)

    assert trace.calculation_status is CalculationStatus.CALCULATED
    assert trace.components["conversion_factor"] == Decimal(expected_cf)
    assert trace.source_artifact_ids == [f"cms_pfs_{expected_version}"]
    assert {rule["rule_version"] for rule in trace.selected_rule_versions} == {
        expected_version
    }


def test_july_first_code_effective_date_fails_closed_then_calculates(
    pfs_store: RulebookStore,
) -> None:
    june = calculate_pfs("G9037", "2024-06-30", "AL:00", "nonfacility", pfs_store)
    july = calculate_pfs("G9037", "2024-07-01", "AL:00", "nonfacility", pfs_store)

    assert june.calculation_status is CalculationStatus.UNSUPPORTED
    assert june.calculated_amount is None
    assert june.missing_parameters == ["code_assignment:no_effective_record"]
    assert july.calculation_status is CalculationStatus.CALCULATED
    assert july.calculated_amount == Decimal("36.81")
    assert july.source_artifact_ids == ["cms_pfs_rvu24c"]


def test_status_j_anesthesia_code_fails_closed(pfs_store: RulebookStore) -> None:
    trace = calculate_pfs("01951", "2024-01-15", "AL:00", "nonfacility", pfs_store)

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.calculated_amount is None
    assert trace.missing_rule == "pfs.anesthesia"
    assert trace.unsupported_adjustments == ["pfs.anesthesia"]
    assert trace.selected_parameters[0]["status_code"] == "J"
    validate_trace(trace)


def test_unresolved_code_effective_date_fails_closed(pfs_store: RulebookStore) -> None:
    row = pfs_store.code_assignments.index[
        pfs_store.code_assignments["assignment_id"].eq("pfs.rvu24c.99213.blank")
    ][0]
    pfs_store.code_assignments.loc[row, "value_status"] = "unresolved_effective_date"

    trace = calculate_pfs("99213", "2024-07-01", "AL:00", "nonfacility", pfs_store)

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.calculated_amount is None
    assert trace.missing_parameters == ["code_assignment:value_status"]
    validate_trace(trace)


def test_special_payment_indicator_fails_closed(pfs_store: RulebookStore) -> None:
    row = pfs_store.code_assignments.index[
        pfs_store.code_assignments["assignment_id"].eq("pfs.rvu24a.99213.blank")
    ][0]
    pfs_store.code_assignments.loc[row, "bilateral_surgery_indicator"] = "1"

    trace = calculate_pfs("99213", "2024-01-15", "AL:00", "nonfacility", pfs_store)

    assert trace.calculation_status is CalculationStatus.UNSUPPORTED
    assert trace.calculated_amount is None
    assert trace.missing_rule == "pfs.bilateral_surgery"
    assert trace.unsupported_adjustments == ["pfs.bilateral_surgery"]
    validate_trace(trace)
