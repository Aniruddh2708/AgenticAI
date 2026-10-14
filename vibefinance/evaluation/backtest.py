"""Disclosed synthetic evaluations with point-in-time inputs and explicit targets."""

from collections import Counter, defaultdict
from functools import lru_cache

import numpy as np
import pandas as pd

from vibefinance.agents.base import Citation, UserProfile
from vibefinance.agents.momentum_agent import analyze
from vibefinance.config import SEED, TICKERS


DEFAULT_SEEDS = tuple(range(SEED, SEED + 12))
HORIZON = 30


def _synthetic_market(ticker, seed, days, dates=None):
    """Independent lognormal increments without the application's demo injections.

    The constant drift is disclosed. Documents use an independent RNG stream,
    and cannot encode these future price increments.
    """
    streams = np.random.SeedSequence([seed, TICKERS.index(ticker), 117]).spawn(4)
    return_rng, opening_rng, spread_rng, volume_rng = [np.random.default_rng(stream) for stream in streams]
    returns = return_rng.normal(.0003, .012, days)
    close = (1000 + TICKERS.index(ticker) * 300) * np.exp(np.cumsum(returns))
    opening = np.r_[close[0], close[:-1]] * (1 + opening_rng.normal(0, .002, days))
    spread = spread_rng.uniform(.002, .018, days)
    frame = pd.DataFrame({
        "date": dates if dates is not None else pd.bdate_range("1990-01-01", periods=days),
        "open": opening, "high": np.maximum(opening, close) * (1 + spread),
        "low": np.minimum(opening, close) * (1 - spread), "close": close,
        "volume": volume_rng.integers(700_000, 1_300_000, days).astype(float),
    })
    frame.attrs.update(mode="synthetic_evaluation", source_id=f"evaluation:{ticker}:seed:{seed}", seed=seed)
    return frame


def _intervals(rows, names, *, repetitions=1000):
    """Bootstrap entire seed clusters; these intervals describe simulations only."""
    seeds = sorted({row["seed"] for row in rows})
    if not rows or len(seeds) < 2:
        return {name: None for name in names}
    sums = np.array([[sum(row[name] for row in rows if row["seed"] == seed)
                      for name in names] for seed in seeds], dtype=float)
    counts = np.array([sum(row["seed"] == seed for row in rows) for seed in seeds])
    rng = np.random.default_rng(SEED + 739)
    indices = rng.integers(0, len(seeds), (repetitions, len(seeds)))
    means = sums[indices].sum(axis=1) / counts[indices].sum(axis=1)[:, None]
    return {name: {"low": float(np.quantile(means[:, n], .025)),
                   "high": float(np.quantile(means[:, n], .975)), "level": .95,
                   "method": "percentile bootstrap of independent seed clusters"}
            for n, name in enumerate(names)}


