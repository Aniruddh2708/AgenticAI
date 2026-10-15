"""Stability-aware research selection using the original development folds.

The reported 2019--2020 holdout is now spent and can enter the final development
fit, but it cannot select a candidate or hyperparameter. Neither selection nor
the development fit consumes outcomes after 2020. This module does not change
portfolio decisions.
"""
import numpy as np
import pandas as pd

from vibefinance.evaluation import forecast


BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 2708
MIN_QUARTER_BLOCKS = 8
DEVELOPMENT_END = "2020-12-31"


def paired_loss_comparison(rows, candidate_loss, baseline_loss):
    """Descriptive paired uncertainty with stocks sampled jointly by quarter.

    Eight quarters provide weak evidence, and dependence between adjacent
    quarters can remain. These intervals are not distribution-free guarantees.
    """
    candidate_loss = np.asarray(candidate_loss, dtype=float)
    baseline_loss = np.asarray(baseline_loss, dtype=float)
    if candidate_loss.shape != (len(rows),) or baseline_loss.shape != (len(rows),):
        raise ValueError("Losses must describe the same validation observations")
    if not len(rows) or not np.isfinite(candidate_loss).all() or not np.isfinite(baseline_loss).all():
        raise ValueError("Need nonempty finite paired validation losses")
    blocks = rows.as_of.dt.to_period("Q").astype(str).to_numpy()
    unique = sorted(set(blocks))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.integers(0, len(unique), (BOOTSTRAP_RESAMPLES, len(unique)))
    delta = candidate_loss - baseline_loss
    sums = np.array([delta[blocks == block].sum() for block in unique])
    counts = np.array([(blocks == block).sum() for block in unique])
    bootstrap = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    low, high = np.quantile(bootstrap, [.025, .975])
    eligible = len(unique) >= MIN_QUARTER_BLOCKS and high < 0
    return {"difference": float(delta.mean()), "low": float(low), "high": float(high),
            "level": .95, "calendar_quarter_blocks": len(unique),
            "resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED,
            "eligible": bool(eligible),
            "reason": "Paired upper bound below zero with at least eight quarters" if eligible else
                      "Insufficient quarters or improvement not supported by paired uncertainty"}


def _select(rows, candidates, baselines, target, loss):
    losses = {name: loss(prediction, target) for name, prediction in candidates.items()}
    # Stable ordering keeps the simpler baseline when losses tie.
    baseline = min(baselines, key=lambda name: float(np.mean(losses[name])))
    comparisons = {name: {"baseline": baseline,
                         **paired_loss_comparison(rows, values, losses[baseline])}
                   for name, values in losses.items() if name not in baselines}
    eligible = [name for name, result in comparisons.items() if result["eligible"]]
    chosen = min(eligible, key=lambda name: float(np.mean(losses[name]))) if eligible else baseline
    return chosen, baseline, comparisons


