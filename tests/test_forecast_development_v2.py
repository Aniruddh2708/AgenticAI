"""Mathematical and temporal controls; generated data is not market evidence."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from vibefinance.evaluation import development as d


def frames(n=550):
    rng = np.random.default_rng(812)
    result = {}
    for t in ("HDFCBANK.NS", "INFY.NS", "ITC.NS", "RELIANCE.NS", "TCS.NS"):
        c = 100*np.exp(np.cumsum(rng.normal(.0002, .012, n)))
        result[t] = pd.DataFrame({"date": pd.bdate_range("2012-01-02", periods=n),
            "open": c, "high": c*1.01, "low": c*.99, "close": c,
            "volume": rng.integers(10000, 100000, n).astype(float)})
    return result


def learnable_rows(n=800):
    rng = np.random.default_rng(72)
    x = rng.normal(size=(n, len(d.FEATURES)))
    out = pd.DataFrame(x, columns=d.FEATURES)
    out["up"] = (rng.uniform(size=n) < 1/(1+np.exp(-2*x[:, 0]))).astype(int)
    out["forward_return"] = .05*x[:, 0]+rng.normal(0, .005, n)
    out["target_end"] = pd.bdate_range("2010-01-01", periods=n)
    out["momentum_label"] = np.where(x[:, 0] > 0, "BULLISH", "BEARISH")
    return out


def test_future_mutation_and_price_units_do_not_change_past_features():
    f = frames()
    before = d.feature_frames(f)
    changed = {t: v.copy() for t, v in f.items()}
    for v in changed.values():
        v.loc[400:, ["open", "high", "low", "close", "volume"]] *= 7
    after = d.feature_frames(changed)
    scaled = {t: v.assign(open=v.open*10, high=v.high*10, low=v.low*10, close=v.close*10) for t, v in f.items()}
    converted = d.feature_frames(scaled)
    for t in f:
        np.testing.assert_allclose(before[t].iloc[:400], after[t].iloc[:400], equal_nan=True)
        np.testing.assert_allclose(before[t], converted[t], equal_nan=True, atol=1e-9)


def test_targets_align_exactly_and_spent_labels_are_absent():
    f = frames(3600)
    rows, _ = d.observations(f)
    assert not rows.empty
    for row in rows.iloc[::149].itertuples():
        frame = f[row.ticker]
        assert row.target_end == frame.date.iloc[row.session_index+30]
        assert row.forward_return == pytest.approx(frame.close.iloc[row.session_index+30]/frame.close.iloc[row.session_index]-1)
    assert not rows.as_of.dt.year.isin([2018, 2019, 2020, 2024, 2025]).any()
    assert not rows.target_end.dt.year.isin([2018, 2019, 2020, 2024, 2025]).any()


def test_missing_peer_is_excluded_without_forward_fill():
    f = frames()
    missing_date = f["ITC.NS"].date.iloc[300]
    f["ITC.NS"] = f["ITC.NS"].drop(index=300).reset_index(drop=True)
    x = d.feature_frames(f)
    assert x["TCS.NS"].loc[300, "peer_return_20"] != x["TCS.NS"].loc[300, "peer_return_20"]
    rows, _ = d.observations(f)
    assert not ((rows.ticker == "TCS.NS") & (rows.as_of == missing_date)).any()


@pytest.mark.parametrize("kind", ["logistic", "stump_logistic", "ridge", "huber", "stump_squared"])
def test_candidates_learn_signal_on_independent_generated_rows_and_serialize(kind):
    train, test = learnable_rows().iloc[:600], learnable_rows().iloc[600:]
    model = json.loads(json.dumps(d.fit(train, kind, .1)))
    prediction = d.predict(model, test)
    if "logistic" in kind:
        assert ((prediction-test.up)**2).mean() < .25
        assert ((prediction > 0) & (prediction < 1)).all()
    else:
        assert np.abs(prediction-test.forward_return).mean() < np.abs(test.forward_return).mean()
    assert model["training_target_end"] < str(test.target_end.min().date())


def test_training_only_transforms_and_baseline_arithmetic():
    train, test = learnable_rows().iloc[:600], learnable_rows().iloc[600:]
    model = d.fit(train, "ridge")
    center = model["center"].copy()
    test = test.copy()
    test.loc[:, list(d.FEATURES)] *= 1e7
    d.predict(model, test)
    assert model["center"] == center
    p, r, _ = d.baselines(train, test)
    np.testing.assert_allclose(p["prior"], (train.up.sum()+1)/(len(train)+2))
    np.testing.assert_allclose(r["mean"], train.forward_return.mean())


def test_uncertainty_clusters_securities_together_and_selection_retains_baseline():
    dates = pd.date_range("2014-01-01", periods=32, freq="30D")
    rows = pd.DataFrame({"as_of": np.repeat(dates, 5), "fold": np.repeat(dates.year, 5)})
    y = np.tile([0, 0, 1, 1, 1], 32)
    p = {"constant_half": np.full(160, .5), "prior": np.full(160, .6),
         "momentum": np.full(160, .6), "candidate1": np.full(160, .6),
         "candidate2": np.full(160, .6), "candidate3": np.full(160, .6)}
    chosen = d.select(rows, p, ("constant_half", "prior", "momentum"), y, lambda p, y: (p-y)**2)
    assert chosen["chosen"] == "prior"
    assert chosen["per_comparison_alpha"] == pytest.approx(.05/9)
    ci = d.clustered_interval(rows, np.ones(160))
    assert ci["origin_dates"] == 32 and ci["shared_quarter_blocks"] < 32
    assert ci["low"] == ci["high"] == 1


def test_protocol_rejects_new_target_or_search_after_registration():
    p = json.loads(Path("data/forecast_development_v2_protocol.json").read_text())
    d.validate_protocol(p)
    with pytest.raises(ValueError):
        d.validate_protocol({**p, "horizon_sessions": 5})
    p["search_budget"]["boosting_rounds"] = 25
    with pytest.raises(ValueError):
        d.validate_protocol(p)


def test_prequential_residuals_are_matured_and_joint_denominator_is_origins():
    dates = pd.date_range("2014-01-01", periods=18, freq="45D")
    rows = pd.DataFrame([{"as_of": date, "target_end": date+pd.Timedelta(days=40),
        "ticker": ticker, "volatility_20": .02, "volatility_60": .02,
        "forward_return": .01} for date in dates for ticker in ("A", "B", "C", "D", "E")])
    p = np.zeros(len(rows))
    result = d.prequential_intervals(rows, p, .05)
    assert len(result["excluded_origins"]) == 9
    method = result["methods"]["pooled_absolute"]
    assert method["sample_size"] == 45
    assert method["simultaneous_coverage"]["complete_origins"] == 9
    altered = rows.copy()
    altered.loc[altered.as_of == dates[-1], "forward_return"] = .99
    changed = d.prequential_intervals(altered, p, .05)
    # The current outcome cannot change its own interval width.
    assert changed["methods"]["pooled_absolute"]["mean_width"] == method["mean_width"]
