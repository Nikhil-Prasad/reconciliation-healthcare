"""Archive and verify the minimal official CMS sources for the CY2024 rulebook."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from reconciliation_healthcare.paths import (
    RULEBOOK_MANIFEST_PATH,
    RULEBOOK_RAW_DIR,
)


CMS = "Centers for Medicare & Medicaid Services"


@dataclass(frozen=True)
class SourceSpec:
    source_artifact_id: str
    payment_system: str
    dataset: str
    relative_path: str
    source_page: str
    source_url: str
    source_release: str
    effective_start: str
    effective_end: str
    description: str

    @property
    def original_filename(self) -> str:
        return Path(self.relative_path).name


PFS_PAGE = "https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files"
OPPS_PAGE = (
    "https://www.cms.gov/medicare/payment/prospective-payment-systems/"
    "hospital-outpatient-pps/quarterly-addenda-updates"
)
IPPS_2024_PAGE = (
    "https://www.cms.gov/medicare/payment/prospective-payment-systems/"
    "acute-inpatient-pps/acute-inpatient-files-download/"
    "files-fy-2024-final-rule-correction-notice"
)
IPPS_2025_PAGE = (
    "https://www.cms.gov/medicare/payment/prospective-payment-systems/"
    "acute-inpatient-pps/fy-2025-ipps-final-rule-home-page"
)


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        "cms_pfs_rvu24a",
        "PFS",
        "CY2024 PFS Relative Value File",
        "pfs/rvu24a-updated-2024-04-01.zip",
        f"{PFS_PAGE}/rvu24a",
        "https://www.cms.gov/files/zip/rvu24a-updated-04/01/2024.zip",
        "RVU24A, updated 2024-04-01",
        "2024-01-01",
        "2024-03-08",
        "January RVUs, GPCIs, policy indicators, and conversion factor.",
    ),
    SourceSpec(
        "cms_pfs_rvu24ar",
        "PFS",
        "CY2024 PFS Relative Value File",
        "pfs/rvu24ar-posted-2024-04-01.zip",
        f"{PFS_PAGE}/rvu24ar",
        "https://www.cms.gov/files/zip/rvu24ar-posted-04/01/2024.zip",
        "RVU24AR, posted 2024-04-01",
        "2024-03-09",
        "2024-03-31",
        "Revised RVUs and conversion factor effective after the March 2024 statutory update.",
    ),
    SourceSpec(
        "cms_pfs_rvu24b",
        "PFS",
        "CY2024 PFS Relative Value File",
        "pfs/rvu24b-updated-2024-03-18.zip",
        f"{PFS_PAGE}/rvu24b",
        "https://www.cms.gov/files/zip/rvu24b-updated-03/18/2024.zip",
        "RVU24B, updated 2024-03-18",
        "2024-04-01",
        "2024-06-30",
        "April quarterly PFS relative-value release.",
    ),
    SourceSpec(
        "cms_pfs_rvu24c",
        "PFS",
        "CY2024 PFS Relative Value File",
        "pfs/rvu24c-updated-2024-09-09.zip",
        f"{PFS_PAGE}/rvu24c",
        "https://www.cms.gov/files/zip/rvu24c-updated-09/09/2024.zip",
        "RVU24C, updated 2024-09-09",
        "2024-07-01",
        "2024-09-30",
        "July quarterly PFS relative-value release, including CMS's September update.",
    ),
    SourceSpec(
        "cms_pfs_rvu24d",
        "PFS",
        "CY2024 PFS Relative Value File",
        "pfs/rvu24d.zip",
        f"{PFS_PAGE}/rvu24d",
        "https://www.cms.gov/files/zip/rvu24d.zip",
        "RVU24D",
        "2024-10-01",
        "2024-12-31",
        "October quarterly PFS relative-value release.",
    ),
    SourceSpec(
        "cms_pfs_carrier_2024_jan_mar8",
        "PFS",
        "CY2024 PFS all-states carrier payment file",
        "pfs/carrier-2024-01-01-through-2024-03-08.zip",
        "https://www.cms.gov/medicare/payment/fee-schedules/physician/carrier-specific-files/all-states",
        (
            "https://www.cms.gov/files/zip/"
            "cy-2024-carrier-files-effective-date-january-1-2024-march-8-2024-updated-04/02/2024.zip"
        ),
        "CY2024 carrier files, updated 2024-04-02",
        "2024-01-01",
        "2024-03-08",
        "Independent CMS-published locality payment amounts used for formula validation.",
    ),
    SourceSpec(
        "cms_pfs_carrier_2024_mar9_dec31",
        "PFS",
        "CY2024 PFS all-states carrier payment file",
        "pfs/carrier-2024-03-09-through-2024-12-31.zip",
        "https://www.cms.gov/medicare/payment/fee-schedules/physician/carrier-specific-files/all-states",
        (
            "https://www.cms.gov/files/zip/"
            "cy-2024-carrier-files-effective-date-march-9-2024-december-31-2024-updated-04/02/2024.zip"
        ),
        "CY2024 revised carrier files, updated 2024-04-02",
        "2024-03-09",
        "2024-12-31",
        "Independent CMS-published locality payment amounts used for formula validation.",
    ),
    SourceSpec(
        "cms_pfs_cr13529",
        "PFS",
        "April 2024 PFS update change request",
        "pfs/r12501cp-cr13529.pdf",
        f"{PFS_PAGE}/rvu24b",
        "https://www.cms.gov/files/document/r12501cp.pdf",
        "CR 13529 / Transmittal R12501CP",
        "2024-01-01",
        "2024-06-30",
        "CMS implementation instructions with row-specific April and retroactive effective dates.",
    ),
    SourceSpec(
        "cms_pfs_cr13624",
        "PFS",
        "July 2024 PFS update change request",
        "pfs/r12629cp-cr13624.pdf",
        f"{PFS_PAGE}/rvu24c",
        "https://www.cms.gov/files/document/r12629cp.pdf",
        "CR 13624 / Transmittal R12629CP",
        "2024-01-01",
        "2024-09-30",
        "CMS implementation instructions with heterogeneous row-level effective dates.",
    ),
    SourceSpec(
        "cms_pfs_cr13751",
        "PFS",
        "October 2024 PFS update change request",
        "pfs/r12774cp-cr13751.pdf",
        f"{PFS_PAGE}/rvu24d",
        "https://www.cms.gov/files/document/r12774cp.pdf",
        "CR 13751 / Transmittal R12774CP",
        "2024-06-17",
        "2024-12-31",
        "CMS October implementation instructions for row-specific effective dates.",
    ),
    SourceSpec(
        "cms_pfs_cr13751_attachment",
        "PFS",
        "October 2024 PFS update machine-readable attachment",
        "pfs/r12774cp1.zip",
        f"{PFS_PAGE}/rvu24d",
        "https://www.cms.gov/files/zip/r12774cp1.zip",
        "CR 13751 machine-readable attachment",
        "2024-06-17",
        "2024-12-31",
        "CMS attachment containing code-level record effective dates.",
    ),
    SourceSpec(
        "cms_opps_2024_q1_addendum_b",
        "OPPS",
        "CY2024 OPPS Addendum B",
        "opps/january-2024-opps-addendum-b.zip",
        f"{OPPS_PAGE}/addendum-b",
        "https://www.cms.gov/files/zip/january-2024-opps-addendum-b.zip",
        "January 2024 Addendum B, updated 2024-04-25",
        "2024-01-01",
        "2024-03-31",
        "Quarter-one HCPCS status indicators, APC assignments, weights, and rates.",
    ),
    SourceSpec(
        "cms_opps_2024_q2_addendum_b",
        "OPPS",
        "CY2024 OPPS Addendum B",
        "opps/april-2024-addendum-b.zip",
        (
            "https://www.cms.gov/medicare/payment/prospective-payment-systems/"
            "hospital-outpatient/addendum-a-b-updates/april-2024-0"
        ),
        "https://www.cms.gov/files/zip/april-2024-addendum-b.zip",
        "April 2024 Addendum B, updated 2024-04-23",
        "2024-04-01",
        "2024-06-30",
        "Quarter-two HCPCS status indicators, APC assignments, weights, and rates.",
    ),
    SourceSpec(
        "cms_opps_2024_q3_addendum_b",
        "OPPS",
        "CY2024 OPPS Addendum B",
        "opps/july-2024-addendum-b-2024-08-05.zip",
        (
            "https://www.cms.gov/medicare/payment/prospective-payment-systems/"
            "hospital-outpatient/addendum-a-b-updates/july-2024-0"
        ),
        "https://www.cms.gov/files/zip/july-2024-addendum-b-080524.zip",
        "July 2024 Addendum B, updated 2024-08-05",
        "2024-07-01",
        "2024-09-30",
        "Quarter-three HCPCS status indicators, APC assignments, weights, and rates.",
    ),
    SourceSpec(
        "cms_opps_2024_q4_addendum_b",
        "OPPS",
        "CY2024 OPPS Addendum B",
        "opps/october-2024-addendum-b-2024-10-02.zip",
        (
            "https://www.cms.gov/medicare/payment/prospective-payment-systems/"
            "hospital-outpatient/addendum-a-b-updates/october-2024-updated-10/02/2024-0"
        ),
        "https://www.cms.gov/files/zip/october-2024-web-addendum-b.zip",
        "October 2024 Addendum B, updated 2024-10-02",
        "2024-10-01",
        "2024-12-31",
        "Quarter-four HCPCS status indicators, APC assignments, weights, and rates.",
    ),
    SourceSpec(
        "cms_opps_2024_final_addenda",
        "OPPS",
        "CY2024 OPPS final-rule addenda",
        "opps/2024-nfrm-opps-addenda.zip",
        (
            "https://www.cms.gov/medicare/payment/prospective-payment-systems/"
            "hospital-outpatient/regulations-notices/cms-1786-fc"
        ),
        "https://www.cms.gov/files/zip/2024-nfrm-opps-addenda.zip",
        "CMS-1786-FC final-rule addenda",
        "2024-01-01",
        "2024-12-31",
        "Annual policy addenda, including status-indicator definitions and C-APC support tables.",
    ),
    SourceSpec(
        "cms_opps_2024_january_update",
        "OPPS",
        "January 2024 OPPS update",
        "opps/mm13488-january-2024-update.pdf",
        OPPS_PAGE,
        "https://www.cms.gov/files/document/mm13488-hospital-outpatient-prospective-payment-system-january-2024-update.pdf",
        "MLN Matters MM13488 / January 2024 OPPS update",
        "2024-01-01",
        "2024-03-31",
        "Official quarterly implementation and effective-date instructions.",
    ),
    SourceSpec(
        "cms_opps_2024_april_update",
        "OPPS",
        "April 2024 OPPS update",
        "opps/mm13568-april-2024-update.pdf",
        OPPS_PAGE,
        "https://www.cms.gov/files/document/mm13568-hospital-outpatient-prospective-payment-system-april-2024-update.pdf",
        "MLN Matters MM13568 / April 2024 OPPS update",
        "2024-01-01",
        "2024-06-30",
        "Official update including retroactive January corrections.",
    ),
    SourceSpec(
        "cms_opps_2024_july_update",
        "OPPS",
        "July 2024 OPPS update",
        "opps/mm13632-july-2024-update.pdf",
        OPPS_PAGE,
        "https://www.cms.gov/files/document/mm13632-hospital-outpatient-prospective-payment-system-july-2024-update.pdf",
        "Revised MLN Matters MM13632 / July 2024 OPPS update",
        "2024-03-22",
        "2024-09-30",
        "Official revised update with mid-quarter and retroactive effective dates.",
    ),
    SourceSpec(
        "cms_opps_2024_october_update",
        "OPPS",
        "October 2024 OPPS update",
        "opps/mm13784-october-2024-update.pdf",
        OPPS_PAGE,
        "https://www.cms.gov/files/document/mm13784-hospital-outpatient-prospective-payment-system-october-2024-update.pdf",
        "MLN Matters MM13784 / October 2024 OPPS update",
        "2024-05-31",
        "2024-12-31",
        "Official update with October and retroactive code-specific dates.",
    ),
    SourceSpec(
        "cms_ipps_fy2024_table1",
        "IPPS",
        "FY2024 IPPS Tables 1A-1E",
        "ipps/fy2024-table-1a-1e.zip",
        IPPS_2024_PAGE,
        "https://www.cms.gov/files/zip/fy2024-ipps-fr-table-1a-1e.zip",
        "CMS-1785-F Tables 1A-1E",
        "2023-10-01",
        "2024-09-30",
        "Operating and capital national standardized amounts.",
    ),
    SourceSpec(
        "cms_ipps_fy2024_wage_tables",
        "IPPS",
        "FY2024 IPPS Tables 2, 3, 4A, and 4B",
        "ipps/fy2024-tables-2-3-4.zip",
        IPPS_2024_PAGE,
        "https://www.cms.gov/files/zip/fy2024-ipps-fr-tables-2-3-4.zip",
        "CMS-1785-F and CMS-1785-CN wage-index tables",
        "2023-10-01",
        "2024-09-30",
        "Corrected provider and geographic wage-index tables.",
    ),
    SourceSpec(
        "cms_ipps_fy2024_table5",
        "IPPS",
        "FY2024 IPPS Table 5",
        "ipps/fy2024-table-5.zip",
        IPPS_2024_PAGE,
        "https://www.cms.gov/files/zip/fy2024-ipps-fr-table-5.zip",
        "CMS-1785-F Table 5",
        "2023-10-01",
        "2024-09-30",
        "MS-DRG relative weights and length-of-stay statistics.",
    ),
    SourceSpec(
        "cms_ipps_fy2025_table1",
        "IPPS",
        "FY2025 IPPS Tables 1A-1E",
        "ipps/fy2025-table-1a-1e.zip",
        IPPS_2025_PAGE,
        "https://www.cms.gov/files/zip/fy-2025-ipps-final-rule-table-1a-1e.zip",
        "CMS-1808-F, CMS-1808-CN, and CMS-1808-IFC Tables 1A-1E",
        "2024-10-01",
        "2025-09-30",
        "IFC operating standardized amounts effective for FY2025.",
    ),
    SourceSpec(
        "cms_ipps_fy2025_wage_tables",
        "IPPS",
        "FY2025 IPPS Tables 2, 3, 4A, and 4B",
        "ipps/fy2025-tables-2-3-4a-4b.zip",
        IPPS_2025_PAGE,
        (
            "https://www.cms.gov/files/zip/"
            "fy-2025-ipps-final-rule-tables-2-3-and-4a-and-4b.zip"
        ),
        "CMS-1808-F, CMS-1808-CN, and CMS-1808-IFC wage-index tables",
        "2024-10-01",
        "2025-09-30",
        "IFC provider and geographic wage-index tables after removal of the low-wage policy.",
    ),
    SourceSpec(
        "cms_ipps_fy2025_table5",
        "IPPS",
        "FY2025 IPPS Table 5",
        "ipps/fy2025-table-5.zip",
        IPPS_2025_PAGE,
        "https://www.cms.gov/files/zip/fy-2025-ipps-final-rule-table-5.zip",
        "CMS-1808-F and CMS-1808-CN Table 5",
        "2024-10-01",
        "2025-09-30",
        "Corrected MS-DRG relative weights and length-of-stay statistics.",
    ),
    SourceSpec(
        "cms_ipps_fy2024_final_rule",
        "IPPS",
        "FY2024 IPPS final rule",
        "ipps/cms-1785-f-federal-register.pdf",
        "https://www.govinfo.gov/app/details/FR-2023-08-28/2023-16252",
        "https://www.govinfo.gov/content/pkg/FR-2023-08-28/pdf/2023-16252.pdf",
        "CMS-1785-F / 88 FR 58640",
        "2023-10-01",
        "2024-09-30",
        "Official FY2024 IPPS regulatory authority and annual policy rules.",
    ),
    SourceSpec(
        "cms_ipps_fy2024_correction_notice",
        "IPPS",
        "FY2024 IPPS correction notice",
        "ipps/cms-1785-cn-federal-register.pdf",
        "https://www.govinfo.gov/app/details/FR-2023-10-04/2023-22060",
        "https://www.govinfo.gov/content/pkg/FR-2023-10-04/pdf/2023-22060.pdf",
        "CMS-1785-CN / 88 FR 68482",
        "2023-10-01",
        "2024-09-30",
        "Official correction to the FY2024 IPPS final rule.",
    ),
    SourceSpec(
        "cms_ipps_fy2024_correction_notice_2",
        "IPPS",
        "FY2024 IPPS second correction notice",
        "ipps/cms-1785-cn2-federal-register.pdf",
        "https://www.govinfo.gov/app/details/FR-2023-11-09/2023-24670",
        "https://www.govinfo.gov/content/pkg/FR-2023-11-09/pdf/2023-24670.pdf",
        "CMS-1785-CN2 / 88 FR 77211",
        "2023-10-01",
        "2024-09-30",
        (
            "Official second correction to the FY2024 IPPS final rule; it restores "
            "an omitted comment and response without changing Stage 2A numeric inputs."
        ),
    ),
    SourceSpec(
        "cms_ipps_fy2025_final_rule",
        "IPPS",
        "FY2025 IPPS final rule",
        "ipps/cms-1808-f-federal-register.pdf",
        "https://www.govinfo.gov/app/details/FR-2024-08-28/2024-17021",
        "https://www.govinfo.gov/content/pkg/FR-2024-08-28/pdf/2024-17021.pdf",
        "CMS-1808-F / 89 FR 68986",
        "2024-10-01",
        "2025-09-30",
        "Official FY2025 IPPS regulatory authority and annual policy rules.",
    ),
    SourceSpec(
        "cms_ipps_fy2025_correction_notice",
        "IPPS",
        "FY2025 IPPS correction notice",
        "ipps/cms-1808-cn2-federal-register.pdf",
        "https://www.govinfo.gov/app/details/FR-2024-10-02/2024-22501",
        "https://www.govinfo.gov/content/pkg/FR-2024-10-02/pdf/2024-22501.pdf",
        "CMS-1808-CN2 / 89 FR 80098",
        "2024-10-01",
        "2025-09-30",
        "Official correction to the FY2025 IPPS final rule.",
    ),
    SourceSpec(
        "cms_ipps_fy2025_ifc",
        "IPPS",
        "FY2025 IPPS interim final action",
        "ipps/cms-1808-ifc-federal-register.pdf",
        "https://www.govinfo.gov/app/details/FR-2024-10-03/2024-22765",
        "https://www.govinfo.gov/content/pkg/FR-2024-10-03/pdf/2024-22765.pdf",
        "CMS-1808-IFC / 89 FR 80405",
        "2024-09-30",
        "2025-09-30",
        "Official FY2025 superseding wage-index and conforming rate changes.",
    ),
)


class SourceIntegrityError(RuntimeError):
    """Raised rather than silently accepting changed bytes at a pinned CMS URL."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download_atomic(url: str, destination: Path) -> dict[str, str | None]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "reconciliation-healthcare/0.1 (CMS payment-rule archival download)"
        },
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        downloaded_at = datetime.now(timezone.utc).isoformat()
        with urllib.request.urlopen(request, timeout=180) as response:
            metadata = {
                "downloaded_at": downloaded_at,
                "http_last_modified": response.headers.get("Last-Modified"),
                "http_etag": response.headers.get("ETag"),
                "content_type": response.headers.get_content_type(),
            }
            with temporary_path.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
        temporary_path.replace(destination)
        return metadata
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _load_manifest(path: Path) -> dict[str, object] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def build_manifest(
    raw_dir: Path = RULEBOOK_RAW_DIR,
    *,
    existing_manifest: dict[str, object] | None = None,
    download_metadata: dict[str, dict[str, str | None]] | None = None,
) -> dict[str, object]:
    generated_at = datetime.now(timezone.utc).isoformat()
    prior_by_id = {
        record["source_artifact_id"]: record
        for record in (existing_manifest or {}).get("records", [])
    }
    download_metadata = download_metadata or {}
    records: list[dict[str, object]] = []
    for spec in SOURCES:
        path = raw_dir / spec.relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Required CMS source is missing: {path}")
        checksum = sha256_file(path)
        prior = prior_by_id.get(spec.source_artifact_id, {})
        if prior and prior.get("sha256") != checksum:
            raise SourceIntegrityError(
                f"Pinned source bytes changed for {spec.source_artifact_id}: "
                f"expected {prior.get('sha256')}, received {checksum}"
            )
        metadata = download_metadata.get(spec.source_artifact_id, {})
        records.append(
            {
                "source_artifact_id": spec.source_artifact_id,
                "source_authority": CMS,
                "payment_system": spec.payment_system,
                "dataset": spec.dataset,
                "original_filename": spec.original_filename,
                "relative_path": spec.relative_path,
                "source_page": spec.source_page,
                "source_url": spec.source_url,
                "downloaded_at": prior.get("downloaded_at")
                or metadata.get("downloaded_at")
                or generated_at,
                "http_last_modified": prior.get("http_last_modified")
                or metadata.get("http_last_modified"),
                "http_etag": prior.get("http_etag") or metadata.get("http_etag"),
                "content_type": prior.get("content_type") or metadata.get("content_type"),
                "source_release": spec.source_release,
                "effective_start": spec.effective_start,
                "effective_end": spec.effective_end,
                "sha256": checksum,
                "bytes": path.stat().st_size,
                "description": spec.description,
                "archival_status": "local_raw_bytes_not_committed",
            }
        )
    return {
        "manifest_schema_version": 1,
        "generated_at": (existing_manifest or {}).get("generated_at", generated_at),
        "records": records,
    }


def download_sources(
    raw_dir: Path = RULEBOOK_RAW_DIR,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"
    existing_manifest = _load_manifest(manifest_path)
    metadata: dict[str, dict[str, str | None]] = {}
    for spec in SOURCES:
        destination = raw_dir / spec.relative_path
        if overwrite or not destination.is_file():
            metadata[spec.source_artifact_id] = _download_atomic(spec.source_url, destination)
    manifest = build_manifest(
        raw_dir,
        existing_manifest=existing_manifest,
        download_metadata=metadata,
    )
    if existing_manifest != manifest:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="redownload pinned URLs")
    args = parser.parse_args()
    manifest = download_sources(overwrite=args.overwrite)
    for record in manifest["records"]:
        print(f"{record['sha256']}  {record['relative_path']}")


if __name__ == "__main__":
    main()
