"""Selection and chronology checks on synthetic fixtures, not score evidence."""
import numpy as np
import pandas as pd
import pytest

from vibefinance.config import TICKERS
from vibefinance.evaluation import forecast, forecast_selection as selection


@pytest.fixture(scope="module")
def synthetic_frames():
    dates = pd.bdate_range("2009-09-01", "2025-12-31")
    frames = {}
    for number, ticker in enumerate(TICKERS):
        rng = np.random.default_rng(4819 + number)
        session = np.arange(len(dates))
        increments = (.0001 + .0015 * np.sin(session / 89 + number)
                      + rng.normal(0, .009, len(dates)))
        close = (100 + 30 * number) * np.exp(np.cumsum(increments))
        frames[ticker] = pd.DataFrame({"date": dates, "close": close,
                                      "volume": np.exp(rng.normal(14, .2, len(dates)))})
        frames[ticker].attrs["mode"] = "synthetic_unit_fixture"
    return frames


@pytest.fixture(scope="module")
def selected(synthetic_frames):
    return selection.select_models(synthetic_frames)


def test_validation_candidates_reproduce_original_causal_folds(synthetic_frames, selected):
    original = forecast.prepare(synthetic_frames, [])
    _, chosen, validation = selected
    for name, scores in original["validation"]["candidate_metrics"].items():
        assert validation["candidate_metrics"][name]["brier"] == pytest.approx(scores["brier"])
        assert validation["candidate_metrics"][name]["mae_return"] == pytest.approx(scores["mae_return"])
    for original_fold, fold in zip(original["validation"]["folds"], validation["folds"]):
        assert all(fold[key] == value for key, value in original_fold.items())
        assert fold["training_target_end"] < fold["start"]
    assert chosen["stability_rule"]["minimum_calendar_quarters"] == 8
    assert chosen["stability_rule"]["resamples"] == 2000
    assert chosen["stability_rule"]["seed"] == 2708


def test_future_outcomes_cannot_change_selection_or_development_fit(synthetic_frames, selected):
    changed = {ticker: frame.copy(deep=True) for ticker, frame in synthetic_frames.items()}
    for frame in changed.values():
        mask = frame.date >= "2021-01-01"
        frame.loc[mask, "close"] *= np.linspace(10, 40, int(mask.sum()))
        frame.loc[mask, "volume"] *= 1000
    assert selection.select_models(changed) == selected


def test_final_fit_uses_only_matured_development_targets(synthetic_frames, selected):
    model, _, validation = selected
    rows = forecast.observations(synthetic_frames)
    expected = rows[(rows.as_of >= "2010-01-01") & (rows.target_end <= "2020-12-31")]
    assert model["training_rows"] == len(expected)
    assert model["training_target_end"] == str(expected.target_end.max().date())
    assert model["training_origin_dates"] == expected.as_of.nunique()
    assert model["training_rows_by_ticker"] == expected.groupby("ticker").size().to_dict()
    np.testing.assert_allclose(model["mean"], expected[list(forecast.FEATURES)].mean().to_numpy())
    assert model["training_target_end"] <= "2020-12-31"
    assert validation["target_end"] <= "2017-12-31"


def test_learned_point_improvement_without_stability_keeps_baseline():
    rows = pd.DataFrame({"as_of": pd.date_range("2016-01-01", periods=8, freq="QS")})
    target = np.zeros(8)
    candidates = {"mean": np.ones(8), "zero": np.full(8, 2.),
                  "ridge_1.0": np.array([.98] * 4 + [1.018] * 4)}
    name, baseline, results = selection._select(
        rows, candidates, ("mean", "zero"), target, lambda p, y: np.abs(p - y))
    assert results["ridge_1.0"]["difference"] < 0
    assert results["ridge_1.0"]["high"] > 0
    assert results["ridge_1.0"]["eligible"] is False
    assert name == baseline == "mean"


def test_supported_paired_improvement_can_replace_baseline():
    rows = pd.DataFrame({"as_of": pd.date_range("2016-01-01", periods=8, freq="QS")})
    candidates = {"mean": np.ones(8), "zero": np.full(8, 2.), "ridge_1.0": np.full(8, .8)}
    name, baseline, results = selection._select(
        rows, candidates, ("mean", "zero"), np.zeros(8), lambda p, y: np.abs(p - y))
    assert results["ridge_1.0"]["high"] == pytest.approx(-.2)
    assert results["ridge_1.0"]["eligible"] is True
    assert name == "ridge_1.0"
    assert baseline == "mean"


def test_fewer_than_eight_quarters_cannot_admit_learned_candidate():
    rows = pd.DataFrame({"as_of": pd.date_range("2016-01-01", periods=7, freq="QS")})
    result = selection.paired_loss_comparison(rows, np.full(7, .1), np.full(7, .2))
    assert result["high"] < 0
    assert result["calendar_quarter_blocks"] == 7
    assert result["eligible"] is False


def test_stocks_share_quarter_draws_and_do_not_inflate_precision():
    rows = pd.DataFrame({"as_of": pd.date_range("2016-01-01", periods=8, freq="QS")})
    baseline_loss = np.full(8, .2)
    candidate_loss = np.linspace(.1, .25, 8)
    single = selection.paired_loss_comparison(rows, candidate_loss, baseline_loss)
    repeated_rows = pd.concat([rows] * 5, ignore_index=True)
    repeated = selection.paired_loss_comparison(
        repeated_rows, np.tile(candidate_loss, 5), np.tile(baseline_loss, 5))
    for key in ("difference", "low", "high"):
        assert single[key] == pytest.approx(repeated[key])
    assert repeated["calendar_quarter_blocks"] == 8


def test_comparison_rejects_unpaired_or_nonfinite_losses():
    rows = pd.DataFrame({"as_of": pd.date_range("2016-01-01", periods=8, freq="QS")})
    with pytest.raises(ValueError, match="same validation observations"):
        selection.paired_loss_comparison(rows, np.zeros(7), np.zeros(8))
    with pytest.raises(ValueError, match="finite"):
        selection.paired_loss_comparison(rows, np.full(8, np.nan), np.zeros(8))


def test_selected_metrics_use_chosen_baseline_or_candidate(selected):
    _, chosen, validation = selected
    probability_scores = validation["candidate_metrics"][chosen["probability_model"]]
    return_scores = validation["candidate_metrics"][chosen["return_model"]]
    assert validation["selected_metrics"]["brier"] == probability_scores["brier"]
    assert validation["selected_metrics"]["mae_return"] == return_scores["mae_return"]
    assert chosen["admission"]["passed"] is False
