from __future__ import annotations

from dataclasses import replace

import duckdb
import pandas as pd
import pytest

from reconciliation_healthcare.paths import DUCKDB_PATH
from reconciliation_healthcare.rulebook.ipps import calculate_ipps_base_payment
from reconciliation_healthcare.rulebook.models import EntityType, SourceRole
from reconciliation_healthcare.rulebook.opps import lookup_opps
from reconciliation_healthcare.rulebook.pfs import calculate_pfs
from reconciliation_healthcare.rulebook.provenance import validate_entity_source_links


def test_every_parameter_and_assignment_has_source_provenance(built_rulebook_store) -> None:
    store = built_rulebook_store
    artifact_ids = set(store.source_artifacts["source_artifact_id"])
    for frame in (store.rule_parameters, store.code_assignments):
        assert frame["source_artifact_id"].notna().all()
        assert frame["source_locator"].str.len().gt(0).all()
        assert set(frame["source_artifact_id"]) <= artifact_ids
    assert set(store.payment_rules["source_artifact_id"]) <= artifact_ids


def test_entity_source_links_are_complete_and_resolve(built_rulebook_store) -> None:
    store = built_rulebook_store
    links = store.entity_source_links
    artifact_ids = set(store.source_artifacts["source_artifact_id"])
    assert links["source_link_id"].is_unique
    assert not links.duplicated(
        [
            "entity_type",
            "entity_id",
            "source_artifact_id",
            "source_role",
            "effective_start",
            "effective_end",
        ]
    ).any()
    assert set(links["source_artifact_id"]) <= artifact_ids
    assert set(links["source_role"]) <= {role.value for role in SourceRole}
    assert set(links["entity_type"]) == {kind.value for kind in EntityType}

    expected = {
        "rule": set(store.payment_rules["rule_id"]),
        "parameter": set(store.rule_parameters["parameter_id"]),
        "assignment": set(store.code_assignments["assignment_id"]),
    }
    for entity_type, expected_ids in expected.items():
        observed_ids = set(links.loc[links["entity_type"].eq(entity_type), "entity_id"])
        assert observed_ids == expected_ids


def test_duplicate_entity_source_link_is_rejected(built_rulebook_store) -> None:
    store = built_rulebook_store
    duplicate = pd.concat(
        [store.entity_source_links, store.entity_source_links.iloc[[0]]],
        ignore_index=True,
    )
    with pytest.raises(ValueError, match="duplicate source links"):
        validate_entity_source_links(
            duplicate,
            payment_rules=store.payment_rules,
            rule_parameters=store.rule_parameters,
            code_assignments=store.code_assignments,
            source_artifacts=store.source_artifacts,
        )


def test_c9790_retroactive_provenance_is_explicit(built_rulebook_store) -> None:
    store = built_rulebook_store
    links = store.sources_for("assignment", "opps.2024_q1.C9790")
    observed = {
        (link["source_artifact_id"], link["source_role"]) for link in links
    }
    assert {
        ("cms_opps_2024_q1_addendum_b", "supporting_documentation"),
        ("cms_opps_2024_april_update", "retroactive_correction"),
        ("cms_opps_2024_q2_addendum_b", "primary_numeric_authority"),
    } <= observed

    trace = lookup_opps("C9790", "2024-01-15", store)
    assert trace.selected_parameters[0]["source_artifact_id"] == (
        "cms_opps_2024_q2_addendum_b"
    )
    assert {
        "cms_opps_2024_q1_addendum_b",
        "cms_opps_2024_april_update",
        "cms_opps_2024_q2_addendum_b",
    } <= set(trace.source_artifact_ids)
    assert any(
        link["source_role"] == "retroactive_correction"
        for link in trace.source_links
    )
    assert "without a normalized code-specific update date" not in (
        trace.selected_parameters[0]["source_locator"]
    )


def test_ipps_fy2024_corrections_are_explicit(built_rulebook_store) -> None:
    store = built_rulebook_store
    uncompensated = {
        (link["source_artifact_id"], link["source_role"])
        for link in store.sources_for("rule", "ipps.fy2024.uncompensated_care")
    }
    assert (
        "cms_ipps_fy2024_correction_notice",
        "correction",
    ) in uncompensated
    assert (
        "cms_ipps_fy2024_correction_notice_2",
        "supporting_documentation",
    ) in uncompensated


