"""Transcript tone is dated, deduplicated, quoted and canonically checked."""

import asyncio
from datetime import date

import pytest

from vibefinance.agents import sentiment_agent
from vibefinance.agents.base import AgentOutput
from vibefinance.orchestrator import analyze
from vibefinance.rag.ingest import Chunk
from vibefinance.rag.retriever import Retriever
from vibefinance.rag.validator import validate_citations, validate_claims


TICKER = "RELIANCE.NS"


def source(text, *, identity="transcript", doc_type="transcript", available="2026-09-20",
           ticker=TICKER, index=0, document_text=""):
    return Chunk(identity, ticker, doc_type, available, f"{identity} [SYNTHETIC]",
                 f"{identity}:{index}", text, document_text)


def output(session):
    return AgentOutput.model_validate(next(a for a in session["recommendation"]["agent_outputs"]
                                          if a["dimension"] == "sentiment"))


def run(store, chunks, **kwargs):
    return asyncio.run(analyze(TICKER, store.profile("arjun"),
        retriever=Retriever(chunks=chunks, embeddings=False), persist=False, **kwargs))


def test_transcript_only_retains_exact_supported_tone_and_reports_missing_news():
    transcript = source("Guidance cut after weak bookings. Management addresses the outlook.")
    result = sentiment_agent.analyze(TICKER, [], transcripts=[(transcript, .8)], as_of="2026-09-20")
    assert result.label == "NEGATIVE" and result.confidence > 0
    assert result.status == "degraded" and "No news input" in result.degraded_reason
    assert result.evidence == ["Guidance cut after weak bookings."]
    assert result.citations[0].source_id == transcript.source_id
    assert result.citations[0].date == transcript.date
    allowed = {transcript.chunk_id: transcript.citation(.8)}
    assert validate_citations(result.citations, allowed) == (result.citations, [])
    assert validate_claims(result.claims, allowed) == (result.claims, [])


def test_news_and_transcript_tone_are_both_used_without_claiming_prediction():
    news = source("Strong demand.", identity="news", doc_type="news")
    transcript = source("Weak demand.")
    result = sentiment_agent.analyze(TICKER, [(news, .7)], transcripts=[(transcript, .8)])
    assert result.label == "MIXED" and result.status == "ok"
    assert set(result.evidence) == {"Strong demand.", "Weak demand."}
    assert {c.source_id for c in result.citations} == {"news", "transcript"}


def test_repeated_transcript_and_sentences_cannot_inflate_tone_strength():
    transcript = source("Strong demand. Improved growth.")
    duplicate = source(transcript.text, index=1)
    mirrored = source(transcript.text, identity="mirrored-transcript")
    once = sentiment_agent.analyze(TICKER, [], transcripts=[(transcript, .8)])
    repeated = sentiment_agent.analyze(TICKER, [], transcripts=[
        (transcript, .8), (transcript, .8), (duplicate, .8), (mirrored, .8)])
    assert repeated.model_dump() == once.model_dump()
    assert len(repeated.evidence) == len(set(repeated.evidence)) == 2


def test_overlapping_chunk_boundary_does_not_add_truncated_duplicate_sentence():
    body = "Strong demand. Improved growth remains supportive. Weak bookings."
    first = source("Strong demand. Improved growth remains supportive.", document_text=body)
    overlap = source("growth remains supportive. Weak bookings.", index=1, document_text=body)
    whole = source(body, document_text=body)
    combined = sentiment_agent.analyze(TICKER, [], transcripts=[(first, .8), (overlap, .8)])
    once = sentiment_agent.analyze(TICKER, [], transcripts=[(whole, .8)])
    assert combined.confidence == once.confidence
    assert combined.label == once.label
    assert combined.evidence == once.evidence
    assert "growth remains supportive." not in combined.evidence


@pytest.mark.parametrize("cutoff", ["2026-09-20", date(2026, 9, 20)])
def test_future_wrong_ticker_and_wrong_type_inputs_do_not_support_tone(cutoff):
    old = source("Weak bookings.")
    future = source("Strong growth improved.", identity="future", available="2026-09-21")
    other_ticker = source("Strong growth improved.", identity="other", ticker="TCS.NS")
    wrong_type = source("Strong growth improved.", identity="result", doc_type="results")
    result = sentiment_agent.analyze(TICKER, [], transcripts=[
        (old, .8), (future, .8), (other_ticker, .8), (wrong_type, .8)], as_of=cutoff)
    assert result.label == "NEGATIVE"
    assert result.evidence == [old.text]
    assert [c.source_id for c in result.citations] == [old.source_id]


