"""Bounded, CPU-only development experiment, with no new holdout claim.

Old research modules/artifacts stay intact. Model choice uses expanding OOF
development predictions only; calibration cannot select or refit a point model.
"""
import numpy as np
import pandas as pd

from vibefinance.data.quality import digest
from vibefinance.evaluation import forecast, uncertainty


FEATURE_RATIONALES = {
    "return_1": "short reversal; origin close",
    "return_5": "weekly trend; five past closes",
    "return_20": "monthly trend; twenty past closes",
    "return_60": "quarter trend; sixty past closes",
    "return_120": "medium trend; 120 past closes",
    "volatility_20": "recent risk; past twenty daily returns",
    "volatility_60": "slower risk; past sixty daily returns",
    "downside_60": "downside semi-deviation including zero positive returns; past sixty",
    "drawdown_120": "distance below trailing maximum; past 120 closes",
    "range_20": "intraday range / close; past twenty OHLC rows",
    "volume_change": "past five / lagged sixty volume, dimensionless; split basis unresolved",
    "illiquidity_change": "absolute return / turnover relative to lagged sixty-day median",
    "vol_regime": "twenty / sixty return volatility; causal regime indicator",
    "peer_return_20": "equal-weight other four surviving stocks; same-date closes, not a market index",
    "relative_return_20": "own monthly return minus four-stock peer basket",
    "peer_return_60": "same-date other-stock quarterly returns; not independent market data",
    "sector_relative_20": "TCS versus INFY and vice versa; zero with availability flag otherwise",
    "sector_peer_available": "one only for the two IT names; no sector proxy invented for singletons",
}
FEATURES = tuple(FEATURE_RATIONALES)
PROBABILITY_SPECS = (("logistic_0.1", "logistic", .1), ("logistic_1.0", "logistic", 1.),
                     ("stump_logistic", "stump_logistic", 0.))
RETURN_SPECS = (("ridge_1.0", "ridge", 1.), ("huber_1.0", "huber", 1.),
                ("stump_squared", "stump_squared", 0.))


def validate_protocol(protocol):
    """Only this frozen search is supported; changed searches need a new version."""
    if (protocol.get("schema_version") != 2 or protocol.get("horizon_sessions") != 30 or
            protocol.get("validation_years") != [2014, 2015, 2016, 2017] or
            protocol.get("train_start") != "2010-01-01" or protocol.get("refit_end") != "2017-12-31" or
            protocol.get("calibration_start") != "2021-01-01" or protocol.get("calibration_end") != "2023-12-31" or
            protocol.get("training_label_stride") != 5 or
            protocol.get("probability_candidates") != [s[0] for s in PROBABILITY_SPECS] or
            protocol.get("return_candidates") != [s[0] for s in RETURN_SPECS]):
        raise ValueError("Unsupported development-v2 protocol or attempted spent-period selection")
    expected_budget = {"folds": 4, "learned_probability_candidates": 3, "learned_return_candidates": 3,
        "boosting_rounds": 24, "stump_quantiles": [.2, .4, .6, .8], "learning_rate": .08,
        "minimum_leaf": 40, "seed": 2708, "adaptive_search": False}
    if protocol.get("search_budget") != expected_budget:
        raise ValueError("Search budget changed; register a different development version")
    if protocol.get("selection") != {
        "probability_metric": "brier", "return_metric": "mae", "minimum_quarters": 12,
        "minimum_winning_folds": 3, "familywise_alpha": .05, "bootstrap_draws": 2000,
        "rule": "candidate must beat every declared appropriate baseline by paired shared-quarter upper loss bound below zero at Bonferroni-adjusted level across 3 candidates x 3 baselines, and beat the best baseline in at least 3/4 years; else best baseline"}:
        raise ValueError("Selection rule changed after registration")
    if digest(protocol) != "683b118165902e477ab9346282ebb206c43e1fe178827a81a893e3c3805d6518":
        raise ValueError("Frozen v2 protocol changed; a new study version is required")


