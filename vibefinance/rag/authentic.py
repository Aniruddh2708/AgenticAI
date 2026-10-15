"""Reproducible import of operator-supplied permitted authentic text sources.

This module never downloads, grants permission, infers historical availability,
or describes an operator declaration as independent source authentication.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from vibefinance.config import TICKERS


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timezone-aware source timestamp required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timezone-aware source timestamp required")
    return result.astimezone(timezone.utc)


def confined(root, relative):
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError("Source path must remain inside the manifest directory")
    path = (root/p).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Source path escapes the manifest directory")
    return path


def https_url(value):
    u = urlsplit(value)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.fragment:
        raise ValueError("Source/evidence URL must be HTTPS without credentials or fragment")
    return value


def import_corpus(manifest_path, output):
    manifest_path, output = Path(manifest_path), Path(output)
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "permitted_authentic_text_corpus":
        raise ValueError("Versioned authentic text manifest required")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 1000:
        raise ValueError("One to 1000 explicitly declared sources required")
    prepared, ids = [], set()
    now = datetime.now(timezone.utc)
    for record in sources:
        source_id = record["source_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", source_id) or source_id in ids:
            raise ValueError("Unique safe source ID required")
        ids.add(source_id)
        if record["ticker"] not in TICKERS or record["doc_type"] not in {"results", "transcript", "risk", "disclosure", "news", "reference"}:
            raise ValueError("Declared security and document type required")
        for key in ("title", "publisher", "security_identity_evidence", "timestamp_evidence"):
            if not isinstance(record[key], str) or not record[key].strip():
                raise ValueError("Source identity and timestamp evidence are required")
        source_url = https_url(record["source_url"])
        rights = record["rights"]
        if (rights["use"] != "noncommercial_research" or rights["permission"] not in
                {"explicit_license", "written_permission", "public_domain"} or
                not isinstance(rights["identifier"], str) or not rights["identifier"].strip()):
            raise ValueError("Explicit permitted-use evidence required; public accessibility alone is insufficient")
        https_url(rights["evidence_url"])
        published = timestamp(record["published_at"])
        retrieved = timestamp(record["retrieved_at"])
        # If first-availability evidence is absent, availability defaults to the
        # actual retrieval, never the earlier fiscal period or publication date.
        available = timestamp(record.get("available_at", record["retrieved_at"]))
        if not published <= available <= retrieved <= now:
            raise ValueError("Publication <= availability <= retrieval <= now required")
        if "available_at" in record and not record.get("availability_evidence"):
            raise ValueError("Historical availability needs its own source evidence")
        path = confined(manifest_path.parent, record["path"])
        if path.stat().st_size > 10_000_000:
            raise ValueError("Source text exceeds 10 MB")
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != record["sha256"]:
            raise ValueError("Source text checksum mismatch")
        if not body.decode("utf-8").strip():
            raise ValueError("Source text is empty")
        metadata = {k: record[k] for k in ("source_id", "ticker", "doc_type", "title", "publisher",
                    "security_identity_evidence", "timestamp_evidence")}
        metadata.update(source_kind="authentic", authenticity="operator_supplied_not_independently_certified",
            source_url=source_url, date=available.date().isoformat(), published_at=published.isoformat(),
            available_at=available.isoformat(), retrieved_at=retrieved.isoformat(),
            source_sha256=record["sha256"], rights=rights)
        prepared.append((metadata, body))
    # Validation completes before any output is created. Never mix authentic
    # imports into the synthetic default directory or replace existing files.
    output.mkdir(parents=True, exist_ok=False)
    documents = []
    for metadata, body in prepared:
        name = metadata["source_id"]+".md"
        encoded = json.dumps(metadata, sort_keys=True).encode()+b"\n"+body
        with (output/name).open("xb") as handle:
            handle.write(encoded)
        documents.append({"source_id": metadata["source_id"], "filename": name,
            "imported_sha256": hashlib.sha256(encoded).hexdigest(), "source_sha256": metadata["source_sha256"],
            "available_at": metadata["available_at"], "source_url": metadata["source_url"]})
    report = {"schema_version": 1, "kind": "authentic_text_import", "status": "imported_operator_supplied",
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(), "documents": documents,
        "independently_authenticated": False, "rights_certified_by_importer": False}
    with (output/"import.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return report
