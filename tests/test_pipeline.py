import asyncio
import threading
import time

import pytest

from vibefinance.agents.base import AgentOutput
from vibefinance.agents.risk_agent import what_if
from vibefinance.config import TICKERS
from vibefinance.data.market_sim import generate_market
from vibefinance.orchestrator import analyze, compare_users
from vibefinance.synthesis.synthesizer import vote


def run(store, retriever, ticker="RELIANCE.NS", user="arjun", **kwargs):
    return asyncio.run(analyze(ticker, store.profile(user), store=store, retriever=retriever, **kwargs))


def test_same_input_different_users(store, retriever):
    results = asyncio.run(compare_users("RELIANCE.NS", store.profiles(), store=store, retriever=retriever))
    recs = {r["recommendation"]["user_id"]: r["recommendation"] for r in results}
    assert {k: r["action"] for k, r in recs.items()} == {"arjun": "ACCUMULATE", "meera": "REDUCE", "rohan": "BUY"}
    assert len({r["market_fingerprint"] for r in results}) == 1
    for dim in ("momentum", "volume", "sentiment", "filings"):
        signals = [next(a for a in r["agent_outputs"] if a["dimension"] == dim) for r in recs.values()]
        assert len({(a["label"], a["confidence"], tuple(a["evidence"])) for a in signals}) == 1
    assert any("FOMO" in n for n in recs["rohan"]["personalization_notes"])


def test_conflict_reduces_confidence(store, retriever):
    session = run(store, retriever, "TCS.NS")
    rec = session["recommendation"]
    assert rec["action"] == "HOLD" and rec["conflicts"]
    outputs = [AgentOutput.model_validate(o) for o in rec["agent_outputs"]]
    _, before, after, _ = vote(outputs)
    assert rec["confidence"] == after < before


def test_outage_and_missing_lower_confidence(store, retriever):
    good = run(store, retriever)
    missing = run(store, retriever, sentiment_outage=True, missing_filing=True)
    assert missing["recommendation"]["action"] == "WATCH"
    assert missing["recommendation"]["confidence"] < good["recommendation"]["confidence"]
    assert missing["metrics"]["degraded_agent_count"] == 2
    for a in missing["recommendation"]["agent_outputs"]:
        if a["dimension"] in {"sentiment", "filings"}:
            assert a["citations"] == [] and a["evidence"] == [] and a["confidence"] == 0


@pytest.mark.parametrize("ticker,dimension", [("ITC.NS", "sentiment"), ("HDFCBANK.NS", "filings")])
def test_seeded_degradation(store, retriever, ticker, dimension):
    session = run(store, retriever, ticker)
    assert next(a for a in session["recommendation"]["agent_outputs"] if a["dimension"] == dimension)["status"] == "degraded"


def test_concentration_override(store, retriever):
    session = run(store, retriever, "ITC.NS", "meera")
    assert session["recommendation"]["action"] == "REDUCE"
    assert any("45%" in note and "15%" in note for note in session["recommendation"]["personalization_notes"])


def test_invalid_market_degrades_without_crash(store, retriever):
    frame = generate_market("RELIANCE.NS")
    frame.loc[0, "close"] = float("nan")
    session = run(store, retriever, frame=frame)
    assert session["metrics"]["failed_agent_count"] == 2
    assert session["recommendation"]["action"] == "WATCH"


def test_timeout_and_failure_are_isolated(store, retriever):
    def slow():
        time.sleep(.05)
    def fail():
        raise ValueError("bad input")
    session = run(store, retriever, timeout=.01, overrides={"sentiment": slow, "filings": fail})
    agents = {a["dimension"]: a for a in session["recommendation"]["agent_outputs"]}
    assert agents["sentiment"]["status"] == agents["filings"]["status"] == "failed"
    assert "timed out" in agents["sentiment"]["degraded_reason"]


def test_all_agents_fail_returns_watch(store, retriever):
    def fail():
        raise RuntimeError("offline")
    session = run(store, retriever, overrides={d: fail for d in ("momentum", "volume", "sentiment", "filings", "risk")})
    assert session["recommendation"]["action"] == "WATCH"
    assert session["recommendation"]["confidence"] == 0
    assert session["metrics"]["citation_coverage"] is None


def test_failed_risk_agent_retains_policy_provenance(store, retriever):
    def fail():
        raise RuntimeError("risk failure")
    session = run(store, retriever, user="meera", overrides={"risk": fail})
    assert session["recommendation"]["action"] == "REDUCE"
    assert any(c["source_id"] == "profile:meera" for c in session["recommendation"]["citations"])


def test_agents_really_overlap(store, retriever):
    # A barrier would time out under sequential execution; avoids timing-sensitive speed assertions.
    barrier = threading.Barrier(5, timeout=2)
    def worker(dimension):
        def work():
            barrier.wait()
            return AgentOutput(agent=dimension, ticker="RELIANCE.NS", dimension=dimension,
                               label="UNKNOWN", confidence=0, evidence=[])
        return work
    session = run(store, retriever, overrides={d: worker(d) for d in ("momentum", "volume", "sentiment", "filings", "risk")})
    assert session["metrics"]["failed_agent_count"] == 0


def test_citation_injection_is_removed(store, retriever):
    def forged():
        from vibefinance.agents.base import Citation
        citation = Citation(source_id="unknown", doc_title="Fake", chunk_id="unknown", excerpt="Fabricated", score=1)
        return AgentOutput(agent="filings", ticker="RELIANCE.NS", dimension="filings", label="SUPPORTIVE",
                           confidence=1, evidence=["Invented profit"], citations=[citation])
    session = run(store, retriever, overrides={"filings": forged})
    out = next(o for o in session["recommendation"]["agent_outputs"] if o["dimension"] == "filings")
    assert out["status"] == "degraded" and not out["evidence"] and not out["citations"]
    assert session["recommendation"]["action"] == "WATCH"


@pytest.mark.parametrize("action", ["BUY", "ACCUMULATE", "HOLD", "REDUCE", "AVOID", "WATCH"])
def test_what_if_conserves_weights(store, action):
    result = what_if(store.profile("arjun"), "RELIANCE.NS", action)
    assert sum(result["holdings_after"].values()) == pytest.approx(1)
    assert all(w >= 0 for w in result["holdings_after"].values())
    assert result["holdings_after"]["RELIANCE.NS"] <= .25


def test_all_tickers_persist_provenance_and_metrics(store, retriever):
    for ticker in TICKERS:
        session = run(store, retriever, ticker)
        stored = store.session(session["session_id"])
        assert stored == session
        assert len(stored["recommendation"]["agent_outputs"]) == 5
        assert stored["metrics"]["citation_coverage"] == 1
        assert stored["recommendation"]["reasoning_chain"] and stored["recommendation"]["disclaimer"]
