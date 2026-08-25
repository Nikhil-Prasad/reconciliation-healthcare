"""Read-only access to canonical rulebook Parquet artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from reconciliation_healthcare.paths import (
    CODE_ASSIGNMENTS_PATH,
    ENTITY_SOURCE_LINKS_PATH,
    PAYMENT_RULES_PATH,
    RULE_PARAMETERS_PATH,
    SOURCE_ARTIFACTS_PATH,
)


@dataclass(frozen=True)
class RulebookStore:
    payment_rules: pd.DataFrame
    rule_parameters: pd.DataFrame
    code_assignments: pd.DataFrame
    source_artifacts: pd.DataFrame
    entity_source_links: pd.DataFrame = field(default_factory=pd.DataFrame)
    provenance_required: bool = False

    @classmethod
    def load(
        cls,
        *,
        payment_rules_path: Path = PAYMENT_RULES_PATH,
        rule_parameters_path: Path = RULE_PARAMETERS_PATH,
        code_assignments_path: Path = CODE_ASSIGNMENTS_PATH,
        source_artifacts_path: Path = SOURCE_ARTIFACTS_PATH,
        entity_source_links_path: Path = ENTITY_SOURCE_LINKS_PATH,
    ) -> "RulebookStore":
        required = (
            payment_rules_path,
            rule_parameters_path,
            code_assignments_path,
            source_artifacts_path,
            entity_source_links_path,
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Rulebook artifacts are missing; run hcl-rulebook-build: " + ", ".join(missing)
            )
        return cls(
            payment_rules=pd.read_parquet(payment_rules_path),
            rule_parameters=pd.read_parquet(rule_parameters_path),
            code_assignments=pd.read_parquet(code_assignments_path),
            source_artifacts=pd.read_parquet(source_artifacts_path),
            entity_source_links=pd.read_parquet(entity_source_links_path),
            provenance_required=True,
        )

    def rule(self, rule_id: str) -> dict[str, object]:
        matches = self.payment_rules[self.payment_rules["rule_id"] == rule_id]
        if len(matches) != 1:
            raise KeyError(f"Expected one rule {rule_id!r}; found {len(matches)}")
        return matches.iloc[0].to_dict()

    def sources_for(self, entity_type: str, entity_id: str) -> list[dict[str, object]]:
        """Return authoritative source relationships for one canonical entity."""

        if self.entity_source_links.empty:
            return []
        matches = self.entity_source_links[
            (self.entity_source_links["entity_type"] == entity_type)
            & (self.entity_source_links["entity_id"] == entity_id)
        ]
        return matches.sort_values("source_link_id", kind="stable").to_dict(
            orient="records"
        )