def feature_frames(frames):
    """No forward fill, fitted preprocessing, future values, or external index."""
    if len(frames) != 5:
        raise ValueError("The declared five-security universe is required")
    panels = {}
    for horizon in (20, 60):
        panels[horizon] = pd.concat({t: f.set_index("date").close.pct_change(horizon, fill_method=None)
                                    for t, f in frames.items()}, axis=1)
    result = {}
    for ticker, frame in sorted(frames.items()):
        f = forecast.features(frame)
        c, v = frame.close, frame.volume
        daily = c.pct_change(fill_method=None)
        f["return_120"] = c.pct_change(120, fill_method=None)
        f["downside_60"] = np.sqrt(daily.clip(upper=0).pow(2).rolling(60).mean())
        f["drawdown_120"] = c / c.rolling(120).max() - 1
        f["range_20"] = ((frame.high-frame.low) / c).rolling(20).mean()
        f["volume_change"] = np.log((v.rolling(5).mean()+1) / (v.shift(1).rolling(60).mean()+1))
        illiquidity = daily.abs() / (c * v).replace(0, np.nan)
        f["illiquidity_change"] = np.log((illiquidity+1e-20) /
                                        (illiquidity.shift(1).rolling(60).median()+1e-20))
        f["vol_regime"] = f.volatility_20 / (f.volatility_60+1e-12)
        for horizon, panel in panels.items():
            peer = panel.drop(columns=ticker)
            # All four contemporaneous peers must be present. Never fill a
            # missing peer with a stale/future observation or change the basket.
            f[f"peer_return_{horizon}"] = peer.mean(axis=1).where(peer.notna().all(axis=1)).reindex(frame.date).to_numpy()
        f["relative_return_20"] = f.return_20 - f.peer_return_20
        other = {"TCS.NS": "INFY.NS", "INFY.NS": "TCS.NS"}.get(ticker)
        f["sector_peer_available"] = float(other is not None)
        f["sector_relative_20"] = (f.return_20 - panels[20][other].reindex(frame.date).to_numpy()
                                     if other else 0.)
        result[ticker] = f[list(FEATURES)]
    return result


def observations(frames):
    # Crop before feature/target construction: no 2024+ values are consumed.
    frames = {t: f[f.date <= pd.Timestamp("2023-12-31")].reset_index(drop=True)
              for t, f in frames.items()}
    xs = feature_frames(frames)
    parts, eligibility = [], {}
    for ticker, frame in sorted(frames.items()):
        x = xs[ticker]
        target_dates = frame.date.shift(-30)
        permitted = (((frame.date >= pd.Timestamp("2010-01-01")) &
                      (target_dates <= pd.Timestamp("2017-12-31"))) |
                     ((frame.date >= pd.Timestamp("2021-01-01")) &
                      (target_dates <= pd.Timestamp("2023-12-31"))))
        finite = np.isfinite(x.to_numpy(float)).all(axis=1)
        mask = permitted & finite
        indices = np.flatnonzero(mask)
        out = x.loc[mask].copy()
        out["as_of"] = frame.loc[mask, "date"].to_numpy()
        out["target_end"] = target_dates[mask].to_numpy()
        # Construct labels only for permitted development/calibration rows.
        out["forward_return"] = frame.close.iloc[indices+30].to_numpy() / frame.close.iloc[indices].to_numpy() - 1
        out["up"] = (out.forward_return > 0).astype(int)
        old = forecast.features(frame)
        score = (.45*np.tanh(old.return_20*12) + .35*np.tanh(old.dma_ratio*30) +
                 .15*np.tanh(old.macd_hist*500) + .05*old.rsi)
        out["momentum_label"] = np.where(score[mask] > .15, "BULLISH", np.where(score[mask] < -.15, "BEARISH", "NEUTRAL"))
        out["ticker"] = ticker
        out["session_index"] = indices
        eligibility[ticker] = {"scoped_positive_volume_rows": len(frame),
            "permitted_label_rows_before_feature_checks": int(permitted.sum()),
            "excluded_missing_feature_or_peer_rows": frame.date[permitted & ~finite].dt.strftime("%Y-%m-%d").tolist(),
            "eligible_daily_rows": len(out), "no_raw_row_imputation": True}
        parts.append(out)
    rows = pd.concat(parts, ignore_index=True).sort_values(["as_of", "ticker"]).reset_index(drop=True)
    return rows, eligibility


