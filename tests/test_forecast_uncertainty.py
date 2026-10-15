"""Uncertainty arithmetic and information-boundary tests, not market evidence.

Small constructed residuals let these tests check finite-sample ranks, honest
units, and forecast-time inputs without choosing a method using real outcomes.
"""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from vibefinance.evaluation import forecast, uncertainty


def calibration_rows(n=25, tickers=("A", "B", "C", "D", "E")):
    records = []
    for i, date in enumerate(pd.bdate_range("2016-01-04", periods=n)):
        for j, ticker in enumerate(tickers, 1):
            records.append({"ticker": ticker, "as_of": date,
                            "forward_return": j * (.02 + .08 * i / max(1, n - 1)),
                            "volatility_20": .01 * j,
                            "volatility_60": .008 * j})
    return pd.DataFrame(records)


@pytest.mark.parametrize("scores,alpha,expected", [
    ([5, 1, 3, 2, 4, 6, 7, 8, 9], .1, 9),
    (list(range(1, 20)), .1, 18),
    ([0] * 25, .1, 0),
    ([.2, .7, .3, .1], .5, .3),
])
def test_residual_quantile_uses_the_requested_finite_sample_order_statistic(scores, alpha, expected):
    assert uncertainty.residual_quantile(scores, alpha) == pytest.approx(expected)


@pytest.mark.parametrize("size,alpha", [(8, .1), (40, .01), (1, .1)])
def test_unsupported_quantile_is_explicit_instead_of_clamped_to_the_maximum(size, alpha):
    with pytest.raises(ValueError, match="Insufficient calibration"):
        uncertainty.residual_quantile(np.arange(size), alpha)


@pytest.mark.parametrize("scores,alpha", [
    ([], .1), ([0, -1], .5), ([0, np.nan], .5), ([0, np.inf], .5),
    ([[0, 1]], .5), ([0, 1], 0), ([0, 1], 1), ([0, 1], np.nan),
])
def test_invalid_quantile_inputs_are_rejected(scores, alpha):
    with pytest.raises(ValueError):
        uncertainty.residual_quantile(scores, alpha)


def test_scale_uses_both_causal_volatilities_and_a_frozen_positive_floor():
    rows = pd.DataFrame({"volatility_20": [.01, .02, 0],
                         "volatility_60": [.03, .01, 0]})
    expected = [.03 * np.sqrt(30), .02 * np.sqrt(30), .005]
    np.testing.assert_allclose(uncertainty.causal_scale(rows, .005), expected)


@pytest.mark.parametrize("floor", [0, -.01, np.inf, np.nan])
def test_invalid_scale_floor_is_rejected(floor):
    with pytest.raises(ValueError, match="floor"):
        uncertainty.causal_scale(calibration_rows(), floor)


@pytest.mark.parametrize("value", [-.01, np.inf, np.nan])
def test_invalid_volatility_is_not_hidden_by_the_floor(value):
    rows = calibration_rows()
    rows.loc[0, "volatility_60"] = value
    with pytest.raises(ValueError, match="volatility"):
        uncertainty.causal_scale(rows, .001)


def test_security_absolute_quantiles_do_not_mix_residuals_between_securities():
    rows = calibration_rows(tickers=("A", "B"))
    calibration = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    probe = rows.groupby("ticker", sort=True).head(1).reset_index(drop=True)
    low, high = uncertainty.bounds(calibration, probe, np.zeros(len(probe)), "security_absolute")
    # Twenty-five observations at 90% use the 24th ordered residual, not an
    # interpolated sample percentile and not the largest pooled-security error.
    radius_a = .02 + .08 * 23 / 24
    np.testing.assert_allclose(low, [-radius_a, -2 * radius_a])
    np.testing.assert_allclose(high, [radius_a, 2 * radius_a])
    assert calibration["methods"]["security_absolute"]["quantile_units_by_ticker"] == {"A": 25, "B": 25}


def test_other_security_outcomes_cannot_change_the_primary_security_interval():
    rows = calibration_rows(tickers=("A", "B"))
    changed = rows.copy(deep=True)
    changed.loc[changed.ticker == "B", "forward_return"] *= 3
    original = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    other = uncertainty.calibrate(changed, np.zeros(len(rows)), .001)
    probe = rows[rows.ticker == "A"].iloc[:2]
    before = uncertainty.bounds(original, probe, np.zeros(len(probe)))
    after = uncertainty.bounds(other, probe, np.zeros(len(probe)))
    for expected, actual in zip(before, after):
        np.testing.assert_array_equal(actual, expected)
    assert original["methods"]["security_vol_scaled"]["radius_by_ticker"]["B"] != other["methods"]["security_vol_scaled"]["radius_by_ticker"]["B"]


