"""Descriptive allocation risk, separated from market-direction evidence.

Limits other than the user's position limit are transparent demo guardrails, not
estimated probabilities or claims about future portfolio volatility.
"""

import math

from vibefinance.agents.base import AgentOutput
from vibefinance.config import SECTORS


SECTOR_LIMIT = .50  # Fraction of the entire portfolio, excluding cash as a sector.
EQUITY_HHI_LIMIT = .40  # HHI of equity weights normalized to sum to one.
MIN_EQUITY_FOR_HHI_GUARD = .50  # A tiny equity sleeve is not high total exposure.


def portfolio_weights(profile):
    weights = {k: v for k, v in profile.holdings.items() if v > 0}
    weights["CASH"] = weights.get("CASH", 0) + max(0, 1 - sum(weights.values()))
    return weights


def hhi(weights):
    """Sum of squared input weights; callers must state their denominator."""
    return sum(w * w for w in weights.values())


def sector_weights(weights):
    result = {}
    for ticker, weight in weights.items():
        sector = SECTORS.get(ticker, "Cash" if ticker == "CASH" else "Other")
        result[sector] = result.get(sector, 0) + weight
    return result


def _allocation_summary(weights):
    equities = {ticker: weight for ticker, weight in weights.items() if ticker != "CASH" and weight > 0}
    equity_weight = sum(equities.values())
    normalized = {ticker: weight / equity_weight for ticker, weight in equities.items()} if equity_weight else {}
    sectors = {sector: weight for sector, weight in sector_weights(weights).items() if sector != "Cash"}
    top_ticker = max(equities, key=equities.get) if equities else None
    top_sector = max(sectors, key=sectors.get) if sectors else None
    largest_sector = sectors.get(top_sector, 0)
    return {
        "total_hhi": hhi(weights),
        "equity_hhi": hhi(normalized),
        "cash_weight": weights.get("CASH", 0),
        "equity_weight": equity_weight,
        "top_equity_ticker": top_ticker,
        "top_equity_weight": equities.get(top_ticker, 0),
        "largest_equity_sector": top_sector,
        "largest_equity_sector_weight": largest_sector,
        "largest_equity_sector_share": largest_sector / equity_weight if equity_weight else 0,
        "sector_weights": sectors,
    }


def portfolio_summary(profile):
    """Allocation snapshot; sector weights use total portfolio as denominator.

    `total_hhi` includes cash and is descriptive only. `equity_hhi` excludes cash
    and normalizes equities, returning zero without equity holdings. Cash is an
    allocation, not a judgment that cash has no risks. Unknown sectors use Other.
    """
    return _allocation_summary(portfolio_weights(profile))


def analyze(ticker, profile, citation):
    weights = portfolio_weights(profile)
    summary = _allocation_summary(weights)
    position = weights.get(ticker, 0)
    limit = profile.max_single_stock_pct
    position_ratio = summary["top_equity_weight"] / limit
    sector_ratio = summary["largest_equity_sector_weight"] / SECTOR_LIMIT
    equity_concentrated = (summary["equity_weight"] >= MIN_EQUITY_FOR_HHI_GUARD
                           and summary["equity_hhi"] > EQUITY_HHI_LIMIT)
    hhi_ratio = summary["equity_hhi"] / EQUITY_HHI_LIMIT if summary["equity_weight"] >= MIN_EQUITY_FOR_HHI_GUARD else 0
    severity = max(position_ratio, sector_ratio, hhi_ratio)
    breached = position_ratio > 1 or sector_ratio > 1 or equity_concentrated
    label = "RISK_HIGH" if breached else "RISK_MED" if severity > .75 else "RISK_LOW"
    # This measures distance from an allocation-policy boundary, not loss odds.
    boundary = 1 if label == "RISK_HIGH" else .75
    confidence = 1 - math.exp(-abs(severity - boundary) * 2)
    return AgentOutput(agent="risk_agent", ticker=ticker, dimension="risk", label=label,
        confidence=confidence, citations=[citation], evidence=[
        f"Position {position:.1%}; profile single-stock limit {limit:.1%}; largest equity holding {summary['top_equity_weight']:.1%}.",
        f"Equity HHI {summary['equity_hhi']:.3f} uses normalized equity holdings; equity allocation {summary['equity_weight']:.1%}; cash {summary['cash_weight']:.1%}.",
        f"Largest equity sector {summary['largest_equity_sector_weight']:.1%} of the entire portfolio; demo sector limit {SECTOR_LIMIT:.0%}.",
        f"Total HHI {summary['total_hhi']:.3f} includes cash and is descriptive, not an equity-risk score.",
        f"Allocation-policy distance strength {confidence:.1%}; not a probability of losses. Equity HHI guard applies above {MIN_EQUITY_FOR_HHI_GUARD:.0%} equity allocation."])


def what_if(profile, ticker, action):
    """Illustrative trade capped at five percentage points, funded from cash.

    No prices, returns or transaction costs are modeled. The proposal respects
    position/sector limits and does not add to the largest position in an already
    concentrated equity sleeve. REDUCE is one step, not a complete rebalance.
    """
    before = portfolio_weights(profile)
    after = dict(before)
    summary_before = _allocation_summary(before)
    change = 0.0
    if action in {"BUY", "ACCUMULATE"}:
        sector = SECTORS.get(ticker, "Other")
        sector_room = max(0, SECTOR_LIMIT - summary_before["sector_weights"].get(sector, 0))
        hhi_guard = (summary_before["equity_weight"] >= MIN_EQUITY_FOR_HHI_GUARD
                     and summary_before["equity_hhi"] > EQUITY_HHI_LIMIT
                     and ticker == summary_before["top_equity_ticker"])
        change = 0 if hhi_guard else min(.05, after.get("CASH", 0), sector_room,
                                         max(0, profile.max_single_stock_pct - after.get(ticker, 0)))
    elif action == "REDUCE":
        change = -min(.05, after.get(ticker, 0))
    after[ticker] = after.get(ticker, 0) + change
    after["CASH"] = after.get("CASH", 0) - change
    summary_after = _allocation_summary(after)
    result = {"holdings_before": before, "holdings_after": after, "trade_weight": change,
              "hhi_before": summary_before["total_hhi"], "hhi_after": summary_after["total_hhi"],
              "top_holding_before": summary_before["top_equity_weight"],
              "top_holding_after": summary_after["top_equity_weight"]}
    for name in ("total_hhi", "equity_hhi", "cash_weight", "equity_weight", "largest_equity_sector_weight"):
        result[f"{name}_before"] = summary_before[name]
        result[f"{name}_after"] = summary_after[name]
    result["what_if_description"] = "Illustrative trade up to 5 percentage points, capped by cash, position and sector limits; costs and returns excluded."
    return result
