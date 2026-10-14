from vibefinance.agents.base import AgentOutput
from vibefinance.agents.sentiment_agent import tone


def analyze(ticker, retrieved):
    if not retrieved:
        return AgentOutput(agent="filings_agent", ticker=ticker, dimension="filings", label="UNKNOWN", confidence=0,
            evidence=[], status="degraded", degraded_reason="No filing retrieved for ticker; no fundamental claims emitted.")
    pos, neg, score = tone(" ".join(c.text for c, _ in retrieved))
    label = "SUPPORTIVE" if score > .1 else "CAUTIONARY" if score < -.1 else "UNKNOWN"
    citations = [c.citation(s) for c, s in retrieved]
    evidence = [f"Retrieved {len(retrieved)} synthetic filing passages; supportive terms {pos}, caution terms {neg}; score {score:.3f}."]
    evidence.extend(f"{c.title}: {c.text}" for c, _ in retrieved)
    return AgentOutput(agent="filings_agent", ticker=ticker, dimension="filings", label=label,
        confidence=abs(score), evidence=evidence, citations=citations)
