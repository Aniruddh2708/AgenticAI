"""Fresh-period pipeline invariants on synthetic unit fixtures only.

No real fresh-period outcomes are opened by these tests. Fixture scores are not
evidence of forecasting skill and are never used to select the real protocol.
"""
import copy
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from vibefinance.config import TICKERS
from vibefinance.evaluation import forecast
from vibefinance.evaluation import forecast_followup as followup
from vibefinance.evaluation import forecast_selection as selection


@pytest.fixture(scope="module")
def followup_frames():
    dates = pd.bdate_range("2009-09-01", "2025-12-31")
    frames = {}
    for number, ticker in enumerate(TICKERS):
        rng = np.random.default_rng(9031 + number)
        session = np.arange(len(dates))
        daily_returns = .00015 + .0008 * np.sin(session / 101 + number) + rng.normal(0, .008, len(dates))
        close = (100 + 40 * number) * np.exp(np.cumsum(daily_returns))
        frame = pd.DataFrame({"date": dates, "open": close * .999,
                              "high": close * 1.01, "low": close * .99,
                              "close": close,
                              "volume": 1_000_000 * np.exp(rng.normal(0, .2, len(dates)))},
                             index=session * 7 + 13)
        frame.attrs["mode"] = "synthetic_unit_fixture"
        frames[ticker] = frame
    return frames


@pytest.fixture(scope="module")
def legacy(followup_frames):
    past = {ticker: frame[frame.date <= "2020-12-31"].copy()
            for ticker, frame in followup_frames.items()}
    return forecast.prepare(past, [{"source": "synthetic unit fixture"}])


@pytest.fixture(scope="module")
def followup_frozen(followup_frames, legacy):
    return followup.prepare_followup(followup_frames, [{"source": "synthetic unit fixture"}], legacy)


@pytest.fixture(scope="module")
def followup_report(followup_frames, followup_frozen):
    return followup.evaluate_followup(followup_frames, followup_frozen)


def test_preparation_cannot_learn_from_fresh_outcomes_or_volume(followup_frames, legacy, followup_frozen):
    changed = {ticker: frame.copy(deep=True) for ticker, frame in followup_frames.items()}
    for frame in changed.values():
        mask = frame.date >= "2024-01-01"
        factor = np.linspace(10, 40, int(mask.sum()))
        frame.loc[mask, ["open", "high", "low", "close"]] *= factor[:, None]
        frame.loc[mask, "volume"] *= 1000
    actual = followup.prepare_followup(changed, followup_frozen["data"], legacy)
    for key in ("protocol", "model", "selection", "validation", "calibration", "legacy",
                "primary_interval_method", "model_readiness", "period_status"):
        assert actual[key] == followup_frozen[key]
    assert actual["frame_fingerprints"] != followup_frozen["frame_fingerprints"]


def test_calibration_targets_mature_before_fresh_period_and_do_not_overlap(followup_frames, followup_frozen):
    protocol = followup.FollowupProtocol(**followup_frozen["protocol"])
    cropped = {ticker: frame[frame.date <= protocol.calibration_end].copy()
               for ticker, frame in followup_frames.items()}
    calibration = forecast.period(forecast.observations(cropped), protocol.calibration_start,
                                  protocol.calibration_end)
    assert len(calibration) == followup_frozen["calibration"]["sample_size"]
    assert calibration.as_of.nunique() == followup_frozen["calibration"]["shared_dates"]
    assert (calibration.target_end <= pd.Timestamp(protocol.calibration_end)).all()
    assert (calibration.target_end < pd.Timestamp(protocol.test_start)).all()
    for _, group in calibration.groupby("ticker"):
        assert (np.diff(group.session_index) >= protocol.horizon_sessions).all()
        assert (group.target_end.to_numpy()[:-1] <= group.as_of.to_numpy()[1:]).all()
    for model_calibration in followup_frozen["calibration"]["point_models"].values():
        assert model_calibration["methods"]["security_vol_scaled"]["quantile_units_by_ticker"] == {
            ticker: len(group) for ticker, group in calibration.groupby("ticker")}
        assert model_calibration["methods"]["joint_vol_scaled"]["quantile_units"] == calibration.as_of.nunique()


