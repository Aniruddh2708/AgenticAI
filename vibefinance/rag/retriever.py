import math
import os
from collections import Counter

from vibefinance.config import STATE_DIR
from vibefinance.rag.ingest import ingest, tokens


class Retriever:
    """Ticker/type filtering first; BM25 offline, optional local-only embedding RRF."""
    def __init__(self, chunks=None, embeddings: bool | None = None):
        self.chunks = ingest() if chunks is None else chunks
        self.mode = "bm25"
        self.warning = None
        self.collection = None
        self.encoder = None
        if embeddings if embeddings is not None else os.getenv("VIBEFINANCE_EMBEDDINGS") == "1":
            try:
                import chromadb
                from sentence_transformers import SentenceTransformer
                self.encoder = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
                client = chromadb.PersistentClient(path=str(STATE_DIR / "chroma"))
                self.collection = client.get_or_create_collection("filings", metadata={"hnsw:space": "cosine"})
                if self.chunks:
                    self.collection.upsert(ids=[c.chunk_id for c in self.chunks],
                        embeddings=self.encoder.encode([c.text for c in self.chunks]).tolist(),
                        documents=[c.text for c in self.chunks],
                        metadatas=[{"ticker": c.ticker, "doc_type": c.doc_type} for c in self.chunks])
                self.mode = "hybrid_embedding_bm25"
            except Exception as exc:
                self.warning = f"Local embeddings unavailable ({type(exc).__name__}); BM25 fallback active."
                self.encoder = self.collection = None

    def retrieve(self, query: str, ticker: str, k: int = 4, doc_types=None):
        candidates = [c for c in self.chunks if c.ticker == ticker and
                      (doc_types is None or c.doc_type in doc_types)]
        if not candidates:
            return []
        bags = [Counter(tokens(c.text)) for c in candidates]
        average = sum(sum(b.values()) for b in bags) / len(bags)
        query_tokens = set(tokens(query))
        scores = []
        for bag in bags:
            score = 0.0
            for term in query_tokens:
                df = sum(term in b for b in bags)
                idf = math.log(1 + (len(bags) - df + .5)/(df + .5))
                tf = bag[term]
                norm = tf + 1.5 * (.25 + .75 * sum(bag.values()) / max(average, 1))
                score += idf * tf * 2.5 / norm if norm else 0
            scores.append(score)
        order = sorted(range(len(candidates)), key=lambda i: (-scores[i], candidates[i].chunk_id))
        if self.collection is not None:
            try:
                where = {"ticker": ticker}
                if doc_types:
                    where = {"$and": [where, {"doc_type": {"$in": list(doc_types)}}]}
                res = self.collection.query(query_embeddings=self.encoder.encode([query]).tolist(),
                    n_results=min(k, len(candidates)), where=where)
                ranks = {chunk_id: n for n, chunk_id in enumerate(res["ids"][0])}
                fused = {i: 1/(60 + rank + 1) + (1/(60 + ranks[candidates[i].chunk_id] + 1)
                         if candidates[i].chunk_id in ranks else 0) for rank, i in enumerate(order)}
                order = sorted(order, key=lambda i: -fused[i])
                return [(candidates[i], min(1.0, fused[i] * 30)) for i in order[:k]]
            except Exception as exc:
                self.warning = f"Embedding query unavailable ({type(exc).__name__}); BM25 fallback active."
                self.mode = "bm25"
        return [(candidates[i], scores[i]/(scores[i] + 1)) for i in order[:k] if scores[i] > 0]
