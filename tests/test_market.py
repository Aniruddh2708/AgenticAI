import numpy as np
import pandas as pd
import pytest

from vibefinance.agents.base import Citation
from vibefinance.agents import momentum_agent, volume_agent
from vibefinance.config import TICKERS
from vibefinance.data.market_live import load_market
from vibefinance.data.market_sim import generate_market, indicators, validate_market

CITE = Citation(source_id="test", doc_title="Test market", chunk_id="test:0", excerpt="data", score=1)


@pytest.mark.parametrize("ticker", TICKERS)
def test_reproducible_valid_prices(ticker):
    a, b = generate_market(ticker), generate_market(ticker)
    pd.testing.assert_frame_equal(a, b)
    validate_market(a)
    assert len(a) == 300 and (a.high >= a.low).all()
    x = indicators(a)
    assert all(np.isfinite(v) for v in x.values())
    assert 0 <= x["rsi"] <= 100


def test_flat_and_rising_rsi():
    frame = generate_market("RELIANCE.NS")
    frame[["open", "high", "low", "close"]] = 100
    frame.volume = 100
    x = indicators(frame)
    assert x["rsi"] == 50 and x["macd"] == 0 and x["volume_z"] == 0
    close = np.arange(100, 100 + len(frame))
    for key in ["open", "high", "low", "close"]:
        frame[key] = close
    assert indicators(frame)["rsi"] == 100


def test_indicator_reference_values():
    frame = generate_market("TCS.NS")
    x = indicators(frame)
    assert x["dma20"] == pytest.approx(frame.close.tail(20).mean())
    assert x["dma50"] == pytest.approx(frame.close.tail(50).mean())
    assert x["return_1m"] == pytest.approx(frame.close.iloc[-1]/frame.close.iloc[-21]-1)
    ref = frame.volume.iloc[-31:-1]
    assert x["volume_z"] == pytest.approx((frame.volume.iloc[-1]-ref.mean())/ref.std(ddof=0))


def test_seed_scenarios():
    for ticker in ("RELIANCE.NS", "TCS.NS"):
        assert momentum_agent.analyze(ticker, generate_market(ticker), CITE).label == "BULLISH"
    assert volume_agent.analyze("RELIANCE.NS", generate_market("RELIANCE.NS"), CITE).label == "SPIKE_UP"
    assert volume_agent.analyze("INFY.NS", generate_market("INFY.NS"), CITE).label == "SPIKE_DOWN"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 0])
def test_bad_prices_rejected(bad):
    frame = generate_market("RELIANCE.NS")
    frame.loc[10, "close"] = bad
    with pytest.raises(ValueError):
        indicators(frame)


def test_live_feed_fallback(monkeypatch):
    import sys
    from types import SimpleNamespace
    def fail(*args, **kwargs):
        raise ConnectionError("offline")
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=fail))
    frame, warning = load_market("RELIANCE.NS", live=True)
    assert frame.attrs["mode"] == "simulated" and warning
