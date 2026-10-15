"""Actual five-agent replay on small, explicitly synthetic price unit fixtures."""
import asyncio
from collections import Counter

import numpy as np
import pandas as pd
import pytest

from vibefinance.config import TICKERS
from vibefinance.evaluation import historical_policy as replay
from vibefinance.evaluation.forecast import Protocol, frame_fingerprints
from vibefinance.profiles.store import Store


@pytest.fixture
def inputs():
    dates = pd.bdate_range("2018-09-01", "2019-07-31")
    frames = {}
    for number, ticker in enumerate(TICKERS):
        phase = np.arange(len(dates))
        close = (100 + number * 20) * np.exp(.0003 * phase + .02 * np.sin(phase / 8))
        frame = pd.DataFrame({"date": dates, "open": close, "high": close * 1.01,
                             "low": close * .99, "close": close,
                             "volume": 1_000_000 + 10_000 * np.sin(phase / 5)})
        frame.attrs.update(mode="synthetic_unit_fixture", source_id=f"unit-price:{ticker}")
        frames[ticker] = frame
    protocol = Protocol()
    frozen = {"protocol": vars(protocol), "frame_fingerprints": frame_fingerprints(frames),
              "data": [{"ticker": ticker, "source": "synthetic unit fixture"} for ticker in TICKERS]}
    return frames, frozen


def test_real_pipeline_withholds_text_and_preserves_portfolio_safeguards(inputs, monkeypatch, tmp_path):
    frames, frozen = inputs
    real_period, real_analyze = replay.period, replay.analyze
    calls = []
    store = Store(tmp_path / "unchanged.sqlite3")
    before = store.path.read_bytes()

    def one_cutoff_per_ticker(*args):
        # Limit runtime without replacing any agent, retrieval or synthesis code.
        return real_period(*args).groupby("ticker", sort=False).head(1).reset_index(drop=True)

    async def inspect_call(ticker, profile, **kwargs):
        assert kwargs["persist"] is False
        assert kwargs["retriever"].chunks == []
        assert (kwargs["frame"].date <= pd.Timestamp(kwargs["as_of"])).all()
        assert kwargs["frame"].date.iloc[-1] == pd.Timestamp(kwargs["as_of"])
        calls.append((ticker, profile.user_id, kwargs["as_of"]))
        return await real_analyze(ticker, profile, **kwargs)

    def forbidden_save(*args):
        raise AssertionError("Historical replay must never write a session")

    monkeypatch.setattr(replay, "period", one_cutoff_per_ticker)
    monkeypatch.setattr(replay, "analyze", inspect_call)
    monkeypatch.setattr(Store, "save_session", forbidden_save)
    result = asyncio.run(replay.historical_policy_evaluation(frames, frozen))
    assert len(calls) == 15
    assert {call[0] for call in calls} == set(TICKERS)
    assert result["price_window_count"] == 5
    assert result["profile_decision_count"] == 15
    assert result["profiles_per_price_window"] == 3
    assert result["action_counts"] == {"REDUCE": 5, "WATCH": 10}
    assert result["action_counts"] == dict(sorted(Counter(row["action"] for row in result["decision_rows"]).items()))
    assert result["policy_checks"]["concentration_override"]["evaluated"] == 5
    assert result["policy_checks"]["missing_fundamentals_pause_entry"]["evaluated"] == 10
    assert result["policy_checks"]["cash_not_equity_high_risk"]["evaluated"] == 5
    assert all(check["passed"] == check["evaluated"] and check["violations"] == 0
               for check in result["policy_checks"].values())
    assert store.path.read_bytes() == before
    assert "synthetic" in result["profile_data"]
    assert "unavailable" in result["text_data"]
    assert result["model_readiness"] == "research_only"
    assert not any("forward_return" in row or "accuracy" in row for row in result["decision_rows"])


def test_replay_rejects_changed_snapshot_before_running_agents(inputs, monkeypatch):
    frames, frozen = inputs
    frames[TICKERS[0]].loc[0, "close"] *= 2

    async def forbidden(*args, **kwargs):
        raise AssertionError("A changed input must not reach agents")

    monkeypatch.setattr(replay, "analyze", forbidden)
    with pytest.raises(ValueError, match="frames changed"):
        asyncio.run(replay.historical_policy_evaluation(frames, frozen))


def test_replay_requires_exact_declared_universe(inputs):
    frames, frozen = inputs
    frames.pop(TICKERS[0])
    with pytest.raises(ValueError, match="five-ticker universe"):
        asyncio.run(replay.historical_policy_evaluation(frames, frozen))
