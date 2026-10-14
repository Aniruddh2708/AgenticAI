from vibefinance.agents.base import AgentOutput, EvidenceClaim
from vibefinance.analysis.financial_facts import extract_financial_facts
from vibefinance.analysis.text import tone, tone_cues


def analyze(ticker, retrieved):
    if not retrieved:
        return AgentOutput(agent="filings_agent", ticker=ticker, dimension="filings", label="UNKNOWN", confidence=0,
            evidence=[], status="degraded", degraded_reason="No filing retrieved for ticker; no fundamental claims emitted.")
    pos, neg, _ = tone(" ".join(c.text for c, _ in retrieved))
    claims = []
    citations = []
    for chunk, relevance in retrieved:
        facts = extract_financial_facts(chunk.text)
        for i, fact in enumerate(facts):
            pos += 2 * (fact.polarity > 0)
            neg += 2 * (fact.polarity < 0)
            claims.append(EvidenceClaim(claim_id=f"filings:{chunk.chunk_id}:fact:{i}",
                text=fact.text, citation_ids=[chunk.chunk_id], method="financial_fact",
                fact_key=fact.key, value=fact.value, unit=fact.unit))
        # Exact excerpts retain context for qualitative rules and the synthetic
        # disclosure. They are not paraphrases of unsupported numeric facts.
        for i, passage in enumerate(dict.fromkeys(c.sentence for c in tone_cues(chunk.text))):
            claims.append(EvidenceClaim(claim_id=f"filings:{chunk.chunk_id}:quote:{i}",
                text=passage, citation_ids=[chunk.chunk_id], method="quotation"))
        if facts or tone_cues(chunk.text):
            citations.append(chunk.citation(relevance))
    score = (pos - neg) / (pos + neg + 1)
    label = "SUPPORTIVE" if score > .1 else "CAUTIONARY" if score < -.1 else "UNKNOWN"
    return AgentOutput(agent="filings_agent", ticker=ticker, dimension="filings", label=label,
        confidence=abs(score), evidence=[claim.text for claim in claims], citations=citations,
        claims=claims, status="ok" if claims else "degraded",
        degraded_reason=None if claims else "No supported financial facts or tone phrases found in retrieved filings.")
