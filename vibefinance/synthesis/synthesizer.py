from itertools import combinations

from vibefinance.agents.base import Recommendation
from vibefinance.agents.risk_agent import (EQUITY_HHI_LIMIT, MIN_EQUITY_FOR_HHI_GUARD,
                                          SECTOR_LIMIT, portfolio_summary)
from vibefinance.config import DISCLAIMER, SECTORS, WEIGHTS

SIGNS = {"BULLISH": 1, "BEARISH": -1, "SPIKE_UP": 1, "SPIKE_DOWN": -1,
         "POSITIVE": 1, "NEGATIVE": -1, "SUPPORTIVE": 1, "CAUTIONARY": -1}


def vote(outputs):
    score = confidence = 0.0
    eligible = []
    for out in outputs:
        if out.dimension not in WEIGHTS or out.status == "failed":
            continue
        weight = WEIGHTS[out.dimension] * (.5 if out.status == "degraded" else 1)
        score += weight * out.confidence * SIGNS.get(out.label, 0)
        confidence += weight * out.confidence
        if SIGNS.get(out.label, 0) and out.confidence > 0:
            eligible.append(out)
    # Full denominator is retained so missing evidence cannot inflate certainty.
    conflicts = [f"{a.dimension} {a.label} opposes {b.dimension} {b.label}; evidence is inconsistent."
                 for a, b in combinations(eligible, 2)
                 if SIGNS[a.label] * SIGNS[b.label] < 0]
    penalty = 1 - min(.5, .15 * len(conflicts))
    return score, confidence, confidence * penalty, conflicts