def test_volatility_scaled_intervals_adapt_at_forecast_time_while_static_intervals_do_not():
    rows = calibration_rows(tickers=("A",))
    calibration = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    probe = rows.iloc[:2].copy()
    probe.loc[probe.index[1], "volatility_20"] *= 4
    scaled_lower, scaled_upper = uncertainty.bounds(calibration, probe, [0, 0])
    static_lower, static_upper = uncertainty.bounds(calibration, probe, [0, 0], "security_absolute")
    assert scaled_upper[1] - scaled_lower[1] == pytest.approx(4 * (scaled_upper[0] - scaled_lower[0]))
    assert static_upper[1] - static_lower[1] == pytest.approx(static_upper[0] - static_lower[0])


def test_eight_dates_do_not_become_forty_independent_primary_or_joint_units():
    rows = calibration_rows(n=8)
    calibration = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    assert calibration["sample_size"] == 40
    assert calibration["shared_dates"] == 8
    assert calibration["methods"]["pooled_absolute"]["available"] is True
    assert calibration["methods"]["pooled_absolute"]["quantile_units"] == 40
    for method in ("security_absolute", "security_vol_scaled", "joint_vol_scaled"):
        assert calibration["methods"][method]["available"] is False
        with pytest.raises(ValueError, match="Insufficient calibration"):
            uncertainty.bounds(calibration, rows.iloc[:5], np.zeros(5), method)


def test_joint_quantile_counts_shared_dates_and_uses_each_dates_maximum():
    rows = calibration_rows(n=10)
    # The largest normalized residual belongs to a different security per date.
    for i, date in enumerate(rows.as_of.unique()):
        mask = (rows.as_of == date) & (rows.ticker == ("A", "B", "C", "D", "E")[i % 5])
        scale = uncertainty.causal_scale(rows.loc[mask], .001)
        rows.loc[mask, "forward_return"] = (i + 1) * .2 * scale
    calibration = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    record = calibration["methods"]["joint_vol_scaled"]
    assert record["available"] is True
    assert record["quantile_units"] == 10
    # At n=10, the 90% finite-sample rank is 10: the last date's maximum is 2.
    assert record["radius"] == pytest.approx(2)
    probe = rows.iloc[:5]
    lower, upper = uncertainty.bounds(calibration, probe, np.zeros(5), "joint_vol_scaled")
    expected = 2 * uncertainty.causal_scale(probe, .001)
    np.testing.assert_allclose(lower, -expected)
    np.testing.assert_allclose(upper, expected)


def test_joint_intervals_are_unavailable_for_mismatched_security_calendars():
    rows = calibration_rows(n=25)
    rows = rows.drop(rows[(rows.ticker == "E") & (rows.as_of == rows.as_of.min())].index)
    calibration = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    assert calibration["methods"]["security_vol_scaled"]["available"] is True
    assert calibration["methods"]["joint_vol_scaled"]["available"] is False
    assert "aligned complete security universe" in calibration["methods"]["joint_vol_scaled"]["reason"]


