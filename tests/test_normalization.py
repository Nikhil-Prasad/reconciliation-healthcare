from __future__ import annotations

import pandas as pd

from reconciliation_healthcare.normalize_nhea import CANONICAL_COLUMNS


def test_principal_normalization_shape_and_years(built_artifacts: dict[str, pd.DataFrame]) -> None:
    dataframe = built_artifacts["source_service"]
    assert len(dataframe) == 34_970
    assert dataframe["year"].min() == 1960
    assert dataframe["year"].max() == 2024
    assert set(dataframe["year"].unique()) == set(range(1960, 2025))
    assert dataframe["source_row"].nunique() == 538
    assert dataframe.groupby("source_row")["year"].nunique().eq(65).all()
    assert set(CANONICAL_COLUMNS).issubset(dataframe.columns)
    assert set(dataframe["accounting_view"]) == {"source_of_funds_by_service"}
    assert set(dataframe["amount_unit"]) == {"USD current dollars"}
    assert set(dataframe["source_unit"]) == {"USD millions, current dollars"}


def test_amounts_statuses_and_not_applicable_are_deterministic(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    dataframe = built_artifacts["source_service"]
    assert dataframe["value_status"].value_counts().to_dict() == {
        "reported": 23_287,
        "not_applicable": 8_953,
        "structural_blank": 2_730,
    }
    assert dataframe.loc[dataframe["value_status"] == "reported", "amount_usd"].notna().all()
    assert dataframe.loc[
        dataframe["value_status"].isin(["not_applicable", "structural_blank"]),
        "amount_usd",
    ].isna().all()
    assert dataframe.loc[
        dataframe["value_status"] == "not_applicable", "source_value_raw"
    ].str.strip().isin({"-", "—", "–"}).all()
    assert dataframe.loc[
        dataframe["value_status"] == "structural_blank", "source_value_raw"
    ].str.strip().eq("").all()
    assert not (dataframe["amount_usd"].dropna() == 0).any()
    assert dataframe["derivation"].isna().all()
    assert dataframe["claim_class"].isna().all()
    assert not dataframe["source_label_raw"].str.contains("Percent", case=False).any()

    pre_medicare = dataframe[
        (dataframe["year"] == 1960)
        & (dataframe["service_category_code"] == "nhe")
        & (dataframe["funding_source_code"] == "medicare")
    ].iloc[0]
    assert pre_medicare["value_status"] == "not_applicable"
    assert pd.isna(pre_medicare["amount_usd"])
    assert pre_medicare["source_value_raw"].strip() == "-"

    structural_blank = dataframe[dataframe["value_status"] == "structural_blank"]
    assert set(structural_blank["service_category_code"]) == {
        "state_local_administration",
        "federal_administration",
        "nonmedical_insurance",
    }


def test_principal_canonical_keys_and_provenance_are_unique(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    dataframe = built_artifacts["source_service"]
    key = ["year", "service_category_code", "funding_source_code"]
    assert not dataframe.duplicated(key).any()
    assert dataframe["source_file"].str.endswith("::NHE2024.csv").all()
    assert dataframe["source_sheet"].eq("NHE2024.csv").all()
    assert dataframe["source_row"].notna().all()
    assert dataframe["source_column"].str.fullmatch(r"[A-Z]+").all()
    assert dataframe["source_label_raw"].notna().all()
    assert dataframe["ingested_at"].notna().all()


def test_hierarchy_flags_prevent_double_counting(built_artifacts: dict[str, pd.DataFrame]) -> None:
    dataframe = built_artifacts["source_service"]
    sample = dataframe[
        (dataframe["year"] == 2024)
        & (dataframe["service_category_code"] == "hospital_care")
    ].set_index("funding_source_code")
    assert sample.loc["health_insurance", "funding_source_is_subtotal"]
    assert not sample.loc["health_insurance", "include_in_service_funding_sum"]
    assert sample.loc["medicaid", "funding_source_is_subtotal"]
    assert sample.loc["medicaid", "include_in_service_funding_sum"]
    assert not sample.loc["medicaid_federal", "include_in_service_funding_sum"]
    assert sample.loc[
        "other_third_party_payers_programs", "include_in_service_funding_sum"
    ]
    assert not sample.loc["worksite_health_care", "include_in_service_funding_sum"]
    assert sample.loc["total_cms_programs", "observation_role"] == "overlapping_analytical_subtotal"
    assert not sample.loc["total_cms_programs", "include_in_service_funding_sum"]


def test_sponsor_view_is_separate_and_uses_available_history(
    built_artifacts: dict[str, pd.DataFrame],
) -> None:
    sponsor = built_artifacts["sponsor"]
    assert len(sponsor) == 304
    assert sponsor["year"].min() == 1987
    assert sponsor["year"].max() == 2024
    assert set(sponsor["accounting_view"]) == {"sponsor"}
    assert sponsor["funding_source_code"].isna().all()
    assert sponsor["service_category_code"].eq("nhe").all()
    assert not sponsor.duplicated(["year", "sponsor_code"]).any()
    assert set(sponsor["source_unit"]) == {"USD billions, current dollars"}
    assert sponsor["source_display_precision_usd"].eq(100_000_000).all()