@lru_cache(maxsize=4)
def backtest(seeds=DEFAULT_SEEDS, days=600):
    """30-session forecasts on independent uninjected synthetic market paths.

    Probabilities use Laplace-smoothed observed up rates for the current label,
    fitted only on completed earlier windows on the same path. These small
    prequential models do not calibrate personalized recommendation confidence.
    """
    if not seeds or len(set(seeds)) != len(seeds) or days < 90:
        raise ValueError("Need distinct seeds and at least 90 sessions per path")
    rows = []
    abstained = 0
    probability_samples = []
    # Separate synthetic calendars preserve uniqueness for clients using
    # (ticker, as_of) as the identifier. These are not real historical dates.
    dates = pd.bdate_range("1990-01-01", periods=days * len(seeds))
    for path, seed in enumerate(seeds):
        random_rng = np.random.default_rng(np.random.SeedSequence([seed, 319]))
        for ticker in TICKERS:
            frame = _synthetic_market(ticker, seed, days, dates[path * days:(path + 1) * days])
            counts = defaultdict(lambda: [0, 0])
            unconditional = [0, 0]
            for end in range(60, days - HORIZON + 1, HORIZON):
                input_frame = frame.iloc[:end].copy()
                as_of = str(input_frame.date.iloc[-1].date())
                citation = Citation(source_id=frame.attrs["source_id"],
                    doc_title="Independent synthetic evaluation OHLCV", chunk_id=f"evaluation:{seed}:{ticker}:{end}",
                    excerpt=f"{end} simulated sessions through {as_of}; no future observations provided.",
                    score=1, date=as_of)
                out = analyze(ticker, input_frame, citation)
                # Previous non-overlapping 30-session outcomes have matured.
                successes, observations = counts[out.label]
                probability_up = (successes + 1) / (observations + 2)
                unconditional_up = (unconditional[0] + 1) / (unconditional[1] + 2)
                forward = float(frame.close.iloc[end + HORIZON - 1] / frame.close.iloc[end - 1] - 1)
                up = int(forward > 0)
                baseline_random = bool(random_rng.integers(0, 2))
                sample = {"seed": seed, "ticker": ticker, "as_of": as_of,
                    "target_end": str(frame.date.iloc[end + HORIZON - 1].date()),
                    "input_sessions": end, "label": out.label, "forward_return": forward,
                    "confidence": out.confidence, "probability_up": probability_up,
                    "probability_training_samples": observations,
                    "unconditional_probability_up": unconditional_up, "realized_up": up,
                    "brier": (probability_up - up)**2,
                    "unconditional_brier": (unconditional_up - up)**2,
                    "coin_brier": (.5 - up)**2, "always_up_brier": (1 - up)**2,
                    "probability_hit": int((probability_up >= .5) == bool(up)),
                    "random_hit": int(baseline_random == bool(up)), "buy_hold_hit": up}
                probability_samples.append(sample)
                if out.label == "NEUTRAL":
                    abstained += 1
                else:
                    sample["hit"] = int((out.label == "BULLISH") == bool(up))
                    sample["hit_minus_random"] = sample["hit"] - sample["random_hit"]
                    sample["hit_minus_always_up"] = sample["hit"] - up
                    rows.append(sample)
                # Only now is this outcome eligible for the next cutoff.
                counts[out.label][0] += up
                counts[out.label][1] += 1
                unconditional[0] += up
                unconditional[1] += 1
    mean = lambda key, observations=rows: float(np.mean([row[key] for row in observations])) if observations else None
    buckets = []
    for index in range(5):
        low, high = index / 5, (index + 1) / 5
        samples = [r for r in rows if low <= r["probability_up"] < high or
                   (index == 4 and r["probability_up"] == 1)]
        buckets.append({"bucket": f"{low:.1f}–{high:.1f}", "count": len(samples),
            "mean_probability_up": mean("probability_up", samples),
            "realized_up_rate": mean("realized_up", samples)})
    intervals = _intervals(rows, ("hit", "random_hit", "buy_hold_hit", "brier",
                                  "hit_minus_random", "hit_minus_always_up"))
    return {"sample_size": len(rows), "total_windows": len(probability_samples),
        "abstained_neutral_windows": abstained, "independent_seed_count": len(seeds),
        "path_count": len(seeds) * len(TICKERS), "sessions_per_path": days,
        "seed_values": list(seeds), "horizon_sessions": HORIZON,
        "hit_rate": mean("hit"), "random_hit_rate": mean("random_hit"),
        "buy_hold_hit_rate": mean("buy_hold_hit"), "brier_score": mean("brier"),
        "probability_classifier_hit_rate": mean("probability_hit"),
        "baselines": {
            "seeded_random_direction": {"hit_rate": mean("random_hit"),
                "description": "Independent fair coin forecasts on exactly the scored dates."},
            "always_up_direction": {"hit_rate": mean("buy_hold_hit"),
                "brier_score": mean("always_up_brier"),
                "description": "Always predicts a positive return; hit rate is not buy-and-hold P&L."},
            "constant_half_probability": {"brier_score": mean("coin_brier")},
            "prequential_unconditional_probability": {"brier_score": mean("unconditional_brier"),
                "description": "Laplace-smoothed prior up rate from matured windows on the same path."},
        },
        "uncertainty_intervals": {"hit_rate": intervals["hit"],
            "random_hit_rate": intervals["random_hit"], "buy_hold_hit_rate": intervals["buy_hold_hit"],
            "brier_score": intervals["brier"]},
        "paired_hit_rate_differences": {
            "momentum_minus_random": {"difference": mean("hit_minus_random"), "interval": intervals["hit_minus_random"]},
            "momentum_minus_always_up": {"difference": mean("hit_minus_always_up"), "interval": intervals["hit_minus_always_up"]},
        },
        "mean_forward_return_by_label": {label: mean("forward_return", [r for r in rows if r["label"] == label])
                                        for label in sorted({r["label"] for r in rows})},
        "calibration": buckets, "rows": rows,
        "calibration_definition": {
            "target": "Probability that close rises over the next 30 trading sessions.",
            "method": "Per-path prequential empirical up rate conditional on momentum label; Beta(1,1) smoothing.",
            "training": "Only completed prior windows; no observations from the forecast window.",
            "confidence": "The original confidence field is momentum signal strength, not this probability or recommendation success probability.",
            "brier_sample": "Same non-neutral windows as hit_rate and calibration; neutral windows are separately counted as abstentions.",
        },
        "limitations": "Independent synthetic prices with constant daily log-return drift 0.0003 and volatility 0.012; no injected demo trends or predictive advantage. "
            "30 trading sessions, not calendar days. Non-overlapping targets share rolling input histories; 95% intervals resample whole seed clusters and describe simulation variability only. "
            "Neutral momentum labels abstain from direction scoring. Technical direction only; excludes personalized actions and historical fundamentals. "
            "Probability calibration is a small prequential empirical model, not final recommendation confidence. Synthetic calendar blocks are row identifiers, not real history. "
            "Baseline hit rates are forecasts on identical scored dates, not trading returns; no demonstrated investment edge."}