def _sigmoid(z):
    return np.exp(-np.logaddexp(0, -z))


def _matrix(rows, model):
    x = rows[list(FEATURES)].to_numpy(float)
    if not np.isfinite(x).all():
        raise ValueError("Missing features require an explicit exclusion, never imputation")
    return np.c_[np.ones(len(x)), np.clip((x-model["center"])/model["scale"], -5, 5)]


def fit(rows, kind, penalty=1.):
    if len(rows) < 120 or rows.up.nunique() != 2:
        raise ValueError("Insufficient matured training labels or outcome classes")
    raw = rows[list(FEATURES)].to_numpy(float)
    if not np.isfinite(raw).all():
        raise ValueError("Nonfinite training features")
    center, scale = np.median(raw, axis=0), raw.std(axis=0)
    scale[scale < 1e-12] = 1
    model = {"kind": kind, "penalty": penalty, "center": center.tolist(), "scale": scale.tolist(),
             "training_rows": len(rows), "training_target_end": str(rows.target_end.max().date())}
    x = _matrix(rows, model)
    y = rows.up.to_numpy(float) if "logistic" in kind else rows.forward_return.to_numpy(float)
    reg = np.diag([0.] + [penalty]*len(FEATURES))
    if kind == "logistic":
        coef = np.zeros(x.shape[1])
        coef[0] = np.log((y.sum()+1)/(len(y)-y.sum()+1))
        for _ in range(60):
            p = _sigmoid(x@coef)
            gradient = x.T@(p-y)/len(y)+reg@coef
            hessian = (x.T*(p*(1-p)))@x/len(y)+reg+np.eye(x.shape[1])*1e-9
            step = np.linalg.solve(hessian, gradient)
            old = np.mean(np.logaddexp(0, x@coef)-y*(x@coef))+.5*coef@reg@coef
            rate = 1.
            while rate > 1e-8:
                candidate = coef-rate*step
                loss = np.mean(np.logaddexp(0, x@candidate)-y*(x@candidate))+.5*candidate@reg@candidate
                if loss <= old:
                    break
                rate /= 2
            coef = candidate
            if np.max(np.abs(rate*step)) < 1e-8:
                break
        if np.max(np.abs(x.T@(_sigmoid(x@coef)-y)/len(y)+reg@coef)) > 1e-5:
            raise ValueError("Logistic solver failed to converge")
        model["coef"] = coef.tolist()
    elif kind in {"ridge", "huber"}:
        coef = np.linalg.solve(x.T@x/len(y)+reg, x.T@y/len(y))
        if kind == "huber":
            # Robustness is determined from training residuals, never a test
            # tail. Fixed IRLS budget and Huber tuning constant were declared.
            delta = max(1e-4, 1.345*1.4826*np.median(np.abs(y-x@coef)))
            for _ in range(30):
                weights = np.minimum(1., delta/(np.abs(y-x@coef)+1e-15))
                coef = np.linalg.solve((x.T*weights)@x/len(y)+reg, (x.T*weights)@y/len(y))
            model["huber_delta"] = float(delta)
        model["coef"] = coef.tolist()
    elif kind in {"stump_squared", "stump_logistic"}:
        base = (np.log((y.sum()+1)/(len(y)-y.sum()+1)) if kind == "stump_logistic" else y.mean())
        prediction = np.full(len(y), base)
        splits = []
        for feature in range(1, x.shape[1]):
            for threshold in np.unique(np.quantile(x[:, feature], [.2, .4, .6, .8])):
                mask = x[:, feature] <= threshold
                if min(mask.sum(), (~mask).sum()) >= 40:
                    splits.append((feature, float(threshold), mask))
        trees = []
        for _ in range(24):
            residual = y-(_sigmoid(prediction) if kind == "stump_logistic" else prediction)
            best = None
            for feature, threshold, mask in splits:
                left, right = residual[mask].mean(), residual[~mask].mean()
                gain = mask.sum()*left**2 + (~mask).sum()*right**2
                if best is None or gain > best[0]:
                    best = (gain, feature, threshold, float(left), float(right))
            if best is None:
                break
            _, feature, threshold, left, right = best
            prediction += .08*np.where(x[:, feature] <= threshold, left, right)
            trees.append([feature, threshold, left, right])
        model.update(base=float(base), trees=trees, learning_rate=.08)
    else:
        raise ValueError("Undeclared candidate")
    return model


