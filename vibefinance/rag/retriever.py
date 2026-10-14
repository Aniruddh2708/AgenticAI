import hashlib
import math
import os
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from vibefinance.config import STATE_DIR
from vibefinance.rag.ingest import ingest, tokens


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"


class Retriever:
    """Ticker/type/date filtering, BM25 and optional local-only embedding RRF.

    Model downloads are separate from application startup. A failed optional
    backend is disabled for this instance; BM25 needs no models or network.
    """
    def __init__(self, chunks=None, embeddings: bool | None = None, *,
                 state_dir: Path | str | None = None, corpus_path: Path | None = None,
                 model_path: Path | str | None = None):
        self.warnings: list[str] = []
        corpus_path = corpus_path if corpus_path is not None else os.getenv("VIBEFINANCE_CORPUS_PATH")
        self.chunks = ingest(corpus_path, warnings=self.warnings) if chunks is None else list(chunks)
        self.mode = "bm25"
        self.collection = None
        self.encoder = None
        self.client = None
        self.state_dir = Path(state_dir) if state_dir is not None else STATE_DIR
        requested = embeddings if embeddings is not None else os.getenv("VIBEFINANCE_EMBEDDINGS") == "1"
        if requested:
            try:
                import chromadb
                from sentence_transformers import SentenceTransformer
                configured_model = model_path or os.getenv("VIBEFINANCE_EMBEDDING_MODEL_PATH")
                self.encoder = SentenceTransformer(
                    str(configured_model) if configured_model else MODEL_NAME,
                    **({} if configured_model else {"revision": MODEL_REVISION}),
                    local_files_only=True, device="cpu",
                )
                self.client = chromadb.PersistentClient(
                    path=str(self.state_dir / "chroma"),
                    settings=chromadb.Settings(anonymized_telemetry=False))
                # Content-addressed collections prevent stale/deleted passages
                # leaking between corpus versions without deleting another
                # instance's active index. Old indexes may be cleaned separately.
                corpus = "\n".join("\x1f".join((c.chunk_id, c.ticker, c.doc_type, c.date, c.text))
                                   for c in sorted(self.chunks, key=lambda chunk: chunk.chunk_id))
                model_identity = str(configured_model) if configured_model else MODEL_NAME + "@" + MODEL_REVISION
                identity = hashlib.sha256((model_identity + "\n" + corpus).encode()).hexdigest()[:20]
                self.collection = self.client.get_or_create_collection(
                    "filings_" + identity, metadata={"hnsw:space": "cosine"})
                if self.chunks:
                    indexed = set(self.collection.get(include=[])["ids"])
                    expected = {chunk.chunk_id for chunk in self.chunks}
                    missing = [chunk for chunk in self.chunks if chunk.chunk_id not in indexed]
                    if missing:
                        self.collection.upsert(ids=[c.chunk_id for c in missing],
                            embeddings=self.encoder.encode([c.text for c in missing]).tolist(),
                            documents=[c.text for c in missing],
                            metadatas=[{"ticker": c.ticker, "doc_type": c.doc_type,
                                        "available_at": date.fromisoformat(c.date).toordinal()}
                                       for c in missing])
                    # Reconcile only this exact corpus's collection, never an
                    # older shared collection or another corpus's collection.
                    stale = sorted(indexed - expected)
                    if stale:
                        self.collection.delete(ids=stale)
                self.mode = "hybrid_embedding_bm25"
            except Exception as exc:
                self._disable_embeddings("Local embeddings", exc)

    @property
    def warning(self):
        return " ".join(self.warnings) or None

    def _disable_embeddings(self, operation: str, exc: Exception) -> None:
        self.warnings.append(f"{operation} unavailable ({type(exc).__name__}); BM25 fallback active.")
        self.encoder = self.collection = None
        self.mode = "bm25"

    def retrieve(self, query: str, ticker: str, k: int = 4, doc_types=None, *,
                 as_of: date | str | None = None):
        """Retrieve documents available on/before an optional historical cutoff."""
        if isinstance(k, bool) or not isinstance(k, int) or k < 0:
            raise ValueError("k must be a nonnegative integer")
        if k == 0:
            return []
        if isinstance(as_of, datetime):
            cutoff = as_of.date()
        else:
            cutoff = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
            if isinstance(as_of, str) and cutoff.isoformat() != as_of:
                raise ValueError("as_of must use YYYY-MM-DD")
        if cutoff is not None and not isinstance(cutoff, date):
            raise ValueError("as_of must be a date or YYYY-MM-DD")
        doc_types = set(doc_types) if doc_types is not None else None
        candidates = [c for c in self.chunks if c.ticker == ticker and
                      (doc_types is None or c.doc_type in doc_types) and
                      (cutoff is None or date.fromisoformat(c.date) <= cutoff)]
        if not candidates or not tokens(query):
            return []
        bags = [Counter(tokens(c.text)) for c in candidates]
        average = sum(sum(b.values()) for b in bags) / len(bags)
        query_tokens = set(tokens(query))
        document_frequency = {term: sum(term in bag for bag in bags) for term in query_tokens}
        scores = []
        for bag in bags:
            score = 0.0
            for term in query_tokens:
                df = document_frequency[term]
                idf = math.log(1 + (len(bags) - df + .5)/(df + .5))
                tf = bag[term]
                norm = tf + 1.5 * (.25 + .75 * sum(bag.values()) / max(average, 1))
                score += idf * tf * 2.5 / norm if norm else 0
            scores.append(score)
        order = sorted(range(len(candidates)), key=lambda i: (-scores[i], candidates[i].chunk_id))
        if self.collection is not None:
            try:
                filters = [{"ticker": ticker}]
                if doc_types:
                    filters.append({"doc_type": {"$in": sorted(doc_types)}})
                if cutoff is not None:
                    filters.append({"available_at": {"$lte": cutoff.toordinal()}})
                where = filters[0] if len(filters) == 1 else {"$and": filters}
                res = self.collection.query(query_embeddings=self.encoder.encode([query]).tolist(),
                    n_results=min(k, len(candidates)), where=where)
                valid_ids = {c.chunk_id for c in candidates}
                ranks = {chunk_id: n for n, chunk_id in enumerate(res["ids"][0]) if chunk_id in valid_ids}
                fused = {i: (1/(60 + rank + 1) if scores[i] > 0 else 0) + (1/(60 + ranks[candidates[i].chunk_id] + 1)
                         if candidates[i].chunk_id in ranks else 0) for rank, i in enumerate(order)}
                order = sorted(order, key=lambda i: (-fused[i], candidates[i].chunk_id))
                # RRF ranking score, not a probability of correctness.
                return [(candidates[i], min(1.0, fused[i] * 30)) for i in order[:k] if fused[i] > 0]
            except Exception as exc:
                self._disable_embeddings("Embedding query", exc)
        return [(candidates[i], scores[i]/(scores[i] + 1)) for i in order[:k] if scores[i] > 0]
