"""Real optional integration check; unavailable models return an honest nonzero status.

Run in the optional environment. Application retrieval remains local-only; this
script's explicit --download flag provisions the pinned model over verified TLS.
Generated evidence and model/index files stay under ignored .runtime by default.
"""
import argparse
import importlib.metadata
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from vibefinance.rag.retriever import MODEL_NAME, MODEL_REVISION, Retriever


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Explicitly download the pinned MiniLM model")
    parser.add_argument("--state-dir", type=Path, default=REPO / ".runtime/embedding-check")
    parser.add_argument("--model-cache", type=Path, default=REPO / ".runtime/huggingface/hub")
    parser.add_argument("--output", type=Path, default=REPO / ".runtime/embedding-integration.json")
    args = parser.parse_args()
    evidence = {"model": MODEL_NAME, "revision": MODEL_REVISION, "real_model_verified": False,
                "package_versions": {}, "download_attempted": args.download}
    for name in ("torch", "chromadb", "sentence-transformers", "transformers"):
        try:
            evidence["package_versions"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            evidence["package_versions"][name] = "not installed"
    # Check the real vector-store package even when the separate model download
    # prerequisite is missing. Fixture vectors do not count as neural verification.
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(args.state_dir / "store-fixture-check"),
                                          settings=chromadb.Settings(anonymized_telemetry=False))
        collection = client.get_or_create_collection("integration_fixture",
                                                    metadata={"hnsw:space": "cosine"})
        collection.upsert(ids=["eligible", "future", "other"],
                          embeddings=[[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
                          metadatas=[{"ticker": "TCS.NS", "available_at": 1},
                                     {"ticker": "TCS.NS", "available_at": 3},
                                     {"ticker": "ITC.NS", "available_at": 1}])
        result = collection.query(query_embeddings=[[1.0, 0.0]], n_results=1,
                                  where={"$and": [{"ticker": "TCS.NS"},
                                                  {"available_at": {"$lte": 2}}]})
        assert result["ids"] == [["eligible"]]
        evidence["real_chroma_store_with_fixture_vectors_verified"] = True
    except Exception as exc:
        evidence["real_chroma_store_with_fixture_vectors_verified"] = False
        evidence["chroma_store_check"] = f"Unavailable ({type(exc).__name__})"
    model_path = os.getenv("VIBEFINANCE_EMBEDDING_MODEL_PATH")
    try:
        from huggingface_hub import snapshot_download
        model_path = snapshot_download(
            MODEL_NAME, revision=MODEL_REVISION, cache_dir=str(args.model_cache),
            local_files_only=not args.download,
            allow_patterns=["*.json", "vocab.txt", "model.safetensors", "1_Pooling/config.json"],
        ) if not model_path else model_path
    except Exception as exc:
        evidence["model_provisioning"] = f"Unavailable ({type(exc).__name__}); local-only fallback checked."
    retriever = Retriever(embeddings=True, state_dir=args.state_dir, model_path=model_path)
    results = retriever.retrieve("operating profit guidance growth risk", "RELIANCE.NS", 4,
                                 {"results", "transcript", "risk"})
    evidence.update(mode=retriever.mode, warnings=retriever.warnings,
                    result_ids=[chunk.chunk_id for chunk, _ in results],
                    fallback_returned_results=bool(results))
    if retriever.mode == "hybrid_embedding_bm25":
        assert results and all(c.ticker == "RELIANCE.NS" for c, _ in results)
        assert retriever.retrieve("profit", "HDFCBANK.NS", doc_types={"results", "transcript"}) == []
        assert retriever.retrieve("profit", "RELIANCE.NS", as_of="2026-09-24") == []
        dated = retriever.retrieve("profit guidance", "RELIANCE.NS", as_of="2026-09-25")
        assert dated and all(c.date <= "2026-09-25" for c, _ in dated)
        reopened = Retriever(embeddings=True, state_dir=args.state_dir, model_path=model_path)
        assert reopened.mode == "hybrid_embedding_bm25"
        assert reopened.collection.name == retriever.collection.name
        assert reopened.collection.count() == len(reopened.chunks)
        evidence.update(real_model_verified=True, checks=["hybrid query", "ticker/type filter",
                       "point-in-time date cutoff", "persistent index reopen"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["real_model_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
