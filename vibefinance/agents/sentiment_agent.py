from datetime import date, datetime, time, timezone

from vibefinance.agents.base import AgentOutput, EvidenceClaim
from vibefinance.analysis.text import sentences, tone, tone_cues


def analyze(ticker, retrieved, outage=False, *, transcripts=None, as_of=None):
    """Finite lexical tone from news and management transcripts, not a forecast.

    Score only the exact, quoted sentences that survive source/date filtering.
    Repeated passages (including chunk overlap and a repeated transcript result)
    count once. The two source channels may describe the same events and are not
    independent corroboration of future returns.
    """
    if outage:
        return AgentOutput(agent="sentiment_agent", ticker=ticker, dimension="sentiment", label="MIXED",
            confidence=0, evidence=[], status="degraded", degraded_reason="Sentiment feed unavailable; no sentiment claims emitted.")

    instant = None
    if isinstance(as_of, str) and "T" in as_of:
        from vibefinance.rag.authentic import timestamp
        as_of = timestamp(as_of)
    if isinstance(as_of, datetime):
        if as_of.tzinfo is None:
            raise ValueError("Intraday as_of requires a timezone")
        instant = as_of.astimezone(timezone.utc)
        cutoff = instant.date()
    elif isinstance(as_of, str):
        cutoff = date.fromisoformat(as_of)
        if cutoff.isoformat() != as_of:
            raise ValueError("as_of must use YYYY-MM-DD")
    else:
        cutoff = as_of
    if cutoff is not None and not isinstance(cutoff, date):
        raise ValueError("as_of must be a date or YYYY-MM-DD")
    instant = instant or (datetime.combine(cutoff, time.min, tzinfo=timezone.utc)
                          if cutoff else datetime.now(timezone.utc))

    claims = []
    citations = []
    seen_passages, seen_chunks, available_types = set(), set(), set()
    for chunk, relevance in list(retrieved or []) + list(transcripts or []):
        if chunk.ticker != ticker or chunk.doc_type not in {"news", "transcript"}:
            continue
        try:
            available = date.fromisoformat(chunk.date)
            if available.isoformat() != chunk.date or (cutoff is not None and available > cutoff):
                continue
            if getattr(chunk, "source_kind", "synthetic") == "authentic":
                from vibefinance.rag.authentic import timestamp
                if timestamp(chunk.available_at) > instant:
                    continue
        except (TypeError, ValueError):
            continue
        available_types.add(chunk.doc_type)
        if chunk.chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk.chunk_id)
        # A chunk that starts/ends mid-sentence must not add a second truncated
        # version of a sentence already represented by an overlapping chunk.
        complete = set(sentences(chunk.document_text)) if chunk.document_text else None
        for i, passage in enumerate(dict.fromkeys(c.sentence for c in tone_cues(chunk.text))):
            key = " ".join(passage.split()).casefold()
            if key in seen_passages or (complete is not None and passage not in complete):
                continue
            seen_passages.add(key)
            claims.append(EvidenceClaim(claim_id=f"sentiment:{chunk.chunk_id}:{i}", text=passage,
                citation_ids=[chunk.chunk_id], method="quotation"))
            if not citations or citations[-1].chunk_id != chunk.chunk_id:
                citations.append(chunk.citation(relevance))
    pos, neg, score = tone(" ".join(claim.text for claim in claims))
    label = "POSITIVE" if score > .15 else "NEGATIVE" if score < -.15 else "MIXED"
    reason = None
    if not claims:
        reason = "No supported tone phrases found in available news or transcripts; no sentiment claims emitted."
    elif available_types != {"news", "transcript"}:
        missing = "news" if "news" not in available_types else "transcript"
        reason = f"No {missing} input available; sentiment uses the other source channel only."
    return AgentOutput(agent="sentiment_agent", ticker=ticker, dimension="sentiment", label=label,
        confidence=(abs(score) if label != "MIXED" else 1/(pos + neg + 1)) if claims else 0,
        evidence=[claim.text for claim in claims], citations=citations, claims=claims,
        status="degraded" if reason else "ok", degraded_reason=reason)
