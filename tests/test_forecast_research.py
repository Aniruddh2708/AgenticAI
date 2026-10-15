"""Research invariants on synthetic unit fixtures, never performance evidence.

These fixtures exercise chronology, fitting, identity and metric arithmetic. Their
scores are deliberately not used to claim improvement or tune the real protocol.
"""
import copy
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from vibefinance.config import TICKERS
from vibefinance.evaluation import forecast


@pytest.fixture(scope="module")
def market_frames():
    dates = pd.bdate_range("2009-09-01", "2020-12-31")
    frames = {}
    for number, ticker in enumerate(TICKERS):
        rng = np.random.default_rng(9817 + number)
        session = np.arange(len(dates))
        increments = (.0001 + .002 * np.sin(session / 73 + number)
                      + rng.normal(0, .008, len(dates)))
        close = (100 + 40 * number) * np.exp(np.cumsum(increments))
        frame = pd.DataFrame({"date": dates, "open": close * .999,
            "high": close * 1.01, "low": close * .99, "close": close,
            "volume": 1_000_000 * np.exp(rng.normal(0, .15, len(dates)))},
            # Non-default indices expose accidental label/position alignment.
            index=session * 3 + 11)
        frame.attrs["mode"] = "synthetic_unit_fixture"
        frames[ticker] = frame
    return frames


@pytest.fixture(scope="module")
def research_rows(market_frames):
    return forecast.observations(market_frames)


@pytest.fixture(scope="module")
def frozen(market_frames):
    sources = [{"ticker": ticker, "source": "synthetic unit fixture, not real data"}
               for ticker in TICKERS]
    return forecast.prepare(market_frames, sources)


@pytest.fixture(scope="module")
def holdout(market_frames, frozen):
    return forecast.evaluate(market_frames, frozen)


def test_feature_prefix_is_unchanged_by_future_prices_volume_or_extension(market_frames):
    frame = market_frames[TICKERS[0]]
    cutoff = int(np.flatnonzero((frame.date >= "2019-01-01").to_numpy())[0])
    changed = frame.copy(deep=True)
    changed.iloc[cutoff:, changed.columns.get_loc("close")] *= 25
    changed.iloc[cutoff:, changed.columns.get_loc("volume")] *= 100
    expected = forecast.features(frame).iloc[:cutoff]
    pd.testing.assert_frame_equal(forecast.features(changed).iloc[:cutoff], expected)
    pd.testing.assert_frame_equal(forecast.features(frame.iloc[:cutoff]), expected)


def test_target_is_exactly_thirty_input_sessions_ahead(market_frames, research_rows):
    for ticker, group in research_rows.groupby("ticker"):
        frame = market_frames[ticker]
        indices = group.session_index.to_numpy(int)
        np.testing.assert_array_equal(group.as_of.to_numpy(), frame.date.iloc[indices].to_numpy())
        np.testing.assert_array_equal(group.target_end.to_numpy(), frame.date.iloc[indices + 30].to_numpy())
        expected = frame.close.iloc[indices + 30].to_numpy() / frame.close.iloc[indices].to_numpy() - 1
        np.testing.assert_allclose(group.forward_return.to_numpy(), expected, rtol=0, atol=0)
        np.testing.assert_array_equal(group.up.to_numpy(), (expected > 0).astype(int))


@pytest.mark.parametrize("start,end", [
    ("2016-01-01", "2016-12-31"), ("2017-01-01", "2017-12-31"),
    ("2018-01-01", "2018-12-31"), ("2019-01-01", "2020-12-31"),
])
def test_scored_periods_purge_boundary_targets_and_do_not_overlap(research_rows, start, end):
    period = forecast.period(research_rows, start, end)
    assert set(period.ticker) == set(TICKERS)
    assert (period.as_of >= pd.Timestamp(start)).all()
    assert (period.target_end <= pd.Timestamp(end)).all()
    for _, group in period.groupby("ticker"):
        group = group.sort_values("as_of")
        assert (np.diff(group.session_index) >= 30).all()
        assert (group.target_end.to_numpy()[:-1] <= group.as_of.to_numpy()[1:]).all()


