from __future__ import annotations

from app.schemas.models import CasePackage, CasePackageInput
from app.services.canonical_json import canonical_sha256


def ingest_case_package(value: CasePackageInput) -> CasePackage:
    records = []
    for source in value.records:
        record = source.model_copy(deep=True)
        record.ingestion_hash = canonical_sha256(
            record.model_dump(mode="python", exclude={"ingestion_hash"})
        )
        records.append(record)
    package_payload = {
        "package_id": value.package_id,
        "incident": value.incident,
        "records": records,
        "schema_version": "threadline-case-package/1.0.0",
        "synthetic_only": True,
    }
    return CasePackage(
        package_id=value.package_id,
        incident=value.incident,
        records=records,
        package_hash=canonical_sha256(package_payload),
    )
