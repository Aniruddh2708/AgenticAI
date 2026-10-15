"""Predeclared fresh-period uncertainty investigation; never promotes actions."""
from dataclasses import asdict, dataclass
import copy

import numpy as np
import pandas as pd

from vibefinance.evaluation import forecast as core
from vibefinance.evaluation.forecast_selection import select_models
from vibefinance.evaluation.uncertainty import bounds, calibrate, causal_scale, interval_metrics


@dataclass(frozen=True)
class FollowupProtocol:
    development_start: str = "2010-01-01"
    refit_end: str = "2020-12-31"
    calibration_start: str = "2021-01-01"
    calibration_end: str = "2023-12-31"
    test_start: str = "2024-01-01"
    test_end: str = "2025-12-31"
    horizon_sessions: int = 30
    interval_alpha: float = .1
    scale_floor_quantile: float = .05

    def validate(self):
        # This investigation is fixed before fresh evaluation, not a CLI grid.
        if asdict(self) != asdict(FollowupProtocol()):
            raise ValueError("Follow-up protocol is predeclared and fixed")


POINT_METHODS = {
    "prior_mean": ("prior", "mean"), "constant_half_zero": ("constant_half", "zero"),
    "always_up_zero": ("always_up", "zero"), "momentum": ("momentum", "momentum"),
}
INTERVAL_METHODS = ("pooled_absolute", "security_absolute", "security_vol_scaled", "joint_vol_scaled")


def _past(frames, end):
    return {ticker: frame[frame.date <= pd.Timestamp(end)].copy() for ticker, frame in frames.items()}


def _points(rows, model, selection, legacy):
    results = {"selected": core.predict(model, rows, selection["probability_kind"], selection["return_kind"])}
    results.update({name: core.predict(model, rows, *kinds) for name, kinds in POINT_METHODS.items()})
    results["legacy_selected"] = core.predict(legacy["model"], rows,
        legacy["selection"]["probability_kind"], legacy["selection"]["return_kind"])
    return results


def prepare_followup(frames, metadata, legacy, protocol=FollowupProtocol()):
    protocol.validate()
    model, selection, validation = select_models(frames)
    train = core.observations(_past(frames, protocol.refit_end))
    train = train[train.as_of >= pd.Timestamp(protocol.development_start)]
    raw_scale = train[["volatility_20", "volatility_60"]].max(axis=1).to_numpy(float) * np.sqrt(30)
    floor = max(1e-6, float(np.quantile(raw_scale, protocol.scale_floor_quantile)))
    # Crop BEFORE constructing targets: no 2024+ labels are even computed here.
    cal_rows = core.period(core.observations(_past(frames, protocol.calibration_end)),
                           protocol.calibration_start, protocol.calibration_end)
    if cal_rows.empty or cal_rows.as_of.nunique() < 20:
        raise ValueError("Need at least twenty shared calibration forecast dates")
    predictions = _points(cal_rows, model, selection, legacy)
    calibrations = {name: calibrate(cal_rows, returns, floor, protocol.interval_alpha)
                    for name, (_, returns) in predictions.items()}
    if any(not record["available"] for entry in calibrations.values() for record in entry["methods"].values()):
        raise ValueError("Insufficient support for a predeclared calibration comparator")
    cal = {"sample_size": len(cal_rows), "shared_dates": int(cal_rows.as_of.nunique()),
        "as_of_start": str(cal_rows.as_of.min().date()), "as_of_end": str(cal_rows.as_of.max().date()),
        "target_end": str(cal_rows.target_end.max().date()), "scale_floor": floor,
        "floor_fitted_on": "Only pre-2021 development price/volatility features",
        "primary": "security_vol_scaled", "point_models": calibrations,
        "guarantee": "No market exchangeability or future-coverage guarantee"}
    return {"schema_version": 1, "kind": "historical_price_forecast", "experiment_version": 2,
        "protocol": asdict(protocol), "features": list(core.FEATURES), "data": metadata,
        "model": model, "selection": selection, "validation": validation, "calibration": cal,
        "frame_fingerprints": core.frame_fingerprints(frames),
        "legacy": {"model": copy.deepcopy(legacy["model"]), "selection": copy.deepcopy(legacy["selection"]),
                   "interval_radius": legacy["calibration"]["interval_radius"]},
        "primary_interval_method": "security_vol_scaled",
        "model_readiness": "research_only", "period_status": "2024-2025 not yet evaluated",
        "horizon_definition": "30 observed positive-volume vendor rows; exchange calendar completeness not established",
        "development_status": "2019-2020 is spent development data; reused for refitting, never re-labelled as a test",
        "comparison_plan": "All point baselines share test dates; each interval uses the same 2021-2023 calibration dates and causal scale rule. Primary interval chosen before fresh scores."}


