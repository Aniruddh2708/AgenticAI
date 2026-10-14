from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from vibefinance.agents.base import UserProfile
from vibefinance.config import TICKERS
from vibefinance.evaluation.backtest import backtest
from vibefinance.orchestrator import analyze, compare_users
from vibefinance.profiles.store import Store
from vibefinance.rag.retriever import Retriever


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


def create_app(db_path=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(db_path)
        app.state.retriever = Retriever()
        yield

    app = FastAPI(title="VibeFinance", version="0.1.0", lifespan=lifespan)

    def get_profile(user_id):
        try:
            return app.state.store.profile(user_id)
        except KeyError:
            raise HTTPException(404, "Profile not found")

    def valid_ticker(ticker):
        if ticker not in TICKERS:
            raise HTTPException(422, "Unsupported NSE demo ticker")

    @app.get("/health")
    def health():
        return {"status": "ok", "profiles": len(app.state.store.profiles()),
                "corpus_chunks": len(app.state.retriever.chunks), "retrieval_mode": app.state.retriever.mode,
                "default_data_mode": "simulated"}

    @app.get("/profiles")
    def profiles():
        return app.state.store.profiles()

    @app.get("/profiles/{user_id}")
    def profile(user_id: str):
        return get_profile(user_id)

    @app.put("/profiles/{user_id}")
    def update_profile(user_id: str, profile: UserProfile):
        if user_id != profile.user_id:
            raise HTTPException(422, "Path and profile user_id must match")
        app.state.store.save_profile(profile)
        return profile

    @app.delete("/profiles/{user_id}", status_code=204)
    def delete_profile(user_id: str):
        get_profile(user_id)
        app.state.store.delete_profile(user_id)

    @app.post("/analyze")
    async def analysis(request: AnalysisRequest):
        valid_ticker(request.ticker)
        return await analyze(request.ticker, get_profile(request.user_id), store=app.state.store,
            retriever=app.state.retriever, sentiment_outage=request.sentiment_outage,
            missing_filing=request.missing_filing, live=request.live)

    @app.post("/compare")
    async def compare(request: AnalysisRequest):
        valid_ticker(request.ticker)
        return await compare_users(request.ticker, app.state.store.profiles(), store=app.state.store,
            retriever=app.state.retriever, sentiment_outage=request.sentiment_outage,
            missing_filing=request.missing_filing, live=request.live)

    @app.post("/watchlist")
    async def watchlist(request: ScanRequest):
        import asyncio
        profile = get_profile(request.user_id)
        for ticker in request.tickers:
            valid_ticker(ticker)
        sessions = await asyncio.gather(*(analyze(t, profile, store=app.state.store,
            retriever=app.state.retriever) for t in dict.fromkeys(request.tickers)))
        alerts = []
        for session in sessions:
            rec = session["recommendation"]
            if rec["action"] in {"BUY", "ACCUMULATE", "REDUCE", "AVOID"} and rec["confidence"] >= .25:
                alerts.append({"ticker": rec["ticker"], "action": rec["action"], "confidence": rec["confidence"],
                               "reason": rec["personalization_notes"]})
        return {"sessions": sessions, "alerts": alerts}

    @app.get("/evaluation")
    def evaluation():
        return backtest()

    @app.get("/history/{user_id}")
    def history(user_id: str, ticker: str | None = None, limit: int = Query(20, ge=1, le=100)):
        get_profile(user_id)
        return app.state.store.history(user_id, ticker, limit)

    def get_session(session_id):
        try:
            return app.state.store.session(session_id)
        except KeyError:
            raise HTTPException(404, "Session not found")

    @app.get("/sessions/{session_id}")
    def session(session_id: str):
        return get_session(session_id)

    @app.post("/sessions/{session_id}/decision")
    def decision(session_id: str, request: DecisionRequest):
        get_session(session_id)
        app.state.store.decision(session_id, request.decision)
        return {"saved": True}

    @app.get("/sessions/{session_id}/decisions")
    def decisions(session_id: str):
        get_session(session_id)
        return app.state.store.decisions(session_id)

    @app.get("/sessions/{session_id}/sources/{chunk_id:path}")
    def source(session_id: str, chunk_id: str):
        for source in get_session(session_id)["sources"]:
            if source["chunk_id"] == chunk_id:
                return source
        raise HTTPException(404, "Source not part of this session")

    return app


app = create_app()
