"""Small, auditable price research models; never changes portfolio actions.

Selection sees chronological validation only. Test labels are consumed by a
separate evaluation operation after a frozen specification has been saved.
No simulated data, price-level R-squared, or test-driven hyperparameter search.
"""
from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd

from vibefinance.evaluation.uncertainty import residual_quantile


FEATURES = ("return_1", "return_5", "return_20", "return_60", "volatility_20",
            "volatility_60", "dma_ratio", "rsi", "macd_hist", "volume_ratio")
PROBABILITY_GRID = (.01, .1, 1.0)
RETURN_GRID = (.1, 1.0, 10.0)


@dataclass(frozen=True)
class Protocol:
    train_start: str = "2010-01-01"
    train_end: str = "2015-12-31"
    validation_start: str = "2016-01-01"
    validation_end: str = "2017-12-31"
    calibration_start: str = "2018-01-01"
    calibration_end: str = "2018-12-31"
    test_start: str = "2019-01-01"
    test_end: str = "2020-12-31"
    horizon_sessions: int = 30
    interval_alpha: float = .1

    def validate(self):
        dates = [pd.Timestamp(getattr(self, key)) for key in (
            "train_start", "train_end", "validation_start", "validation_end", "calibration_start",
            "calibration_end", "test_start", "test_end")]
        if any(a >= b for a, b in zip(dates, dates[1:])):
            raise ValueError("Research split dates must be strictly chronological")
        if self.horizon_sessions != 30 or not 0 < self.interval_alpha < 1:
            raise ValueError("This protocol supports 30-session targets and valid interval alpha")


def features(frame):
    """Only current/past adjusted close and volume; no centered/full-data fits."""
    c, v = frame.close.astype(float), frame.volume.astype(float)
    r = c.pct_change(fill_method=None)
    result = pd.DataFrame(index=frame.index)
    for n in (1, 5, 20, 60):
        result[f"return_{n}"] = c.pct_change(n, fill_method=None)
    for n in (20, 60):
        result[f"volatility_{n}"] = r.rolling(n).std(ddof=0)
    result["dma_ratio"] = c.rolling(20).mean() / c.rolling(50).mean() - 1
    d = c.diff()
    gain = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    result["rsi"] = (gain / (gain + loss)).fillna(.5) * 2 - 1
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    result["macd_hist"] = (macd - macd.ewm(span=9, adjust=False).mean()) / c
    # Lag baseline volume to exclude today's volume from its own reference.
    result["volume_ratio"] = np.log((v.rolling(5).mean() + 1) /
                                    (v.shift(1).rolling(30).mean() + 1))
    return result[list(FEATURES)]


def observations(frames, horizon=30):
    rows = []
    for ticker, frame in sorted(frames.items()):
        x = features(frame)
        out = x.copy()
        out["as_of"] = frame.date.to_numpy()
        out["target_end"] = frame.date.shift(-horizon).to_numpy()
        out["forward_return"] = frame.close.shift(-horizon) / frame.close - 1
        out["ticker"] = ticker
        out["session_index"] = np.arange(len(frame))
        # These are the original heuristic's terms, evaluated causally.
        score = (.45 * np.tanh(out.return_20 * 12)
                 + .35 * np.tanh(out.dma_ratio * 30)
                 + .15 * np.tanh(out.macd_hist * 500) + .05 * out.rsi)
        out["momentum_label"] = np.where(score > .15, "BULLISH",
                                        np.where(score < -.15, "BEARISH", "NEUTRAL"))
        out = out.dropna(subset=[*FEATURES, "target_end", "forward_return"])
        out["up"] = (out.forward_return > 0).astype(int)
        rows.append(out)
    if not rows:
        raise ValueError("No historical observations")
    return pd.concat(rows, ignore_index=True).sort_values(["as_of", "ticker"]).reset_index(drop=True)


def period(rows, start, end, horizon=30):
    """Non-overlapping targets per ticker, purged at the period's right edge."""
    subset = rows[(rows.as_of >= pd.Timestamp(start)) & (rows.target_end <= pd.Timestamp(end))]
    parts = [group.sort_values("as_of").iloc[::horizon] for _, group in subset.groupby("ticker")]
    return pd.concat(parts).sort_values(["as_of", "ticker"]).reset_index(drop=True) if parts else subset


def matured_before(rows, cutoff):
    return rows[rows.target_end < pd.Timestamp(cutoff)].copy()


