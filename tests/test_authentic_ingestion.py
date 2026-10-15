"""Explicit source fixtures exercise machinery, never authenticate real documents."""
import hashlib
import json
from pathlib import Path

import pytest

from vibefinance.rag.authentic import import_corpus
from vibefinance.rag.evaluate import evaluate
from vibefinance.rag.ingest import ingest
from vibefinance.rag.retriever import Retriever
from vibefinance.rag.validator import validate_citations


@pytest.fixture
def packet(tmp_path):
    body = b"Revenue growth improved profit.\r\nOriginal exact passage with repeated  spaces.\r\n"
    (tmp_path/"text.txt").write_bytes(body)
    record = {"source_id": "format_fixture_only", "ticker": "TCS.NS", "doc_type": "results",
        "title": "Generated format fixture, not a real filing", "publisher": "Fixture publisher",
        "security_identity_evidence": "Fixture identity, not verified", "timestamp_evidence": "Fixture timestamp",
        "source_url": "https://source.example.test/fixture", "path": "text.txt",
        "sha256": hashlib.sha256(body).hexdigest(), "published_at": "2020-01-01T12:00:00+00:00",
        "available_at": "2020-01-01T15:00:00+00:00", "availability_evidence": "Fixture availability",
        "retrieved_at": "2020-01-02T00:00:00+00:00",
        "rights": {"permission": "explicit_license", "identifier": "FIXTURE_NOT_A_LICENSE",
                   "use": "noncommercial_research", "evidence_url": "https://source.example.test/fixture-rights"}}
    path = tmp_path/"manifest.json"
    path.write_text(json.dumps({"schema_version": 1, "kind": "permitted_authentic_text_corpus", "sources": [record]}))
    return path, tmp_path/"output", record


def edit_packet(packet, **updates):
    path, _, record = packet
    record.update(updates)
    path.write_text(json.dumps({"schema_version": 1, "kind": "permitted_authentic_text_corpus", "sources": [record]}))


def test_import_retains_hash_crlf_exact_spans_and_provenance(packet):
    manifest, output, _ = packet
    report = import_corpus(manifest, output)
    assert report["independently_authenticated"] is False
    chunks = ingest(output, size=6, overlap=2)
    assert len(chunks) > 1
    for c in chunks:
        assert c.document_text[c.span_start:c.span_end] == c.text
        assert "\r\n" in c.document_text
        assert c.source_kind == "authentic" and c.published_at
        citation = c.citation()
        assert citation.source_sha256 == packet[2]["sha256"]
        forged = citation.model_copy(update={"available_at": "1900-01-01T00:00:00+00:00"})
        assert validate_citations([forged], {citation.chunk_id: citation}) == ([], [citation.chunk_id])
    with pytest.raises(FileExistsError):
        import_corpus(manifest, output)


@pytest.mark.parametrize("updates", [
    {"sha256": "0"*64}, {"path": "../outside.txt"},
    {"source_url": "https://user:password@source.example.test/"},
    {"published_at": "2020-01-02T00:00:00+00:00"},
    {"available_at": "2020-01-01"}, {"availability_evidence": ""},
    {"rights": {"permission": "publicly_accessible", "identifier": "none", "use": "noncommercial_research"}},
])
def test_invalid_sources_fail_before_creating_any_output(packet, updates):
    edit_packet(packet, **updates)
    with pytest.raises((ValueError, KeyError)):
        import_corpus(packet[0], packet[1])
    assert not packet[1].exists()


def test_first_retrieval_is_conservative_default_availability(packet):
    path, output, record = packet
    record.pop("available_at")
    edit_packet(packet)
    import_corpus(path, output)
    retriever = Retriever(corpus_path=output, embeddings=False)
    assert retriever.retrieve("profit", "TCS.NS", as_of="2020-01-01T23:59:59+00:00") == []
    assert retriever.retrieve("profit", "TCS.NS", as_of="2020-01-02T00:00:00+00:00")


def test_intraday_ticker_type_kind_filters_and_tampered_body(packet):
    import_corpus(packet[0], packet[1])
    r = Retriever(corpus_path=packet[1], embeddings=False)
    assert r.retrieve("profit", "TCS.NS", as_of="2020-01-01") == []
    assert r.retrieve("profit", "TCS.NS", as_of="2020-01-01T14:59:59Z") == []
    assert r.retrieve("profit", "TCS.NS", as_of="2020-01-01T20:30:00+05:30")
    assert r.retrieve("profit", "ITC.NS") == []
    assert r.retrieve("profit", "TCS.NS", doc_types={"news"}) == []
    assert r.retrieve("profit", "TCS.NS", source_kinds={"synthetic"}) == []
    p = packet[1]/"format_fixture_only.md"
    p.write_bytes(p.read_bytes()+b"tampering")
    assert ingest(packet[1]) == []


def test_held_out_judgments_and_unjudged_pool_are_explicit(packet):
    import_corpus(packet[0], packet[1])
    r = Retriever(corpus_path=packet[1], embeddings=False)
    questions = [{"id": "fixture_q", "split": "held_out", "judged_by": "Fixture only",
        "judgment_evidence": "Generated relevance fixture, not real evaluation", "query": "profit growth",
        "ticker": "TCS.NS", "as_of": "2020-01-02", "relevance_by_source_id": {"format_fixture_only": 2}}]
    result = evaluate(r, questions)
    assert result["mean_ndcg_at_k"] == result["mean_recall_at_k"] == 1
    assert result["all_spans_exact"] is True
    questions[0]["relevance_by_source_id"] = {"unrelated_fixture": 2}
    result = evaluate(r, questions)
    assert result["judgment_pool_complete"] is False
    assert result["mean_ndcg_at_k"] is None
    questions[0]["split"] = "training"
    with pytest.raises(ValueError):
        evaluate(r, questions)


def test_sentiment_rechecks_actual_intraday_availability_even_for_supplied_chunks(packet):
    from vibefinance.agents import sentiment_agent
    from dataclasses import replace
    import_corpus(packet[0], packet[1])
    chunk = replace(ingest(packet[1])[0], doc_type="news")
    future = sentiment_agent.analyze("TCS.NS", [(chunk, 1.)], as_of="2020-01-01T14:59:59Z")
    assert not future.claims and future.confidence == 0
    available = sentiment_agent.analyze("TCS.NS", [(chunk, 1.)], as_of="2020-01-01T15:00:00Z")
    assert available.claims and available.citations[0].source_kind == "authentic"
