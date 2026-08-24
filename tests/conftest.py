from __future__ import annotations

import os
from pathlib import Path
import tempfile

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ORIGINAL_HCL_PROJECT_ROOT = os.environ.get("HCL_PROJECT_ROOT")
_ISOLATED_DIRECTORY = tempfile.TemporaryDirectory(prefix="hcl-pytest-")
ISOLATED_PROJECT_ROOT = Path(_ISOLATED_DIRECTORY.name)
_raw_parent = ISOLATED_PROJECT_ROOT / "data" / "raw"
_raw_parent.mkdir(parents=True)
(_raw_parent / "cms_nhea").symlink_to(
    PROJECT_ROOT / "data" / "raw" / "cms_nhea",
    target_is_directory=True,
)
os.environ["HCL_PROJECT_ROOT"] = str(ISOLATED_PROJECT_ROOT)

# Project paths are resolved at import time, after the isolated root is configured.
from reconciliation_healthcare.inspect_nhea import write_inventory
from reconciliation_healthcare.ledger import build_ledger
from reconciliation_healthcare.normalize_nhea import normalize_all


@pytest.fixture(scope="session", autouse=True)
def isolated_project_root() -> None:
    yield
    if _ORIGINAL_HCL_PROJECT_ROOT is None:
        os.environ.pop("HCL_PROJECT_ROOT", None)
    else:
        os.environ["HCL_PROJECT_ROOT"] = _ORIGINAL_HCL_PROJECT_ROOT
    _ISOLATED_DIRECTORY.cleanup()


@pytest.fixture(scope="session")
def built_artifacts() -> dict[str, pd.DataFrame]:
    """Build artifacts in an isolated tree so tests never refresh project outputs."""
    write_inventory()
    source_service, sponsor = normalize_all()
    ledger, ledger_cells = build_ledger()
    return {
        "source_service": source_service,
        "sponsor": sponsor,
        "ledger": ledger,
        "ledger_cells": ledger_cells,
    }