def test_floor_is_fitted_only_on_declared_development_features(followup_frames, followup_frozen):
    protocol = followup.FollowupProtocol(**followup_frozen["protocol"])
    cropped = {ticker: frame[frame.date <= protocol.refit_end].copy()
               for ticker, frame in followup_frames.items()}
    train = forecast.observations(cropped)
    train = train[train.as_of >= pd.Timestamp(protocol.development_start)]
    # The scale uses observed past returns, not calibration residuals, forecast
    # errors or a percentile fitted to the higher-volatility fresh test period.
    scale = train[["volatility_20", "volatility_60"]].max(axis=1).to_numpy(float) * np.sqrt(30)
    expected = max(1e-6, float(np.quantile(scale, .05)))
    assert followup_frozen["calibration"]["scale_floor"] == expected


def test_calibration_and_later_prices_cannot_change_the_development_fit_or_floor(followup_frames, legacy, followup_frozen):
    changed = {ticker: frame.copy(deep=True) for ticker, frame in followup_frames.items()}
    for frame in changed.values():
        mask = frame.date >= "2021-01-01"
        factor = np.exp(np.linspace(0, 2, int(mask.sum())))
        frame.loc[mask, ["open", "high", "low", "close"]] *= factor[:, None]
        frame.loc[mask, "volume"] *= 17
    actual = followup.prepare_followup(changed, followup_frozen["data"], legacy)
    for key in ("model", "selection", "validation", "legacy"):
        assert actual[key] == followup_frozen[key]
    assert actual["calibration"]["scale_floor"] == followup_frozen["calibration"]["scale_floor"]
    assert actual["calibration"]["point_models"] != followup_frozen["calibration"]["point_models"]


def test_preparation_and_evaluation_preserve_original_and_revised_frozen_inputs(followup_frames, legacy, followup_frozen):
    original_before, revised_before = copy.deepcopy(legacy), copy.deepcopy(followup_frozen)
    followup.prepare_followup(followup_frames, followup_frozen["data"], legacy)
    report = followup.evaluate_followup(followup_frames, followup_frozen)
    assert legacy == original_before
    assert followup_frozen == revised_before
    assert report["model_id"] == forecast.fingerprint(revised_before)
    assert report["model_readiness"] == "research_only"
    assert report["selection"]["admission"]["passed"] is False
    assert "spent" in report["period_status"]
    assert "spent development" in report["development_status"]


@pytest.mark.parametrize("change", ["price", "date", "universe"])
def test_evaluation_rejects_changes_to_the_frozen_snapshot(followup_frames, followup_frozen, change):
    changed = {ticker: frame.copy(deep=True) for ticker, frame in followup_frames.items()}
    frame = changed[TICKERS[0]]
    if change == "price":
        frame.iloc[-1, frame.columns.get_loc("close")] *= 1.01
    elif change == "date":
        frame.iloc[-1, frame.columns.get_loc("date")] += pd.Timedelta(days=1)
    else:
        changed.pop(TICKERS[0])
    with pytest.raises(ValueError, match="snapshot changed"):
        followup.evaluate_followup(changed, followup_frozen)


def test_point_metrics_and_paired_differences_use_the_identical_saved_dates(followup_report):
    records = followup_report["test_rows"]
    target = np.array([record["forward_return"] for record in records])
    y = np.array([record["realized_up"] for record in records])
    methods = set(records[0]["predictions"])
    assert len({(record["ticker"], record["as_of"]) for record in records}) == len(records)
    assert all(set(record["predictions"]) == methods for record in records)
    assert len(records) == followup_report["test"]["sample_size"]
    for name, scores in followup_report["test"]["metrics"].items():
        p = np.array([record["predictions"][name]["probability_up"] for record in records])
        r = np.array([record["predictions"][name]["return"] for record in records])
        assert scores["brier"] == pytest.approx(np.mean((p - y) ** 2))
        assert scores["mae_return"] == pytest.approx(np.mean(np.abs(r - target)))
        assert scores["rmse_return"] == pytest.approx(np.sqrt(np.mean((r - target) ** 2)))
        assert scores["accuracy"] == pytest.approx(np.mean((p >= .5) == y))
    selected = np.array([record["predictions"]["selected"]["probability_up"] for record in records])
    prior = np.array([record["predictions"]["prior_mean"]["probability_up"] for record in records])
    comparison = followup_report["test"]["uncertainty"]["selected_minus_prior_mean_brier"]
    assert comparison["estimate"] == pytest.approx(np.mean((selected - y) ** 2 - (prior - y) ** 2))
    assert comparison["low"] <= comparison["high"]
    assert comparison["calendar_quarter_blocks"] == 8