def predict(model, rows):
    x = _matrix(rows, model)
    if "coef" in model:
        values = x@model["coef"]
    else:
        values = np.full(len(rows), model["base"])
        for feature, threshold, left, right in model["trees"]:
            values += model["learning_rate"]*np.where(x[:, feature] <= threshold, left, right)
    return _sigmoid(values) if "logistic" in model["kind"] else np.maximum(-1., values)


def baselines(train, rows):
    prior = (train.up.sum()+1)/(len(train)+2)
    mean = train.forward_return.mean()
    probabilities = {"constant_half": np.full(len(rows), .5), "prior": np.full(len(rows), prior),
                     "always_up": np.ones(len(rows))}
    returns = {"zero": np.zeros(len(rows)), "mean": np.full(len(rows), mean)}
    p, r, params = [], [], {}
    for label in ("BULLISH", "BEARISH", "NEUTRAL"):
        group = train[train.momentum_label == label]
        params[label] = {"probability": float((group.up.sum()+1)/(len(group)+2)),
                         "return": float(group.forward_return.mean()) if len(group) else float(mean)}
    for label in rows.momentum_label:
        p.append(params[label]["probability"])
        r.append(params[label]["return"])
    probabilities["momentum"], returns["momentum"] = np.array(p), np.array(r)
    return probabilities, returns, {"prior": float(prior), "mean": float(mean), "momentum": params}


def clustered_interval(rows, values, *, alpha=.05, draws=2000):
    values = np.asarray(values, float)
    if values.shape != (len(rows),) or not len(rows) or not np.isfinite(values).all():
        raise ValueError("Need finite, identically aligned per-row measurements")
    blocks = rows.as_of.dt.to_period("Q").astype(str).to_numpy()
    unique = sorted(set(blocks))
    sums = np.array([values[blocks == b].sum() for b in unique])
    counts = np.array([(blocks == b).sum() for b in unique])
    samples = np.random.default_rng(2708).integers(0, len(unique), (draws, len(unique)))
    means = sums[samples].sum(axis=1)/counts[samples].sum(axis=1)
    return {"estimate": float(values.mean()), "low": float(np.quantile(means, alpha/2)),
            "high": float(np.quantile(means, 1-alpha/2)), "confidence_level": 1-alpha,
            "shared_quarter_blocks": len(unique), "origin_dates": int(rows.as_of.nunique()),
            "method": "stocks sampled jointly by calendar quarter; approximate development uncertainty; adjacent-block dependence remains"}


def select(rows, predictions, baselines_, target, loss):
    losses = {n: loss(v, target) for n, v in predictions.items() if n != "always_up"}
    best = min(baselines_, key=lambda n: float(losses[n].mean()))
    candidate_names = [n for n in losses if n not in baselines_]
    comparisons, eligible = {}, []
    adjusted_alpha = .05/(len(candidate_names)*len(baselines_))
    for name in candidate_names:
        pairs = {b: clustered_interval(rows, losses[name]-losses[b], alpha=adjusted_alpha) for b in baselines_}
        wins = sum(losses[name][rows.fold.to_numpy() == y].mean() < losses[best][rows.fold.to_numpy() == y].mean()
                   for y in sorted(rows.fold.unique()))
        supported = all(c["high"] < 0 and c["shared_quarter_blocks"] >= 12 for c in pairs.values()) and wins >= 3
        comparisons[name] = {"versus_baselines": pairs, "winning_folds_vs_best_baseline": int(wins),
                             "eligible_development_candidate": bool(supported)}
        if supported:
            eligible.append(name)
    chosen = min(eligible, key=lambda n: float(losses[n].mean())) if eligible else best
    return {"chosen": chosen, "best_baseline": best, "comparisons": comparisons,
            "familywise_alpha": .05, "per_comparison_alpha": adjusted_alpha,
            "fresh_admission": False}


