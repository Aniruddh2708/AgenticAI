import numpy as np
import pandas as pd

from vibefinance.config import SEED, TICKERS


def generate_market(ticker: str, days: int = 300, seed: int = SEED) -> pd.DataFrame:
    """Stable per-ticker seed; 300 sessions allow 30-session forward evaluation."""
    if ticker not in TICKERS:
        raise ValueError("Unsupported ticker")
    if days < 90:
        raise ValueError("At least 90 sessions are needed")
    rng = np.random.default_rng(seed + TICKERS.index(ticker) * 1009)
    returns = rng.normal(.0007, .012, days)
    # Inject fixed-window demo scenarios; do not seed evaluation's future labels.
    if ticker in ("RELIANCE.NS", "TCS.NS"):
        returns[-50:] = rng.normal(.004, .0035, 50)
    if ticker == "INFY.NS":
        returns[-20:] = rng.normal(.002, .004, 20)
    if ticker == "ITC.NS":
        returns[-30:] = rng.normal(-.001, .008, 30)
    close = (1000 + TICKERS.index(ticker) * 300) * np.exp(np.cumsum(returns))
    opening = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, .002, days))
    spread = rng.uniform(.002, .018, days)
    volume = rng.integers(700_000, 1_300_000, days).astype(float)
    if ticker == "RELIANCE.NS":
        volume[-1] = 3_800_000
    if ticker == "INFY.NS":
        volume[-20:] = np.linspace(700_000, 350_000, 20)
    frame = pd.DataFrame({"date": pd.bdate_range(end="2026-09-30", periods=days),
                          "open": opening, "high": np.maximum(opening, close) * (1 + spread),
                          "low": np.minimum(opening, close) * (1 - spread),
                          "close": close, "volume": volume})
    frame.attrs.update(mode="simulated", source_id=f"market:{ticker}:seed:{seed}", seed=seed)
    return frame


def validate_market(frame: pd.DataFrame) -> None:
    required = ["open", "high", "low", "close", "volume"]
    if len(frame) < 60 or any(c not in frame for c in required):
        raise ValueError("Need 60 complete OHLCV sessions")
    values = frame[required].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (frame[required[:4]] <= 0).any().any() or (frame.volume < 0).any():
        raise ValueError("OHLCV contains invalid values")
    if (frame.high < frame[["open", "close"]].max(axis=1)).any() or (frame.low > frame[["open", "close"]].min(axis=1)).any():
        raise ValueError("OHLC bounds are inconsistent")


def indicators(frame: pd.DataFrame) -> dict[str, float]:
    validate_market(frame)
    close = frame.close
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean().iloc[-1]
    rsi = 50.0 if gain == loss == 0 else (100.0 if loss == 0 else 100 - 100/(1 + gain/loss))
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    base_vol = frame.volume.iloc[-31:-1]
    std = float(base_vol.std(ddof=0))
    return {"rsi": float(rsi), "macd": float(macd.iloc[-1]),
            "macd_hist_pct": float((macd.iloc[-1] - signal.iloc[-1]) / close.iloc[-1]),
            "dma20": float(close.iloc[-20:].mean()), "dma50": float(close.iloc[-50:].mean()),
            "return_1m": float(close.iloc[-1] / close.iloc[-21] - 1),
            "volume_z": float((frame.volume.iloc[-1] - base_vol.mean()) / std) if std > 0 else 0.0,
            "volume_ratio": float(frame.volume.iloc[-5:].mean() / base_vol.mean()) if base_vol.mean() > 0 else 1.0,
            "volatility": float(close.pct_change().iloc[-30:].std() * np.sqrt(252))}