def _losses(rows, probability, returns, lower=None, upper=None, alpha=.1):
    y, target = rows.up.to_numpy(float), rows.forward_return.to_numpy(float)
    result = {"brier": (probability-y)**2, "mae_return": np.abs(returns-target)}
    if lower is not None:
        result.update(coverage=((target >= lower) & (target <= upper)).astype(float), width=upper-lower,
            interval_score=upper-lower+2/alpha*(np.maximum(lower-target,0)+np.maximum(target-upper,0)))
    return result


def clustered_interval(rows, values, draws):
    blocks = rows.as_of.dt.to_period("Q").astype(str).to_numpy()
    names = sorted(set(blocks))
    sums = np.array([values[blocks == name].sum() for name in names])
    counts = np.array([(blocks == name).sum() for name in names])
    sampled = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {"estimate": float(values.mean()), "low": float(np.quantile(sampled,.025)),
        "high": float(np.quantile(sampled,.975)), "level": .95,
        "calendar_quarter_blocks": len(names), "method": "Paired shared-calendar-quarter percentile bootstrap, approximate and low-power"}


def simultaneous_coverage(rows, covered, securities):
    """Only complete declared-universe origins can score simultaneous coverage."""
    if rows[["as_of", "ticker"]].duplicated().any():
        raise ValueError("Duplicate security/date coverage observations")
    covered = np.asarray(covered, float)
    if covered.shape != (len(rows),) or not np.isfinite(covered).all() or not np.isin(covered,[0,1]).all():
        raise ValueError("Coverage observations must be aligned finite indicators")
    expected=set(securities)
    if not expected or not set(rows.ticker).issubset(expected):
        raise ValueError("Coverage rows must belong to the declared universe")
    complete,partial=[],0
    for date,group in rows.assign(covered=covered.astype(bool)).groupby("as_of"):
        if set(group.ticker)==expected:
            complete.append((date,bool(group.covered.all())))
        else:
            partial+=1
    return {"coverage":float(np.mean([value for _,value in complete])) if complete else None,
        "complete_forecast_dates":len(complete),"excluded_partial_forecast_dates":partial,
        "calendar_quarters":len({pd.Timestamp(date).to_period('Q') for date,_ in complete}),
        "definition":"All declared securities at the same origin; security-specific vendor-row targets may end on different dates",
        "limitation":"Partial groups are unscored; complete origins may cover fewer periods than marginal evaluation"}