def test_duplicate_calibration_rows_cannot_inflate_the_quantile_sample():
    rows = calibration_rows()
    rows = pd.concat([rows, rows.iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="unique"):
        uncertainty.calibrate(rows, np.zeros(len(rows)), .001)


@pytest.mark.parametrize("alpha", [0, 1, -.1, np.inf, np.nan])
def test_invalid_calibration_alpha_is_rejected_before_method_availability(alpha):
    rows = calibration_rows()
    with pytest.raises(ValueError, match="alpha"):
        uncertainty.calibrate(rows, np.zeros(len(rows)), .001, alpha)


@pytest.mark.parametrize("column,value", [("ticker", None), ("as_of", pd.NaT)])
def test_missing_calibration_identity_cannot_be_counted_as_a_unit(column, value):
    rows = calibration_rows()
    rows.loc[0, column] = value
    with pytest.raises(ValueError, match="ticker/date"):
        uncertainty.calibrate(rows, np.zeros(len(rows)), .001)


def test_missing_target_date_is_rejected_when_dates_are_supplied():
    rows = calibration_rows()
    rows["target_end"] = rows.as_of + pd.offsets.BDay(1)
    rows.loc[0, "target_end"] = pd.NaT
    with pytest.raises(ValueError, match="target dates"):
        uncertainty.calibrate(rows, np.zeros(len(rows)), .001)


@pytest.mark.parametrize("offset", [0, -1, 30])
def test_noncausal_or_overlapping_calibration_targets_are_rejected(offset):
    rows = calibration_rows()
    rows["target_end"] = rows.as_of + pd.offsets.BDay(offset)
    with pytest.raises(ValueError, match="chronological and non-overlapping"):
        uncertainty.calibrate(rows, np.zeros(len(rows)), .001)


def test_adjacent_nonoverlapping_targets_are_valid_even_when_rows_are_shuffled():
    rows = calibration_rows()
    rows["target_end"] = rows.as_of + pd.offsets.BDay(1)
    expected = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    shuffled = rows.sample(frac=1, random_state=179).reset_index(drop=True)
    assert uncertainty.calibrate(shuffled, np.zeros(len(shuffled)), .001) == expected


def test_bounds_need_no_future_outcomes_or_target_dates_and_do_not_modify_inputs():
    rows = calibration_rows()
    before = rows.copy(deep=True)
    centers = np.zeros(len(rows))
    calibration = uncertainty.calibrate(rows, centers, .001)
    pd.testing.assert_frame_equal(rows, before)
    np.testing.assert_array_equal(centers, 0)
    # The only future inputs to interval construction are causal volatility and
    # frozen centers; no forward_return or target_end field is supplied.
    probe = rows.drop(columns="forward_return").iloc[:5].copy()
    expected = uncertainty.bounds(calibration, probe, np.zeros(5))
    probe["forward_return"] = [10, -1, 1_000_000, np.nan, np.inf]
    probe["target_end"] = pd.Timestamp("2099-01-01")
    actual = uncertainty.bounds(calibration, probe, np.zeros(5))
    for old, new in zip(expected, actual):
        np.testing.assert_array_equal(old, new)
    np.testing.assert_array_equal(uncertainty.causal_scale(probe, .001),
                                  uncertainty.causal_scale(before.iloc[:5], .001))


def test_bounds_reject_unknown_security_and_changes_to_the_frozen_floor():
    rows = calibration_rows()
    calibration = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    probe = rows.iloc[:1].copy()
    probe["ticker"] = "UNSEEN"
    with pytest.raises(ValueError, match="Uncalibrated"):
        uncertainty.bounds(calibration, probe, [0])
    with pytest.raises(ValueError, match="floor mismatch"):
        uncertainty.bounds(calibration, rows.iloc[:1], [0], floor=.002)


def test_bounds_clip_the_return_support_and_reject_impossible_point_estimates():
    rows = calibration_rows(tickers=("A",))
    calibration = uncertainty.calibrate(rows, np.zeros(len(rows)), .001)
    lower, upper = uncertainty.bounds(calibration, rows.iloc[:1], [-.99])
    assert lower[0] == -1
    assert lower[0] <= upper[0]
    with pytest.raises(ValueError, match="at least -100%"):
        uncertainty.bounds(calibration, rows.iloc[:1], [-1.01])


def test_interval_metrics_count_endpoints_and_report_observed_coverage_separately():
    rows = pd.DataFrame({"forward_return": [-.5, -.1, 0, .5, 1]})
    lower = np.array([-.4, -.1, -.2, -.5, -.2])
    upper = np.array([.4, .1, .2, .5, .8])
    result = uncertainty.interval_metrics(rows, lower, upper, alpha=.1)
    assert result["nominal_coverage"] == pytest.approx(.9)
    assert result["coverage"] == pytest.approx(3 / 5)
    assert result["lower_miss_rate"] == pytest.approx(1 / 5)
    assert result["upper_miss_rate"] == pytest.approx(1 / 5)
    assert result["mean_width"] == pytest.approx((.8 + .2 + .4 + 1 + 1) / 5)
    # One lower miss of 0.1 and one upper miss of 0.2 cost 20 times their size.
    assert result["interval_score"] == pytest.approx((2.8 + .2 + .4 + 1 + 5) / 5)


@pytest.mark.parametrize("lower,upper,alpha", [
    ([1], [0], .1), ([0], [np.inf], .1), ([0, 0], [1, 1], .1),
    ([0], [1], 0), ([0], [1], 1),
])
def test_invalid_interval_metrics_inputs_are_rejected(lower, upper, alpha):
    with pytest.raises(ValueError, match="Invalid interval"):
        uncertainty.interval_metrics(pd.DataFrame({"forward_return": [0]}), lower, upper, alpha)


def test_core_prepare_rejects_unsupported_high_coverage_instead_of_changing_alpha():
    dates = pd.bdate_range("2009-09-01", "2020-12-31")
    frames = {}
    for i, ticker in enumerate(("A", "B", "C")):
        rng = np.random.default_rng(791 + i)
        close = 100 * np.exp(np.cumsum(rng.normal(.0002, .009, len(dates))))
        frames[ticker] = pd.DataFrame({"date": dates, "close": close,
                                       "volume": np.full(len(dates), 1_000_000)})
    protocol = replace(forecast.Protocol(), interval_alpha=.01)
    with pytest.raises(ValueError, match="Insufficient calibration"):
        forecast.prepare(frames, [], protocol)
