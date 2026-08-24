"""Download and inventory the authoritative CMS NHEA v0.1 source files."""

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

from reconciliation_healthcare.paths import MANIFEST_PATH, RAW_DIR


SOURCE_PAGE = (
    "https://www.cms.gov/data-research/statistics-trends-and-reports/"
    "national-health-expenditure-data/historical"
)


@dataclass(frozen=True)
class SourceSpec:
    dataset: str
    url: str
    coverage: str
    description: str

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]


SOURCES = (
    SourceSpec(
        dataset="NHE Tables",
        url="https://www.cms.gov/files/zip/nhe-tables.zip",
        coverage="1960-2024 (table-dependent)",
        description="Detailed National Health Expenditure Accounts tables.",
    ),
    SourceSpec(
        dataset="NHE by type of service and source of funds",
        url=(
            "https://www.cms.gov/files/zip/"
            "national-health-expenditures-type-service-source-funds-cy-1960-2024.zip"
        ),
        coverage="1960-2024",
        description=(
            "National health expenditures by type of service and source of funds; "
            "principal Claims Ledger source."
        ),
    ),
    SourceSpec(
        dataset="NHE Summary including share of GDP",
        url=(
            "https://www.cms.gov/files/zip/"
            "nhe-summary-including-share-gdp-cy-1960-2024.zip"
        ),
        coverage="1960-2024",
        description="Summary measures including NHE, population, per-capita spending, and GDP share.",
    ),
    SourceSpec(
        dataset="Definitions, Sources, and Methods",
        url="https://www.cms.gov/files/document/definitions-sources-methods.pdf",
        coverage="1960-2024 methodology",
        description="NHEA Methodology Paper, 2024 vintage; last updated January 2026.",
    ),
    SourceSpec(
        dataset="Quick Definitions for NHEA Categories",
        url=(
            "https://www.cms.gov/files/document/"
            "quick-definitions-national-health-expenditures-accounts-nhea-categories.pdf"
        ),
        coverage="2024 NHEA vintage",
        description="Concise CMS definitions for NHEA service and source-of-funds categories.",
    ),
    SourceSpec(
        dataset="Summary of 2024 benchmark changes",
        url="https://www.cms.gov/files/document/summary-benchmark-changes-2024.pdf",
        coverage="2024 comprehensive revision",
        description="CMS summary of historical-series changes in the 2024 comprehensive revision.",
    ),
    SourceSpec(
        dataset="Accounting for Federal COVID Expenditures",
        url=(
            "https://www.cms.gov/files/document/"
            "accounting-federal-covid-expenditures-national-health-expenditure-accounts.pdf"
        ),
        coverage="COVID-19 public health emergency",
        description="CMS explanation of federal COVID expenditure treatment in the NHEA.",
    ),
)


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
        headers={"User-Agent": "reconciliation-healthcare/0.1 (CMS NHEA archival download)"},
    )
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        downloaded_at = datetime.now(timezone.utc).isoformat()
        with urllib.request.urlopen(request, timeout=120) as response:
            response_metadata = {
                "downloaded_at": downloaded_at,
                "http_last_modified": response.headers.get("Last-Modified"),
                "http_etag": response.headers.get("ETag"),
                "content_type": response.headers.get_content_type(),
            }
            with temporary_path.open("wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
        temporary_path.replace(destination)
        return response_metadata
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def build_manifest(
    raw_dir: Path = RAW_DIR,
    *,
    download_metadata: dict[str, dict[str, str | None]] | None = None,
    existing_manifest: dict[str, object] | None = None,
) -> dict[str, object]:
    generated_at = datetime.now(timezone.utc).isoformat()
    download_metadata = download_metadata or {}
    existing_records = {
        record["original_filename"]: record
        for record in (existing_manifest or {}).get("records", [])
    }
    records: list[dict[str, object]] = []
    for spec in SOURCES:
        path = raw_dir / spec.filename
        if not path.is_file():
            raise FileNotFoundError(f"Required CMS source is missing: {path}")
        checksum = sha256_file(path)
        prior = existing_records.get(spec.filename, {})
        same_prior_file = prior.get("sha256") == checksum
        metadata = download_metadata.get(spec.filename, {})
        record = {
            "source_authority": "Centers for Medicare & Medicaid Services",
            "dataset": spec.dataset,
            "description": spec.description,
            "original_filename": spec.filename,
            "downloaded_at": (prior.get("downloaded_at") if same_prior_file else None)
            or metadata.get("downloaded_at")
            or generated_at,
            "source_page": SOURCE_PAGE,
            "source_url": spec.url,
            "sha256": checksum,
            "bytes": path.stat().st_size,
            "coverage": spec.coverage,
            "source_release": "2024 NHEA vintage; CMS page updated 2026-01-14",
            "http_last_modified": metadata.get("http_last_modified")
            or (prior.get("http_last_modified") if same_prior_file else None),
            "http_etag": metadata.get("http_etag")
            or (prior.get("http_etag") if same_prior_file else None),
            "content_type": metadata.get("content_type")
            or (prior.get("content_type") if same_prior_file else None),
        }
        records.append(record)
    return {
        "manifest_schema_version": 1,
        "generated_at": generated_at,
        "records": records,
    }


def download_sources(raw_dir: Path = RAW_DIR, *, overwrite: bool = False) -> dict[str, object]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"
    existing_manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else None
    )
    download_metadata: dict[str, dict[str, str | None]] = {}
    for spec in SOURCES:
        destination = raw_dir / spec.filename
        if overwrite or not destination.exists():
            download_metadata[spec.filename] = _download_atomic(spec.url, destination)
    manifest = build_manifest(
        raw_dir,
        download_metadata=download_metadata,
        existing_manifest=existing_manifest,
    )
    if existing_manifest is not None and (
        existing_manifest.get("manifest_schema_version")
        == manifest["manifest_schema_version"]
        and existing_manifest.get("records") == manifest["records"]
    ):
        return existing_manifest
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="redownload existing source files")
    args = parser.parse_args()
    manifest = download_sources(overwrite=args.overwrite)
    for record in manifest["records"]:
        print(f"{record['sha256']}  {record['original_filename']}")


if __name__ == "__main__":
    main()
