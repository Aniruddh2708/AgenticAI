import json
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vibefinance.agents.base import Citation
from vibefinance.config import ROOT


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


@dataclass(frozen=True)
class Chunk:
    source_id: str
    ticker: str
    doc_type: str
    date: str
    title: str
    chunk_id: str
    text: str
    document_text: str = ""
    source_kind: str = "synthetic"
    source_url: str = ""
    source_sha256: str = ""
    published_at: str = ""
    available_at: str = ""
    span_start: int | None = None
    span_end: int | None = None

    def citation(self, score: float = 1.0) -> Citation:
        return Citation(source_id=self.source_id, doc_title=self.title, chunk_id=self.chunk_id,
                        excerpt=self.text, score=score, date=self.date,
                        **{key: getattr(self, key) for key in ("source_kind", "source_url", "source_sha256",
                           "published_at", "available_at", "span_start", "span_end")})


def ingest(path: Path | None = None, size: int = 120, overlap: int = 20,
           *, warnings: list[str] | None = None) -> list[Chunk]:
    """Load valid local documents, reporting skipped files without their contents.

    ``warnings`` is additive to the historic list return value. Metadata dates
    represent availability dates, not the fiscal period described in a filing.
    """
    if not 0 <= overlap < size:
        raise ValueError("Chunk overlap must be less than size")
    result = []
    source_ids = set()
    directory = Path(path) if path is not None else ROOT / "data/corpus"

    def report(message: str) -> None:
        if warnings is not None:
            warnings.append(message)
        logging.getLogger(__name__).warning(message)

    try:
        if not directory.is_dir():
            report("Corpus directory unavailable; no document evidence loaded.")
            return []
        files = sorted(directory.glob("*.md"))
    except OSError as exc:
        report(f"Corpus listing unavailable ({type(exc).__name__}); no document evidence loaded.")
        return []
    fields = {"source_id", "ticker", "doc_type", "date", "title"}
    for file in files:
        try:
            header, body = file.read_bytes().decode("utf-8").split("\n", 1)
            raw_metadata = json.loads(header)
            if not isinstance(raw_metadata, dict) or not fields <= raw_metadata.keys():
                raise ValueError("Missing document metadata")
            metadata = {key: raw_metadata[key] for key in fields}
            if any(not isinstance(value, str) or not value.strip() for value in metadata.values()):
                raise ValueError("Metadata must contain nonempty strings")
            if date.fromisoformat(metadata["date"]).isoformat() != metadata["date"]:
                raise ValueError("Availability date must use YYYY-MM-DD")
            if metadata["source_id"] in source_ids:
                raise ValueError("Duplicate source ID")
            if not body.strip():
                raise ValueError("Document body is empty")
            kind = raw_metadata.get("source_kind", "synthetic")
            if kind not in {"synthetic", "authentic"}:
                raise ValueError("Unknown source kind")
            metadata["source_kind"] = kind
            if kind == "synthetic":
                # Preserve the legacy text-loader contract across Windows
                # checkouts. Authentic imports below retain original bytes and
                # character offsets, including CRLF, for hash/span provenance.
                body = body.replace("\r\n", "\n").replace("\r", "\n")
            if kind == "authentic":
                from vibefinance.rag.authentic import https_url, timestamp
                if hashlib.sha256(body.encode()).hexdigest() != raw_metadata.get("source_sha256"):
                    raise ValueError("Authentic source body hash mismatch")
                published = timestamp(raw_metadata["published_at"])
                available = timestamp(raw_metadata["available_at"])
                if available < published or available.date().isoformat() != metadata["date"]:
                    raise ValueError("Invalid source availability")
                https_url(raw_metadata["source_url"])
                metadata.update({key: raw_metadata[key] for key in ("source_url", "source_sha256", "published_at", "available_at")})
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            report(f"Skipped corpus file {file.name!r} ({type(exc).__name__}); invalid or unreadable document.")
            continue
        source_ids.add(metadata["source_id"])
        # Keep exact character spans so citations highlight inside the original
        # document even when it contains newlines or repeated whitespace.
        words = list(re.finditer(r"\S+", body))
        for n, start in enumerate(range(0, len(words), size - overlap)):
            end = min(start + size, len(words))
            text = body[words[start].start():words[end - 1].end()]
            result.append(Chunk(**metadata, chunk_id=f"{metadata['source_id']}:{n}",
                                text=text, document_text=body,
                                span_start=words[start].start(), span_end=words[end-1].end()))
            if start + size >= len(words):
                break
    return result
