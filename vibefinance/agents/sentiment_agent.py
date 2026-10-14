from collections import Counter

from vibefinance.agents.base import AgentOutput
from vibefinance.rag.ingest import tokens

POSITIVE = {"growth", "improved", "strong", "expansion", "profit", "supportive", "resilient", "upgrade"}
NEGATIVE = {"decline", "weak", "cut", "attrition", "delay", "litigation", "caution", "downgrade"}


def tone(text):
    bag = Counter(tokens(text))
    positive = sum(bag[w] for w in POSITIVE)
    negative = sum(bag[w] for w in NEGATIVE)
    return positive, negative, (positive - negative) / (positive + negative + 1)


def analyze(ticker, retrieved, outage=False):
    if outage or not retrieved:
        return AgentOutput(agent="sentiment_agent", ticker=ticker, dimension="sentiment", label="MIXED",
            confidence=0, evidence=[], status="degraded", degraded_reason="Sentiment feed unavailable; no sentiment claims emitted.")
    pos, neg, score = tone(" ".join(c.text for c, _ in retrieved))
    label = "POSITIVE" if score > .15 else "NEGATIVE" if score < -.15 else "MIXED"
    return AgentOutput(agent="sentiment_agent", ticker=ticker, dimension="sentiment", label=label,
        confidence=abs(score) if label != "MIXED" else 1/(pos + neg + 1),
        evidence=[f"Synthetic-news lexicon: {pos} positive / {neg} negative tokens; normalized tone {score:.3f}."],
        citations=[c.citation(s) for c, s in retrieved])
