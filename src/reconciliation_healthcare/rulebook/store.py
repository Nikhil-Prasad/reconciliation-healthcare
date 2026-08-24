"""Read-only access to canonical rulebook Parquet artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from reconciliation_healthcare.paths import (
    CODE_ASSIGNMENTS_PATH,
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

    @classmethod
    def load(
        cls,
        *,
        payment_rules_path: Path = PAYMENT_RULES_PATH,
        rule_parameters_path: Path = RULE_PARAMETERS_PATH,
        code_assignments_path: Path = CODE_ASSIGNMENTS_PATH,
        source_artifacts_path: Path = SOURCE_ARTIFACTS_PATH,
    ) -> "RulebookStore":
        required = (
            payment_rules_path,
            rule_parameters_path,
            code_assignments_path,
            source_artifacts_path,
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
        )

    def rule(self, rule_id: str) -> dict[str, object]:
        matches = self.payment_rules[self.payment_rules["rule_id"] == rule_id]
        if len(matches) != 1:
            raise KeyError(f"Expected one rule {rule_id!r}; found {len(matches)}")
        return matches.iloc[0].to_dict()
