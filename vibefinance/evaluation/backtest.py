from functools import lru_cache

import numpy as np

from vibefinance.agents.base import Citation
from vibefinance.agents.momentum_agent import analyze
from vibefinance.config import SEED, TICKERS
from vibefinance.data.market_sim import generate_market


@lru_cache(maxsize=1)
def backtest():
    """Walk-forward technical signal only, without future filings or prices in inputs.

    Uses non-overlapping 30-session windows per ticker. This is not a backtest of
    personalized recommendations: those would require historical point-in-time filings.
    """
    rows = []
    rng = np.random.default_rng(SEED)
    dummy = Citation(source_id="evaluation", doc_title="Simulated walk-forward input", chunk_id="evaluation:0", excerpt="Simulated OHLCV", score=1)
    for ticker in TICKERS:
        frame = generate_market(ticker)
        for end in range(60, len(frame) - 30 + 1, 30):
            out = analyze(ticker, frame.iloc[:end], dummy)
            if out.label == "NEUTRAL":
                continue
            forward = float(frame.close.iloc[end + 29] / frame.close.iloc[end - 1] - 1)
            up = forward > 0
            predicted_up = out.label == "BULLISH"
            # Convert signal-strength confidence to a direction probability.
            probability = .5 + out.confidence/2 if predicted_up else .5 - out.confidence/2
            rows.append({"ticker": ticker, "as_of": str(frame.date.iloc[end - 1].date()),
                "label": out.label, "forward_return": forward, "confidence": out.confidence,
                "probability_up": probability, "realized_up": int(up),
                "hit": int(predicted_up == up), "random_hit": int(bool(rng.integers(0, 2)) == up),
                "buy_hold_hit": int(up)})
    if not rows:
        return {"sample_size": 0, "rows": [], "calibration": [], "hit_rate": None}
    buckets = []
    for low in np.arange(0, 1, .2):
        items = [r for r in rows if low <= r["probability_up"] < low + .2 or
                 (low > .79 and r["probability_up"] == 1)]
        buckets.append({"bucket": f"{low:.1f}–{low+.2:.1f}", "count": len(items),
            "mean_probability_up": float(np.mean([r["probability_up"] for r in items])) if items else None,
            "realized_up_rate": float(np.mean([r["realized_up"] for r in items])) if items else None})
    return {"sample_size": len(rows), "hit_rate": float(np.mean([r["hit"] for r in rows])),
        "random_hit_rate": float(np.mean([r["random_hit"] for r in rows])),
        "buy_hold_hit_rate": float(np.mean([r["buy_hold_hit"] for r in rows])),
        "brier_score": float(np.mean([(r["probability_up"] - r["realized_up"])**2 for r in rows])),
        "mean_forward_return_by_label": {label: float(np.mean([r["forward_return"] for r in rows if r["label"] == label]))
                                        for label in {r["label"] for r in rows}},
        "calibration": buckets, "rows": rows,
        "limitations": "Synthetic prices; small sample; 30 trading sessions, not calendar days; non-overlapping windows within ticker, cross-ticker correlation possible. Technical direction only; excludes personalized actions and historical fundamentals. Baseline hit rates use the same dates and are not trading returns."}
