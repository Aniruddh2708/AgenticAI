import asyncio
import hashlib
import time
import uuid

from vibefinance.agents import filings_agent, momentum_agent, risk_agent, sentiment_agent, volume_agent
from vibefinance.agents.base import Citation, run_agent
from vibefinance.config import AGENT_TIMEOUT_SECONDS, TICKERS
from vibefinance.data.market_live import load_market
from vibefinance.data.market_sim import indicators
from vibefinance.evaluation.metrics import session_metrics
from vibefinance.profiles.store import Store
from vibefinance.rag.retriever import Retriever
from vibefinance.rag.validator import validate_citations
from vibefinance.synthesis.synthesizer import synthesize


async def analyze(ticker, profile, *, store=None, retriever=None, sentiment_outage=False,
                  missing_filing=False, live=False, frame=None, timeout=AGENT_TIMEOUT_SECONDS,
                  overrides=None, persist=True):
    if ticker not in TICKERS:
        raise ValueError("Unsupported ticker")
    start = time.perf_counter()
    trace = []
    warnings = []
    if frame is None:
        frame, warning = await asyncio.to_thread(load_market, ticker, live)
        if warning:
            warnings.append(warning)
    mode = frame.attrs.get("mode", "provided")
    market_id = frame.attrs.get("source_id", f"market:{ticker}:provided")
    try:
        stats = indicators(frame)
        date = str(frame.date.iloc[-1].date()) if "date" in frame else "provided"
        market_text = f"{ticker}: {len(frame)} OHLCV sessions, as of {date}. " + "; ".join(f"{k}={v:.6f}" for k, v in stats.items())
    except (ValueError, TypeError, AttributeError, KeyError):
        stats = {}
        date = "unavailable"
        market_text = "Invalid or insufficient market data; no computed market claims."
        warnings.append("Market input invalid; price and volume agents will report failures.")
    market_cite = Citation(source_id=market_id, doc_title=f"{ticker} OHLCV [{mode.upper()}]",
                          chunk_id=f"{market_id}:snapshot", excerpt=market_text, score=1, date=date)
    profile_id = f"profile:{profile.user_id}"
    profile_cite = Citation(source_id=profile_id, doc_title=f"{profile.name} — profile snapshot",
        chunk_id=f"{profile_id}:snapshot", excerpt=profile.model_dump_json(), score=1, date="session snapshot")
    trace.append({"step": "Market ingest", "detail": f"{mode} · {len(frame)} sessions · {ticker}"})
    if retriever is None:
        retriever = await asyncio.to_thread(Retriever)
    filings = [] if missing_filing else await asyncio.to_thread(retriever.retrieve,
        "growth profit guidance risk decline weak cut attrition supportive", ticker, 4,
        {"transcript", "results", "disclosure", "risk"})
    news = await asyncio.to_thread(retriever.retrieve, "growth profit weak guidance", ticker, 3, {"news"})
    if retriever.warning:
        warnings.append(retriever.warning)
    trace.append({"step": "Retrieval", "detail": f"{retriever.mode}: {len(filings)} filing / {len(news)} news chunks; ticker metadata filter applied."})
    allowed = {c.chunk_id: c for c in [market_cite, profile_cite] + [c.citation(s) for c, s in filings + news]}
    functions = {"momentum": lambda: momentum_agent.analyze(ticker, frame, market_cite),
        "volume": lambda: volume_agent.analyze(ticker, frame, market_cite),
        "sentiment": lambda: sentiment_agent.analyze(ticker, news, sentiment_outage or ticker == "ITC.NS"),
        "filings": lambda: filings_agent.analyze(ticker, filings),
        "risk": lambda: risk_agent.analyze(ticker, profile, profile_cite)}
    if overrides:
        functions.update(overrides)
    parallel_start = time.perf_counter()
    outputs = await asyncio.gather(*(run_agent(d, ticker, fn, timeout) for d, fn in functions.items()))
    parallel_ms = (time.perf_counter() - parallel_start) * 1000
    trace.append({"step": "Five parallel agents", "detail": f"asyncio.gather completed in {parallel_ms:.2f} ms."})
    for out in outputs:
        out.citations, rejected = validate_citations(out.citations, allowed)
        if rejected or (out.evidence and not out.citations):
            out.evidence = []
            out.confidence = 0
            out.status = "degraded"
            out.degraded_reason = "Unregistered or altered citations rejected; unsupported evidence removed."
        if out.status != "ok":
            warnings.append(f"{out.dimension}: {out.degraded_reason}")
    trace.append({"step": "Citation validation", "detail": "Only exact retrieved passages or registered data snapshots accepted."})
    rec = synthesize(profile, ticker, outputs, stats.get("volatility", 0), profile_citation=profile_cite)
    total_ms = (time.perf_counter() - start) * 1000
    metrics = session_metrics(outputs, rec, profile, total_ms, parallel_ms)
    metrics["total_latency_ms"] = (time.perf_counter() - start) * 1000
    trace.append({"step": "Personalized synthesis", "detail": f"{rec.action}; {len(rec.conflicts)} conflicts; confidence {rec.confidence:.1%}."})
    session = {"session_id": uuid.uuid4().hex, "recommendation": rec.model_dump(), "metrics": metrics,
               "trace": trace, "warnings": warnings, "data_mode": mode, "retrieval_mode": retriever.mode,
               "market_source": market_cite.model_dump(), "sources": [c.model_dump() for c in allowed.values()],
               "market_fingerprint": market_id + ":" + date + ":" + hashlib.sha256(
                   frame.to_json(date_format="iso", double_precision=10).encode()).hexdigest()[:16]}
    if persist:
        target_store = store or Store()
        await asyncio.to_thread(target_store.save_session, session)
        trace.append({"step": "Persistence", "detail": f"Session {session['session_id']} saved in SQLite."})
        # Persist the final trace, too, without adding duplicate session records.
        with target_store.connect() as db:
            import json
            db.execute("UPDATE sessions SET payload=? WHERE id=?", (json.dumps(session), session["session_id"]))
    return session


async def compare_users(ticker, profiles, **kwargs):
    frame, warning = await asyncio.to_thread(load_market, ticker, kwargs.pop("live", False))
    retriever = kwargs.pop("retriever", None) or await asyncio.to_thread(Retriever)
    # Same immutable frame, corpus, and failure settings for every user.
    results = await asyncio.gather(*(analyze(ticker, p, frame=frame, retriever=retriever, **kwargs) for p in profiles))
    if warning:
        for result in results:
            result["warnings"].append(warning)
    return results
