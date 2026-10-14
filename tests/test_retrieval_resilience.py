import json
import sys
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from vibefinance.rag.ingest import Chunk, ingest
from vibefinance.rag.retriever import Retriever


def document(path, source_id="valid", body="Revenue growth improved profit.", **updates):
    metadata = {"source_id": source_id, "ticker": "TCS.NS", "doc_type": "results",
                "date": "2026-09-25", "title": "Synthetic results"}
    metadata.update(updates)
    path.write_text(json.dumps(metadata) + "\n" + body, encoding="utf-8")


def test_invalid_documents_skipped_with_explicit_warnings_and_full_body(tmp_path):
    document(tmp_path / "a_valid.md", body="Revenue growth improved profit.\nMargins declined.")
    document(tmp_path / "b_duplicate.md")
    document(tmp_path / "c_bad_date.md", source_id="bad_date", date="2026-99-01")
    document(tmp_path / "d_empty.md", source_id="empty", body="")
    document(tmp_path / "e_bad_type.md", source_id=None)
    (tmp_path / "f_bad_json.md").write_text("{invalid}\ncontent")
    (tmp_path / "g_missing_header.md").write_text("plain document")
    warnings = []
    chunks = ingest(tmp_path, size=4, overlap=1, warnings=warnings)
    assert chunks and {chunk.source_id for chunk in chunks} == {"valid"}
    assert len(warnings) == 6
    assert all("Skipped corpus file" in warning for warning in warnings)
    assert all(chunk.document_text == "Revenue growth improved profit.\nMargins declined." for chunk in chunks)
    assert all(chunk.text in chunk.document_text for chunk in chunks)
    assert "{invalid}" not in " ".join(warnings)


def test_missing_corpus_reports_degraded_empty_registry(tmp_path):
    retriever = Retriever(corpus_path=tmp_path / "missing", embeddings=False)
    assert retriever.retrieve("profit", "TCS.NS") == []
    assert retriever.warning and "no document evidence" in retriever.warning


def test_extra_metadata_is_compatible_without_constructing_untrusted_fields(tmp_path):
    document(tmp_path / "valid.md", publisher="demo", chunk_id="attempted-override")
    chunks = ingest(tmp_path)
    assert len(chunks) == 1 and chunks[0].chunk_id == "valid:0"


def sample_chunks():
    return [Chunk("old", "TCS.NS", "results", "2026-01-01", "Old", "old:0", "profit growth"),
            Chunk("future", "TCS.NS", "results", "2026-12-01", "Future", "future:0", "profit growth"),
            Chunk("other", "ITC.NS", "results", "2026-01-01", "Other", "other:0", "profit growth")]


def test_bm25_historical_cutoff_and_empty_type_filter():
    retriever = Retriever(sample_chunks(), embeddings=False)
    assert [c.source_id for c, _ in retriever.retrieve("profit", "TCS.NS", as_of="2026-06-01")] == ["old"]
    assert retriever.retrieve("profit", "TCS.NS", as_of=date(2025, 12, 31)) == []
    assert retriever.retrieve("profit", "TCS.NS", doc_types=set()) == []
    assert retriever.retrieve("profit", "TCS.NS", k=0) == []
    assert retriever.retrieve("123 ?!", "TCS.NS") == []
    with pytest.raises(ValueError):
        retriever.retrieve("profit", "TCS.NS", as_of="not-a-date")
    with pytest.raises(ValueError):
        retriever.retrieve("profit", "TCS.NS", as_of="20260601")
    with pytest.raises(ValueError):
        retriever.retrieve("profit", "TCS.NS", k=-1)


class Encoded(list):
    def tolist(self):
        return self


class Encoder:
    def __init__(self, *args, **kwargs):
        self.arguments = kwargs

    def encode(self, texts):
        return Encoded([[1.0, 0.0] for _ in texts])


