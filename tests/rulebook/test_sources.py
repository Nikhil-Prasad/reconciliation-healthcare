from __future__ import annotations

import json
import zipfile

from reconciliation_healthcare.paths import RULEBOOK_MANIFEST_PATH, RULEBOOK_RAW_DIR
from reconciliation_healthcare.rulebook.sources import SOURCES, sha256_file


CORE_EXPECTED_HASHES = {
    "cms_pfs_rvu24a": "0d25be13406d04c85501204755e5c48599a8900cf41a82899a956020e0a64e68",
    "cms_pfs_rvu24ar": "df87e861580b15f6a8c334afa5b57f1997ec24261e8f67f6d6b185dff56c38f8",
    "cms_opps_2024_q1_addendum_b": "696b652db25c06924e261d389920b86fb8253ec2b8b2dca7e5d53890a97a98fc",
    "cms_opps_2024_q4_addendum_b": "f7fd47eb848d92e3577e94c4ea2e4de36fbfac96ffdf779c2ab7b2a9a4b2a36e",
    "cms_ipps_fy2024_wage_tables": "5345289ae4acb5747e69f42b15aa4a8763d40250464265b510a41d63496c4cbb",
    "cms_ipps_fy2025_table1": "c9e0912959b81f32aedb3c3db33856a8fbfe1a206f75913a9de770168ed34cce",
}


def test_rulebook_sources_exist_and_match_pinned_manifest() -> None:
    manifest = json.loads(RULEBOOK_MANIFEST_PATH.read_text(encoding="utf-8"))
    records = manifest["records"]
    assert len(records) == len(SOURCES)
    assert {record["source_artifact_id"] for record in records} == {
        source.source_artifact_id for source in SOURCES
    }
    for record in records:
        path = RULEBOOK_RAW_DIR / record["relative_path"]
        assert path.is_file()
        assert path.stat().st_size == record["bytes"]
        assert sha256_file(path) == record["sha256"]
        assert record["source_authority"] == "Centers for Medicare & Medicaid Services"
        assert record["source_url"].startswith("https://www.cms.gov/")
        assert record["effective_start"] <= record["effective_end"]
        assert record["downloaded_at"]
        assert record["http_last_modified"]
    by_id = {record["source_artifact_id"]: record for record in records}
    for artifact_id, checksum in CORE_EXPECTED_HASHES.items():
        assert by_id[artifact_id]["sha256"] == checksum


def test_core_archives_have_expected_machine_readable_members() -> None:
    manifest = json.loads(RULEBOOK_MANIFEST_PATH.read_text(encoding="utf-8"))
    by_id = {record["source_artifact_id"]: record for record in manifest["records"]}
    expectations = {
        "cms_pfs_rvu24a": ("PPRRVU24_JAN.csv", "GPCI2024.csv", "RVU24A.pdf"),
        "cms_opps_2024_q1_addendum_b": (".csv", ".xlsx"),
        "cms_ipps_fy2024_table1": (".xlsx", ".txt"),
        "cms_ipps_fy2025_table5": (".xlsx", ".txt"),
    }
    for artifact_id, fragments in expectations.items():
        path = RULEBOOK_RAW_DIR / by_id[artifact_id]["relative_path"]
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
        for fragment in fragments:
            assert any(fragment in name for name in names), (artifact_id, fragment)