def test_opps_packaging_interpretation_selects_its_policy_authority(
    built_rulebook_store,
) -> None:
    trace = lookup_opps("C1734", "2024-03-31", built_rulebook_store)
    assert "opps.packaging" in {
        rule["rule_id"] for rule in trace.selected_rule_versions
    }
    assert any(
        link["entity_id"] == "opps.packaging"
        and link["source_artifact_id"] == "cms_opps_2024_final_addenda"
        for link in trace.source_links
    )


def test_trace_provenance_is_effective_dated(built_rulebook_store) -> None:
    store = built_rulebook_store
    links = store.entity_source_links.copy()
    sentinel = links[
        links["entity_id"].eq("opps.2024_q1.C9790")
    ].iloc[0].copy()
    sentinel["source_link_id"] = "assignment|opps.2024_q1.C9790|future-sentinel"
    sentinel["source_artifact_id"] = "cms_opps_2024_q4_addendum_b"
    sentinel["source_role"] = "supporting_documentation"
    sentinel["source_locator"] = "future audit sentinel"
    sentinel["effective_start"] = "2024-03-01"
    sentinel["effective_end"] = "2024-03-31"
    links = pd.concat([links, sentinel.to_frame().T], ignore_index=True)
    trace = lookup_opps(
        "C9790",
        "2024-01-15",
        replace(store, entity_source_links=links),
    )
    assert all(
        link["source_locator"] != "future audit sentinel"
        for link in trace.source_links
    )
    assert "cms_opps_2024_q4_addendum_b" not in trace.source_artifact_ids


def test_canonical_store_rejects_missing_trace_links(built_rulebook_store) -> None:
    store = built_rulebook_store
    links = store.entity_source_links[
        ~(
            store.entity_source_links["entity_type"].eq("assignment")
            & store.entity_source_links["entity_id"].eq("opps.2024_q1.G0402")
        )
    ].copy()
    with pytest.raises(ValueError, match="lack an active entity_source_link"):
        lookup_opps(
            "G0402",
            "2024-01-15",
            replace(store, entity_source_links=links),
        )


def test_canonical_store_rejects_empty_provenance_table(
    built_rulebook_store,
) -> None:
    store = replace(
        built_rulebook_store,
        entity_source_links=pd.DataFrame(),
        provenance_required=True,
    )
    with pytest.raises(ValueError, match="has no entity_source_links"):
        lookup_opps("G0402", "2024-01-15", store)


def test_executed_traces_return_complete_resolved_linked_sources(
    built_rulebook_store,
) -> None:
    store = built_rulebook_store
    traces = (
        calculate_pfs("99213", "2024-03-09", "AL:00", "nonfacility", store),
        lookup_opps("G0402", "2024-01-15", store),
        calculate_ipps_base_payment(
            store,
            ms_drg="039",
            discharge_date="2024-10-01",
            provider_ccn="050008",
            quality_submitted=True,
            meaningful_ehr_user=True,
        ),
    )
    artifact_ids = set(store.source_artifacts["source_artifact_id"])
    for trace in traces:
        linked_artifacts = {link["source_artifact_id"] for link in trace.source_links}
        assert linked_artifacts
        assert set(trace.source_artifact_ids) == linked_artifacts
        assert linked_artifacts <= artifact_ids


def test_normalized_code_assignments_exclude_copyrighted_descriptions(
    built_rulebook_store,
) -> None:
    columns = {column.lower() for column in built_rulebook_store.code_assignments.columns}
    assert "description" not in columns
    assert "short_descriptor" not in columns
    assert "long_descriptor" not in columns


def test_rulebook_tables_are_integrated_into_existing_duckdb(built_rulebook_store) -> None:
    expected = {
        "payment_rules",
        "rule_edges",
        "rule_parameters",
        "code_assignments",
        "source_artifacts",
        "entity_source_links",
        "nhea_source_service",
        "nhea_sponsor",
    }
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as connection:
        observed = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
    assert expected <= observed