def synthesize(profile, ticker, outputs, volatility=0.0, profile_citation=None):
    score, raw_conf, confidence, conflicts = vote(outputs)
    valid = [out for out in outputs if out.status != "failed" and out.citations and out.confidence > 0]
    sufficient = any(out.dimension == "momentum" for out in valid) and any(out.dimension == "filings" for out in valid)
    notes = []
    basis = "market_evidence"
    rules = []
    weight = profile.holdings.get(ticker, 0)
    portfolio = portfolio_summary(profile)
    # The profile is known even if a market source or risk worker fails. Reducing
    # an oversized allocation is a portfolio policy, not a bearish price claim.
    if weight > profile.max_single_stock_pct:
        action = "REDUCE"
        basis = "portfolio_policy"
        rules.append("single_stock_limit")
        notes.append(f"Concentration override: {weight:.0%} position exceeds your {profile.max_single_stock_pct:.0%} limit; consider gradual rebalancing.")
        if not sufficient:
            notes.append("Market evidence is incomplete; this reduction addresses the known allocation limit and makes no claim about future price direction.")
    elif not sufficient:
        action = "WATCH"
        basis = "incomplete_evidence"
        notes.append("Price trend and cited fundamentals are both required for an actionable demo signal; evidence is incomplete.")
    elif conflicts:
        action = "HOLD"
        basis = "conflict_resolution"
        notes.append("Conflicting signals pause new purchases until the disagreement is resolved.")
    elif score < -.25:
        action = "REDUCE" if weight > 0 else "AVOID"
    elif profile.risk_tolerance == "conservative":
        action = "ACCUMULATE" if score > .65 and volatility < .30 else "HOLD"
        notes.append(f"Conservative policy caps upside action at ACCUMULATE; annualized volatility {volatility:.1%}, limit 30%.")
    elif profile.risk_tolerance == "moderate":
        action = "ACCUMULATE" if score > .30 else "HOLD"
        notes.append(f"Moderate policy uses a staged entry above score 0.30 over your {profile.horizon_months}-month horizon.")
    else:
        action = "BUY" if score > .30 else "WATCH"
        notes.append("Aggressive policy accepts a directional entry above score 0.30, subject to your position limit.")

    if action in {"BUY", "ACCUMULATE"}:
        sector = SECTORS.get(ticker, "Other")
        sector_weight = portfolio["sector_weights"].get(sector, 0)
        if weight >= profile.max_single_stock_pct:
            action = "HOLD"
            rules.append("single_stock_limit")
            notes.append("Your position is at its single-stock limit; do not increase it.")
        elif sector_weight >= SECTOR_LIMIT:
            action = "HOLD"
            rules.append("sector_limit")
            notes.append(f"{sector} is {sector_weight:.0%} of the portfolio, at or above the {SECTOR_LIMIT:.0%} demo sector limit; pause purchases in this sector.")
        elif (portfolio["equity_weight"] >= MIN_EQUITY_FOR_HHI_GUARD
              and portfolio["equity_hhi"] > EQUITY_HHI_LIMIT
              and ticker == portfolio["top_equity_ticker"]):
            action = "HOLD"
            rules.append("equity_concentration")
            notes.append(f"Equity HHI {portfolio['equity_hhi']:.3f} exceeds the {EQUITY_HHI_LIMIT:.2f} demo guardrail with {portfolio['equity_weight']:.0%} in equities; do not add to the largest position.")
        elif portfolio["cash_weight"] <= 0:
            action = "HOLD" if weight else "WATCH"
            rules.append("cash_funding")
            notes.append("No cash is available for the illustrated purchase; a separate funded reallocation would be required.")
        if rules:
            basis = "portfolio_policy"

    # Horizon controls entry suitability; behavior controls corroboration, not
    # predictions. Neither changes the market strength displayed as confidence.
    if action in {"BUY", "ACCUMULATE"} and profile.horizon_months <= 6:
        horizon_volatility_limit = .60 if profile.risk_tolerance == "aggressive" else .30
        if volatility > horizon_volatility_limit:
            action = "HOLD" if weight else "WATCH"
            basis = "portfolio_policy"
            rules.append("short_horizon_volatility")
            notes.append(f"A horizon of six months or less and annualized volatility {volatility:.1%} exceed the {horizon_volatility_limit:.0%} demo suitability guardrail for {profile.risk_tolerance} profiles; pause entry.")
    if action in {"BUY", "ACCUMULATE"} and profile.behavior.get("chases_momentum"):
        confirmed = any(out.dimension == "filings" and out.label == "SUPPORTIVE"
                        and out.confidence >= .5 and out.status == "ok" for out in valid)
        if not confirmed:
            action = "HOLD" if weight else "WATCH"
            basis = "portfolio_policy"
            rules.append("momentum_chasing_confirmation")
            notes.append("Momentum-chasing entry guard: require a cited, non-degraded supportive filing with strength at least 50% before increasing exposure.")
    if profile.horizon_months <= 6:
        notes.append("A horizon of six months or less makes drawdowns harder to recover; avoid relying on one short-term signal.")
    if profile.behavior.get("chases_momentum"):
        notes.append("Momentum may match your FOMO pattern; wait for confirmation and set a position limit before acting.")
    if profile.behavior.get("panic_sell_count", 0) >= 2:
        notes.append("Your panic-selling history suggests reviewing a gradual rebalance rather than making an abrupt exit.")
    if profile.behavior.get("avg_hold_days", 365) < 30:
        notes.append("Your average holding period is under 30 days; allow time to reassess evidence before trading again.")
    if basis == "portfolio_policy":
        notes.append("Displayed confidence measures market evidence strength; it is neither a probability of returns nor certainty that a portfolio-policy action will succeed.")
    citations = {c.chunk_id: c for out in outputs if out.status != "failed" for c in out.citations}
    if profile_citation is not None:
        citations[profile_citation.chunk_id] = profile_citation
    reasoning = [f"1. The displayed market input and source passages produce {len(valid)} usable agent outputs."]
    for n, out in enumerate(outputs, 2):
        refs = ", ".join(c.source_id for c in out.citations)
        explanation = "; ".join(out.evidence[:1]) if out.evidence else out.degraded_reason or "No usable evidence."
        reasoning.append(f"{n}. {out.dimension}: {out.label} ({out.confidence:.1%}). {explanation}" + (f" [Sources: {refs}]" if refs else " [Unavailable evidence]"))
    reasoning.append(f"7. Weighted score {score:.3f}; uncalibrated market evidence strength {raw_conf:.1%} → {confidence:.1%} after {len(conflicts)} opposing pair(s); not a success probability.")
    reasoning.append(f"8. Profile policy selects {action}. " + " ".join(notes) +
                     (f" [Source: {profile_citation.source_id}]" if profile_citation is not None else ""))
    return Recommendation(user_id=profile.user_id, ticker=ticker, action=action, confidence=confidence,
        decision_basis=basis, confidence_kind="evidence_strength", policy_rules=rules,
        reasoning_chain=reasoning, citations=list(citations.values()), agent_outputs=outputs,
        conflicts=conflicts, personalization_notes=notes, disclaimer=DISCLAIMER)
