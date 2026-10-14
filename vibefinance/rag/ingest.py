import json
import re
from dataclasses import dataclass
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

    def citation(self, score: float = 1.0) -> Citation:
        return Citation(source_id=self.source_id, doc_title=self.title, chunk_id=self.chunk_id,
                        excerpt=self.text, score=score, date=self.date)


def ingest(path: Path | None = None, size: int = 120, overlap: int = 20) -> list[Chunk]:
    if not 0 <= overlap < size:
        raise ValueError("Chunk overlap must be less than size")
    result = []
    source_ids = set()
    for file in sorted((path or ROOT / "data/corpus").glob("*.md")):
        header, body = file.read_text().split("\n", 1)
        metadata = json.loads(header)
        if metadata["source_id"] in source_ids:
            raise ValueError("Duplicate source ID")
        source_ids.add(metadata["source_id"])
        words = body.split()
        for n, start in enumerate(range(0, len(words), size - overlap)):
            text = " ".join(words[start:start + size])
            result.append(Chunk(**metadata, chunk_id=f"{metadata['source_id']}:{n}", text=text))
            if start + size >= len(words):
                break
    return result