@pytest.mark.parametrize("transcripts", [[], None])
def test_missing_sources_emit_no_claims_or_strength(transcripts):
    result = sentiment_agent.analyze(TICKER, [], transcripts=transcripts)
    assert result.status == "degraded" and result.confidence == 0
    assert result.evidence == result.claims == result.citations == []


def test_explicit_outage_withholds_even_available_transcript_evidence():
    transcript = source("Strong growth improved.")
    result = sentiment_agent.analyze(TICKER, [], outage=True, transcripts=[(transcript, .8)])
    assert result.status == "degraded" and "unavailable" in result.degraded_reason
    assert result.confidence == 0 and result.evidence == result.claims == result.citations == []


def test_transcript_with_no_recognized_cues_is_not_invented_evidence():
    transcript = source("The office address is listed in the appendix.")
    result = sentiment_agent.analyze(TICKER, [], transcripts=[(transcript, .8)])
    assert result.status == "degraded" and result.confidence == 0
    assert result.evidence == result.claims == result.citations == []


def test_orchestrator_registers_transcript_once_with_date_type_and_canonical_score(store):
    transcript = source("Strong growth improved. Guidance raised.")
    news = source("Growth remains supportive.", identity="news", doc_type="news")
    future = source("Guidance cut after weak demand.", identity="future", available="2026-09-21")
    session = run(store, [transcript, news, future], as_of="2026-09-20")
    sentiment = output(session)
    assert sentiment.label == "POSITIVE" and sentiment.status == "ok"
    registered = {s["chunk_id"]: s for s in session["sources"]}
    assert len(registered) == len(session["sources"])
    assert future.chunk_id not in registered
    transcript_source = registered[transcript.chunk_id]
    assert transcript_source["date"] == transcript.date
    assert transcript_source["doc_type"] == "transcript"
    assert transcript_source["document_text"] == transcript.text
    allowed = {c.chunk_id: c for c in sentiment.citations}
    assert validate_claims(sentiment.claims, allowed) == (sentiment.claims, [])
    for agent in session["recommendation"]["agent_outputs"]:
        for citation in agent["citations"]:
            assert citation["score"] == registered[citation["chunk_id"]]["score"]
    assert session["metrics"]["rejected_claim_count"] == 0


def test_missing_filing_toggle_withholds_transcripts_but_preserves_supported_news(store):
    transcript = source("Guidance cut after weak demand.")
    news = source("Growth remains supportive.", identity="news", doc_type="news")
    session = run(store, [transcript, news], missing_filing=True)
    sentiment = output(session)
    assert sentiment.status == "degraded" and "No transcript input" in sentiment.degraded_reason
    assert sentiment.evidence == [news.text]
    assert transcript.chunk_id not in {s["chunk_id"] for s in session["sources"]}
    assert session["recommendation"]["action"] == "WATCH"


def test_transcript_signal_is_recomputed_before_registered_quotes_authorize_it(store):
    transcript = source("Strong growth improved. Guidance raised.")
    original = output(run(store, [transcript]))
    forged = original.model_copy(update={"label": "NEGATIVE", "confidence": 1}, deep=True)
    checked = output(run(store, [transcript], overrides={"sentiment": lambda: forged}))
    assert checked.status == "degraded" and checked.confidence == 0
    assert checked.label == "UNKNOWN" and not checked.evidence and not checked.claims
    assert "recomputation" in checked.degraded_reason


def test_transcript_retrieval_failure_retains_supported_news_with_disclosure(store):
    transcript = source("Strong growth improved.")
    news = source("Growth remains supportive.", identity="news", doc_type="news")

    class FailedTranscriptRetriever(Retriever):
        def retrieve(self, query, ticker, k=4, doc_types=None, **kwargs):
            if doc_types == {"transcript"}:
                raise ConnectionError("Transcript index unavailable")
            return super().retrieve(query, ticker, k, doc_types, **kwargs)

    session = asyncio.run(analyze(TICKER, store.profile("arjun"), persist=False,
        retriever=FailedTranscriptRetriever(chunks=[transcript, news], embeddings=False)))
    sentiment = output(session)
    assert sentiment.status == "degraded" and "No transcript input" in sentiment.degraded_reason
    assert sentiment.evidence == [news.text]
    assert any("transcript retrieval unavailable" in warning for warning in session["warnings"])