def training_rows(rows, protocol, cutoff):
    initial = (rows.as_of >= pd.Timestamp(protocol.train_start)) & (rows.target_end <= pd.Timestamp(protocol.train_end))
    previous_validation = ((rows.as_of >= pd.Timestamp(protocol.validation_start)) &
                           (rows.target_end <= pd.Timestamp(protocol.validation_end)))
    return rows[(initial | previous_validation) & (rows.target_end < pd.Timestamp(cutoff))].copy()


def frame_fingerprints(frames):
    return {ticker: hashlib.sha256(frame.to_json(orient="records", date_format="iso", double_precision=15).encode()).hexdigest()
            for ticker, frame in sorted(frames.items())}


def _sigmoid(z):
    return np.exp(-np.logaddexp(0, -z))


def fit(rows, probability_penalty, return_penalty):
    if len(rows) < 120 or rows.up.nunique() != 2:
        raise ValueError("Need at least 120 matured training rows with both outcomes")
    x = rows[list(FEATURES)].to_numpy(float)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-10] = 1
    x = np.c_[np.ones(len(x)), np.clip((x - mean) / scale, -10, 10)]
    y = rows.up.to_numpy(float)
    penalty = np.diag([0] + [probability_penalty] * len(FEATURES))
    beta = np.zeros(x.shape[1])
    beta[0] = np.log((y.sum() + 1) / (len(y) - y.sum() + 1))
    for _ in range(80):
        p = _sigmoid(x @ beta)
        gradient = x.T @ (p - y) / len(y) + penalty @ beta
        hessian = (x.T * (p * (1 - p))) @ x / len(y) + penalty + np.eye(x.shape[1]) * 1e-9
        step = np.linalg.solve(hessian, gradient)
        # Backtracking preserves convergence for separated/volatile samples.
        objective = np.mean(np.logaddexp(0, x @ beta) - y * (x @ beta)) + .5 * beta @ penalty @ beta
        rate = 1.0
        while rate > 1e-8:
            candidate = beta - rate * step
            loss = np.mean(np.logaddexp(0, x @ candidate) - y * (x @ candidate)) + .5 * candidate @ penalty @ candidate
            if loss <= objective:
                break
            rate *= .5
        beta = candidate
        if np.max(np.abs(rate * step)) < 1e-8:
            break
    if np.max(np.abs(x.T @ (_sigmoid(x @ beta) - y) / len(y) + penalty @ beta)) > 1e-5:
        raise ValueError("Logistic optimization did not converge")
    ridge = np.diag([0] + [return_penalty] * len(FEATURES))
    returns = rows.forward_return.to_numpy(float)
    coef = np.linalg.solve(x.T @ x / len(x) + ridge, x.T @ returns / len(x))
    labels = {}
    for label in ("BULLISH", "BEARISH", "NEUTRAL"):
        group = rows[rows.momentum_label == label]
        labels[label] = {"probability": float((group.up.sum() + 1) / (len(group) + 2)),
                         "return": float(group.forward_return.mean()) if len(group) else float(returns.mean())}
    return {"mean": mean.tolist(), "scale": scale.tolist(), "logistic": beta.tolist(),
            "ridge": coef.tolist(), "prior_probability": float((y.sum() + 1) / (len(y) + 2)),
            "mean_return": float(returns.mean()), "momentum": labels,
            "training_rows": len(rows), "training_target_end": str(rows.target_end.max().date())}


def predict(model, rows, probability_model="logistic", return_model="ridge"):
    raw = rows[list(FEATURES)].to_numpy(float)
    x = np.c_[np.ones(len(raw)), np.clip((raw - model["mean"]) / model["scale"], -10, 10)]
    probabilities = {
        "logistic": _sigmoid(x @ model["logistic"]),
        "prior": np.full(len(rows), model["prior_probability"]),
        "constant_half": np.full(len(rows), .5), "always_up": np.ones(len(rows)),
        "momentum": np.array([model["momentum"][label]["probability"] for label in rows.momentum_label]),
    }
    returns = {
        "ridge": x @ model["ridge"], "mean": np.full(len(rows), model["mean_return"]),
        "zero": np.zeros(len(rows)),
        "momentum": np.array([model["momentum"][label]["return"] for label in rows.momentum_label]),
    }
    return probabilities[probability_model], returns[return_model]