def test_preparation_cannot_learn_from_mutated_test_outcomes(market_frames, frozen):
    changed = {ticker: frame.copy(deep=True) for ticker, frame in market_frames.items()}
    for frame in changed.values():
        mask = frame.date >= "2019-01-01"
        factor = np.linspace(10, 30, int(mask.sum()))
        frame.loc[mask, ["open", "high", "low", "close"]] *= factor[:, None]
        frame.loc[mask, "volume"] *= 100
    other = forecast.prepare(changed, frozen["data"])
    for key in ("model", "selection", "validation", "calibration", "protocol"):
        assert other[key] == frozen[key]
    assert other["frame_fingerprints"] != frozen["frame_fingerprints"]


def test_expanding_folds_fit_only_matured_declared_training_data(frozen, research_rows):
    protocol = forecast.Protocol(**frozen["protocol"])
    for fold in frozen["validation"]["folds"]:
        fitted = forecast.training_rows(research_rows, protocol, fold["start"])
        assert len(fitted) == fold["training_rows"]
        assert (fitted.as_of >= pd.Timestamp(protocol.train_start)).all()
        assert (fitted.target_end < pd.Timestamp(fold["start"])).all()
        assert fold["training_target_end"] < fold["start"]
    assert frozen["model"]["training_target_end"] < protocol.calibration_start
    assert frozen["calibration"]["target_end"] < protocol.test_start


def test_custom_training_gap_is_excluded_from_every_actual_fit(monkeypatch, market_frames):
    protocol = replace(forecast.Protocol(), train_end="2014-12-31")
    real_fit = forecast.fit
    calls = []

    def inspect_fit(rows, probability_penalty, return_penalty):
        initial = ((rows.as_of >= pd.Timestamp(protocol.train_start)) &
                   (rows.target_end <= pd.Timestamp(protocol.train_end)))
        validation = ((rows.as_of >= pd.Timestamp(protocol.validation_start)) &
                      (rows.target_end <= pd.Timestamp(protocol.validation_end)))
        assert (initial | validation).all()
        assert not rows.as_of.dt.year.eq(2015).any()
        calls.append((len(rows), rows.target_end.max()))
        return real_fit(rows, probability_penalty, return_penalty)

    monkeypatch.setattr(forecast, "fit", inspect_fit)
    result = forecast.prepare(market_frames, [], protocol)
    assert calls
    assert calls[0][1] <= pd.Timestamp(protocol.train_end)
    assert result["validation"]["folds"][0]["training_target_end"] <= protocol.train_end
    assert result["model"]["training_rows"] == calls[-1][0]


def test_holdout_metrics_recompute_from_all_saved_same_row_predictions(holdout):
    records = holdout["test_rows"]
    target = np.array([row["forward_return"] for row in records])
    y = np.array([row["realized_up"] for row in records])
    metrics = holdout["test"]["metrics"]
    assert len(records) == holdout["test"]["sample_size"]
    assert len({(row["ticker"], row["as_of"]) for row in records}) == len(records)
    for name, scores in metrics.items():
        p = np.array([row["predictions"][name]["probability_up"] for row in records])
        r = np.array([row["predictions"][name]["return"] for row in records])
        assert scores["brier"] == pytest.approx(np.mean((p - y) ** 2))
        assert scores["mae_return"] == pytest.approx(np.mean(np.abs(r - target)))
        assert scores["rmse_return"] == pytest.approx(np.sqrt(np.mean((r - target) ** 2)))
        assert scores["accuracy"] == pytest.approx(np.mean((p >= .5) == y))
    assert metrics["constant_half_zero"]["brier"] == pytest.approx(.25)
    assert metrics["constant_half_zero"]["mae_return"] == pytest.approx(np.mean(np.abs(target)))
    assert metrics["always_up_zero"]["accuracy"] == pytest.approx(y.mean())
    selected = np.array([row["predictions"]["selected"]["probability_up"] for row in records])
    prior = np.array([row["predictions"]["prior_mean"]["probability_up"] for row in records])
    assert holdout["test"]["uncertainty"]["selected_minus_prior_mean_brier"]["difference"] == pytest.approx(
        np.mean((selected - y) ** 2 - (prior - y) ** 2))