def select_models(frames):
    """Select on 2016/2017 only, then fit matured 2010--2020 development rows.

    Hyperparameter grids, selection dates, metric, shared-quarter resampling,
    confidence level, and minimum block count are fixed before fresh evaluation.
    A learned candidate replaces the best validation baseline only when its
    paired 95% upper loss-difference bound is strictly below zero.
    """
    protocol = forecast.Protocol()
    # Crop before even constructing targets: later outcomes do not enter this
    # operation, including its temporary data frames.
    development_frames = {ticker: frame[frame.date <= pd.Timestamp(DEVELOPMENT_END)].copy()
                          for ticker, frame in frames.items()}
    rows = forecast.observations(development_frames, protocol.horizon_sessions)
    validation_parts, predictions, folds = [], {}, []
    for year in (2016, 2017):
        start, end = f"{year}-01-01", f"{year}-12-31"
        training = forecast.training_rows(rows, protocol, start)
        validation = forecast.period(rows, start, end, protocol.horizon_sessions)
        if len(validation) < 10:
            raise ValueError("Too few observations in a declared validation fold")
        validation_parts.append(validation)
        folds.append({"start": start, "end": end, "training_rows": len(training),
                      "training_target_end": str(training.target_end.max().date()),
                      "validation_rows": len(validation),
                      "validation_origin_dates": int(validation.as_of.nunique())})
        for penalty in forecast.PROBABILITY_GRID:
            model = forecast.fit(training, penalty, forecast.RETURN_GRID[0])
            probability, _ = forecast.predict(model, validation)
            predictions.setdefault(f"logistic_{penalty}", []).append(probability)
        for penalty in forecast.RETURN_GRID:
            model = forecast.fit(training, forecast.PROBABILITY_GRID[0], penalty)
            _, returns = forecast.predict(model, validation)
            predictions.setdefault(f"ridge_{penalty}", []).append(returns)
        probability, returns = forecast.predict(model, validation, "prior", "mean")
        predictions.setdefault("prior", []).append(probability)
        predictions.setdefault("mean", []).append(returns)
        predictions.setdefault("constant_half", []).append(np.full(len(validation), .5))
        predictions.setdefault("zero", []).append(np.zeros(len(validation)))

    validation = pd.concat(validation_parts, ignore_index=True)
    pooled = {name: np.concatenate(parts) for name, parts in predictions.items()}
    probabilities = {name: pooled[name] for name in ("prior", "constant_half", *(
        f"logistic_{penalty}" for penalty in forecast.PROBABILITY_GRID))}
    returns = {name: pooled[name] for name in ("mean", "zero", *(
        f"ridge_{penalty}" for penalty in forecast.RETURN_GRID))}
    probability_name, probability_baseline, probability_stability = _select(
        validation, probabilities, ("prior", "constant_half"), validation.up.to_numpy(float),
        lambda prediction, target: (prediction - target) ** 2)
    return_name, return_baseline, return_stability = _select(
        validation, returns, ("mean", "zero"), validation.forward_return.to_numpy(float),
        lambda prediction, target: np.abs(prediction - target))
    probability_penalty = (float(probability_name.split("_")[1])
                           if probability_name.startswith("logistic_") else forecast.PROBABILITY_GRID[0])
    return_penalty = (float(return_name.split("_")[1])
                      if return_name.startswith("ridge_") else forecast.RETURN_GRID[0])
    probability_kind = "logistic" if probability_name.startswith("logistic_") else probability_name
    return_kind = "ridge" if return_name.startswith("ridge_") else return_name

    # Final fitting cannot change the already selected candidate or penalty.
    development = rows[(rows.as_of >= pd.Timestamp(protocol.train_start)) &
                       (rows.target_end <= pd.Timestamp(DEVELOPMENT_END))].copy()
    model = forecast.fit(development, probability_penalty, return_penalty)
    model["training_as_of_start"] = str(development.as_of.min().date())
    model["training_as_of_end"] = str(development.as_of.max().date())
    model["training_origin_dates"] = int(development.as_of.nunique())
    model["training_rows_by_ticker"] = {
        ticker: len(group) for ticker, group in development.groupby("ticker")}
    selection = {"probability_model": probability_name, "return_model": return_name,
                 "probability_kind": probability_kind, "return_kind": return_kind,
                 "probability_penalty": probability_penalty, "return_penalty": return_penalty,
                 "probability_baseline": probability_baseline, "return_baseline": return_baseline,
                 "criterion": "2016/2017 expanding validation Brier/MAE; a learned model requires a paired 95% upper loss-difference bound below zero against the best baseline",
                 "stability_rule": {"minimum_calendar_quarters": MIN_QUARTER_BLOCKS,
                                    "resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED,
                                    "confidence_level": .95, "upper_bound_strictly_below": 0},
                 "development_end": DEVELOPMENT_END,
                 "admission": {"passed": False, "reason": "Research only; fresh evaluation is still required"}}
    candidate_metrics = {name: forecast.metrics(validation, probability, pooled["mean"])
                         for name, probability in probabilities.items()}
    candidate_metrics.update({name: forecast.metrics(validation, pooled["prior"], prediction)
                              for name, prediction in returns.items()})
    chosen_metrics = forecast.metrics(validation, probabilities[probability_name], returns[return_name])
    validation_summary = {"sample_size": len(validation),
                          "origin_dates": int(validation.as_of.nunique()),
                          "as_of_start": str(validation.as_of.min().date()),
                          "as_of_end": str(validation.as_of.max().date()),
                          "target_end": str(validation.target_end.max().date()),
                          "metrics": {"selected": chosen_metrics}, "selected_metrics": chosen_metrics,
                          "folds": folds, "candidate_metrics": candidate_metrics,
                          "stability_results": {"probability": probability_stability,
                                                "return": return_stability},
                          "limitations": [
                              "Only sixteen shared origin dates and eight quarters; estimates are unstable.",
                              "Quarter bootstrap jointly samples stocks, but adjacent quarters can remain dependent.",
                              "Candidate comparisons are exploratory development checks, not proof of an investment edge.",
                              "The reported 2019-2020 holdout is spent and used only in the final development fit."]}
    return model, selection, validation_summary
