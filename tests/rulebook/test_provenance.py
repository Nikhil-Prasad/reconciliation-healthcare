from __future__ import annotations

import duckdb

from reconciliation_healthcare.paths import DUCKDB_PATH


def test_every_parameter_and_assignment_has_source_provenance(built_rulebook_store) -> None:
    store = built_rulebook_store
    artifact_ids = set(store.source_artifacts["source_artifact_id"])
    for frame in (store.rule_parameters, store.code_assignments):
        assert frame["source_artifact_id"].notna().all()
        assert frame["source_locator"].str.len().gt(0).all()
        assert set(frame["source_artifact_id"]) <= artifact_ids
    assert set(store.payment_rules["source_artifact_id"]) <= artifact_ids


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
