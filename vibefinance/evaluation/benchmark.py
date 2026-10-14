"""Measure real sequential and parallel pipelines on an identical workload."""

import asyncio
import hashlib
import time

import numpy as np

from vibefinance.data.market_sim import generate_market
from vibefinance.evaluation.backtest import _policy_profiles, backtest
from vibefinance.orchestrator import analyze
from vibefinance.rag.retriever import Retriever


def _output_signature(session):
    recommendation = session["recommendation"]
    return {
        "market_fingerprint": session["market_fingerprint"],
        "action": recommendation["action"], "confidence": recommendation["confidence"],
        "agents": [(out["dimension"], out["label"], out["confidence"], out["status"],
                    out["evidence"], [(c["chunk_id"], c["excerpt"]) for c in out["citations"]])
                   for out in recommendation["agent_outputs"]],
    }


async def benchmark_async(repeats=7, *, ticker="RELIANCE.NS", profile=None, retriever=None, frame=None):
    """Alternate mode order, warm both paths, preserve inputs and compare outputs.

    No artificial sleeps or agent work are added. The speedup can be below one.
    This measures the warmed compute pipeline with persistence disabled, not
    HTTP latency, cold start, embedding downloads or a production workload.
    """
    if not isinstance(repeats, int) or isinstance(repeats, bool) or not 2 <= repeats <= 100:
        raise ValueError("repeats must be an integer from 2 through 100")
    profile = profile if profile is not None else _policy_profiles(ticker)[2]
    retriever = retriever if retriever is not None else Retriever(embeddings=False)
    frame = frame if frame is not None else generate_market(ticker)
    before = hashlib.sha256(frame.to_json(date_format="iso").encode()).hexdigest()
    # A cached evaluation is used by session_metrics. Account for its warmup
    # explicitly rather than charging whichever execution mode ran first.
    await asyncio.to_thread(backtest)
    expected = None
    timings = {"parallel": [], "sequential": []}
    agent_timings = {"parallel": [], "sequential": []}
    sessions = {}
    for mode in ("parallel", "sequential"):
        session = await analyze(ticker, profile, frame=frame, retriever=retriever,
                                execution_mode=mode, persist=False)
        signature = _output_signature(session)
        if expected is None:
            expected = signature
        elif signature != expected:
            raise RuntimeError("Sequential and parallel warmup outputs differ")
    for repeat in range(repeats):
        modes = ("parallel", "sequential") if repeat % 2 == 0 else ("sequential", "parallel")
        for mode in modes:
            started = time.perf_counter()
            session = await analyze(ticker, profile, frame=frame, retriever=retriever,
                                    execution_mode=mode, persist=False)
            elapsed_ms = (time.perf_counter() - started) * 1000
            if _output_signature(session) != expected:
                raise RuntimeError("Benchmark output changed across execution modes or repetitions")
            timings[mode].append(elapsed_ms)
            agent_timings[mode].append(session["metrics"].get("agents_wall_ms",
                                       session["metrics"].get("parallel_agents_ms")))
            sessions[mode] = session
    after = hashlib.sha256(frame.to_json(date_format="iso").encode()).hexdigest()
    if before != after:
        raise RuntimeError("Benchmark market input was mutated")
    parallel = np.asarray(timings["parallel"])
    sequential = np.asarray(timings["sequential"])
    rng = np.random.default_rng(781)
    indices = rng.integers(0, repeats, (1000, repeats))
    ratios = np.median(sequential[indices], axis=1) / np.median(parallel[indices], axis=1)
    return {
        "repeats_per_mode": repeats, "warmup_runs_per_mode": 1,
        "alternating_execution_order": True, "persist": False,
        "identical_outputs": True, "unchanged_market_input": True,
        "workload": {"ticker": ticker, "user_id": profile.user_id,
            "data_mode": sessions["parallel"]["data_mode"],
            "retrieval_mode": sessions["parallel"]["retrieval_mode"],
            "market_fingerprint": expected["market_fingerprint"]},
        "wall_time_ms": timings, "agent_phase_ms": agent_timings,
        "median_wall_time_ms": {mode: float(np.median(values)) for mode, values in timings.items()},
        "measured_speedup": float(np.median(sequential) / np.median(parallel)),
        "speedup_interval": {"low": float(np.quantile(ratios, .025)),
            "high": float(np.quantile(ratios, .975)), "level": .95,
            "method": "paired bootstrap of repeated timings; describes local scheduling variability"},
        "limitations": "Real timings of identical warmed local workloads, including retrieval, agents, synthesis and metrics. "
            "Excludes cold-start setup, HTTP, persistence and network/model downloads. Small repetition count and host scheduling limit precision. "
            "Lightweight agents can run slower in parallel; a ratio below one is a slowdown, not evidence of a broken benchmark. "
            "This result does not establish production throughput or performance on live feeds."}


def benchmark(repeats=7, **kwargs):
    """Synchronous CLI convenience; asynchronous callers use benchmark_async."""
    return asyncio.run(benchmark_async(repeats, **kwargs))
