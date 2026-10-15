"""Bounded stages, reproducible evidence and truthful persistence status."""
import asyncio
import hashlib
import json
import time
import uuid
from collections import defaultdict, deque

import pandas as pd

from vibefinance.agents import filings_agent, momentum_agent, risk_agent, sentiment_agent, volume_agent
from vibefinance.agents.base import Citation, EvidenceClaim, run_agent
from vibefinance.config import AGENT_TIMEOUT_SECONDS, TICKERS
from vibefinance.data.market_live import load_market
from vibefinance.data.market_sim import indicators
from vibefinance.evaluation.metrics import session_metrics
from vibefinance.profiles.store import Store
from vibefinance.rag.retriever import Retriever
from vibefinance.rag.validator import validate_citations, validate_claims
from types import MappingProxyType
from vibefinance.synthesis.synthesizer import synthesize


RETRIEVER_INITIALIZATION_TIMEOUT_SECONDS = 60.0


async def prepare_retriever(timeout=RETRIEVER_INITIALIZATION_TIMEOUT_SECONDS):
    try:
        return await asyncio.wait_for(asyncio.to_thread(Retriever), timeout)
    except Exception as exc:
        fallback = Retriever(chunks=[], embeddings=False)
        fallback.warnings.append(f"Retrieval initialization unavailable ({type(exc).__name__}); document evidence withheld.")
        return fallback


