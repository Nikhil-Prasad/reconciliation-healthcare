from __future__ import annotations

from datetime import date

from reconciliation_healthcare.rulebook.graph import RULE_COLUMNS, build_rule_graph
from reconciliation_healthcare.rulebook.models import (
    ExecutionStatus,
    PolicyFunction,
    RuleType,
)
from reconciliation_healthcare.rulebook.normalize import (
    ASSIGNMENT_COLUMNS,
    PARAMETER_COLUMNS,
)


def test_canonical_table_columns_and_primary_keys(built_rulebook_store) -> None:
    store = built_rulebook_store
    assert list(store.payment_rules.columns) == RULE_COLUMNS
    assert list(store.rule_parameters.columns) == PARAMETER_COLUMNS
    assert list(store.code_assignments.columns) == ASSIGNMENT_COLUMNS
    assert store.payment_rules["rule_id"].is_unique
    assert store.rule_parameters["parameter_id"].is_unique
    assert store.code_assignments["assignment_id"].is_unique


def test_rule_vocabularies_are_controlled(built_rulebook_store) -> None:
    rules = built_rulebook_store.payment_rules
    assert set(rules["rule_type"]) <= {value.value for value in RuleType}
    assert set(rules["policy_function"]) <= {value.value for value in PolicyFunction}
    assert set(rules["execution_status"]) <= {value.value for value in ExecutionStatus}


def test_rule_edges_reference_existing_rules(built_rulebook_store) -> None:
    from reconciliation_healthcare.paths import RULE_EDGES_PATH
    import pandas as pd

    edges = pd.read_parquet(RULE_EDGES_PATH)
    rule_ids = set(built_rulebook_store.payment_rules["rule_id"])
    assert edges["edge_id"].is_unique
    assert set(edges["from_rule_id"]) <= rule_ids
    assert set(edges["to_rule_id"]) <= rule_ids
    assert {"depends_on", "may_add", "may_apply", "routes_to", "may_combine_with"} <= set(
        edges["edge_type"]
    )


def test_rule_edge_intervals_are_contained_by_both_endpoints(
    built_rulebook_store,
) -> None:
    from reconciliation_healthcare.paths import RULE_EDGES_PATH
    import pandas as pd

    edges = pd.read_parquet(RULE_EDGES_PATH)
    rules = built_rulebook_store.payment_rules.set_index("rule_id")

    for edge in edges.to_dict(orient="records"):
        edge_start = pd.Timestamp(edge["effective_start"])
        edge_end = pd.Timestamp(edge["effective_end"])
        from_rule = rules.loc[edge["from_rule_id"]]
        to_rule = rules.loc[edge["to_rule_id"]]
        assert pd.Timestamp(from_rule["effective_start"]) <= edge_start <= edge_end
        assert edge_end <= pd.Timestamp(from_rule["effective_end"])
        assert pd.Timestamp(to_rule["effective_start"]) <= edge_start <= edge_end
        assert edge_end <= pd.Timestamp(to_rule["effective_end"])


def test_ipps_deferred_rules_switch_on_september_30_october_1(
    built_rulebook_store,
) -> None:
    rules = built_rulebook_store.payment_rules
    deferred_suffixes = {
        "ime",
        "dsh",
        "uncompensated_care",
        "ntap",
        "outlier",
        "hrrp",
        "vbp",
        "hac",
        "transfer",
        "final_payment",
    }
    boundaries = (
        (
            date(2024, 9, 30),
            "fy2024",
            date(2023, 10, 1),
            date(2024, 9, 30),
            "cms_ipps_fy2024_table1",
            "CMS-1785",
        ),
        (
            date(2024, 10, 1),
            "fy2025",
            date(2024, 10, 1),
            date(2025, 9, 30),
            "cms_ipps_fy2025_table1",
            "CMS-1808",
        ),
    )

    for target_date, version, start, end, artifact_id, authority in boundaries:
        for suffix in deferred_suffixes:
            candidates = rules[
                rules["payment_system"].eq("IPPS")
                & rules["rule_id"].str.endswith(f".{suffix}")
                & rules["effective_start"].le(target_date)
                & rules["effective_end"].ge(target_date)
            ]
            assert candidates["rule_id"].tolist() == [f"ipps.{version}.{suffix}"]
            selected = candidates.iloc[0]
            assert selected["rule_version"] == version.upper()
            assert selected["effective_start"] == start
            assert selected["effective_end"] == end
            assert selected["source_artifact_id"] == artifact_id
            assert authority in selected["regulatory_authority"]


def test_ipps_final_payment_edges_are_same_fiscal_year() -> None:
    _, edges = build_rule_graph()
    edge_types = {
        "base_operating_payment": "depends_on",
        "ime": "may_add",
        "dsh": "may_add",
        "uncompensated_care": "may_add",
        "ntap": "may_add",
        "outlier": "may_add",
        "hrrp": "may_apply",
        "vbp": "may_apply",
        "hac": "may_apply",
        "transfer": "may_apply",
    }
    fiscal_years = (
        ("fy2024", "2023-10-01", "2024-09-30"),
        ("fy2025", "2024-10-01", "2025-09-30"),
    )

    for version, start, end in fiscal_years:
        final_payment = f"ipps.{version}.final_payment"
        outgoing = edges[edges["from_rule_id"].eq(final_payment)]
        expected = {
            f"ipps.{version}.{suffix}": edge_type
            for suffix, edge_type in edge_types.items()
        }
        assert dict(zip(outgoing["to_rule_id"], outgoing["edge_type"], strict=True)) == expected
        assert set(outgoing["effective_start"]) == {start}
        assert set(outgoing["effective_end"]) == {end}


def test_site_of_service_paths_are_explicit(built_rulebook_store) -> None:
    rules = built_rulebook_store.payment_rules.set_index("rule_id")
    assert rules.loc["site.office_professional_path", "policy_function"] == "site_of_service"
    assert rules.loc["site.hospital_outpatient_path", "policy_function"] == "site_of_service"
    assert "nonfacility" in rules.loc["site.office_professional_path", "output_description"].lower()
    assert "opps" in rules.loc["site.hospital_outpatient_path", "output_description"].lower()