def probability_metrics(rows, prediction):
    m = forecast.metrics(rows, prediction, np.zeros(len(rows)))
    return {k: m[k] for k in ("brier", "log_loss", "accuracy", "balanced_accuracy", "realized_up_rate")}


def return_metrics(rows, prediction):
    target = rows.forward_return.to_numpy(float)
    return {"mae_return": float(np.abs(prediction-target).mean()),
            "rmse_return": float(np.sqrt(np.mean((prediction-target)**2))),
            "bias_return": float(np.mean(prediction-target))}


def reliability(rows, p):
    return [{"lower": low, "upper": low+.2, "count": int(mask.sum()),
             "mean_probability": float(p[mask].mean()) if mask.any() else None,
             "observed_up_rate": float(rows.up.to_numpy()[mask].mean()) if mask.any() else None}
            for low in (0., .2, .4, .6, .8)
            for mask in [(p >= low) & ((p < low+.2) if low < .8 else (p <= 1))]]


def prequential_intervals(rows, centers, floor):
    """Past matured OOF residuals only, on identical complete-origin cohorts.

    Method comparison is descriptive development evidence; model selection over
    these OOF rows is itself exploratory. No independent evaluation is implied.
    """
    lows, highs, indices = {}, {}, []
    exclusions = []
    methods = ("pooled_absolute", "security_vol_scaled", "joint_vol_scaled")
    for origin, group in rows.groupby("as_of", sort=True):
        past = rows[(rows.target_end < origin)].copy()
        dates = sorted(past.as_of.unique())[-24:]
        past = past[past.as_of.isin(dates)]
        complete = len(group) == 5 and group.ticker.nunique() == 5
        if past.as_of.nunique() < 9 or not complete:
            exclusions.append({"origin": str(origin.date()), "reason": "fewer_than_nine_matured_origins" if complete else "incomplete_security_group"})
            continue
        calibration = uncertainty.calibrate(past, centers[past.index], floor)
        if not all(calibration["methods"][m]["available"] for m in methods):
            exclusions.append({"origin": str(origin.date()), "reason": "finite_rank_or_cohort_unavailable"})
            continue
        indices.extend(group.index)
        for method in methods:
            lo, hi = uncertainty.bounds(calibration, group, centers[group.index], method)
            lows.setdefault(method, []).extend(lo)
            highs.setdefault(method, []).extend(hi)
    selected = rows.loc[indices].reset_index(drop=True)
    results = {}
    for method in lows:
        lo, hi = np.array(lows[method]), np.array(highs[method])
        covered = (selected.forward_return >= lo) & (selected.forward_return <= hi)
        # Every included origin was checked complete; simultaneous denominator
        # is distinct origins, never individual security rows or partial groups.
        joint = selected[["as_of"]].assign(covered=covered).groupby("as_of").covered.all()
        score = hi-lo + 20*(np.maximum(lo-selected.forward_return.to_numpy(), 0)+
                            np.maximum(selected.forward_return.to_numpy()-hi, 0))
        results[method] = {**uncertainty.interval_metrics(selected, lo, hi),
            "sample_size": len(selected), "coverage_uncertainty": clustered_interval(selected, covered.astype(float)),
            "score_uncertainty": clustered_interval(selected, score),
            "simultaneous_coverage": {"complete_origins": len(joint), "covered_origins": int(joint.sum()),
                                      "coverage": float(joint.mean()), "partial_groups_counted": False},
            "by_ticker": {t: {"sample_size": int(mask.sum()),
                **uncertainty.interval_metrics(selected[mask], lo[mask], hi[mask])}
                for t in sorted(selected.ticker.unique()) for mask in [selected.ticker.to_numpy() == t]}}
    return {"methods": results, "excluded_origins": exclusions, "primary": "pooled_absolute",
            "status": "development_only", "update": "last 24 origins whose labels matured strictly before issuance",
            "exchangeability_guarantee": False}