class Collection:
    def __init__(self, name):
        self.name = name
        self.entries = {"stale:0": {"ticker": "TCS.NS", "doc_type": "results", "available_at": 0}}
        self.deleted = []
        self.query_calls = 0
        self.last_where = None

    def get(self, **kwargs):
        return {"ids": list(self.entries)}

    def upsert(self, ids, metadatas, **kwargs):
        self.entries.update(zip(ids, metadatas))

    def delete(self, ids):
        self.deleted.extend(ids)
        for key in ids:
            del self.entries[key]

    def query(self, where, **kwargs):
        self.query_calls += 1
        self.last_where = where
        # Deliberately return an out-of-cutoff and an unknown ID to verify the
        # final candidate check independently of the vector store's filters.
        return {"ids": [["future:0", "ghost:0", "old:0"]]}


def mock_embeddings(monkeypatch):
    collections = {}
    paths = []

    class Client:
        def __init__(self, path, **kwargs):
            paths.append(path)

        def get_or_create_collection(self, name, **kwargs):
            return collections.setdefault(name, Collection(name))

    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace(PersistentClient=Client,
                                                                Settings=lambda **kwargs: kwargs))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Encoder))
    return collections, paths


def test_hybrid_initialization_reconciles_only_own_collection_and_reuses_it(monkeypatch, tmp_path):
    collections, paths = mock_embeddings(monkeypatch)
    retriever = Retriever(sample_chunks(), embeddings=True, state_dir=tmp_path)
    assert retriever.mode == "hybrid_embedding_bm25"
    assert paths == [str(tmp_path / "chroma")]
    assert retriever.encoder.arguments["local_files_only"] is True
    assert retriever.collection.deleted == ["stale:0"]
    first = retriever.collection
    reopened = Retriever(sample_chunks(), embeddings=True, state_dir=tmp_path)
    assert reopened.collection is first
    modified = [replace(chunk, text="Different profit text") for chunk in sample_chunks()]
    changed = Retriever(modified, embeddings=True, state_dir=tmp_path)
    assert changed.collection is not first
    assert set(first.entries) == {chunk.chunk_id for chunk in sample_chunks()}
    assert len(collections) == 2


def test_hybrid_cutoff_filter_does_not_admit_future_or_unknown_ids(monkeypatch, tmp_path):
    mock_embeddings(monkeypatch)
    retriever = Retriever(sample_chunks(), embeddings=True, state_dir=tmp_path)
    results = retriever.retrieve("profit", "TCS.NS", doc_types={"results"}, as_of="2026-06-01")
    assert [chunk.source_id for chunk, _ in results] == ["old"]
    assert retriever.collection.last_where == {"$and": [
        {"ticker": "TCS.NS"}, {"doc_type": {"$in": ["results"]}},
        {"available_at": {"$lte": date(2026, 6, 1).toordinal()}}]}


def test_failed_embedding_query_disables_backend_after_single_attempt(monkeypatch, tmp_path):
    mock_embeddings(monkeypatch)
    retriever = Retriever(sample_chunks(), embeddings=True, state_dir=tmp_path)
    collection = retriever.collection

    def unavailable(**kwargs):
        collection.query_calls += 1
        raise RuntimeError("index not readable")

    collection.query = unavailable
    first = retriever.retrieve("profit", "TCS.NS", as_of="2026-06-01")
    second = retriever.retrieve("profit", "TCS.NS", as_of="2026-06-01")
    assert first == second and first
    assert collection.query_calls == 1
    assert retriever.mode == "bm25" and retriever.encoder is None and retriever.collection is None
    assert "Embedding query unavailable" in retriever.warning


def test_index_initialization_failure_falls_back_offline(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Encoder))

    def denied(**kwargs):
        raise PermissionError("state is read-only")

    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace(PersistentClient=denied,
                                                                Settings=lambda **kwargs: kwargs))
    retriever = Retriever(sample_chunks(), embeddings=True, state_dir=tmp_path)
    assert retriever.mode == "bm25" and "PermissionError" in retriever.warning
    assert retriever.retrieve("profit", "TCS.NS", as_of="2026-06-01")
