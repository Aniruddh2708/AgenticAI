"""Allocation rules must remain correct when market evidence is incomplete."""

import asyncio

import pytest

from vibefinance.agents.base import AgentOutput, Citation, UserProfile
from vibefinance.agents.risk_agent import analyze as risk_analyze
from vibefinance.agents.risk_agent import portfolio_summary, what_if
from vibefinance.orchestrator import analyze
from vibefinance.synthesis.synthesizer import synthesize


def profile(holdings, **kwargs):
    return UserProfile(user_id="policy", name="Policy test", risk_tolerance="aggressive",
                       horizon_months=24, holdings=holdings,
                       max_single_stock_pct=kwargs.pop("max_single_stock_pct", .60), **kwargs)


def source():
    return Citation(source_id="test", doc_title="Test snapshot", chunk_id="test:snapshot",
                    excerpt="Synthetic policy regression input", score=1)


def bullish(ticker="RELIANCE.NS", filings_strength=.9):
    return [AgentOutput(agent=dimension, dimension=dimension, ticker=ticker, label=label,
                        confidence=filings_strength if dimension == "filings" else .9,
                        evidence=["Test evidence"], citations=[source()])
            for dimension, label in (("momentum", "BULLISH"), ("volume", "SPIKE_UP"),
                                     ("sentiment", "POSITIVE"), ("filings", "SUPPORTIVE"))]


def test_missing_filing_does_not_cancel_known_concentration_limit(store, retriever):
    result = asyncio.run(analyze("ITC.NS", store.profile("meera"), retriever=retriever,
                                missing_filing=True, persist=False))
    recommendation = result["recommendation"]
    assert recommendation["action"] == "REDUCE"
    assert recommendation["decision_basis"] == "portfolio_policy"
    assert recommendation["confidence_kind"] == "evidence_strength"
    assert "single_stock_limit" in recommendation["policy_rules"]
    assert any("no claim about future price" in note for note in recommendation["personalization_notes"])
    assert any(c["source_id"] == "profile:meera" for c in recommendation["citations"])


def test_overweight_policy_needs_no_market_probability():
    p = profile({"RELIANCE.NS": .70})
    rec = synthesize(p, "RELIANCE.NS", [], profile_citation=source())
    assert rec.action == "REDUCE"
    assert rec.confidence == 0
    assert rec.decision_basis == "portfolio_policy"


@pytest.mark.parametrize("holdings", [{}, {"CASH": 1}])
def test_cash_only_is_not_high_equity_risk(holdings):
    p = profile(holdings)
    summary = portfolio_summary(p)
    assert summary["total_hhi"] == 1
    assert summary["equity_hhi"] == summary["equity_weight"] == 0
    assert summary["cash_weight"] == 1
    assert summary["largest_equity_sector_weight"] == 0
    assert risk_analyze("RELIANCE.NS", p, source()).label == "RISK_LOW"


def test_metrics_distinguish_normalized_equity_from_cash_allocation():
    summary = portfolio_summary(profile({"TCS.NS": .20, "INFY.NS": .10, "RELIANCE.NS": .10}))
    assert summary["cash_weight"] == pytest.approx(.60)
    assert summary["equity_hhi"] == pytest.approx(.5 ** 2 + .25 ** 2 + .25 ** 2)
    assert summary["total_hhi"] == pytest.approx(.20 ** 2 + .10 ** 2 + .10 ** 2 + .60 ** 2)
    assert summary["largest_equity_sector_weight"] == pytest.approx(.30)
    assert summary["largest_equity_sector_share"] == pytest.approx(.75)


def test_small_equity_sleeve_does_not_trigger_hhi_guard():
    p = profile({"RELIANCE.NS": .01})
    assert portfolio_summary(p)["equity_hhi"] == 1
    assert risk_analyze("RELIANCE.NS", p, source()).label == "RISK_LOW"
    assert synthesize(p, "RELIANCE.NS", bullish()).action == "BUY"


