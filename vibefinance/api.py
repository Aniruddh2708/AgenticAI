"""Local API with optional shared-demo authentication and explicit unavailable storage."""
import asyncio
import hmac
import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field

from vibefinance.agents.base import UserProfile
from vibefinance.auth import AuthenticationError, AuthSettings, OIDCVerifier
from vibefinance.profiles.production_store import (StorageUnavailableError, create_production_store,
    initialize_production_storage, production_storage_health)
from vibefinance.config import ROOT, TICKERS
from vibefinance.evaluation.backtest import backtest
from vibefinance.evaluation.forecast_report import load_forecast_report
from vibefinance.deployment import release_revision
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
        app.state.auth_settings = AuthSettings.from_env()
        app.state.verifier = None
        app.state.storage_error = None
        app.state.store = None
        app.state.seed_profiles = {}
        if app.state.auth_settings.mode != "demo":
            # Production never redirects account data to SQLite or demo profiles.
            await asyncio.to_thread(initialize_production_storage)
            app.state.verifier = OIDCVerifier(app.state.auth_settings)
        else:
            try:
                app.state.store = Store(db_path)
            except (sqlite3.Error, OSError, ValueError) as exc:
                app.state.storage_error = f"Storage initialization unavailable ({type(exc).__name__}); using disclosed read-only seed profiles rather than saved custom profiles."
            app.state.seed_profiles = {p.user_id: p for p in
                (UserProfile.model_validate(data) for data in json.loads((ROOT / "data/users.json").read_text()))}
        app.state.retriever = await prepare_retriever()
        app.state.benchmark_lock = asyncio.Lock()
        app.state.policy_lock = asyncio.Lock()
        try:
            yield
        finally:
            if app.state.verifier is not None:
                app.state.verifier.close()

    app = FastAPI(title="VibeFinance", version="0.2.0", lifespan=lifespan)
    # The supplied terminal-style HTML is the offline demo's primary frontend.
    # Static assets never require internet or share a user's data. Stateful
    # endpoints retain all existing authentication and storage protections.
    web_dir = Path(__file__).resolve().parent / "web"
    app.mount("/assets", StaticFiles(directory=web_dir), name="dashboard-assets")

    @app.get("/", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    def web_dashboard():
        return FileResponse(web_dir / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/_stcore/health", include_in_schema=False)
    def dashboard_compatibility_health():
        # Container health checks support both the legacy Streamlit deployment
        # and the new same-origin FastAPI dashboard during the transition.
        return PlainTextResponse("ok")

    @app.middleware("http")
    async def access_and_timing(request, call_next):
        settings = getattr(app.state, "auth_settings", None)
        if settings is None:
            return JSONResponse(status_code=503, content={"detail": "Application startup is incomplete."})
        if request.url.path not in {"/health", "/", "/dashboard", "/_stcore/health"} and not request.url.path.startswith("/assets/"):
            # Only non-sensitive web shell assets are public. API data endpoints
            # are still protected by demo bearer token or managed account auth.
            authorization = request.headers.get("Authorization", "")
            if settings.mode != "demo":
                try:
                    request.state.principal = await asyncio.to_thread(
                        app.state.verifier.authenticate, authorization,
                        method=request.method, path=request.url.path)
                except AuthenticationError:
                    return JSONResponse(status_code=401,
                        content={"detail": "A valid individual sign-in is required."},
                        headers={"WWW-Authenticate": "Bearer"})
            elif token := os.getenv("VIBEFINANCE_API_TOKEN", ""):
                if not hmac.compare_digest(authorization.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
                    return JSONResponse(status_code=401, content={"detail": "A valid demo access token is required."})
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["Server-Timing"] = f"application;dur={(time.perf_counter()-started)*1000:.3f}"
        return response

    @app.exception_handler(StorageUnavailableError)
    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(OSError)
    async def unavailable_storage(request, exc):
        return JSONResponse(status_code=503, content={"detail": "Persistent storage is unavailable; this operation was not completed."})

    def production():
        return app.state.auth_settings.mode != "demo"

    def persistent_store(request):
        if production():
            principal = getattr(request.state, "principal", None)
            if principal is None:
                raise HTTPException(401, "A valid individual sign-in is required.")
            if not hasattr(request.state, "account_store"):
                request.state.account_store = create_production_store(principal.account_id)
            return request.state.account_store
        if app.state.store is None:
            # A restored disk or repaired path can be retried without changing secrets.
            try:
                app.state.store = Store(db_path)
                app.state.storage_error = None
            except (sqlite3.Error, OSError, ValueError):
                raise HTTPException(503, "Persistent storage is unavailable. Analysis can use disclosed seed profiles, but changes and history cannot be saved.")
        return app.state.store

    def profiles_for_analysis(request):
        if production():
            return persistent_store(request).profiles()
        if app.state.store is not None:
            try:
                return app.state.store.profiles()
            except (sqlite3.Error, OSError, ValueError):
                app.state.storage_error = "Profile storage unavailable; using disclosed read-only seed profiles."
        return list(app.state.seed_profiles.values())

    def get_profile(user_id, request):
        for profile in profiles_for_analysis(request):
            if profile.user_id == user_id:
                return profile
        raise HTTPException(404, "Profile not found")

    def valid_ticker(ticker):
        if ticker not in TICKERS:
            raise HTTPException(422, "Unsupported NSE demo ticker")

    def storage_warning():
        return [app.state.storage_error] if app.state.storage_error else []

    def analysis_store(request):
        return persistent_store(request) if production() else app.state.store or UnavailableStore()

    def offline_research_only():
        if production():
            raise HTTPException(403, "Run synthetic benchmark jobs in the offline research environment.")

    def record_persistence(results):
        failures = [result["persistence"]["error"] for result in results if result["persistence"]["status"] == "failed"]
        if failures:
            app.state.storage_error = failures[0]
        elif results and all(result["persistence"]["status"] == "saved" for result in results):
            app.state.storage_error = None

    @app.get("/health")
    def health(request: Request):
        if production():
            try:
                available = bool(production_storage_health())
            except StorageUnavailableError:
                available = False
            return {"status": "ok" if available and not app.state.retriever.warning else "degraded",
                    "storage_available": available, "storage_backend": "postgresql",
                    "authentication_enabled": True, "auth_mode": app.state.auth_settings.mode,
                    "corpus_chunks": len(app.state.retriever.chunks),
                    "retrieval_mode": app.state.retriever.mode, "default_data_mode": "simulated",
                    "revision": release_revision()}
        current_profiles = profiles_for_analysis(request)
        return {"status": "degraded" if app.state.storage_error or app.state.retriever.warning else "ok",
                "profiles": len(current_profiles), "storage_available": app.state.storage_error is None,
                "corpus_chunks": len(app.state.retriever.chunks), "retrieval_mode": app.state.retriever.mode,
                "default_data_mode": "simulated", "authentication_enabled": bool(os.getenv("VIBEFINANCE_API_TOKEN")),
                "revision": release_revision()}

    @app.get("/profiles")
    def profiles(request: Request):
        return profiles_for_analysis(request)

    @app.get("/profiles/{user_id}")
    def profile(user_id: str, request: Request):
        return get_profile(user_id, request)

    @app.put("/profiles/{user_id}")
    def update_profile(user_id: str, profile: UserProfile, request: Request):
        if user_id != profile.user_id:
            raise HTTPException(422, "Path and profile user_id must match")
        persistent_store(request).save_profile(profile)
        return profile

    @app.delete("/profiles/{user_id}", status_code=204)
    def delete_profile(user_id: str, request: Request):
        get_profile(user_id, request)
        try:
            persistent_store(request).delete_profile(user_id)
        except KeyError:
            raise HTTPException(404, "Profile not found")

    @app.post("/analyze")
    async def analysis(request: AnalysisRequest, http_request: Request):
        valid_ticker(request.ticker)
        profile = get_profile(request.user_id, http_request)
        result = await analyze(request.ticker, profile, store=analysis_store(http_request),
            retriever=app.state.retriever, sentiment_outage=request.sentiment_outage,
            missing_filing=request.missing_filing, live=request.live,
            upstream_warnings=storage_warning())
        record_persistence([result])
        return result

    @app.post("/compare")
    async def compare(request: AnalysisRequest, http_request: Request):
        valid_ticker(request.ticker)
        profiles = profiles_for_analysis(http_request)
        results = await compare_users(request.ticker, profiles, store=analysis_store(http_request),
            retriever=app.state.retriever, sentiment_outage=request.sentiment_outage,
            missing_filing=request.missing_filing, live=request.live,
            upstream_warnings=storage_warning())
        record_persistence(results)
        return results

    @app.post("/watchlist")
    async def watchlist(request: ScanRequest, http_request: Request):
        profile = get_profile(request.user_id, http_request)
        for ticker in request.tickers:
            valid_ticker(ticker)
        sessions = await asyncio.gather(*(analyze(t, profile, store=analysis_store(http_request),
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

    @app.get("/evaluation/forecast")
    def forecast_evaluation():
        return load_forecast_report()

    @app.get("/evaluation/policies")
    async def policies():
        offline_research_only()
        from vibefinance.evaluation.backtest import policy_evaluation
        async with app.state.policy_lock:
            return await policy_evaluation()

    @app.get("/benchmark")
    async def benchmark(repeats: int = Query(5, ge=2, le=20)):
        offline_research_only()
        from vibefinance.evaluation.benchmark import benchmark_async
        async with app.state.benchmark_lock:
            return await benchmark_async(repeats=repeats)

    @app.get("/history/{user_id}")
    def history(user_id: str, request: Request, ticker: str | None = None, limit: int = Query(20, ge=1, le=100)):
        get_profile(user_id, request)
        return persistent_store(request).history(user_id, ticker, limit)

    def get_session(session_id, request):
        try:
            return persistent_store(request).session(session_id)
        except KeyError:
            raise HTTPException(404, "Session not found")

    @app.get("/sessions/{session_id}")
    def session(session_id: str, request: Request):
        return get_session(session_id, request)

    @app.post("/sessions/{session_id}/decision")
    def decision(session_id: str, request: DecisionRequest, http_request: Request):
        get_session(session_id, http_request)
        try:
            persistent_store(http_request).decision(session_id, request.decision)
        except KeyError:
            raise HTTPException(404, "Session not found")
        return {"saved": True}

    @app.get("/sessions/{session_id}/decisions")
    def decisions(session_id: str, request: Request):
        get_session(session_id, request)
        return persistent_store(request).decisions(session_id)

    @app.get("/sessions/{session_id}/sources/{chunk_id:path}")
    def source(session_id: str, chunk_id: str, request: Request):
        for source in get_session(session_id, request)["sources"]:
            if source["chunk_id"] == chunk_id:
                return source
        raise HTTPException(404, "Source not part of this session")

    return app


app = create_app()
