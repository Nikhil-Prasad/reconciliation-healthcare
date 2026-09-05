from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from reconciliation_healthcare.learning import (
    EXAMPLES,
    GUIDE_FILE,
    LEDGER_FILE,
    TRACE_DIRECTORY,
    render_worked_examples,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example_project(tmp_path: Path) -> Path:
    paths = [LEDGER_FILE, *(TRACE_DIRECTORY / name for name in EXAMPLES.values())]
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY_ROOT / relative, destination)
    return tmp_path


def test_learning_guide_reproduces_using_only_committed_examples(example_project) -> None:
    assert not (example_project / "data").exists()
    assert render_worked_examples(example_project) == (REPOSITORY_ROOT / GUIDE_FILE).read_text(
        encoding="utf-8"
    )


def test_learning_guide_rejects_a_mismatched_setting_comparison(example_project) -> None:
    path = example_project / TRACE_DIRECTORY / EXAMPLES["facility"]
    payload = json.loads(path.read_text())
    payload["input_context"]["locality"] = "NY:01"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="PFS comparison contexts differ on locality"):
        render_worked_examples(example_project)


def test_learning_guide_rejects_replacing_a_packaged_null_with_zero(example_project) -> None:
    path = example_project / TRACE_DIRECTORY / EXAMPLES["packaged"]
    payload = json.loads(path.read_text())
    payload["calculated_amount"] = "0"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Packaging example requires status N and a null published rate"):
        render_worked_examples(example_project)


def test_learning_guide_rejects_ambiguous_national_observation(example_project) -> None:
    path = example_project / LEDGER_FILE
    lines = path.read_text().splitlines()
    hospital_line = next(line for line in lines if line.startswith("hospital_care,"))
    path.write_text("\n".join([*lines, hospital_line]) + "\n")
    with pytest.raises(ValueError, match="exactly one Hospital Care"):
        render_worked_examples(example_project)
