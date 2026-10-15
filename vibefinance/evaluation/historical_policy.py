"""Replay existing safeguards on historical prices without inventing filings.

This checks the complete five-agent pipeline's constrained behavior. It does not
score recommendation accuracy, estimate profit or promote the price forecaster.
"""
from collections import Counter

import pandas as pd

from vibefinance.config import TICKERS
from vibefinance.evaluation.backtest import _policy_profiles
from vibefinance.evaluation.forecast import Protocol, frame_fingerprints, observations, period
from vibefinance.orchestrator import analyze
from vibefinance.rag.retriever import Retriever


async def historical_policy_evaluation(frames, frozen):
    """Use frozen test cutoffs and synthetic profiles, with no text evidence.

    Every price window receives three profile decisions. These share one market
    input/outcome and are not independent forecasts or simulated trades.
    """
    protocol = Protocol(**frozen["protocol"])
    protocol.validate()
    if set(frames) != set(TICKERS):
        raise ValueError("Historical policy replay requires the declared five-ticker universe")
    if frame_fingerprints(frames) != frozen["frame_fingerprints"]:
        raise ValueError("Historical frames changed after selection was frozen")
    windows = period(observations(frames, protocol.horizon_sessions),
                     protocol.test_start, protocol.test_end, protocol.horizon_sessions)
    if windows.empty or set(windows.ticker) != set(TICKERS):
        raise ValueError("Historical policy replay has no eligible window for every ticker")

    # Authentic publication snapshots have not been supplied. An explicitly empty
    # index prevents today's fictional corpus from entering historical decisions.
    retriever = Retriever(chunks=[], embeddings=False)
    decisions = []
    dimensions = {"momentum", "volume", "sentiment", "filings", "risk"}
    for window in windows.itertuples(index=False):
        ticker, as_of = window.ticker, str(window.as_of.date())
        frame = frames[ticker]
        prefix = frame[frame.date <= pd.Timestamp(as_of)].copy()
        for profile in _policy_profiles(ticker):
            session = await analyze(ticker, profile, frame=prefix, as_of=as_of,
                                    retriever=retriever, persist=False)
            recommendation = session["recommendation"]
            outputs = recommendation["agent_outputs"]
            textual = [output for output in outputs if output["dimension"] in {"sentiment", "filings"}]
            allowed_sources = {session["market_source"]["source_id"], f"profile:{profile.user_id}"}
            checks = {
                "all_five_agents_present": len(outputs) == 5 and {out["dimension"] for out in outputs} == dimensions,
                "market_inputs_available_by_cutoff": bool(session["market_rows"]) and all(
                    pd.Timestamp(row["date"]) <= pd.Timestamp(as_of) for row in session["market_rows"]),
                "historical_text_evidence_withheld": len(textual) == 2 and all(
                    not out["evidence"] and not out["claims"] and not out["citations"]
                    and out["confidence"] == 0 and out["status"] == "degraded" for out in textual),
                "only_price_and_profile_sources": all(
                    source["source_id"] in allowed_sources for source in session["sources"]),
                "persistence_disabled": session["persistence"]["status"] == "not_requested",
                "confidence_remains_evidence_strength": recommendation["confidence_kind"] == "evidence_strength",
            }
            if profile.user_id == "evaluation_concentrated":
                checks["concentration_override"] = (
                    recommendation["action"] == "REDUCE" and
                    recommendation["decision_basis"] == "portfolio_policy" and
                    "single_stock_limit" in recommendation["policy_rules"])
            else:
                checks["missing_fundamentals_pause_entry"] = (
                    recommendation["action"] == "WATCH" and
                    recommendation["decision_basis"] == "incomplete_evidence")
            if profile.user_id == "evaluation_cash":
                risk = next((out for out in outputs if out["dimension"] == "risk"), None)
                checks["cash_not_equity_high_risk"] = risk is not None and risk["label"] != "RISK_HIGH"
            decisions.append({"ticker": ticker, "as_of": as_of, "user_id": profile.user_id,
                "input_sessions": len(prefix), "action": recommendation["action"],
                "decision_basis": recommendation["decision_basis"], "checks": checks})

    names = sorted({name for row in decisions for name in row["checks"]})
    return {"schema_version": 1, "kind": "historical_policy_constraints", "protocol": frozen["protocol"],
        "data": frozen.get("data", []), "price_window_count": len(windows),
        "profile_decision_count": len(decisions), "profiles_per_price_window": 3,
        "profile_data": "Three synthetic static profiles; not real investor histories",
        "text_data": "Authentic historical filings/news unavailable; explicit empty retrieval index",
        "as_of_start": str(windows.as_of.min().date()), "as_of_end": str(windows.as_of.max().date()),
        "action_counts": dict(sorted(Counter(row["action"] for row in decisions).items())),
        "policy_checks": {name: {
            "evaluated": sum(name in row["checks"] for row in decisions),
            "passed": sum(row["checks"].get(name, False) for row in decisions),
            "violations": sum(name in row["checks"] and not row["checks"][name] for row in decisions)}
            for name in names},
        "decision_rows": decisions, "model_readiness": "research_only",
        "limitations": [
            "Real dated price snapshots alone do not supply point-in-time fundamentals or news. Today's synthetic documents are never used in this replay.",
            "Missing fundamentals intentionally cause WATCH for unconcentrated profiles; concentration REDUCE addresses an allocation rule, not predicted price decline.",
            "Three synthetic profiles share each price window. Profile decisions are correlated policy checks, not independent forecasts or trades.",
            "No recommendation accuracy, calibrated action-success probability, realized profit, transaction costs, portfolio revaluation or investment effectiveness is measured.",
            "Static profile and portfolio safeguards are disclosed demo policies. This replay establishes only the listed checks on the declared historical windows.",
            "The price forecaster does not enter synthesis. This replay cannot promote it or establish full-agent predictive quality."]}
