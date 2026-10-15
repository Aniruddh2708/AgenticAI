import numpy as np

from vibefinance.agents.base import AgentOutput
from vibefinance.data.market_sim import indicators


def analyze(ticker, frame, citation, *, computed_indicators=None):
    # The orchestrator supplies its independently computed immutable snapshot.
    # Direct callers retain validation/computation from their own market frame.
    x = indicators(frame) if computed_indicators is None else computed_indicators
    score = float(np.tanh(x["return_1m"] * 12) * .45
                  + np.tanh((x["dma20"]/x["dma50"] - 1) * 30) * .35
                  + np.tanh(x["macd_hist_pct"] * 500) * .15
                  + ((x["rsi"] - 50)/50) * .05)
    label = "BULLISH" if score > .15 else "BEARISH" if score < -.15 else "NEUTRAL"
    confidence = abs(score) if label != "NEUTRAL" else 1 - abs(score)/.15
    return AgentOutput(agent="momentum_agent", ticker=ticker, dimension="momentum", label=label,
        confidence=min(1, confidence), citations=[citation], evidence=[
        f"RSI(14) {x['rsi']:.1f}; overbought threshold 70 (not a buy instruction).",
        f"20/50 DMA {x['dma20']:.2f}/{x['dma50']:.2f}; MACD {x['macd']:.2f}.",
        f"20-session return {x['return_1m']:.1%}; trend score {score:.3f} (direction threshold ±0.15)."])