def metrics(rows, p, r):
    y = rows.up.to_numpy(float)
    target = rows.forward_return.to_numpy(float)
    clipped = np.clip(p, 1e-9, 1 - 1e-9)
    direction = p >= .5
    positive, negative = y == 1, y == 0
    return {"brier": float(np.mean((p - y) ** 2)),
            "log_loss": float(-np.mean(y * np.log(clipped) + (1-y) * np.log1p(-clipped))),
            "accuracy": float(np.mean(direction == y)),
            "balanced_accuracy": float((np.mean(direction[positive]) + np.mean(~direction[negative])) / 2)
                if positive.any() and negative.any() else None,
            "mae_return": float(np.mean(np.abs(r - target))),
            "rmse_return": float(np.sqrt(np.mean((r - target) ** 2))),
            "realized_up_rate": float(y.mean())}


def _summary(rows, results):
    return {"sample_size": len(rows), "as_of_start": str(rows.as_of.min().date()),
            "as_of_end": str(rows.as_of.max().date()), "target_end": str(rows.target_end.max().date()),
            "metrics": {name: metrics(rows, p, r) for name, (p, r) in results.items()}}


def prepare(frames, data, protocol=Protocol()):
    """Expanding yearly validation, then independent interval calibration.

    No held-out test targets or metrics are read by this function. Features are
    computed causally; fitting uses only labels matured before the next boundary.
    """
    protocol.validate()
    rows = observations(frames, protocol.horizon_sessions)
    validation_rows, predictions, folds = [], {}, []
    first, last = pd.Timestamp(protocol.validation_start), pd.Timestamp(protocol.validation_end)
    for year in range(first.year, last.year + 1):
        start = max(first, pd.Timestamp(f"{year}-01-01"))
        end = min(last, pd.Timestamp(f"{year}-12-31"))
        train = training_rows(rows, protocol, start)
        val = period(rows, start, end, protocol.horizon_sessions)
        if len(val) < 10:
            raise ValueError("Too few validation rows in a predeclared fold")
        validation_rows.append(val)
        folds.append({"start": str(start.date()), "end": str(end.date()),
                      "training_rows": len(train), "training_target_end": str(train.target_end.max().date()),
                      "validation_rows": len(val)})
        for penalty in PROBABILITY_GRID:
            model = fit(train, penalty, RETURN_GRID[0])
            p, _ = predict(model, val)
            predictions.setdefault(f"logistic_{penalty}", []).append(p)
        for penalty in RETURN_GRID:
            model = fit(train, PROBABILITY_GRID[0], penalty)
            _, r = predict(model, val)
            predictions.setdefault(f"ridge_{penalty}", []).append(r)
        for name, prob, ret in (("prior", "prior", "mean"), ("momentum", "momentum", "momentum"),
                                 ("constant_half", "constant_half", "zero"), ("always_up", "always_up", "zero")):
            p, r = predict(model, val, prob, ret)
            predictions.setdefault(name + "_p", []).append(p)
            predictions.setdefault(name + "_r", []).append(r)
    val = pd.concat(validation_rows, ignore_index=True)
    pooled = {key: np.concatenate(value) for key, value in predictions.items()}
    probability_candidates = {"prior": pooled["prior_p"], "constant_half": pooled["constant_half_p"],
        **{f"logistic_{penalty}": pooled[f"logistic_{penalty}"] for penalty in PROBABILITY_GRID}}
    return_candidates = {"mean": pooled["prior_r"], "zero": pooled["constant_half_r"],
        **{f"ridge_{penalty}": pooled[f"ridge_{penalty}"] for penalty in RETURN_GRID}}
    # Stable tie preference for the simpler baseline; test scores never select.
    probability_name = min(probability_candidates, key=lambda k: np.mean((probability_candidates[k] - val.up) ** 2))
    return_name = min(return_candidates, key=lambda k: np.mean(np.abs(return_candidates[k] - val.forward_return)))
    probability_penalty = float(probability_name.split("_")[1]) if probability_name.startswith("logistic_") else PROBABILITY_GRID[0]
    return_penalty = float(return_name.split("_")[1]) if return_name.startswith("ridge_") else RETURN_GRID[0]
    training = training_rows(rows, protocol, protocol.calibration_start)
    model = fit(training, probability_penalty, return_penalty)
    p_kind = "logistic" if probability_name.startswith("logistic_") else probability_name
    r_kind = "ridge" if return_name.startswith("ridge_") else return_name
    calibration = period(rows, protocol.calibration_start, protocol.calibration_end, protocol.horizon_sessions)
    if len(calibration) < 20:
        raise ValueError("Need at least 20 independent-period calibration rows")
    _, r = predict(model, calibration, p_kind, r_kind)
    errors = np.sort(np.abs(r - calibration.forward_return.to_numpy(float)))
    # A rank beyond n has no finite supported bound. Never silently clamp it.
    radius = residual_quantile(errors, protocol.interval_alpha)
    candidate_metrics = {name: metrics(val, p, pooled["prior_r"]) for name, p in probability_candidates.items()}
    candidate_metrics.update({name: metrics(val, pooled["prior_p"], r) for name, r in return_candidates.items()})
    selected_metrics = metrics(val, probability_candidates[probability_name], return_candidates[return_name])
    return {"schema_version": 1, "kind": "historical_price_forecast", "protocol": asdict(protocol),
            "features": list(FEATURES), "data": data, "frame_fingerprints": frame_fingerprints(frames), "model": model,
            "selection": {"probability_model": probability_name, "return_model": return_name,
                          "probability_kind": p_kind, "return_kind": r_kind,
                          "probability_penalty": probability_penalty, "return_penalty": return_penalty,
                          "criterion": "Expanding-year validation Brier / return MAE; test never used",
                          "admission": {"passed": False, "reason": "Held-out test not yet evaluated"}},
            "validation": {**_summary(val, {"selected": (probability_candidates[probability_name], return_candidates[return_name])}),
                           "folds": folds, "candidate_metrics": candidate_metrics, "selected_metrics": selected_metrics},
            "calibration": {"sample_size": len(calibration), "as_of_start": str(calibration.as_of.min().date()),
                            "target_end": str(calibration.target_end.max().date()), "interval_radius": radius,
                            "nominal_coverage": 1 - protocol.interval_alpha,
                            "method": "Split absolute-residual quantile on separate calibration period; no exchangeability guarantee in markets"},
            "model_readiness": "research_only"}