def test_original_momentum_comparison_uses_its_exact_abstention_mask(holdout):
    records = holdout["test_rows"]
    directional = [row for row in records if row["momentum_label"] != "NEUTRAL"]
    measured = holdout["test"]["original_momentum_direction"]
    assert measured["total_windows"] == len(records)
    assert measured["scored_windows"] == len(directional)
    assert measured["neutral_abstentions"] == len(records) - len(directional)
    assert directional  # The fixture covers the directional branch.
    assert measured["hit_rate"] == pytest.approx(np.mean([
        (row["momentum_label"] == "BULLISH") == bool(row["realized_up"]) for row in directional]))
    assert measured["always_up_same_mask_hit_rate"] == pytest.approx(np.mean([
        row["realized_up"] for row in directional]))


def test_evaluation_preserves_frozen_selection_and_remains_research_only(market_frames, frozen):
    before = copy.deepcopy(frozen)
    result = forecast.evaluate(market_frames, frozen)
    assert frozen == before
    assert result["model_id"] == forecast.fingerprint(before)
    assert result["model_readiness"] == "research_only"
    assert frozen["selection"]["admission"] == {"passed": False, "reason": "Held-out test not yet evaluated"}
    for key in ("probability_model", "return_model", "probability_penalty", "return_penalty"):
        assert result["selection"][key] == before["selection"][key]


@pytest.mark.parametrize("change", ["price", "date", "universe"])
def test_evaluation_rejects_different_snapshot_identity(market_frames, frozen, change):
    changed = {ticker: frame.copy(deep=True) for ticker, frame in market_frames.items()}
    if change == "price":
        changed[TICKERS[0]].iloc[-1, changed[TICKERS[0]].columns.get_loc("close")] *= 1.01
    elif change == "date":
        changed[TICKERS[0]].iloc[-1, changed[TICKERS[0]].columns.get_loc("date")] += pd.Timedelta(days=1)
    else:
        changed.pop(TICKERS[0])
    with pytest.raises(ValueError, match="frames changed"):
        forecast.evaluate(changed, frozen)


def test_regularized_fit_converges_and_predicts_finitely_on_extreme_features(research_rows):
    train = research_rows.iloc[:600].copy()
    # Near separation and a constant column exercise logistic backtracking and
    # scaling safeguards without requiring a predictive score to improve.
    train["up"] = (np.arange(len(train)) % 3 == 0).astype(int)
    train["return_1"] = np.where(train.up, 1000.0, -1000.0)
    train["volume_ratio"] = 0.0
    model = forecast.fit(train, .01, .1)
    probe = train.iloc[:20].copy()
    probe.loc[:, "return_1"] *= 1_000_000
    p, r = forecast.predict(model, probe)
    assert np.isfinite(p).all() and np.isfinite(r).all()
    assert ((p >= 0) & (p <= 1)).all()
    assert model["scale"][-1] == 1.0
    np.testing.assert_allclose(model["mean"], train[list(forecast.FEATURES)].mean().to_numpy())


@pytest.mark.parametrize("changes", [
    {"train_end": "2016-01-01"}, {"calibration_end": "2019-01-01"},
    {"horizon_sessions": 0}, {"interval_alpha": 1.0},
])
def test_invalid_temporal_protocol_is_rejected(changes):
    with pytest.raises(ValueError):
        replace(forecast.Protocol(), **changes).validate()
