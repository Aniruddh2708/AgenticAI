from vibefinance.agents.base import AgentOutput, EvidenceClaim
from vibefinance.analysis.text import tone, tone_cues


def analyze(ticker, retrieved, outage=False):
    if outage or not retrieved:
        return AgentOutput(agent="sentiment_agent", ticker=ticker, dimension="sentiment", label="MIXED",
            confidence=0, evidence=[], status="degraded", degraded_reason="Sentiment feed unavailable; no sentiment claims emitted.")
    pos, neg, score = tone(" ".join(c.text for c, _ in retrieved))
    label = "POSITIVE" if score > .15 else "NEGATIVE" if score < -.15 else "MIXED"
    claims = []
    citations = []
    for chunk, relevance in retrieved:
        passages = dict.fromkeys(c.sentence for c in tone_cues(chunk.text))
        if passages:
            citations.append(chunk.citation(relevance))
        for i, passage in enumerate(passages):
            claims.append(EvidenceClaim(claim_id=f"sentiment:{chunk.chunk_id}:{i}", text=passage,
                citation_ids=[chunk.chunk_id], method="quotation"))
    return AgentOutput(agent="sentiment_agent", ticker=ticker, dimension="sentiment", label=label,
        confidence=(abs(score) if label != "MIXED" else 1/(pos + neg + 1)) if claims else 0,
        evidence=[claim.text for claim in claims], citations=citations, claims=claims,
        status="ok" if claims else "degraded",
        degraded_reason=None if claims else "No supported tone phrases found in the retrieved news.")