def evaluate_followup(frames, frozen):
    protocol = FollowupProtocol(**frozen["protocol"])
    protocol.validate()
    if core.frame_fingerprints(frames) != frozen["frame_fingerprints"]:
        raise ValueError("Fresh data snapshot changed after freeze")
    rows = core.period(core.observations(frames), protocol.test_start, protocol.test_end)
    if len(rows) < 20 or rows.ticker.nunique() != len(frames):
        raise ValueError("Insufficient declared fresh evaluation rows")
    results = _points(rows, frozen["model"], frozen["selection"], frozen["legacy"])
    summary = core._summary(rows, results)
    quarters = rows.as_of.dt.to_period("Q").nunique()
    draws = np.random.default_rng(2708).integers(0, quarters, (2000, quarters))
    intervals, arrays = {}, {}
    for name, (p, r) in results.items():
        arrays[name] = _losses(rows, p, r)
        intervals[name] = {}
        for method in INTERVAL_METHODS:
            lo, hi = bounds(frozen["calibration"]["point_models"][name], rows, r, method)
            score = interval_metrics(rows, lo, hi, protocol.interval_alpha)
            values = _losses(rows, p, r, lo, hi, protocol.interval_alpha)
            score["uncertainty"] = {key: clustered_interval(rows, values[key], draws)
                                    for key in ("coverage", "width", "interval_score")}
            joint = simultaneous_coverage(rows,values["coverage"],frames)
            score["simultaneous_security_coverage"] = joint["coverage"]
            score["simultaneous_coverage_details"] = joint
            score["by_ticker"] = {ticker: {"sample_size": int(mask.sum()),
                **interval_metrics(rows[mask], lo[mask], hi[mask], protocol.interval_alpha)}
                for ticker in sorted(frames) for mask in [rows.ticker.to_numpy() == ticker]}
            score["by_year"] = {str(year): {"sample_size": int(mask.sum()),
                **interval_metrics(rows[mask], lo[mask], hi[mask], protocol.interval_alpha)}
                for year in sorted(rows.as_of.dt.year.unique()) for mask in [rows.as_of.dt.year.to_numpy() == year]}
            intervals[name][method] = score
            arrays[name + "__" + method] = values
    # Original frozen interval, applied without recalibration to identical dates.
    lp, lr = results["legacy_selected"]
    radius = frozen["legacy"]["interval_radius"]
    lo, hi = np.maximum(-1, lr-radius), lr+radius
    legacy_values = _losses(rows, lp, lr, lo, hi, protocol.interval_alpha)
    intervals["legacy_selected"]["frozen_2018_absolute"] = {
        **interval_metrics(rows,lo,hi,protocol.interval_alpha),
        "uncertainty": {key: clustered_interval(rows, legacy_values[key], draws)
                        for key in ("coverage","width","interval_score")},
        "calibration_period": "Frozen original 2018 residuals; point model trained through 2017"}
    arrays["legacy_selected__frozen_2018_absolute"] = legacy_values
    primary_key = "selected__security_vol_scaled"
    paired = {}
    for baseline in ("prior_mean", "constant_half_zero", "momentum", "legacy_selected"):
        for loss in ("brier", "mae_return"):
            paired[f"selected_minus_{baseline}_{loss}"] = clustered_interval(rows,
                arrays["selected"][loss] - arrays[baseline][loss], draws)
    for comparator in ("selected__pooled_absolute", "selected__security_absolute", "selected__joint_vol_scaled",
                       "prior_mean__security_vol_scaled", "constant_half_zero__security_vol_scaled",
                       "legacy_selected__frozen_2018_absolute"):
        for loss in ("coverage", "width", "interval_score"):
            paired[f"primary_minus_{comparator}_{loss}"] = clustered_interval(rows,
                arrays[primary_key][loss]-arrays[comparator][loss],draws)
    p, r = results["selected"]
    summary.update(intervals=intervals, uncertainty=paired, shared_dates=int(rows.as_of.nunique()),
        primary_interval_method=frozen["primary_interval_method"],
        interval=intervals["selected"]["security_vol_scaled"],
        by_ticker={ticker: {"sample_size":int(mask.sum()),"metrics":{name:core.metrics(rows[mask],pp[mask],rr[mask])
            for name,(pp,rr) in results.items()}} for ticker in sorted(frames) for mask in [rows.ticker.to_numpy()==ticker]},
        by_year={str(year): {"sample_size":int(mask.sum()),"metrics":{name:core.metrics(rows[mask],pp[mask],rr[mask])
            for name,(pp,rr) in results.items()}} for year in sorted(rows.as_of.dt.year.unique())
            for mask in [rows.as_of.dt.year.to_numpy()==year]})
    selection = copy.deepcopy(frozen["selection"])
    baseline_retained = selection["probability_kind"] in {"prior", "constant_half"} and selection["return_kind"] in {"mean", "zero"}
    point_reason = "Baseline retained; no feature-model superiority established. " if baseline_retained else "Feature candidate remains research-only pending independent replication. "
    selection["admission"] = {"passed":False,
        "reason":point_reason+"Interval evidence is empirical, with only eight time blocks and no future-coverage guarantee. No action or deployment promotion."}
    records = []
    for i,row in rows.iterrows():
        per_method = {}
        for name,(_,rr) in results.items():
            per_method[name] = {}
            for method in INTERVAL_METHODS:
                ll, uu = bounds(frozen["calibration"]["point_models"][name],rows.iloc[[i]],rr[i:i+1],method)
                per_method[name][method] = {"lower":float(ll[0]),"upper":float(uu[0])}
        records.append({"ticker":row.ticker,"as_of":str(row.as_of.date()),"target_end":str(row.target_end.date()),
            "forward_return":float(row.forward_return),"realized_up":int(row.up),
            "causal_scale":float(causal_scale(rows.iloc[[i]],frozen["calibration"]["scale_floor"])[0]),
            "predictions":{name:{"probability_up":float(pp[i]),"return":float(rr[i])} for name,(pp,rr) in results.items()},
            "intervals":per_method})
    return {"schema_version":1,"kind":"historical_price_forecast","experiment_version":2,
        "protocol":frozen["protocol"],"features":frozen["features"],"data":frozen["data"],
        "model_id":core.fingerprint(frozen),"selection":selection,"validation":frozen["validation"],
        "calibration":frozen["calibration"],"test":summary,"test_rows":records,"model_readiness":"research_only",
        "period_status":"2024-2025 evaluated once and now spent; any subsequent analysis is exploratory",
        "horizon_definition":frozen["horizon_definition"],"development_status":frozen["development_status"],
        "limitations":[
            "Third-party retrospective Yahoo archive; independent provider cross-check and exchange-calendar completeness not established.",
            "Thirty observed vendor traded rows, not a guaranteed complete exchange-session calendar or executable trading strategy.",
            "Existing five-stock survivor universe; no point-in-time index constituents, authentic historical text or personalized effectiveness target.",
            "Same-date securities share shocks. Per-security calibration has only about twenty-four non-overlapping dates; dependence across time remains.",
            "Quarter-cluster confidence intervals are approximate, with only eight test quarters and dependence across boundaries possible.",
            "Volatility at forecast time cannot anticipate every future regime jump; nominal 90% is a target, never a coverage guarantee.",
            "Joint intervals target simultaneous coverage over the five securities; compare them separately from marginal intervals.",
            "Primary interval and baseline preference were fixed before fresh scores; reported comparators are not selected using this test.",
            "Original 2019-2020 results remain frozen and spent. This 2024-2025 evaluation is now spent too; no retuning or automatic promotion."]}