def test_interval_coverage_width_and_score_recompute_from_all_saved_method_bounds(followup_report):
    records = followup_report["test_rows"]
    target = np.array([record["forward_return"] for record in records])
    alpha = followup_report["protocol"]["interval_alpha"]
    for name in records[0]["predictions"]:
        for method in followup.INTERVAL_METHODS:
            lower = np.array([record["intervals"][name][method]["lower"] for record in records])
            upper = np.array([record["intervals"][name][method]["upper"] for record in records])
            score = followup_report["test"]["intervals"][name][method]
            covered = (target >= lower) & (target <= upper)
            below, above = np.maximum(lower - target, 0), np.maximum(target - upper, 0)
            assert score["coverage"] == pytest.approx(covered.mean())
            assert score["mean_width"] == pytest.approx((upper - lower).mean())
            assert score["interval_score"] == pytest.approx(np.mean(upper - lower + 2 / alpha * (below + above)))
            assert score["lower_miss_rate"] == pytest.approx(np.mean(target < lower))
            assert score["upper_miss_rate"] == pytest.approx(np.mean(target > upper))
            assert score["nominal_coverage"] == pytest.approx(.9)
            assert score["uncertainty"]["coverage"]["estimate"] == pytest.approx(covered.mean())
            assert score["uncertainty"]["width"]["estimate"] == pytest.approx((upper - lower).mean())
            assert score["uncertainty"]["interval_score"]["calendar_quarter_blocks"] == 8
    assert followup_report["test"]["primary_interval_method"] == "security_vol_scaled"


def test_security_and_year_subgroups_preserve_all_observations(followup_report):
    records = followup_report["test_rows"]
    summary = followup_report["test"]
    assert sum(value["sample_size"] for value in summary["by_ticker"].values()) == len(records)
    assert sum(value["sample_size"] for value in summary["by_year"].values()) == len(records)
    assert set(summary["by_year"]) == {"2024", "2025"}
    for ticker, subgroup in summary["by_ticker"].items():
        selected = [record for record in records if record["ticker"] == ticker]
        intervals = [record["intervals"]["selected"]["security_vol_scaled"] for record in selected]
        covered = [interval["lower"] <= record["forward_return"] <= interval["upper"]
                   for record, interval in zip(selected, intervals)]
        reported = summary["interval"]["by_ticker"][ticker]
        assert subgroup["sample_size"] == reported["sample_size"] == len(selected)
        assert reported["coverage"] == pytest.approx(np.mean(covered))


def test_original_radius_is_applied_without_recalibration_on_identical_fresh_dates(followup_report, legacy):
    records = followup_report["test_rows"]
    target = np.array([record["forward_return"] for record in records])
    center = np.array([record["predictions"]["legacy_selected"]["return"] for record in records])
    radius = legacy["calibration"]["interval_radius"]
    lower, upper = np.maximum(-1, center - radius), center + radius
    score = followup_report["test"]["intervals"]["legacy_selected"]["frozen_2018_absolute"]
    assert score["coverage"] == pytest.approx(np.mean((target >= lower) & (target <= upper)))
    assert score["mean_width"] == pytest.approx(np.mean(upper - lower))
    assert "2018" in score["calibration_period"]


@pytest.mark.parametrize("changes", [{"interval_alpha": .05}, {"test_start": "2023-01-01"},
                                         {"refit_end": "2021-12-31"}])
def test_followup_protocol_cannot_be_reconfigured_after_predeclaration(changes):
    with pytest.raises(ValueError, match="predeclared and fixed"):
        replace(followup.FollowupProtocol(), **changes).validate()


def test_baseline_ties_and_unsupported_complexity_keep_the_simpler_choice():
    rows = pd.DataFrame({"as_of": pd.to_datetime(["2016-01-04", "2016-04-04", "2016-07-04", "2016-10-04"]),
                         "ticker": ["A"] * 4})
    chosen, baseline, comparisons = selection._select(
        rows, {"prior": np.zeros(4), "constant_half": np.zeros(4), "complex": np.zeros(4)},
        ("prior", "constant_half"), np.zeros(4), lambda prediction, target: (prediction - target) ** 2)
    assert chosen == baseline == "prior"
    assert comparisons["complex"]["eligible"] is False
    # An apparent improvement on four quarters does not satisfy the explicit
    # minimum evidence rule, even when every observed candidate loss is smaller.
    chosen, baseline, comparisons = selection._select(
        rows, {"prior": np.ones(4), "complex": np.zeros(4)}, ("prior",),
        np.zeros(4), lambda prediction, target: (prediction - target) ** 2)
    assert chosen == baseline == "prior"
    assert comparisons["complex"]["difference"] < 0
    assert comparisons["complex"]["eligible"] is False
