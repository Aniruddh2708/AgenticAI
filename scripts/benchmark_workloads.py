"""Declared local performance workloads; no artificial delays or remote writes."""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from vibefinance.api import create_app
from vibefinance.evaluation.benchmark import benchmark_async
from vibefinance.rag.ingest import ingest
from vibefinance.rag.retriever import Retriever


async def measure(repeats):
    results = {}
    for ticker in ("RELIANCE.NS", "TCS.NS", "ITC.NS", "HDFCBANK.NS"):
        results[ticker] = await benchmark_async(repeats, ticker=ticker)
    chunks = ingest()
    expanded = [replace(c, source_id=f"load_fixture_{n}_{c.source_id}",
                        chunk_id=f"load_fixture_{n}_{c.chunk_id}") for n in range(20) for c in chunks]
    results["synthetic_20x_corpus"] = await benchmark_async(repeats, retriever=Retriever(expanded, embeddings=False))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Performance evidence already exists; choose a new report")
    workloads = asyncio.run(measure(args.repeats))
    with tempfile.TemporaryDirectory(prefix="vf-perf-") as temp:
        with TestClient(create_app(Path(temp)/"state.sqlite3")) as client:
            client.post("/analyze", json={"ticker": "RELIANCE.NS"}).raise_for_status()
            times, signatures = [], []
            for _ in range(args.repeats):
                started = time.perf_counter()
                response = client.post("/analyze", json={"ticker": "RELIANCE.NS"})
                response.raise_for_status()
                session = response.json()
                assert session["persistence"]["status"] == "saved"
                times.append((time.perf_counter()-started)*1000)
                signatures.append(session["market_fingerprint"])
            assert len(set(signatures)) == 1
            comparison = client.post("/compare", json={"ticker": "RELIANCE.NS"}).json()
            assert len({s["market_fingerprint"] for s in comparison}) == 1
            actions = {s["recommendation"]["user_id"]: s["recommendation"]["action"] for s in comparison}
            assert actions == {"meera": "REDUCE", "arjun": "ACCUMULATE", "rohan": "BUY"}
    result = {"kind": "local_workload_performance", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "workloads": workloads, "api_asgi_sqlite": {"samples_ms": times,
            "median_ms": statistics.median(times), "persistence_verified": True,
            "scope": "in-process HTTP client plus real SQLite; excludes network and production load"},
        "identical_market_profile_actions": actions,
        "limitations": "Warm local timings, synthetic inputs and corpus load fixture. No throughput, neural retrieval or hosted performance claim."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps({n: r["measured_speedup"] for n, r in workloads.items()}, indent=2))


if __name__ == "__main__":
    main()
