from __future__ import annotations

from reconciliation_healthcare.rulebook.graph import RULE_COLUMNS
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


def test_site_of_service_paths_are_explicit(built_rulebook_store) -> None:
    rules = built_rulebook_store.payment_rules.set_index("rule_id")
    assert rules.loc["site.office_professional_path", "policy_function"] == "site_of_service"
    assert rules.loc["site.hospital_outpatient_path", "policy_function"] == "site_of_service"
    assert "nonfacility" in rules.loc["site.office_professional_path", "output_description"].lower()
    assert "opps" in rules.loc["site.hospital_outpatient_path", "output_description"].lower()