async def analyze(ticker, profile, *, store=None, retriever=None, sentiment_outage=False,
                  missing_filing=False, live=False, frame=None, timeout=AGENT_TIMEOUT_SECONDS,
                  overrides=None, persist=True, execution_mode="parallel", as_of=None,
                  upstream_warnings=None):
    if ticker not in TICKERS:
        raise ValueError("Unsupported ticker")
    if execution_mode not in {"parallel", "sequential"}:
        raise ValueError("Execution mode must be parallel or sequential")
    start = time.perf_counter()
    trace, warnings = [], list(upstream_warnings or [])
    if frame is None:
        try:
            frame, warning = await asyncio.wait_for(asyncio.to_thread(load_market, ticker, live), timeout + 5)
            if warning:
                warnings.append(warning)
        except Exception as exc:
            frame = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
            frame.attrs["mode"] = "unavailable"
            warnings.append(f"Market ingestion unavailable ({type(exc).__name__}); no price claims emitted.")
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        warnings.append("Market input is not a table; no price claims emitted.")
    mode = frame.attrs.get("mode", "provided")
    market_id = frame.attrs.get("source_id", f"market:{ticker}:provided")
    try:
        stats = indicators(frame)
        date = str(pd.Timestamp(frame.date.iloc[-1]).date()) if "date" in frame else "provided"
        market_text = f"{ticker}: {len(frame)} OHLCV sessions, as of {date}. " + "; ".join(f"{k}={v:.6f}" for k, v in stats.items())
    except (ValueError, TypeError, AttributeError, KeyError):
        stats, date = {}, "unavailable"
        market_text = "Invalid or insufficient market data; no computed market claims."
        warnings.append("Market input invalid; price and volume agents will report failures.")
    market_cite = Citation(source_id=market_id, doc_title=f"{ticker} OHLCV [{mode.upper()}]",
                          chunk_id=f"{market_id}:snapshot", excerpt=market_text, score=1, date=date, source_kind="computed")
    profile_id = f"profile:{profile.user_id}"
    profile_cite = Citation(source_id=profile_id, doc_title=f"{profile.name} — profile snapshot",
        chunk_id=f"{profile_id}:snapshot", excerpt=profile.model_dump_json(), score=1, date="session snapshot", source_kind="computed")
    trace.append({"step": "Market ingest", "detail": f"{mode} · {len(frame)} sessions · {ticker}"})
    # Loading local embedding weights/indexes is cold-start work. Keep its budget
    # independent of the short deadline for each warmed agent/query.
    retriever = retriever if retriever is not None else await prepare_retriever()

    async def retrieve(query, types, k):
        try:
            options = {"as_of": as_of} if as_of is not None else {}
            return await asyncio.wait_for(asyncio.to_thread(retriever.retrieve, query, ticker, k, types, **options), timeout)
        except Exception as exc:
            warnings.append(f"{','.join(sorted(types))} retrieval unavailable ({type(exc).__name__}); claims withheld.")
            return []

    filings, news, transcripts = await asyncio.gather(
        retrieve("growth profit guidance risk decline weak cut attrition supportive", {"transcript", "results", "disclosure", "risk"}, 4)
        if not missing_filing else asyncio.sleep(0, result=[]),
        retrieve("growth profit weak guidance", {"news"}, 3),
        retrieve("growth profit guidance strong weak demand attrition", {"transcript"}, 3)
        if not missing_filing else asyncio.sleep(0, result=[]))
    if getattr(retriever, "warning", None):
        warnings.append(retriever.warning)
    retrieval_mode = getattr(retriever, "mode", "unavailable")
    trace.append({"step": "Retrieval", "detail": f"{retrieval_mode}: {len(filings)} filing / {len(news)} news / {len(transcripts)} transcript chunks; ticker/type/date filters applied. Shared passages are not independent corroboration."})
    # A transcript may be retrieved for both financial facts and tone. Use the
    # same canonical citation/score in both agents and one source-registry row.
    retrieved = {}
    for chunk, score in filings + news + transcripts:
        retrieved.setdefault(chunk.chunk_id, (chunk, score))
    filings = [retrieved[chunk.chunk_id] for chunk, _ in filings]
    news = [retrieved[chunk.chunk_id] for chunk, _ in news]
    transcripts = [retrieved[chunk.chunk_id] for chunk, _ in transcripts]
    allowed = {c.chunk_id: c for c in [market_cite, profile_cite] + [c.citation(s) for c, s in retrieved.values()]}
    # Reuse the validated market computation, not an agent-produced answer.
    # Canonical claim checks still regenerate labels/evidence independently;
    # scalar snapshot values are immutable and cannot be changed by an agent.
    indicator_snapshot = MappingProxyType(dict(stats)) if stats else None
    functions = {"momentum": lambda: momentum_agent.analyze(ticker, frame, market_cite, computed_indicators=indicator_snapshot),
        "volume": lambda: volume_agent.analyze(ticker, frame, market_cite, computed_indicators=indicator_snapshot),
        "sentiment": lambda: sentiment_agent.analyze(ticker, news, sentiment_outage or ticker == "ITC.NS",
            transcripts=transcripts, as_of=as_of),
        "filings": lambda: filings_agent.analyze(ticker, filings),
        "risk": lambda: risk_agent.analyze(ticker, profile, profile_cite)}
    canonical_functions = dict(functions)
    if overrides:
        if set(overrides) - set(functions):
            raise ValueError("Unsupported agent override")
        functions.update(overrides)
    agents_start = time.perf_counter()
    if execution_mode == "parallel":
        outputs = await asyncio.gather(*(run_agent(d, ticker, fn, timeout) for d, fn in functions.items()))
    else:
        outputs = [await run_agent(d, ticker, fn, timeout) for d, fn in functions.items()]
    agents_ms = (time.perf_counter() - agents_start) * 1000
    trace.append({"step": f"Five {execution_mode} agents", "detail": f"Measured agent window {agents_ms:.2f} ms; no artificial delays."})

    claim_total = supported_total = 0
    for out in outputs:
        original_evidence = list(out.evidence)
        out.citations, rejected_citations = validate_citations(out.citations, allowed)
        approved = {}
        canonical_claims = []
        classification_mismatch = False
        if out.status != "failed":
            try:
                canonical = canonical_functions[out.dimension]()
                canonical_claims = canonical.claims
                classification_mismatch = out.label != canonical.label or out.confidence != canonical.confidence
                if out.dimension in {"momentum", "volume", "risk"}:
                    for index, text in enumerate(canonical.evidence):
                        key = f"{out.dimension}:computed:{index}"
                        approved[key] = EvidenceClaim(claim_id=key, text=text,
                            citation_ids=[c.chunk_id for c in canonical.citations], method="computed")
                    if not out.claims:
                        out.claims = [claim for claim in approved.values() if claim.text in original_evidence]
            except Exception:
                approved = {}
                classification_mismatch = True
        provided_claims = list(out.claims)
        valid_claims, rejected_claims = validate_claims(provided_claims, allowed, computed_facts=approved)
        cited_ids = {c.chunk_id for c in out.citations}
        valid_claims = [claim for claim in valid_claims if set(claim.citation_ids) <= cited_ids]
        if out.dimension in {"momentum", "volume", "risk"}:
            valid_claims = [claim for claim in valid_claims if claim.method == "computed"]
        else:
            valid_claims = [claim for claim in valid_claims if claim in canonical_claims]
        if classification_mismatch or out.status == "failed":
            valid_claims = []
        if out.status == "failed":
            out.confidence = 0
            out.label = "UNKNOWN"
            out.citations = []
        by_text = defaultdict(deque)
        for claim in valid_claims:
            by_text[claim.text].append(claim)
        supported, supported_claims = [], []
        for text in original_evidence:
            if by_text[text]:
                supported.append(text)
                supported_claims.append(by_text[text].popleft())
        submitted_count = max(len(original_evidence), len(provided_claims))
        claim_total += submitted_count
        supported_total += len(supported)
        if out.status != "failed" and (classification_mismatch or rejected_citations or rejected_claims
                or len(supported) != submitted_count or (out.confidence > 0 and not supported)):
            fraction = len(supported) / submitted_count if submitted_count else 0
            out.confidence *= fraction
            out.status = "degraded"
            out.degraded_reason = ("Classification did not match deterministic recomputation; claims withheld."
                if classification_mismatch else "Unsupported claims or citations removed by deterministic support checks.")
            if not supported:
                out.confidence = 0
                out.label = "UNKNOWN"
                out.citations = []
        out.evidence = supported
        out.claims = supported_claims
        if out.status != "ok":
            warnings.append(f"{out.dimension}: {out.degraded_reason}")
    trace.append({"step": "Evidence support validation", "detail": f"{supported_total}/{claim_total} submitted statements supported by quotation, extraction or recomputation; general semantic entailment is not certified."})
    rec = synthesize(profile, ticker, outputs, stats.get("volatility", 0), profile_citation=profile_cite)
    metrics = session_metrics(outputs, rec, profile, (time.perf_counter() - start) * 1000, agents_ms)
    metrics.update({"execution_mode": execution_mode, "agent_execution_ms": agents_ms,
        "submitted_claim_count": claim_total, "supported_claim_count": supported_total,
        "rejected_claim_count": claim_total - supported_total,
        "claim_support_coverage": supported_total / claim_total if claim_total else None,
        "citation_coverage": supported_total / claim_total if claim_total else None})
    trace.append({"step": "Personalized synthesis", "detail": f"{rec.action}; {len(rec.conflicts)} conflicts; {rec.confidence_kind} {rec.confidence:.1%}; basis {rec.decision_basis}."})
    source_docs = {c.chunk_id: getattr(c, "document_text", c.text) or c.text for c, _ in retrieved.values()}
    source_types = {c.chunk_id: c.doc_type for c, _ in retrieved.values()}
    source_types.update({market_cite.chunk_id: "market", profile_cite.chunk_id: "profile"})
    sources = [{**citation.model_dump(), "doc_type": source_types[citation.chunk_id],
        "document_text": source_docs.get(citation.chunk_id, citation.excerpt)} for citation in allowed.values()]
    market_rows = json.loads(frame.to_json(orient="records", date_format="iso")) if stats else []
    metrics["total_latency_ms"] = (time.perf_counter() - start) * 1000
    session = {"session_id": uuid.uuid4().hex, "recommendation": rec.model_dump(), "metrics": metrics,
        "trace": trace, "warnings": warnings, "data_mode": mode, "retrieval_mode": retrieval_mode,
        "market_source": market_cite.model_dump(), "sources": sources, "market_rows": market_rows,
        "market_fingerprint": market_id + ":" + date + ":" + hashlib.sha256(
            frame.to_json(date_format="iso", double_precision=10).encode()).hexdigest()[:16],
        "persistence": {"status": "not_requested", "error": None}}
    if persist:
        session["persistence"]["status"] = "saved"
        trace.append({"step": "Persistence", "detail": f"Session {session['session_id']} saved atomically in SQLite."})
        try:
            target_store = store if store is not None else Store()
            await asyncio.to_thread(target_store.save_session, session)
        except Exception as exc:
            error = f"Storage unavailable ({type(exc).__name__}); analysis was not saved."
            session["persistence"] = {"status": "failed", "error": error}
            warnings.append(error)
            trace[-1] = {"step": "Persistence", "detail": error}
    return session


async def compare_users(ticker, profiles, **kwargs):
    live = kwargs.pop("live", False)
    try:
        frame, warning = await asyncio.wait_for(asyncio.to_thread(load_market, ticker, live), AGENT_TIMEOUT_SECONDS + 5)
    except Exception as exc:
        frame = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        frame.attrs["mode"] = "unavailable"
        warning = f"Market ingestion unavailable ({type(exc).__name__})."
    retriever = kwargs.pop("retriever", None)
    retriever = retriever if retriever is not None else await prepare_retriever()
    warnings = list(kwargs.pop("upstream_warnings", []) or [])
    if warning:
        warnings.append(warning)
    return await asyncio.gather(*(analyze(ticker, p, frame=frame, retriever=retriever,
        upstream_warnings=warnings, **kwargs) for p in profiles))
