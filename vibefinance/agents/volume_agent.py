import numpy as np

from vibefinance.agents.base import AgentOutput
from vibefinance.data.market_sim import indicators


def analyze(ticker, frame, citation):
    x = indicators(frame)
    divergence = x["return_1m"] > 0 and x["volume_ratio"] < .8
    spike = abs(x["volume_z"]) > 2
    label = "SPIKE_DOWN" if divergence or (spike and x["return_1m"] < 0) else "SPIKE_UP" if spike else "NORMAL"
    strength = max(abs(x["volume_z"]) / 4, (1 - x["volume_ratio"]) / .5 if divergence else 0)
    confidence = float(np.tanh(strength)) if label != "NORMAL" else max(0, 1 - abs(x["volume_z"]) / 2)
    return AgentOutput(agent="volume_agent", ticker=ticker, dimension="volume", label=label,
        confidence=confidence, citations=[citation], evidence=[
        f"Latest volume z-score {x['volume_z']:.2f} versus preceding 30 sessions; anomaly threshold ±2.",
        f"5-session volume / prior 30-session mean {x['volume_ratio']:.2f}; 20-session price return {x['return_1m']:.1%}.",
        "Price rising while volume falls: participation divergence." if divergence else "No price-up/volume-down divergence at the 0.8 ratio threshold."])
