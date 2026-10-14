import sys
from types import SimpleNamespace

from vibefinance.agents.base import Citation
from vibefinance.rag.ingest import ingest
from vibefinance.rag.retriever import Retriever
from vibefinance.rag.validator import validate_citations


def test_ticker_filter_and_missing_filing(retriever):
    chunks = ingest()
    assert 15 <= len({c.source_id for c in chunks}) <= 30
    results = retriever.retrieve("guidance risk cut", "TCS.NS", 4, {"transcript", "risk"})
    assert results and all(c.ticker == "TCS.NS" for c, _ in results)
    assert retriever.retrieve("guidance", "HDFCBANK.NS", 4, {"transcript", "risk", "disclosure", "results"}) == []


def test_invented_source_and_altered_passage_rejected(retriever):
    chunk, score = retriever.retrieve("growth", "RELIANCE.NS", 1)[0]
    correct = chunk.citation(score)
    allowed = {correct.chunk_id: correct}
    fake = correct.model_copy(update={"source_id": "fabricated"})
    altered = correct.model_copy(update={"excerpt": "made up guidance"})
    unknown = Citation(source_id="ghost", doc_title="ghost", chunk_id="ghost", excerpt="ghost", score=1)
    valid, rejected = validate_citations([correct, fake, altered, unknown], allowed)
    assert valid == [correct] and len(rejected) == 3


def test_embedding_failure_uses_bm25(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("no local model")
    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=unavailable))
    retriever = Retriever(embeddings=True)
    assert retriever.mode == "bm25" and retriever.warning
    assert retriever.retrieve("growth", "RELIANCE.NS")
