import math

from vibefinance.agents.base import AgentOutput
from vibefinance.config import SECTORS


def portfolio_weights(profile):
    weights = {k: v for k, v in profile.holdings.items() if v > 0}
    weights["CASH"] = weights.get("CASH", 0) + max(0, 1 - sum(weights.values()))
    return weights


def hhi(weights):
    return sum(w * w for w in weights.values())


def sector_weights(weights):
    result = {}
    for ticker, weight in weights.items():
        sector = SECTORS.get(ticker, "Cash" if ticker == "CASH" else "Other")
        result[sector] = result.get(sector, 0) + weight
    return result


def analyze(ticker, profile, citation):
    weights = portfolio_weights(profile)
    concentration = hhi(weights)
    position = weights.get(ticker, 0)
    sectors = sector_weights(weights)
    equity_sector = max((v for k, v in sectors.items() if k != "Cash"), default=0)
    limit = profile.max_single_stock_pct
    severity = max(position / limit, concentration / .4, equity_sector / .5)
    label = "RISK_HIGH" if position > limit or severity > 1.25 else "RISK_MED" if severity > .75 else "RISK_LOW"
    boundary = 1.25 if label == "RISK_HIGH" else .75
    confidence = 1 - math.exp(-abs(severity - boundary) * 2)
    return AgentOutput(agent="risk_agent", ticker=ticker, dimension="risk", label=label,
        confidence=confidence, citations=[citation], evidence=[
        f"Position {position:.1%}; profile single-stock limit {limit:.1%}.",
        f"Portfolio HHI {concentration:.3f} including cash; largest equity sector {equity_sector:.1%}.",
        f"Risk severity {severity:.3f}; high threshold 1.25 or position above limit."])


def what_if(profile, ticker, action):
    """Illustrative 5%-point trade, funded from cash; preserve total portfolio weight."""
    before = portfolio_weights(profile)
    after = dict(before)
    change = 0.0
    if action in {"BUY", "ACCUMULATE"}:
        change = min(.05, after.get("CASH", 0), max(0, profile.max_single_stock_pct - after.get(ticker, 0)))
    elif action == "REDUCE":
        change = -min(.05, after.get(ticker, 0))
    after[ticker] = after.get(ticker, 0) + change
    after["CASH"] = after.get("CASH", 0) - change
    return {"holdings_before": before, "holdings_after": after, "trade_weight": change,
            "hhi_before": hhi(before), "hhi_after": hhi(after),
            "top_holding_before": max((v for k, v in before.items() if k != "CASH"), default=0),
            "top_holding_after": max((v for k, v in after.items() if k != "CASH"), default=0)}