def _policy_profiles(ticker):
    return [
        UserProfile(user_id="evaluation_concentrated", name="Synthetic concentrated profile",
            risk_tolerance="conservative", horizon_months=120, holdings={ticker: .45, "CASH": .55},
            max_single_stock_pct=.15),
        UserProfile(user_id="evaluation_cash", name="Synthetic cash profile",
            risk_tolerance="moderate", horizon_months=36, holdings={"CASH": 1}, max_single_stock_pct=.25),
        UserProfile(user_id="evaluation_moderate", name="Synthetic diversified profile",
            risk_tolerance="moderate", horizon_months=36,
            holdings={name: .08 for name in TICKERS}, max_single_stock_pct=.25),
    ]


def _dated_documents(ticker, seed, dates):
    """Synthetic publications independent of market-price RNG and future returns."""
    from vibefinance.rag.ingest import Chunk

    rng = np.random.default_rng(np.random.SeedSequence([seed, TICKERS.index(ticker), 991]))
    documents = []
    for n in range(29, len(dates), 60):
        publication = str(dates[n].date())
        positive = bool(rng.integers(0, 2))
        revenue_change = int(rng.integers(1, 16))
        margin = int(rng.integers(10, 25))
        text = (f"Synthetic financial results: revenue {'grew' if positive else 'declined'} {revenue_change}% year on year. "
                f"Operating margin was {margin}%. "
                + ("Management raised growth guidance; profit increased and debt declined." if positive else
                   "Management cut growth guidance; profit declined. Regulatory risk remains unresolved."))
        source_id = f"synthetic-replay:{seed}:{ticker}:{n}"
        documents.append(Chunk(source_id=source_id, ticker=ticker, doc_type="results", date=publication,
            title=f"SYNTHETIC dated results ({publication})", chunk_id=f"{source_id}:0", text=text))
        news_id = f"{source_id}:news"
        documents.append(Chunk(source_id=news_id, ticker=ticker, doc_type="news", date=publication,
            title=f"SYNTHETIC dated news ({publication})", chunk_id=f"{news_id}:0",
            text="Synthetic news: profit growth and supportive guidance." if positive else
                 "Synthetic news: weak profit and cut guidance; uncertainty persists."))
    return documents


