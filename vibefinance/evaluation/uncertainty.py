"""Empirical return intervals with honest calibration units and causal scales.

No financial time-series coverage guarantee is claimed. Distinct securities on
one forecast date share shocks; the joint option uses date maxima, not IID rows.
"""
import numpy as np


def residual_quantile(scores, alpha=.1):
    values = np.asarray(scores, dtype=float)
    if (values.ndim != 1 or not len(values) or not np.isfinite(values).all()
            or (values < 0).any() or not 0 < alpha < 1):
        raise ValueError("Need finite nonnegative residual scores and valid alpha")
    rank = int(np.ceil((len(values) + 1) * (1 - alpha)))
    if rank > len(values):
        raise ValueError("Insufficient calibration units for a finite requested quantile")
    return float(np.sort(values)[rank - 1])


def causal_scale(rows, floor):
    if not np.isfinite(floor) or floor <= 0:
        raise ValueError("Scale floor must be finite and positive")
    values = rows[["volatility_20", "volatility_60"]].to_numpy(float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Need finite causal nonnegative volatility features")
    return np.maximum(values.max(axis=1) * np.sqrt(30), floor)


def _centers(centers, size):
    values = np.asarray(centers, dtype=float)
    if values.shape != (size,) or not np.isfinite(values).all() or (values < -1).any():
        raise ValueError("Predicted returns must be finite, aligned and at least -100%")
    return values


def calibrate(rows, centers, floor, alpha=.1):
    if not 0 < alpha < 1:
        raise ValueError("Calibration alpha must be between zero and one")
    if (rows.empty or rows[["ticker", "as_of"]].isna().any().any()
            or rows[["ticker", "as_of"]].duplicated().any()):
        raise ValueError("Need unique nonempty ticker/date calibration rows")
    if "target_end" in rows:
        if rows.target_end.isna().any():
            raise ValueError("Calibration target dates must be present")
        for _, group in rows.groupby("ticker"):
            group = group.sort_values("as_of")
            if ((group.target_end <= group.as_of).any() or
                    (group.target_end.to_numpy()[:-1] > group.as_of.to_numpy()[1:]).any()):
                raise ValueError("Calibration targets must be chronological and non-overlapping")
    centers = _centers(centers, len(rows))
    target = rows.forward_return.to_numpy(float)
    if not np.isfinite(target).all() or (target < -1).any():
        raise ValueError("Invalid calibration return outcomes")
    scale = causal_scale(rows, floor)
    absolute = np.abs(target - centers)
    normalized = absolute / scale
    tickers = sorted(rows.ticker.unique())
    methods = {}
    for method in ("pooled_absolute", "security_absolute", "security_vol_scaled", "joint_vol_scaled"):
        record = {"available": True, "nominal_coverage": 1 - alpha}
        try:
            if method == "pooled_absolute":
                record.update(radius=residual_quantile(absolute, alpha), quantile_units=len(rows),
                              shared_dates=int(rows.as_of.nunique()),
                              unit="pooled correlated security/date residuals; no IID interpretation")
            elif method.startswith("security_"):
                scores = absolute if method == "security_absolute" else normalized
                radii, counts = {}, {}
                for ticker in tickers:
                    mask = rows.ticker.to_numpy() == ticker
                    radii[ticker] = residual_quantile(scores[mask], alpha)
                    counts[ticker] = int(mask.sum())
                record.update(radius_by_ticker=radii, quantile_units_by_ticker=counts,
                              unit="distinct non-overlapping forecast dates per security")
            else:
                grouped = rows[["as_of", "ticker"]].copy()
                grouped["score"] = normalized
                if (grouped.groupby("as_of").ticker.nunique() != len(tickers)).any():
                    raise ValueError("Joint calibration needs an aligned complete security universe")
                date_scores = grouped.groupby("as_of").score.max().to_numpy(float)
                record.update(radius=residual_quantile(date_scores, alpha), quantile_units=len(date_scores),
                              unit="maximum standardized residual across securities at each shared date",
                              coverage_target="simultaneous across the declared securities, rather than marginal")
        except ValueError as exc:
            record = {"available": False, "reason": str(exc), "nominal_coverage": 1 - alpha}
        methods[method] = record
    return {"alpha": alpha, "scale_floor": float(floor), "sample_size": len(rows),
            "shared_dates": int(rows.as_of.nunique()), "securities": tickers,
            "primary": "security_vol_scaled", "methods": methods,
            "scale_rule": "max(past 20/past 60 observed-row return volatility) * sqrt(30), floored at training-only 5th percentile",
            "guarantee": "Empirical nominal coverage only; market regimes are not exchangeable"}


def bounds(calibration, rows, centers, method="security_vol_scaled", floor=None):
    """No labels or future returns are read here."""
    centers = _centers(centers, len(rows))
    record = calibration["methods"][method]
    if not record["available"]:
        raise ValueError(record["reason"])
    if floor is not None and floor != calibration["scale_floor"]:
        raise ValueError("Frozen scale floor mismatch")
    if not set(rows.ticker).issubset(set(calibration["securities"])):
        raise ValueError("Uncalibrated prediction security")
    if "radius_by_ticker" in record:
        width = np.array([record["radius_by_ticker"][t] for t in rows.ticker], dtype=float)
    else:
        width = np.full(len(rows), record["radius"])
    if method in {"security_vol_scaled", "joint_vol_scaled"}:
        width *= causal_scale(rows, calibration["scale_floor"])
    return np.maximum(-1, centers - width), centers + width


def interval_metrics(rows, lower, upper, alpha=.1):
    lower, upper = np.asarray(lower, float), np.asarray(upper, float)
    target = rows.forward_return.to_numpy(float)
    if (lower.shape != target.shape or upper.shape != target.shape or not len(target)
            or not np.isfinite([lower, upper, target]).all() or (lower > upper).any()
            or not 0 < alpha < 1):
        raise ValueError("Invalid interval/outcome arrays or alpha")
    below, above = target < lower, target > upper
    score = upper - lower + 2 / alpha * (np.maximum(lower - target, 0) + np.maximum(target - upper, 0))
    return {"coverage": float(np.mean(~(below | above))),
            "mean_width": float(np.mean(upper - lower)), "interval_score": float(score.mean()),
            "lower_miss_rate": float(below.mean()), "upper_miss_rate": float(above.mean()),
            "nominal_coverage": 1 - alpha}