def fingerprint(frozen):
    return hashlib.sha256(json.dumps(frozen, sort_keys=True, allow_nan=False).encode()).hexdigest()


def evaluate(frames, frozen):
    """One fixed holdout; shared-calendar-quarter bootstrap, never IID tickers."""
    protocol = Protocol(**frozen["protocol"])
    protocol.validate()
    if frame_fingerprints(frames) != frozen["frame_fingerprints"]:
        raise ValueError("Historical frames changed after selection was frozen")
    if frozen["features"] != list(FEATURES):
        raise ValueError("Feature specification changed after selection was frozen")
    rows = period(observations(frames), protocol.test_start, protocol.test_end)
    if len(rows) < 20 or rows.ticker.nunique() != len(frames):
        raise ValueError("Insufficient held-out observations for the declared universe")
    model, selection = frozen["model"], frozen["selection"]
    if model["training_target_end"] >= protocol.calibration_start:
        raise ValueError("Training labels overlap calibration/test")
    results = {"selected": predict(model, rows, selection["probability_kind"], selection["return_kind"])}
    for name, p, r in (("prior_mean", "prior", "mean"), ("constant_half_zero", "constant_half", "zero"),
                       ("always_up_zero", "always_up", "zero"), ("momentum", "momentum", "momentum")):
        results[name] = predict(model, rows, p, r)
    summary = _summary(rows, results)
    p, r = results["selected"]
    y, target = rows.up.to_numpy(float), rows.forward_return.to_numpy(float)
    blocks = rows.as_of.dt.to_period("Q").astype(str).to_numpy()
    unique_blocks = sorted(set(blocks))
    rng = np.random.default_rng(2708)
    draws = rng.integers(0, len(unique_blocks), (2000, len(unique_blocks)))
    paired = {}
    for baseline in ("prior_mean", "constant_half_zero", "momentum"):
        bp, br = results[baseline]
        for loss, delta in (("brier", (p-y)**2 - (bp-y)**2),
                            ("mae_return", np.abs(r-target) - np.abs(br-target))):
            sums = np.array([delta[blocks == b].sum() for b in unique_blocks])
            counts = np.array([(blocks == b).sum() for b in unique_blocks])
            boot = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
            paired[f"selected_minus_{baseline}_{loss}"] = {"difference": float(delta.mean()),
                "low": float(np.quantile(boot, .025)), "high": float(np.quantile(boot, .975)),
                "level": .95, "calendar_quarter_blocks": len(unique_blocks)}
    buckets = []
    for n in range(5):
        mask = (p >= n/5) & ((p < (n+1)/5) if n < 4 else (p <= 1))
        buckets.append({"bucket": f"{n/5:.1f}-{(n+1)/5:.1f}", "count": int(mask.sum()),
                        "mean_probability_up": float(p[mask].mean()) if mask.any() else None,
                        "realized_up_rate": float(y[mask].mean()) if mask.any() else None})
    radius = frozen["calibration"]["interval_radius"]
    coverage = float(np.mean(np.abs(r-target) <= radius))
    neutral = rows.momentum_label.to_numpy() == "NEUTRAL"
    nonneutral = ~neutral
    summary.update({"calibration": buckets, "uncertainty": paired,
        "interval": {"nominal_coverage": 1-protocol.interval_alpha, "observed_coverage": coverage,
                     "radius_return": radius, "method": frozen["calibration"]["method"]},
        "by_ticker": {ticker: {"sample_size": int(mask.sum()), **metrics(rows[mask], p[mask], r[mask])}
                      for ticker in sorted(frames) for mask in [rows.ticker.to_numpy() == ticker]},
        "by_year": {str(year): {"sample_size": int(mask.sum()), **metrics(rows[mask], p[mask], r[mask])}
                    for year in sorted(rows.as_of.dt.year.unique()) for mask in [rows.as_of.dt.year.to_numpy() == year]},
        "original_momentum_direction": {"total_windows": len(rows), "neutral_abstentions": int(neutral.sum()),
            "scored_windows": int(nonneutral.sum()), "hit_rate": float(np.mean(
                (rows.momentum_label.to_numpy()[nonneutral] == "BULLISH") == y[nonneutral])) if nonneutral.any() else None,
            "always_up_same_mask_hit_rate": float(y[nonneutral].mean()) if nonneutral.any() else None,
            "fair_coin_expected_hit_rate": .5}})
    # This is a conservative research gate, not a trading deployment approval.
    needed = [paired[f"selected_minus_{baseline}_{loss}"]["high"] < 0
              for baseline in ("prior_mean", "constant_half_zero") for loss in ("brier", "mae_return")]
    learned = selection["probability_kind"] == "logistic" and selection["return_kind"] == "ridge"
    admitted = learned and all(needed) and len(unique_blocks) >= 8 and coverage >= .85
    selection = {**selection, "admission": {"passed": bool(admitted),
        "reason": "Research gate requires learned models, eight quarters, paired 95% improvements over prior/zero baselines for both targets, and >=85% interval coverage. Independent replication still required."}}
    records = []
    for i, row in rows.iterrows():
        records.append({"ticker": row.ticker, "as_of": str(row.as_of.date()), "target_end": str(row.target_end.date()),
            "forward_return": float(target[i]), "realized_up": int(y[i]), "momentum_label": row.momentum_label,
            "predictions": {name: {"probability_up": float(pp[i]), "return": float(rr[i])}
                            for name, (pp, rr) in results.items()},
            "interval_lower": float(r[i] - radius), "interval_upper": float(r[i] + radius)})
    return {"schema_version": 1, "kind": "historical_price_forecast", "protocol": frozen["protocol"],
        "data": frozen["data"], "features": list(FEATURES), "model_id": fingerprint(frozen),
        "selection": selection, "validation": frozen["validation"], "calibration": frozen["calibration"],
        "test": summary, "test_rows": records, "model_readiness": "research_only",
        "limitations": [
            "Five present-day selected stocks form a survivor universe, not point-in-time index constituents; no general-market claim.",
            "Historical vendor adjustments may be retrospective. Ratio features avoid absolute-level leakage but do not reconstruct vintage releases.",
            "30-session close-to-close forecast after observing close; not an executable trading strategy, realized P&L or investment advice.",
            "Training targets overlap. Validation/calibration/test targets do not overlap within each ticker; stocks share market shocks.",
            "Quarter-cluster bootstrap jointly samples stocks; eight holdout quarters give approximate, low-power intervals, with dependence across blocks possible.",
            "Split-residual intervals assume exchangeability for coverage guarantees; financial regime shifts violate this assumption. Report empirical coverage.",
            "No news/filings or profile features enter this price model. Five-agent action confidence and personalized effectiveness remain unvalidated.",
            "A historical holdout is spent after reporting; future tuning must reserve a new untouched period. No automatic promotion to portfolio actions."]}