async def policy_evaluation(seeds=(SEED, SEED + 1), days=240):
    """Point-in-time full-agent replay plus constraints, not a strategy backtest."""
    from vibefinance.orchestrator import analyze as run_pipeline
    from vibefinance.rag.retriever import Retriever

    if not seeds or len(set(seeds)) != len(seeds) or days < 90:
        raise ValueError("Need distinct seeds and at least 90 sessions per path")
    rows = []
    for seed in seeds:
        for ticker in TICKERS:
            frame = _synthetic_market(ticker, seed, days)
            publications = _dated_documents(ticker, seed, frame.date)
            for end in range(60, days - HORIZON + 1, 60):
                as_of = str(frame.date.iloc[end - 1].date())
                available = [chunk for chunk in publications if chunk.date <= as_of]
                # Later publications never enter the index or an agent's input.
                latest = {kind: max((c for c in available if c.doc_type == kind),
                                   key=lambda c: c.date, default=None) for kind in ("results", "news")}
                retriever = Retriever([c for c in latest.values() if c is not None], embeddings=False)
                for profile in _policy_profiles(ticker):
                    missing = profile.user_id == "evaluation_concentrated" and end == 60
                    session = await run_pipeline(ticker, profile, retriever=retriever,
                        frame=frame.iloc[:end].copy(), missing_filing=missing, persist=False, as_of=as_of)
                    recommendation = session["recommendation"]
                    outputs = recommendation["agent_outputs"]
                    risk = next(out for out in outputs if out["dimension"] == "risk")
                    citations = [source for source in session["sources"] if source["source_id"].startswith("synthetic-replay:")]
                    checks = {"all_five_agents_present": {out["dimension"] for out in outputs} ==
                              {"momentum", "volume", "sentiment", "filings", "risk"},
                              "sources_published_by_cutoff": all(source["date"] <= as_of for source in citations)}
                    if profile.user_id == "evaluation_concentrated":
                        checks["concentration_override"] = recommendation["action"] in {"REDUCE", "HOLD"}
                    if profile.user_id == "evaluation_cash":
                        checks["cash_not_equity_high_risk"] = risk["label"] != "RISK_HIGH"
                    rows.append({"seed": seed, "ticker": ticker, "as_of": as_of,
                        "user_id": profile.user_id, "action": recommendation["action"],
                        "signal_strength": recommendation["confidence"], "missing_filing": missing,
                        "document_dates": [source["date"] for source in citations],
                        "forward_return": float(frame.close.iloc[end + HORIZON - 1] / frame.close.iloc[end - 1] - 1),
                        "failed_agent_count": sum(out["status"] == "failed" for out in outputs),
                        "checks": checks})
    check_names = sorted({name for row in rows for name in row["checks"]})
    return {"sample_size": len(rows), "rows": rows,
        "independent_seed_count": len(seeds), "distinct_market_windows": len(rows) // 3,
        "action_counts": dict(sorted(Counter(row["action"] for row in rows).items())),
        "policy_checks": {name: {"evaluated": sum(name in row["checks"] for row in rows),
                                  "passed": sum(row["checks"].get(name, False) for row in rows),
                                  "violations": sum(name in row["checks"] and not row["checks"][name] for row in rows)}
                          for name in check_names},
        "mean_forward_return_by_action": {action: float(np.mean([row["forward_return"] for row in rows if row["action"] == action]))
            for action in sorted({row["action"] for row in rows})},
        "limitations": "Full five-agent replay on synthetic dated financial/news fixtures generated independently of future synthetic prices. "
            "Only publications available at each cutoff are indexed. Missing-filings cases test concentration precedence. "
            "Three static synthetic profiles share each market outcome; rows are correlated and not independent trades. "
            "Action-conditioned forward returns are descriptive only, not a trading strategy, causal policy benefit, action accuracy or investment alpha. "
            "No transaction simulation, costs, portfolio revaluation, real historical filings, or recommendation-confidence probability calibration. "
            "The application intentionally simulates an ITC sentiment outage even in this replay."}
