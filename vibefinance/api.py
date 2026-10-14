"""Local API with optional shared-demo authentication and explicit unavailable storage."""
import asyncio
import hmac
import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from vibefinance.agents.base import UserProfile
from vibefinance.config import ROOT, TICKERS
from vibefinance.evaluation.backtest import backtest
from vibefinance.orchestrator import analyze, compare_users, prepare_retriever
from vibefinance.profiles.store import Store


class AnalysisRequest(BaseModel):
    ticker: str = "RELIANCE.NS"
    user_id: str = "arjun"
    sentiment_outage: bool = False
    missing_filing: bool = False
    live: bool = False


class DecisionRequest(BaseModel):
    decision: Literal["follow", "watch", "skip"]


class ScanRequest(BaseModel):
    user_id: str = "arjun"
    tickers: list[str] = Field(default_factory=lambda: list(TICKERS), min_length=1, max_length=5)


class UnavailableStore:
    """Never redirect a failed configured database to another database."""
    def save_session(self, session):
        raise sqlite3.OperationalError("Configured storage is unavailable")


def create_app(db_path=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.storage_error = None
        app.state.store = None
        try:
            app.state.store = Store(db_path)
        except (sqlite3.Error, OSError, ValueError) as exc:
            app.state.storage_error = f"Storage initialization unavailable ({type(exc).__name__}); using disclosed read-only seed profiles rather than saved custom profiles."
        app.state.seed_profiles = {p.user_id: p for p in
            (UserProfile.model_validate(data) for data in json.loads((ROOT / "data/users.json").read_text()))}
        app.state.retriever = await prepare_retriever()
        app.state.benchmark_lock = asyncio.Lock()
        app.state.policy_lock = asyncio.Lock()
        yield

    app = FastAPI(title="VibeFinance", version="0.2.0", lifespan=lifespan)

    @app.middleware("http")
    async def access_and_timing(request, call_next):
        token = os.getenv("VIBEFINANCE_API_TOKEN", "")
        if token and request.url.path != "/health":
            authorization = request.headers.get("Authorization", "")
            if not hmac.compare_digest(authorization.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
                return JSONResponse(status_code=401, content={"detail": "A valid demo access token is required."})
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["Server-Timing"] = f"application;dur={(time.perf_counter()-started)*1000:.3f}"
        return response

    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(OSError)
    async def unavailable_storage(request, exc):
        return JSONResponse(status_code=503, content={"detail": "Persistent storage is unavailable; this operation was not completed."})

    def persistent_store():
        if app.state.store is None:
            # A restored disk or repaired path can be retried without changing secrets.
            try:
                app.state.store = Store(db_path)
                app.state.storage_error = None
            except (sqlite3.Error, OSError, ValueError):
                raise HTTPException(503, "Persistent storage is unavailable. Analysis can use disclosed seed profiles, but changes and history cannot be saved.")
        return app.state.store

    def profiles_for_analysis():
        if app.state.store is not None:
            try:
                return app.state.store.profiles()
            except (sqlite3.Error, OSError, ValueError):
                app.state.storage_error = "Profile storage unavailable; using disclosed read-only seed profiles."
        return list(app.state.seed_profiles.values())

    def get_profile(user_id):
        for profile in profiles_for_analysis():
            if profile.user_id == user_id:
                return profile
        raise HTTPException(404, "Profile not found")

    def valid_ticker(ticker):
        if ticker not in TICKERS:
            raise HTTPException(422, "Unsupported NSE demo ticker")

    def storage_warning():
        return [app.state.storage_error] if app.state.storage_error else []

    def record_persistence(results):
        failures = [result["persistence"]["error"] for result in results if result["persistence"]["status"] == "failed"]
        if failures:
            app.state.storage_error = failures[0]
        elif results and all(result["persistence"]["status"] == "saved" for result in results):
            app.state.storage_error = None

    @app.get("/health")
    def health():
        current_profiles = profiles_for_analysis()
        return {"status": "degraded" if app.state.storage_error or app.state.retriever.warning else "ok",
                "profiles": len(current_profiles), "storage_available": app.state.storage_error is None,
                "corpus_chunks": len(app.state.retriever.chunks), "retrieval_mode": app.state.retriever.mode,
                "default_data_mode": "simulated", "authentication_enabled": bool(os.getenv("VIBEFINANCE_API_TOKEN"))}

    @app.get("/profiles")
    def profiles():
        return profiles_for_analysis()

    @app.get("/profiles/{user_id}")
    def profile(user_id: str):
        return get_profile(user_id)

    @app.put("/profiles/{user_id}")
    def update_profile(user_id: str, profile: UserProfile):
        if user_id != profile.user_id:
            raise HTTPException(422, "Path and profile user_id must match")
        persistent_store().save_profile(profile)
        return profile

    @app.delete("/profiles/{user_id}", status_code=204)
    def delete_profile(user_id: str):
        get_profile(user_id)
        try:
            persistent_store().delete_profile(user_id)
        except KeyError:
            raise HTTPException(404, "Profile not found")

    @app.post("/analyze")
    async def analysis(request: AnalysisRequest):
        valid_ticker(request.ticker)
        profile = get_profile(request.user_id)
        result = await analyze(request.ticker, profile, store=app.state.store or UnavailableStore(),
            retriever=app.state.retriever, sentiment_outage=request.sentiment_outage,
            missing_filing=request.missing_filing, live=request.live,
            upstream_warnings=storage_warning())
        record_persistence([result])
        return result

    @app.post("/compare")
    async def compare(request: AnalysisRequest):
        valid_ticker(request.ticker)
        profiles = profiles_for_analysis()
        results = await compare_users(request.ticker, profiles, store=app.state.store or UnavailableStore(),
            retriever=app.state.retriever, sentiment_outage=request.sentiment_outage,
            missing_filing=request.missing_filing, live=request.live,
            upstream_warnings=storage_warning())
        record_persistence(results)
        return results

    @app.post("/watchlist")
    async def watchlist(request: ScanRequest):
        profile = get_profile(request.user_id)
        for ticker in request.tickers:
            valid_ticker(ticker)
        sessions = await asyncio.gather(*(analyze(t, profile, store=app.state.store or UnavailableStore(),
            retriever=app.state.retriever, upstream_warnings=storage_warning()) for t in dict.fromkeys(request.tickers)))
        record_persistence(sessions)
        alerts = []
        for session in sessions:
            rec = session["recommendation"]
            if rec["action"] in {"BUY", "ACCUMULATE", "REDUCE", "AVOID"} and (
                rec["confidence"] >= .25 or rec["decision_basis"] == "portfolio_policy"):
                alerts.append({"ticker": rec["ticker"], "action": rec["action"], "confidence": rec["confidence"],
                               "reason": rec["personalization_notes"], "decision_basis": rec["decision_basis"]})
        return {"sessions": sessions, "alerts": alerts}

    @app.get("/evaluation")
    def evaluation():
        return backtest()

    @app.get("/evaluation/policies")
    async def policies():
        from vibefinance.evaluation.backtest import policy_evaluation
        async with app.state.policy_lock:
            return await policy_evaluation()

    @app.get("/benchmark")
    async def benchmark(repeats: int = Query(5, ge=2, le=20)):
        from vibefinance.evaluation.benchmark import benchmark_async
        async with app.state.benchmark_lock:
            return await benchmark_async(repeats=repeats)

    @app.get("/history/{user_id}")
    def history(user_id: str, ticker: str | None = None, limit: int = Query(20, ge=1, le=100)):
        get_profile(user_id)
        return persistent_store().history(user_id, ticker, limit)

    def get_session(session_id):
        try:
            return persistent_store().session(session_id)
        except KeyError:
            raise HTTPException(404, "Session not found")

    @app.get("/sessions/{session_id}")
    def session(session_id: str):
        return get_session(session_id)

    @app.post("/sessions/{session_id}/decision")
    def decision(session_id: str, request: DecisionRequest):
        get_session(session_id)
        try:
            persistent_store().decision(session_id, request.decision)
        except KeyError:
            raise HTTPException(404, "Session not found")
        return {"saved": True}

    @app.get("/sessions/{session_id}/decisions")
    def decisions(session_id: str):
        get_session(session_id)
        return persistent_store().decisions(session_id)

    @app.get("/sessions/{session_id}/sources/{chunk_id:path}")
    def source(session_id: str, chunk_id: str):
        for source in get_session(session_id)["sources"]:
            if source["chunk_id"] == chunk_id:
                return source
        raise HTTPException(404, "Source not part of this session")

    return app


app = create_app()