def test_sector_guard_stops_same_sector_but_allows_diversification():
    p = profile({"TCS.NS": .30, "INFY.NS": .25})
    blocked = synthesize(p, "TCS.NS", bullish("TCS.NS"))
    assert blocked.action == "HOLD"
    assert blocked.policy_rules == ["sector_limit"]
    assert what_if(p, "TCS.NS", "BUY")["trade_weight"] == 0
    assert synthesize(p, "HDFCBANK.NS", bullish("HDFCBANK.NS")).action == "BUY"


def test_equity_hhi_guard_stops_largest_position_not_diversification():
    p = profile({"RELIANCE.NS": .45, "ITC.NS": .10})
    rec = synthesize(p, "RELIANCE.NS", bullish())
    assert rec.action == "HOLD"
    assert rec.policy_rules == ["equity_concentration"]
    assert what_if(p, "RELIANCE.NS", "BUY")["trade_weight"] == 0
    assert synthesize(p, "HDFCBANK.NS", bullish("HDFCBANK.NS")).action == "BUY"


def test_exact_position_limit_stops_new_purchases():
    p = profile({"RELIANCE.NS": .20}, max_single_stock_pct=.20)
    rec = synthesize(p, "RELIANCE.NS", bullish())
    assert rec.action == "HOLD" and rec.policy_rules == ["single_stock_limit"]
    assert what_if(p, "RELIANCE.NS", "BUY")["trade_weight"] == 0


def test_cash_funded_illustration_does_not_propose_unfunded_trade():
    p = profile({"RELIANCE.NS": .25, "ITC.NS": .25, "TCS.NS": .25, "HDFCBANK.NS": .25})
    rec = synthesize(p, "RELIANCE.NS", bullish())
    assert rec.action == "HOLD"
    assert rec.policy_rules == ["cash_funding"]


def test_short_horizon_volatility_guard_affects_entry_not_evidence_strength():
    long = profile({"RELIANCE.NS": .10})
    short = long.model_copy(update={"horizon_months": 3})
    long_rec = synthesize(long, "RELIANCE.NS", bullish(), volatility=.65)
    short_rec = synthesize(short, "RELIANCE.NS", bullish(), volatility=.65)
    assert long_rec.action == "BUY"
    assert short_rec.action == "HOLD"
    assert short_rec.policy_rules == ["short_horizon_volatility"]
    assert short_rec.confidence == long_rec.confidence


def test_momentum_chasing_requires_independent_filing_confirmation():
    p = profile({"RELIANCE.NS": .10}, behavior={"chases_momentum": True})
    weak = synthesize(p, "RELIANCE.NS", bullish(filings_strength=.30))
    strong = synthesize(p, "RELIANCE.NS", bullish(filings_strength=.90))
    assert weak.action == "HOLD"
    assert weak.policy_rules == ["momentum_chasing_confirmation"]
    assert strong.action == "BUY"


def test_total_hhi_can_increase_when_equity_concentration_falls():
    # Selling into a larger cash allocation can raise total HHI. Report both;
    # never present total HHI alone as a before/after investment-risk judgment.
    result = what_if(profile({"RELIANCE.NS": .30, "ITC.NS": .20}), "RELIANCE.NS", "REDUCE")
    assert result["hhi_before"] == result["total_hhi_before"]
    assert result["hhi_after"] == result["total_hhi_after"]
    assert result["total_hhi_after"] > result["total_hhi_before"]
    assert result["equity_hhi_after"] < result["equity_hhi_before"]
    assert sum(result["holdings_after"].values()) == pytest.approx(1)


def test_what_if_respects_remaining_sector_headroom():
    p = profile({"TCS.NS": .30, "INFY.NS": .18})
    result = what_if(p, "INFY.NS", "BUY")
    assert result["trade_weight"] == pytest.approx(.02)
    assert result["largest_equity_sector_weight_after"] == pytest.approx(.50)