def run(frames, protocol):
    validate_protocol(protocol)
    if sorted(frames) != protocol["universe"]:
        raise ValueError("Declared universe mismatch")
    rows, eligibility = observations(frames)
    parts, probabilities, returns, folds = [], {}, {}, []
    for year in protocol["validation_years"]:
        training = rows[(rows.as_of >= pd.Timestamp(protocol["train_start"])) &
                        (rows.target_end < pd.Timestamp(f"{year}-01-01"))]
        training = pd.concat([g.iloc[::5] for _, g in training.groupby("ticker")]).sort_values(["as_of", "ticker"])
        val = forecast.period(rows, f"{year}-01-01", f"{year}-12-31").copy()
        if len(val) != 40 or val.groupby("as_of").ticker.nunique().ne(5).any():
            raise ValueError("Missing declared development cohort; inspect data, never silently drop or realign")
        val["fold"] = year
        parts.append(val)
        bp, br, _ = baselines(training, val)
        for name, kind, penalty in PROBABILITY_SPECS:
            bp[name] = predict(fit(training, kind, penalty), val)
        for name, kind, penalty in RETURN_SPECS:
            br[name] = predict(fit(training, kind, penalty), val)
        for n, v in bp.items():
            probabilities.setdefault(n, []).append(v)
        for n, v in br.items():
            returns.setdefault(n, []).append(v)
        folds.append({"year": year, "training_rows": len(training), "training_shared_origins": int(training.as_of.nunique()),
            "training_max_target_end": str(training.target_end.max().date()), "validation_rows": len(val),
            "validation_origins": int(val.as_of.nunique()), "first_origin": str(val.as_of.min().date()),
            "last_origin": str(val.as_of.max().date()), "last_target": str(val.target_end.max().date())})
    validation = pd.concat(parts, ignore_index=True)
    ps = {n: np.concatenate(v) for n, v in probabilities.items()}
    rs = {n: np.concatenate(v) for n, v in returns.items()}
    sp = select(validation, ps, ("constant_half", "prior", "momentum"), validation.up.to_numpy(float),
                lambda p, y: (p-y)**2)
    sr = select(validation, rs, ("zero", "mean", "momentum"), validation.forward_return.to_numpy(float),
                lambda r, y: np.abs(r-y))
    training = rows[rows.target_end <= pd.Timestamp(protocol["refit_end"])].copy()
    training = pd.concat([g.iloc[::5] for _, g in training.groupby("ticker")]).sort_values(["as_of", "ticker"])
    floor = max(1e-5, float(np.quantile(training[["volatility_20", "volatility_60"]].max(axis=1)*np.sqrt(30), .05)))
    cal = forecast.period(rows, protocol["calibration_start"], protocol["calibration_end"])
    if len(cal) != 120 or cal.groupby("as_of").ticker.nunique().ne(5).any():
        raise ValueError("Missing declared calibration cohort; no silent subset")
    bp, br, baseline_parameters = baselines(training, cal)
    learned_models = {}
    for name, kind, penalty in PROBABILITY_SPECS:
        if name == sp["chosen"]:
            learned_models[name] = fit(training, kind, penalty)
            bp[name] = predict(learned_models[name], cal)
    for name, kind, penalty in RETURN_SPECS:
        if name == sr["chosen"]:
            learned_models[name] = fit(training, kind, penalty)
            br[name] = predict(learned_models[name], cal)
    # Freeze the selection identity before residual calibration. Calibration
    # outcomes cannot feed back into parameters, hyperparameters or selection.
    frozen = {"protocol_sha256": digest(protocol), "probability_selection": sp, "return_selection": sr,
              "models": learned_models, "baseline_parameters": baseline_parameters,
              "training_max_target_end": str(training.target_end.max().date()),
              "training_rows": len(training), "features": list(FEATURES), "scale_floor": floor}
    calibration = uncertainty.calibrate(cal, br[sr["chosen"]], floor)
    pm = {n: probability_metrics(validation, p) for n, p in ps.items()}
    rm = {n: return_metrics(validation, r) for n, r in rs.items()}
    target_up, target_return = validation.up.to_numpy(float), validation.forward_return.to_numpy(float)
    metric_uncertainty = {
        "brier": {n: clustered_interval(validation, (p-target_up)**2) for n, p in ps.items()},
        "mae_return": {n: clustered_interval(validation, np.abs(r-target_return)) for n, r in rs.items()}}
    paired_baselines = {
        "probability": {b: clustered_interval(validation, (ps[sp["chosen"]]-target_up)**2-(ps[b]-target_up)**2)
                        for b in ("constant_half", "prior", "momentum")},
        "return": {b: clustered_interval(validation, np.abs(rs[sr["chosen"]]-target_return)-np.abs(rs[b]-target_return))
                   for b in ("zero", "mean", "momentum")}}
    by_group = {}
    for field, values in (("ticker", sorted(validation.ticker.unique())), ("fold", protocol["validation_years"])):
        by_group[field] = {str(v): {"sample_size": int(mask.sum()),
            "probability": {n: probability_metrics(validation[mask], p[mask]) for n, p in ps.items()},
            "return": {n: return_metrics(validation[mask], r[mask]) for n, r in rs.items()}}
            for v in values for mask in [validation[field].to_numpy() == v]}
    # Causal regime threshold is fit separately on the first training fold.
    first_train = rows[rows.target_end < pd.Timestamp("2014-01-01")]
    threshold = float(first_train.volatility_20.median())
    prequential_floor = max(1e-5, float(np.quantile(
        first_train[["volatility_20", "volatility_60"]].max(axis=1)*np.sqrt(30), .05)))
    by_group["regime"] = {label: {"sample_size": int(mask.sum()),
        "probability": {n: probability_metrics(validation[mask], p[mask]) for n, p in ps.items()},
        "return": {n: return_metrics(validation[mask], r[mask]) for n, r in rs.items()}}
        for label, mask in (("calm", validation.volatility_20.to_numpy() <= threshold),
                            ("elevated", validation.volatility_20.to_numpy() > threshold)) if mask.any()}
    records = [{"ticker": row.ticker, "as_of": str(row.as_of.date()), "target_end": str(row.target_end.date()),
        "fold": int(row.fold), "realized_up": int(row.up), "forward_return": float(row.forward_return),
        "probabilities": {n: float(p[i]) for n, p in ps.items()},
        "returns": {n: float(r[i]) for n, r in rs.items()}} for i, row in validation.iterrows()]
    calibration_records = [{"ticker": row.ticker, "as_of": str(row.as_of.date()),
        "target_end": str(row.target_end.date()), "forward_return": float(row.forward_return),
        "predicted_return": float(br[sr["chosen"]][i]),
        "causal_scale": float(uncertainty.causal_scale(cal, floor)[i])}
        for i, row in cal.iterrows()]
    return {"schema_version": 2, "kind": "forecast_development", "status": "exploratory_development_only",
        "protocol": protocol, "feature_rationales": FEATURE_RATIONALES, "eligibility": eligibility,
        "development": {"sample_size": len(validation), "shared_origins": int(validation.as_of.nunique()),
            "folds": folds, "probability_metrics": pm, "return_metrics": rm, "by_group": by_group,
            "metric_uncertainty": metric_uncertainty, "selected_minus_baselines": paired_baselines,
            "reliability": {n: reliability(validation, p) for n, p in ps.items()},
            "regime_threshold": threshold, "selection_optimism": "same OOF development rows select models; no fresh performance estimate"},
        "selection": frozen, "model_id": digest(frozen), "calibration": calibration,
        "calibration_scope": {"start": protocol["calibration_start"], "end": protocol["calibration_end"],
            "rows": len(cal), "origins": int(cal.as_of.nunique()), "evaluation": "not scored; previously inspected calibration"},
        "prequential_intervals": {**prequential_intervals(validation, rs[sr["chosen"]], prequential_floor),
                                 "scale_floor_frozen_before": "2014-01-01", "scale_floor": prequential_floor},
        "admission": {"passed": False, "reason": "Development only; no fresh independent evaluation or passed full data-quality review"},
        "as_of": protocol["calibration_end"], "data_freshness": "historical research snapshot; not a current forecast",
        "portfolio_actions_changed": False, "development_rows": records,
        "calibration_rows": calibration_records, "calibration_rows_sha256": digest(calibration_records),
        "limitations": protocol["limitations"] + [
            "Marginal versus simultaneous coverage have different units. Finite ranks do not imply exchangeability.",
            "Multiplicity correction and quarter resampling are conservative development screens, not proof of predictive advantage.",
            "Expected return, up probability, return interval and portfolio-policy evidence strength are distinct quantities."]}
